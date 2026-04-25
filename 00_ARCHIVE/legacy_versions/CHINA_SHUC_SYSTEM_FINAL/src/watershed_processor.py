#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流域处理器 - Watershed Processor
===============================

负责流域数据的智能合并处理，实现90%面积合规率的核心算法：
- 动态阈值调整算法
- 激进合并策略
- 拓扑图构建和优化

Version: 3.1.0
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx
from shapely.ops import unary_union
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class WatershedProcessor:
    """
    流域处理器类
    
    实现智能流域合并算法，支持：
    - 动态阈值计算
    - 激进合并策略
    - 拓扑关系维护
    - 合并历史追踪
    """
    
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
    
    def merge_watersheds(self, input_shapefile):
        """
        执行流域合并的主要方法
        
        Args:
            input_shapefile (str): 输入shapefile路径
            
        Returns:
            dict: 包含合并结果和统计信息
        """
        # 1. 加载和预处理数据
        self._load_data(input_shapefile)
        
        # 2. 计算动态阈值
        self.dynamic_threshold = self._calculate_dynamic_threshold()
        
        # 3. 构建拓扑图
        self._build_topology_graph()
        
        # 4. 执行激进合并
        merge_stats = self._execute_aggressive_merging()
        
        return {
            'merged_watersheds': self.watershed_data,
            'statistics': merge_stats,
            'merge_history': self.merge_history,
            'dynamic_threshold': self.dynamic_threshold
        }
    
    def _load_data(self, shapefile_path):
        """加载和预处理数据"""
        self.watershed_data = gpd.read_file(shapefile_path)
        
        # 确保面积字段存在
        if 'area_km2' not in self.watershed_data.columns:
            if 'Areakm2' in self.watershed_data.columns:
                self.watershed_data['area_km2'] = self.watershed_data['Areakm2']
            else:
                self.watershed_data['area_km2'] = self.watershed_data.geometry.area / 1000000
        
        # 修复数据问题
        self._fix_data_issues()
    
    def _fix_data_issues(self):
        """修复数据问题"""
        issues_fixed = 0
        
        # 修复self-reference问题
        if 'LINKNO' in self.watershed_data.columns and 'USLINKNO2' in self.watershed_data.columns:
            self_refs = self.watershed_data['LINKNO'] == self.watershed_data['USLINKNO2']
            if self_refs.any():
                self.watershed_data.loc[self_refs, 'USLINKNO2'] = -1
                issues_fixed += self_refs.sum()
        
        # 修复无效几何
        invalid_geom = ~self.watershed_data.geometry.is_valid
        if invalid_geom.any():
            self.watershed_data.loc[invalid_geom, 'geometry'] = \
                self.watershed_data.loc[invalid_geom, 'geometry'].buffer(0)
            issues_fixed += invalid_geom.sum()
        
        return issues_fixed
    
    def _calculate_dynamic_threshold(self):
        """
        计算动态阈值
        
        基于数据分布的自适应阈值计算，核心算法：
        threshold = max(60, min(90, Q75 + (Q90-Q75)/2))
        """
        areas = self.watershed_data['area_km2'].dropna()
        
        if len(areas) == 0:
            return 80  # 默认阈值
        
        # 计算分位数
        q25 = areas.quantile(0.25)
        q50 = areas.quantile(0.50)
        q75 = areas.quantile(0.75)
        q90 = areas.quantile(0.90)
        
        # 动态阈值公式
        dynamic_threshold = q75 + (q90 - q75) / 2
        
        # 约束在合理范围内
        threshold = max(50, min(100, dynamic_threshold))
        
        return threshold
    
    def _build_topology_graph(self):
        """构建拓扑关系图"""
        self.topology_graph = nx.DiGraph()
        
        # 添加节点
        for idx, row in self.watershed_data.iterrows():
            watershed_id = row.get('LINKNO', idx)
            self.topology_graph.add_node(watershed_id, 
                                       area=row['area_km2'],
                                       geometry=row['geometry'],
                                       original_id=watershed_id)
        
        # 添加边 (上下游关系)
        if 'DSLINKNO1' in self.watershed_data.columns:
            for idx, row in self.watershed_data.iterrows():
                source = row.get('LINKNO', idx)
                target = row.get('DSLINKNO1')
                
                if pd.notna(target) and target != -1 and target in self.topology_graph.nodes:
                    self.topology_graph.add_edge(source, target)
    
    def _execute_aggressive_merging(self):
        """
        执行激进合并策略
        
        Returns:
            dict: 合并统计信息
        """
        original_count = len(self.watershed_data)
        iteration = 0
        last_compliance_rate = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # 获取需要合并的流域
            small_watersheds = self._identify_merge_candidates()
            
            if not small_watersheds:
                break
            
            # 执行一轮合并
            merged_count = self._merge_iteration(small_watersheds)
            
            # 计算当前合规率
            current_compliance = self._calculate_compliance_rate()
            
            # 记录合并历史
            self.merge_history.append({
                'iteration': iteration,
                'merged_count': merged_count,
                'remaining_watersheds': len(self.watershed_data),
                'compliance_rate': current_compliance
            })
            
            # 早停条件：合规率达到目标
            if (self.enable_early_stopping and 
                current_compliance >= self.target_compliance):
                break
            
            # 防止无进展循环
            if current_compliance <= last_compliance_rate and merged_count == 0:
                break
                
            last_compliance_rate = current_compliance
        
        final_count = len(self.watershed_data)
        compression_rate = (original_count - final_count) / original_count
        final_compliance = self._calculate_compliance_rate()
        
        return {
            'original_count': original_count,
            'final_count': final_count,
            'compression_rate': compression_rate,
            'final_compliance_rate': final_compliance,
            'iterations': iteration,
            'dynamic_threshold_used': self.dynamic_threshold
        }
    
    def _identify_merge_candidates(self):
        """识别需要合并的小流域"""
        small_watersheds = self.watershed_data[
            self.watershed_data['area_km2'] < self.dynamic_threshold
        ].copy()
        
        # 按面积排序，优先合并最小的
        return small_watersheds.sort_values('area_km2')
    
    def _merge_iteration(self, small_watersheds):
        """执行一轮合并"""
        merged_count = 0
        
        for idx, watershed in small_watersheds.iterrows():
            if idx not in self.watershed_data.index:
                continue  # 已被合并
            
            # 寻找合并目标
            merge_target = self._find_merge_target(idx, watershed)
            
            if merge_target is not None:
                # 执行合并
                self._merge_watersheds(idx, merge_target)
                merged_count += 1
        
        return merged_count
    
    def _find_merge_target(self, watershed_idx, watershed_row):
        """
        寻找合并目标
        
        优先级：下游 > 上游 > 相邻 > 最近
        """
        watershed_id = watershed_row.get('LINKNO', watershed_idx)
        
        # 1. 优先合并到下游
        downstream_id = watershed_row.get('DSLINKNO1')
        if (pd.notna(downstream_id) and downstream_id != -1):
            downstream_idx = self._find_watershed_by_linkno(downstream_id)
            if downstream_idx is not None:
                return downstream_idx
        
        # 2. 寻找上游流域
        upstream_watersheds = self.watershed_data[
            self.watershed_data.get('DSLINKNO1') == watershed_id
        ]
        if not upstream_watersheds.empty:
            # 选择面积最大的上游
            target_idx = upstream_watersheds['area_km2'].idxmax()
            return target_idx
        
        # 3. 寻找相邻流域
        adjacent_target = self._find_adjacent_watershed(watershed_row)
        if adjacent_target is not None:
            return adjacent_target
        
        # 4. 寻找最近的流域
        nearest_target = self._find_nearest_watershed(watershed_row)
        return nearest_target
    
    def _find_watershed_by_linkno(self, linkno):
        """根据LINKNO查找流域索引"""
        matches = self.watershed_data[
            self.watershed_data.get('LINKNO') == linkno
        ]
        return matches.index[0] if not matches.empty else None
    
    def _find_adjacent_watershed(self, watershed_row):
        """寻找相邻的流域"""
        try:
            current_geom = watershed_row['geometry']
            
            # 寻找接触的流域
            for idx, other_row in self.watershed_data.iterrows():
                if idx == watershed_row.name:
                    continue
                
                if current_geom.touches(other_row['geometry']):
                    return idx
        except:
            pass
        
        return None
    
    def _find_nearest_watershed(self, watershed_row):
        """寻找最近的流域"""
        try:
            current_geom = watershed_row['geometry']
            min_distance = float('inf')
            nearest_idx = None
            
            for idx, other_row in self.watershed_data.iterrows():
                if idx == watershed_row.name:
                    continue
                
                distance = current_geom.distance(other_row['geometry'])
                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = idx
            
            return nearest_idx
        except:
            return None
    
    def _merge_watersheds(self, source_idx, target_idx):
        """合并两个流域"""
        try:
            source_row = self.watershed_data.loc[source_idx]
            target_row = self.watershed_data.loc[target_idx]
            
            # 合并几何
            merged_geometry = unary_union([
                source_row['geometry'], 
                target_row['geometry']
            ])
            
            # 合并面积
            merged_area = source_row['area_km2'] + target_row['area_km2']
            
            # 更新目标流域
            self.watershed_data.loc[target_idx, 'geometry'] = merged_geometry
            self.watershed_data.loc[target_idx, 'area_km2'] = merged_area
            
            # 更新拓扑关系
            self._update_topology_after_merge(source_idx, target_idx)
            
            # 删除源流域
            self.watershed_data = self.watershed_data.drop(source_idx)
            
        except Exception as e:
            print(f"合并流域时出错: {e}")
    
    def _update_topology_after_merge(self, source_idx, target_idx):
        """合并后更新拓扑关系"""
        try:
            source_linkno = self.watershed_data.loc[source_idx].get('LINKNO')
            target_linkno = self.watershed_data.loc[target_idx].get('LINKNO')
            
            # 更新指向源流域的引用
            upstream_refs = self.watershed_data['DSLINKNO1'] == source_linkno
            if upstream_refs.any():
                self.watershed_data.loc[upstream_refs, 'DSLINKNO1'] = target_linkno
            
        except Exception as e:
            pass  # 拓扑更新失败不影响几何合并
    
    def _calculate_compliance_rate(self):
        """计算面积合规率"""
        if len(self.watershed_data) == 0:
            return 0.0
        
        compliant_watersheds = self.watershed_data[
            self.watershed_data['area_km2'] >= self.dynamic_threshold
        ]
        
        return len(compliant_watersheds) / len(self.watershed_data)