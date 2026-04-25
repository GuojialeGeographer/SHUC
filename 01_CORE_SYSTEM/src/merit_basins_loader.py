#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MERIT-Basins 数据集成模块 - MERIT-Basins Data Loader
====================================================

负责加载、解析和索引 MERIT-Basins 向量数据，提供：
- MERIT-Basins cat_*/riv_* 数据加载
- NextDownID / up1-up4 / maxup 拓扑字段解析
- COMID 唯一标识索引
- 与 MERIT Hydro 栅格数据的空间关联
- 分 Pfafstetter 分区加载机制

MERIT-Basins 核心字段:
  cat_* (catchment):  COMID, unitarea, uparea, NextDownID, up1, up2, up3, up4, maxup, order
  riv_* (river reach): COMID, lengthkm, slope_taudem, NextDownID, up1-up4, maxup

Version: 4.0.0
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from pyproj import Geod

logger = logging.getLogger('china_shuc')


class MERITBasinsLoader:
    """
    MERIT-Basins 数据加载与集成模块
    
    负责：
    1. 加载 cat_*/riv_* 向量数据
    2. 构建拓扑图（基于 NextDownID）
    3. 建立空间索引
    4. 提供流域查询接口
    """
    
    # MERIT-Basins 标准字段定义
    CATCHMENT_FIELDS = [
        'COMID', 'unitarea', 'uparea', 'NextDownID',
        'up1', 'up2', 'up3', 'up4', 'maxup', 'order'
    ]
    
    RIVER_FIELDS = [
        'COMID', 'lengthkm', 'slope_taudem', 'NextDownID',
        'up1', 'up2', 'up3', 'up4', 'maxup', 'order'
    ]
    
    # Pfafstetter Level-1 分区码（全球）
    PFAF_REGIONS = {
        '01': 'North America Pacific',
        '02': 'North America Arctic',
        '03': 'South America Pacific',
        '04': 'South America Atlantic',
        '05': 'Europe Arctic',
        '06': 'Europe Atlantic & Mediterranean',
        '07': 'Africa',
        '08': 'Asia Arctic',
        '09': 'Asia Pacific',
        '10': 'Asia Indian Ocean',
    }
    
    # 中国主要覆盖的 Pfafstetter 分区
    CHINA_PFAF_REGIONS = ['08', '09', '10']
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化 MERIT-Basins 加载器
        
        Args:
            config: 配置字典，包含数据路径等参数
        """
        self.config = config or {}
        self.geod = Geod(ellps='WGS84')
        
        # 数据存储
        self.catchments: Optional[gpd.GeoDataFrame] = None
        self.rivers: Optional[gpd.GeoDataFrame] = None
        
        # 索引
        self._comid_index: Dict[int, int] = {}  # COMID -> DataFrame index
        self._topology_cache: Optional[Dict] = None
        
        # 统计信息
        self.load_stats = {
            'catchment_count': 0,
            'river_count': 0,
            'topology_complete': False,
            'load_time_seconds': 0,
        }
    
    def load_catchments(self, catchment_path: str, 
                        bounds: Optional[Tuple[float, float, float, float]] = None,
                        target_crs: Optional[str] = None) -> gpd.GeoDataFrame:
        """
        加载 MERIT-Basins catchment (cat_*) 数据
        
        Args:
            catchment_path: cat_*.shp 文件路径（可以是目录或单个文件）
            bounds: 可选裁剪边界 (lon_min, lat_min, lon_max, lat_max)
            target_crs: 可选目标坐标系
            
        Returns:
            加载的 GeoDataFrame
        """
        import time
        start_time = time.time()
        
        path = Path(catchment_path)
        
        # 如果是目录，查找所有 cat_*.shp
        if path.is_dir():
            shp_files = sorted(path.glob('cat_*.shp'))
            if not shp_files:
                # 也尝试直接查找所有 .shp
                shp_files = sorted(path.glob('*.shp'))
            if not shp_files:
                raise FileNotFoundError(f"未找到 catchment shapefile: {path}")
            
            if len(shp_files) == 1:
                gdf = gpd.read_file(shp_files[0])
            else:
                # 合并多个文件
                frames = []
                for f in shp_files:
                    try:
                        frames.append(gpd.read_file(f))
                    except Exception as e:
                        logger.warning(f"跳过文件 {f.name}: {e}")
                        continue
                gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
        else:
            gdf = gpd.read_file(str(path))
        
        # 裁剪到边界
        if bounds is not None:
            lon_min, lat_min, lon_max, lat_max = bounds
            bbox = box(lon_min, lat_min, lon_max, lat_max)
            gdf = gdf[gdf.geometry.intersects(bbox)].copy()
        
        # 坐标系转换
        if target_crs is not None and gdf.crs is not None:
            gdf = gdf.to_crs(target_crs)
        
        # 标准化字段名（MERIT-Basins 字段可能大小写不同）
        gdf = self._standardize_fields(gdf)
        
        # 计算精确面积（使用 Geod 测地面积）
        gdf['area_km2_geod'] = self._compute_geod_areas(gdf)
        
        # 如果没有 unitarea 字段，使用 Geod 面积
        if 'unitarea' not in gdf.columns:
            gdf['unitarea'] = gdf['area_km2_geod']
        
        # 建立索引
        self.catchments = gdf
        self._build_comid_index(gdf)
        
        elapsed = time.time() - start_time
        self.load_stats['catchment_count'] = len(gdf)
        self.load_stats['load_time_seconds'] = elapsed
        
        logger.info(f"加载 MERIT-Basins catchments: {len(gdf)} 个单元, 耗时 {elapsed:.1f}s")
        
        return gdf
    
    def load_rivers(self, river_path: str,
                    bounds: Optional[Tuple[float, float, float, float]] = None) -> gpd.GeoDataFrame:
        """
        加载 MERIT-Basins river reach (riv_*) 数据
        
        Args:
            river_path: riv_*.shp 文件路径
            bounds: 可选裁剪边界
            
        Returns:
            加载的 GeoDataFrame
        """
        import time
        start_time = time.time()
        
        path = Path(river_path)
        
        if path.is_dir():
            shp_files = sorted(path.glob('riv_*.shp'))
            if not shp_files:
                shp_files = sorted(path.glob('*.shp'))
            if not shp_files:
                raise FileNotFoundError(f"未找到 river shapefile: {path}")
            
            if len(shp_files) == 1:
                gdf = gpd.read_file(shp_files[0])
            else:
                frames = []
                for f in shp_files:
                    try:
                        frames.append(gpd.read_file(f))
                    except Exception as e:
                        logger.warning(f"跳过文件 {f.name}: {e}")
                        continue
                gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
        else:
            gdf = gpd.read_file(str(path))
        
        if bounds is not None:
            lon_min, lat_min, lon_max, lat_max = bounds
            bbox = box(lon_min, lat_min, lon_max, lat_max)
            gdf = gdf[gdf.geometry.intersects(bbox)].copy()
        
        gdf = self._standardize_fields(gdf)
        
        self.rivers = gdf
        self.load_stats['river_count'] = len(gdf)
        
        elapsed = time.time() - start_time
        logger.info(f"加载 MERIT-Basins rivers: {len(gdf)} 条河段, 耗时 {elapsed:.1f}s")
        
        return gdf
    
    def build_topology(self) -> Dict:
        """
        基于 NextDownID 和 up1-up4 构建拓扑关系
        
        Returns:
            拓扑信息字典，包含：
            - adjacency: 邻接关系 {COMID: [downstream_COMID, [upstream_COMIDs]]}
            - outlets: 出口流域列表
            - sources: 源头流域列表
            - orphans: 孤立流域列表
            - has_cycles: 是否存在环
        """
        if self.catchments is None:
            raise ValueError("请先加载 catchment 数据")
        
        gdf = self.catchments
        
        adjacency = {}
        outlets = []
        sources = []
        orphans = []
        
        comid_set = set(gdf['COMID'].values)
        
        for _, row in gdf.iterrows():
            comid = row['COMID']
            downstream = row.get('NextDownID', -1)
            
            # 收集上游
            upstream_list = []
            for up_field in ['up1', 'up2', 'up3', 'up4']:
                up_id = row.get(up_field, -1)
                if pd.notna(up_id) and up_id != -1 and up_id != 0 and up_id in comid_set:
                    upstream_list.append(int(up_id))
            
            # 分类
            if pd.isna(downstream) or downstream == -1 or downstream == 0:
                # 出口或孤立
                if len(upstream_list) == 0:
                    orphans.append(comid)
                else:
                    outlets.append(comid)
                downstream = None
            elif downstream not in comid_set:
                # 下游不在数据集中（可能是边界）
                outlets.append(comid)
                downstream = None
            
            if len(upstream_list) == 0 and downstream is not None:
                sources.append(comid)
            
            adjacency[comid] = {
                'downstream': downstream,
                'upstream': upstream_list,
                'maxup': int(row.get('maxup', 0)) if pd.notna(row.get('maxup')) else 0,
            }
        
        # 环检测
        has_cycles = self._detect_cycles(adjacency)
        
        self._topology_cache = {
            'adjacency': adjacency,
            'outlets': outlets,
            'sources': sources,
            'orphans': orphans,
            'has_cycles': has_cycles,
            'total_catchments': len(adjacency),
        }
        
        self.load_stats['topology_complete'] = not has_cycles
        
        logger.info(f"拓扑构建完成: {len(adjacency)} 节点, "
                    f"{len(outlets)} 出口, {len(sources)} 源头, "
                    f"{len(orphans)} 孤立, 环={has_cycles}")
        
        return self._topology_cache
    
    def get_upstream_recursive(self, comid: int, adjacency: Optional[Dict] = None) -> Set[int]:
        """
        递归获取所有上游 COMID
        
        Args:
            comid: 起始 COMID
            adjacency: 拓扑邻接表（默认使用已构建的）
            
        Returns:
            所有上游 COMID 集合（不含自身）
        """
        if adjacency is None:
            if self._topology_cache is None:
                self.build_topology()
            adjacency = self._topology_cache['adjacency']
        
        visited = set()
        stack = [comid]
        
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            
            if current in adjacency:
                for up_id in adjacency[current]['upstream']:
                    if up_id not in visited:
                        stack.append(up_id)
        
        visited.discard(comid)  # 移除自身
        return visited
    
    def get_downstream_chain(self, comid: int, adjacency: Optional[Dict] = None) -> List[int]:
        """
        获取从指定 COMID 到出口的下游链
        
        Args:
            comid: 起始 COMID
            
        Returns:
            下游 COMID 链（含自身）
        """
        if adjacency is None:
            if self._topology_cache is None:
                self.build_topology()
            adjacency = self._topology_cache['adjacency']
        
        chain = [comid]
        visited = {comid}
        current = comid
        
        while current in adjacency:
            downstream = adjacency[current]['downstream']
            if downstream is None or downstream in visited:
                break
            chain.append(downstream)
            visited.add(downstream)
            current = downstream
        
        return chain
    
    def find_by_comid(self, comid: int) -> Optional[pd.Series]:
        """
        根据 COMID 查找流域
        
        Args:
            comid: MERIT-Basins COMID
            
        Returns:
            对应的行数据，不存在返回 None
        """
        if self.catchments is None:
            return None
        
        if comid in self._comid_index:
            idx = self._comid_index[comid]
            return self.catchments.loc[idx]
        
        return None
    
    def get_catchment_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """
        获取当前加载的 catchment 数据的空间范围
        
        Returns:
            (lon_min, lat_min, lon_max, lat_max) 或 None
        """
        if self.catchments is None:
            return None
        bounds = self.catchments.total_bounds
        return tuple(bounds)
    
    def extract_sub_basin(self, outlet_comid: int) -> Optional[gpd.GeoDataFrame]:
        """
        提取指定出口的上游子流域
        
        Args:
            outlet_comid: 出口流域 COMID
            
        Returns:
            子流域 GeoDataFrame
        """
        if self.catchments is None or self._topology_cache is None:
            logger.error("请先加载数据并构建拓扑")
            return None
        
        upstream_ids = self.get_upstream_recursive(outlet_comid)
        all_ids = upstream_ids | {outlet_comid}
        
        mask = self.catchments['COMID'].isin(all_ids)
        return self.catchments[mask].copy()
    
    # ==================== 内部方法 ====================
    
    def _standardize_fields(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """标准化字段名"""
        # MERIT-Basins 字段可能有不同的命名约定
        field_mapping = {
            'COMID': 'COMID',
            'comid': 'COMID',
            'NextDownID': 'NextDownID',
            'nextdownid': 'NextDownID',
            'nextdown': 'NextDownID',
            'unitarea': 'unitarea',
            'uparea': 'uparea',
            'lengthkm': 'lengthkm',
            'order': 'order',
        }
        
        rename_dict = {}
        for col in gdf.columns:
            col_lower = col.lower()
            if col_lower in field_mapping and col != field_mapping[col_lower]:
                rename_dict[col] = field_mapping[col_lower]
        
        if rename_dict:
            gdf = gdf.rename(columns=rename_dict)
        
        # 确保 COMID 为整数
        if 'COMID' in gdf.columns:
            gdf['COMID'] = gdf['COMID'].astype(int)
        
        # 确保 NextDownID 处理 -1 和 NaN
        if 'NextDownID' in gdf.columns:
            gdf['NextDownID'] = gdf['NextDownID'].fillna(-1).astype(int)
            gdf.loc[gdf['NextDownID'] == 0, 'NextDownID'] = -1
        
        # 处理 up1-up4 字段
        for field in ['up1', 'up2', 'up3', 'up4']:
            if field in gdf.columns:
                gdf[field] = pd.to_numeric(gdf[field], errors='coerce').fillna(-1).astype(int)
                gdf.loc[gdf[field] == 0, field] = -1
        
        # 确保 maxup 字段
        if 'maxup' in gdf.columns:
            gdf['maxup'] = pd.to_numeric(gdf['maxup'], errors='coerce').fillna(0).astype(int)
        
        return gdf
    
    def _compute_geod_areas(self, gdf: gpd.GeoDataFrame) -> pd.Series:
        """使用 Geod 计算精确测地面积 (km2)"""
        areas = []
        for geom in gdf.geometry:
            if geom is None or geom.is_empty:
                areas.append(0.0)
            elif geom.geom_type == 'Polygon':
                area_m2, _ = self.geod.geometry_area_perimeter(geom)
                areas.append(abs(area_m2) / 1_000_000)
            elif geom.geom_type == 'MultiPolygon':
                total = 0.0
                for poly in geom.geoms:
                    a, _ = self.geod.geometry_area_perimeter(poly)
                    total += abs(a)
                areas.append(total / 1_000_000)
            else:
                areas.append(0.0)
        return pd.Series(areas, index=gdf.index)
    
    def _build_comid_index(self, gdf: gpd.GeoDataFrame):
        """构建 COMID 到 DataFrame 索引的映射"""
        self._comid_index = {}
        if 'COMID' in gdf.columns:
            for idx, comid in gdf['COMID'].items():
                self._comid_index[int(comid)] = idx
    
    def _detect_cycles(self, adjacency: Dict) -> bool:
        """
        检测拓扑图中是否存在环（使用 DFS）
        
        Args:
            adjacency: 拓扑邻接表
            
        Returns:
            True 如果存在环
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in adjacency}
        
        def dfs(node):
            color[node] = GRAY
            if node in adjacency:
                ds = adjacency[node].get('downstream')
                if ds is not None and ds in color:
                    if color[ds] == GRAY:
                        return True  # 发现环
                    if color[ds] == WHITE and dfs(ds):
                        return True
            color[node] = BLACK
            return False
        
        for node in adjacency:
            if color[node] == WHITE:
                if dfs(node):
                    return True
        
        return False
    
    def get_load_summary(self) -> Dict:
        """获取加载摘要信息"""
        summary = dict(self.load_stats)
        
        if self.catchments is not None:
            gdf = self.catchments
            summary['catchment_area_range'] = {
                'min_km2': round(gdf['area_km2_geod'].min(), 2) if 'area_km2_geod' in gdf.columns else None,
                'max_km2': round(gdf['area_km2_geod'].max(), 2) if 'area_km2_geod' in gdf.columns else None,
                'mean_km2': round(gdf['area_km2_geod'].mean(), 2) if 'area_km2_geod' in gdf.columns else None,
                'total_km2': round(gdf['area_km2_geod'].sum(), 2) if 'area_km2_geod' in gdf.columns else None,
            }
        
        if self._topology_cache is not None:
            summary['topology'] = {
                'outlets': len(self._topology_cache['outlets']),
                'sources': len(self._topology_cache['sources']),
                'orphans': len(self._topology_cache['orphans']),
                'has_cycles': self._topology_cache['has_cycles'],
            }
        
        return summary


# ==================== 工具函数 ====================

def compute_geod_area(geom) -> float:
    """
    计算单个几何体的精确测地面积 (km2)
    
    Args:
        geom: Shapely geometry 对象
        
    Returns:
        面积 (km2)
    """
    geod = Geod(ellps='WGS84')
    
    if geom is None or geom.is_empty:
        return 0.0
    elif geom.geom_type == 'Polygon':
        area_m2, _ = geod.geometry_area_perimeter(geom)
        return abs(area_m2) / 1_000_000
    elif geom.geom_type == 'MultiPolygon':
        total = 0.0
        for poly in geom.geoms:
            a, _ = geod.geometry_area_perimeter(poly)
            total += abs(a)
        return total / 1_000_000
    else:
        return 0.0


def compute_geod_areas_series(gdf: gpd.GeoDataFrame) -> pd.Series:
    """
    批量计算 GeoDataFrame 中所有几何体的精确测地面积
    
    Args:
        gdf: 包含 geometry 列的 GeoDataFrame
        
    Returns:
        面积 Series (km2)
    """
    return pd.Series(
        [compute_geod_area(geom) for geom in gdf.geometry],
        index=gdf.index,
        name='area_km2_geod'
    )
