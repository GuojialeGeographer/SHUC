#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流域处理器 - Watershed Processor (v4.0)
========================================

负责流域数据的智能合并处理：
- 精确测地面积计算（替代 WGS84 度坐标面积）
- 动态阈值调整算法
- 拓扑图构建和优化（增强拓扑更新传播）
- 空间索引加速邻接搜索（STRtree）
- 兼容 MERIT-Basins (NextDownID) 和 TauDEM (DSLINKNO) 字段

Version: 4.0.0
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx
from shapely.ops import unary_union
from shapely.strtree import STRtree
from pyproj import Geod
from collections import defaultdict
import time
import logging
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger('china_shuc')

# 全局 Geod 实例（用于精确面积计算）
_GEOD = Geod(ellps='WGS84')


def compute_area_km2(geometry) -> float:
    """
    计算单个几何体的精确测地面积 (km2)
    
    使用 pyproj.Geod 进行球面面积计算，避免 WGS84 度坐标面积不准确的问题。
    
    Args:
        geometry: Shapely geometry (Polygon 或 MultiPolygon)
        
    Returns:
        面积 (km2)
    """
    if geometry is None or geometry.is_empty:
        return 0.0
    try:
        if geometry.geom_type == 'Polygon':
            area_m2, _ = _GEOD.geometry_area_perimeter(geometry)
            return abs(area_m2) / 1_000_000
        elif geometry.geom_type == 'MultiPolygon':
            total = 0.0
            for poly in geometry.geoms:
                a, _ = _GEOD.geometry_area_perimeter(poly)
                total += abs(a)
            return total / 1_000_000
        else:
            return 0.0
    except Exception:
        # 回退：使用投影面积（不精确但不会崩溃）
        return abs(geometry.area) / 1_000_000


def compute_areas_batch(gdf: gpd.GeoDataFrame) -> pd.Series:
    """
    批量计算 GeoDataFrame 中所有几何体的精确测地面积
    
    Args:
        gdf: 包含 geometry 列的 GeoDataFrame
        
    Returns:
        面积 Series (km2)
    """
    return pd.Series(
        [compute_area_km2(geom) for geom in gdf.geometry],
        index=gdf.index,
        name='area_km2'
    )


class WatershedProcessor:
    """
    流域处理器类 (v4.0)
    
    改进点（相比 v3.1）：
    1. 精确测地面积计算（替代 WGS84 度坐标面积）
    2. 空间索引加速邻接搜索（STRtree 替代 O(n^2) 遍历）
    3. 增强拓扑更新传播（合并后完整重建上下游指针）
    4. 兼容 MERIT-Basins (NextDownID) 和 TauDEM (DSLINKNO) 字段
    5. 合并历史追踪增强（记录每次合并的源/目标/面积变化）
    """
    
    # 支持的下游拓扑字段（按优先级）
    DOWNSTREAM_FIELDS = ['DSLINKNO1', 'DSLINKNO', 'NextDownID']
    
    # 支持的上游拓扑字段
    UPSTREAM_FIELDS = ['USLINKNO1', 'USLINKNO2', 'up1', 'up2', 'up3', 'up4']
    
    # 支持的 ID 字段
    ID_FIELDS = ['LINKNO', 'COMID']
    
    def __init__(self, config):
        """
        初始化流域处理器
        
        Args:
            config (dict): 处理配置参数
        """
        self.config = config
        self.watershed_data = None
        self.topology_graph = None
        self.merge_history = []
        self.dynamic_threshold = 80  # 默认阈值
        
        # 从配置中读取参数
        self.target_compliance = config.get('target_compliance_rate', 0.90)
        self.merge_strategy = config.get('merge_strategy', 'aggressive')
        self.max_iterations = config.get('max_iterations', 50)
        self.enable_early_stopping = config.get('enable_early_stopping', True)
        
        # 动态阈值参数（可配置）
        self.threshold_min = config.get('threshold_min', 50)
        self.threshold_max = config.get('threshold_max', 500)
        self.threshold_formula = config.get('threshold_formula', 'Q75+(Q90-Q75)/2')
        
        # 检测到的字段名（运行时确定）
        self._id_field = None
        self._ds_field = None
        self._us_fields = []
        
        # 空间索引
        self._spatial_index = None
    
    def merge_watersheds(self, input_shapefile):
        """
        执行流域合并的主要方法
        
        Args:
            input_shapefile (str): 输入 shapefile 路径
            
        Returns:
            dict: 包含合并结果和统计信息
        """
        # 1. 加载和预处理数据
        self._load_data(input_shapefile)
        
        # 2. 检测拓扑字段
        self._detect_topology_fields()
        
        # 3. 构建空间索引
        self._build_spatial_index()
        
        # 4. 计算动态阈值
        self.dynamic_threshold = self._calculate_dynamic_threshold()
        logger.info(f"动态阈值: {self.dynamic_threshold:.1f} km2")
        
        # 5. 构建拓扑图
        self._build_topology_graph()
        
        # 6. 执行合并
        merge_stats = self._execute_aggressive_merging()
        
        return {
            'merged_watersheds': self.watershed_data,
            'statistics': merge_stats,
            'merge_history': self.merge_history,
            'dynamic_threshold': self.dynamic_threshold
        }
    
    # ==================== 数据加载 ====================
    
    def _load_data(self, shapefile_path):
        """加载和预处理数据"""
        self.watershed_data = gpd.read_file(shapefile_path)
        
        # 使用精确测地面积计算
        self.watershed_data['area_km2'] = compute_areas_batch(self.watershed_data)
        
        # 修复数据问题
        fixed = self._fix_data_issues()
        if fixed > 0:
            logger.info(f"修复 {fixed} 个数据问题")
    
    def _detect_topology_fields(self):
        """自动检测可用的拓扑字段"""
        columns = set(self.watershed_data.columns)
        
        # 检测 ID 字段
        for field in self.ID_FIELDS:
            if field in columns:
                self._id_field = field
                break
        
        # 检测下游字段
        for field in self.DOWNSTREAM_FIELDS:
            if field in columns:
                self._ds_field = field
                break
        
        # 检测上游字段
        self._us_fields = [f for f in self.UPSTREAM_FIELDS if f in columns]
        
        logger.info(f"检测到拓扑字段: ID={self._id_field}, "
                    f"下游={self._ds_field}, 上游={self._us_fields}")
    
    def _fix_data_issues(self):
        """修复数据问题"""
        issues_fixed = 0
        
        # 修复 self-reference 问题
        if self._id_field and 'USLINKNO2' in self.watershed_data.columns:
            self_refs = self.watershed_data[self._id_field] == self.watershed_data['USLINKNO2']
            if self_refs.any():
                self.watershed_data.loc[self_refs, 'USLINKNO2'] = -1
                issues_fixed += self_refs.sum()
        
        # 修复无效几何（使用 make_valid 替代 buffer(0)）
        invalid_geom = ~self.watershed_data.geometry.is_valid
        if invalid_geom.any():
            self.watershed_data.loc[invalid_geom, 'geometry'] = \
                self.watershed_data.loc[invalid_geom, 'geometry'].make_valid()
            issues_fixed += invalid_geom.sum()
        
        return issues_fixed
    
    # ==================== 面积计算 ====================
    
    def _calculate_dynamic_threshold(self):
        """
        计算动态阈值
        
        公式: threshold = Q75 + (Q90 - Q75) / 2
        约束范围: [threshold_min, threshold_max]
        
        Returns:
            动态阈值 (km2)
        """
        areas = self.watershed_data['area_km2'].dropna()
        
        if len(areas) == 0:
            return self.threshold_min
        
        q75 = areas.quantile(0.75)
        q90 = areas.quantile(0.90)
        
        # 动态阈值公式
        dynamic_threshold = q75 + (q90 - q75) / 2
        
        # 约束在配置的范围内
        threshold = max(self.threshold_min, min(self.threshold_max, dynamic_threshold))
        
        return threshold
    
    # ==================== 空间索引 ====================
    
    def _build_spatial_index(self):
        """构建空间索引（STRtree）"""
        try:
            self._spatial_index = STRtree(self.watershed_data.geometry)
            logger.info("空间索引构建完成 (STRtree)")
        except Exception as e:
            logger.warning(f"空间索引构建失败: {e}，将使用回退方法")
            self._spatial_index = None
    
    # ==================== 拓扑图 ====================
    
    def _build_topology_graph(self):
        """构建拓扑关系图"""
        self.topology_graph = nx.DiGraph()
        
        gdf = self.watershed_data
        
        # 添加节点
        for idx, row in gdf.iterrows():
            node_id = self._get_node_id(row, idx)
            self.topology_graph.add_node(node_id,
                                         area=row['area_km2'],
                                         geometry=row['geometry'],
                                         df_index=idx,
                                         original_id=node_id)
        
        # 添加边（上下游关系）
        if self._ds_field and self._id_field:
            id_to_node = {}
            for idx, row in gdf.iterrows():
                node_id = self._get_node_id(row, idx)
                id_to_node[node_id] = node_id
            
            for idx, row in gdf.iterrows():
                source_id = self._get_node_id(row, idx)
                target_id = row.get(self._ds_field)
                
                if pd.notna(target_id) and target_id != -1 and target_id != 0:
                    target_id = int(target_id)
                    if target_id in id_to_node:
                        self.topology_graph.add_edge(source_id, target_id)
        
        logger.info(f"拓扑图构建完成: {self.topology_graph.number_of_nodes()} 节点, "
                    f"{self.topology_graph.number_of_edges()} 边")
    
    def _get_node_id(self, row, default_idx):
        """获取节点 ID"""
        if self._id_field and self._id_field in row.index:
            val = row[self._id_field]
            if pd.notna(val):
                return int(val)
        return default_idx
    
    # ==================== 合并逻辑 ====================
    
    def _execute_aggressive_merging(self):
        """
        执行激进合并策略
        
        Returns:
            dict: 合并统计信息
        """
        original_count = len(self.watershed_data)
        iteration = 0
        last_compliance_rate = 0
        no_progress_count = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # 获取需要合并的流域
            small_watersheds = self._identify_merge_candidates()
            
            if small_watersheds.empty:
                logger.info(f"迭代 {iteration}: 无需合并的流域，停止")
                break
            
            # 执行一轮合并
            merged_count = self._merge_iteration(small_watersheds)
            
            # 重算面积（合并后几何变化）
            self.watershed_data['area_km2'] = compute_areas_batch(self.watershed_data)
            
            # 重建空间索引
            self._build_spatial_index()
            
            # 计算当前合规率
            current_compliance = self._calculate_compliance_rate()
            
            # 记录合并历史
            self.merge_history.append({
                'iteration': iteration,
                'merged_count': merged_count,
                'remaining_watersheds': len(self.watershed_data),
                'compliance_rate': current_compliance,
                'threshold': self.dynamic_threshold,
            })
            
            logger.info(f"迭代 {iteration}: 合并 {merged_count} 个, "
                        f"剩余 {len(self.watershed_data)}, "
                        f"合规率 {current_compliance:.1%}")
            
            # 早停条件：合规率达到目标
            if self.enable_early_stopping and current_compliance >= self.target_compliance:
                logger.info(f"达到目标合规率 {self.target_compliance:.0%}，停止合并")
                break
            
            # 防止无进展循环
            if merged_count == 0:
                no_progress_count += 1
                if no_progress_count >= 3:
                    logger.info("连续 3 轮无合并进展，停止")
                    break
            else:
                no_progress_count = 0
            
            last_compliance_rate = current_compliance
        
        final_count = len(self.watershed_data)
        compression_rate = (original_count - final_count) / original_count if original_count > 0 else 0
        final_compliance = self._calculate_compliance_rate()
        
        return {
            'original_count': original_count,
            'final_count': final_count,
            'compression_rate': compression_rate,
            'final_compliance_rate': final_compliance,
            'iterations': iteration,
            'dynamic_threshold_used': self.dynamic_threshold,
        }
    
    def _identify_merge_candidates(self):
        """识别需要合并的小流域"""
        small_watersheds = self.watershed_data[
            self.watershed_data['area_km2'] < self.dynamic_threshold
        ].copy()
        
        return small_watersheds.sort_values('area_km2')
    
    def _merge_iteration(self, small_watersheds):
        """执行一轮合并"""
        merged_count = 0
        merged_indices = set()
        
        for idx, watershed in small_watersheds.iterrows():
            if idx not in self.watershed_data.index:
                continue  # 已被合并
            if idx in merged_indices:
                continue  # 本轮已作为目标被合并
            
            # 寻找合并目标
            merge_target = self._find_merge_target(idx, watershed)
            
            if merge_target is not None:
                # 执行合并
                self._merge_watersheds(idx, merge_target)
                merged_count += 1
                merged_indices.add(idx)
        
        return merged_count
    
    def _find_merge_target(self, watershed_idx, watershed_row):
        """
        寻找合并目标
        
        优先级：下游 > 上游 > 空间邻接 > 最近邻
        
        Args:
            watershed_idx: 当前流域的 DataFrame 索引
            watershed_row: 当前流域的数据行
            
        Returns:
            合并目标的 DataFrame 索引，或 None
        """
        watershed_id = self._get_node_id(watershed_row, watershed_idx)
        
        # 1. 优先合并到下游
        if self._ds_field:
            downstream_id = watershed_row.get(self._ds_field)
            if pd.notna(downstream_id) and downstream_id != -1 and downstream_id != 0:
                downstream_idx = self._find_index_by_id(int(downstream_id))
                if downstream_idx is not None and downstream_idx in self.watershed_data.index:
                    return downstream_idx
        
        # 2. 寻找上游流域（选面积最大的）
        if self._ds_field and self._id_field:
            upstream = self.watershed_data[
                (self.watershed_data[self._ds_field] == watershed_id) &
                (self.watershed_data.index != watershed_idx)
            ]
            if not upstream.empty:
                target_idx = upstream['area_km2'].idxmax()
                return target_idx
        
        # 3. 空间邻接搜索（使用 STRtree 或回退方法）
        adjacent_target = self._find_adjacent_watershed_optimized(watershed_row)
        if adjacent_target is not None:
            return adjacent_target
        
        # 4. 最近邻兜底
        nearest_target = self._find_nearest_watershed(watershed_row)
        return nearest_target
    
    def _find_index_by_id(self, linkno):
        """根据 ID 查找 DataFrame 索引"""
        if self._id_field is None:
            return None
        matches = self.watershed_data[self.watershed_data[self._id_field] == linkno]
        return matches.index[0] if not matches.empty else None
    
    def _find_adjacent_watershed_optimized(self, watershed_row):
        """
        使用空间索引优化的邻接搜索
        
        优先使用 STRtree（O(n log n)），回退到 touches 遍历（O(n^2)）
        """
        current_geom = watershed_row['geometry']
        current_idx = watershed_row.name
        
        if self._spatial_index is not None:
            try:
                # 使用 STRtree 查询候选
                candidate_indices = self._spatial_index.query(current_geom)
                
                for cand_idx in candidate_indices:
                    if cand_idx == current_idx:
                        continue
                    if cand_idx not in self.watershed_data.index:
                        continue
                    
                    other_geom = self.watershed_data.loc[cand_idx, 'geometry']
                    if current_geom.touches(other_geom):
                        return cand_idx
            except Exception:
                pass
        
        # 回退方法：直接遍历
        return self._find_adjacent_watershed_fallback(current_geom, current_idx)
    
    def _find_adjacent_watershed_fallback(self, current_geom, current_idx):
        """回退的邻接搜索"""
        for idx in self.watershed_data.index:
            if idx == current_idx:
                continue
            try:
                if current_geom.touches(self.watershed_data.loc[idx, 'geometry']):
                    return idx
            except Exception:
                continue
        return None
    
    def _find_nearest_watershed(self, watershed_row):
        """寻找最近的流域"""
        try:
            current_geom = watershed_row['geometry']
            current_idx = watershed_row.name
            
            # 使用空间索引加速
            if self._spatial_index is not None:
                try:
                    nearest_idx = self._spatial_index.nearest(current_geom)
                    if nearest_idx != current_idx and nearest_idx in self.watershed_data.index:
                        return nearest_idx
                except Exception:
                    pass
            
            # 回退方法
            min_distance = float('inf')
            nearest_idx = None
            
            for idx in self.watershed_data.index:
                if idx == current_idx:
                    continue
                distance = current_geom.distance(self.watershed_data.loc[idx, 'geometry'])
                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = idx
            
            return nearest_idx
        except Exception:
            return None
    
    def _merge_watersheds(self, source_idx, target_idx):
        """
        合并两个流域
        
        增强点：
        - 合并后完整重建拓扑指针
        - 记录合并历史
        """
        try:
            source_row = self.watershed_data.loc[source_idx]
            target_row = self.watershed_data.loc[target_idx]
            
            source_area = source_row['area_km2']
            target_area = target_row['area_km2']
            
            # 合并几何
            merged_geometry = unary_union([
                source_row['geometry'],
                target_row['geometry']
            ])
            
            # 更新目标流域
            self.watershed_data.loc[target_idx, 'geometry'] = merged_geometry
            
            # 面积暂不更新（迭代结束后统一重算）
            
            # 完整更新拓扑关系
            self._update_topology_after_merge(source_idx, target_idx)
            
            # 删除源流域
            self.watershed_data = self.watershed_data.drop(source_idx)
            
            # 记录合并历史
            source_id = self._get_node_id(source_row, source_idx)
            target_id = self._get_node_id(target_row, target_idx)
            self.merge_history.append({
                'source_id': source_id,
                'target_id': target_id,
                'source_area': round(source_area, 2),
                'target_area': round(target_area, 2),
                'merged_area': round(source_area + target_area, 2),
            })
            
        except Exception as e:
            logger.warning(f"合并流域时出错: {e}")
    
    def _update_topology_after_merge(self, source_idx, target_idx):
        """
        合并后完整重建拓扑关系
        
        增强点（相比 v3.1）：
        1. 更新所有指向 source 的上游引用为 target
        2. 处理 source 的下游指向（如果 target 是 source 的上游）
        3. 处理 source 的上游字段（如果有 up1-up4）
        4. 移除自引用
        """
        if not self._ds_field:
            return
        
        gdf = self.watershed_data
        
        source_id = self._get_node_id(gdf.loc[source_idx], source_idx)
        target_id = self._get_node_id(gdf.loc[target_idx], target_idx)
        
        if source_id is None or target_id is None:
            return
        
        # 1. 更新所有指向 source 的下游引用为 target
        refs_to_source = gdf[self._ds_field] == source_id
        if refs_to_source.any():
            gdf.loc[refs_to_source, self._ds_field] = target_id
        
        # 2. 处理 up1-up4 字段（如果存在）
        for us_field in self._us_fields:
            if us_field in gdf.columns:
                refs = gdf[us_field] == source_id
                if refs.any():
                    gdf.loc[refs, us_field] = target_id
        
        # 3. 如果 target 的下游是 source，更新为 source 的下游
        target_ds = gdf.loc[target_idx, self._ds_field]
        if pd.notna(target_ds) and int(target_ds) == source_id:
            source_ds = gdf.loc[source_idx, self._ds_field]
            if pd.notna(source_ds):
                gdf.loc[target_idx, self._ds_field] = source_ds
            else:
                gdf.loc[target_idx, self._ds_field] = -1
        
        # 4. 移除自引用
        if self._id_field:
            target_own_id = gdf.loc[target_idx, self._id_field]
            if pd.notna(target_own_id):
                target_ds_val = gdf.loc[target_idx, self._ds_field]
                if pd.notna(target_ds_val) and int(target_ds_val) == int(target_own_id):
                    gdf.loc[target_idx, self._ds_field] = -1
        
        # 5. 更新拓扑图
        if self.topology_graph is not None:
            if self.topology_graph.has_node(source_id):
                # 获取 source 的边信息
                in_edges = list(self.topology_graph.in_edges(source_id))
                out_edges = list(self.topology_graph.out_edges(source_id))
                
                # 将 source 的入边重指向 target
                for src, _ in in_edges:
                    if src != target_id and self.topology_graph.has_node(src):
                        if not self.topology_graph.has_edge(src, target_id):
                            self.topology_graph.add_edge(src, target_id)
                
                # 将 source 的出边赋予 target
                for _, dst in out_edges:
                    if dst != target_id and self.topology_graph.has_node(dst):
                        if not self.topology_graph.has_edge(target_id, dst):
                            self.topology_graph.add_edge(target_id, dst)
                
                self.topology_graph.remove_node(source_id)
    
    def _calculate_compliance_rate(self):
        """计算面积合规率"""
        if len(self.watershed_data) == 0:
            return 0.0
        
        compliant_watersheds = self.watershed_data[
            self.watershed_data['area_km2'] >= self.dynamic_threshold
        ]
        
        return len(compliant_watersheds) / len(self.watershed_data)
