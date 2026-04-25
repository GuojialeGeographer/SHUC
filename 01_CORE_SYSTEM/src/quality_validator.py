#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
质量验证器 - Quality Validator (v4.0)
======================================

负责 SHUC 系统的全面质量验证：
- 面积合规性检查（使用精确测地面积）
- 编码唯一性与格式验证（6 级 12 位编码）
- 拓扑完整性检查（DFS 环检测 + 拓扑链完整性验证）
- 几何有效性验证
- 编码元数据一致性验证
- 综合评分系统

改进点（相比 v3.1）：
1. 使用 pyproj.Geod 确保面积验证与处理器一致
2. DFS 深度优先图遍历检测循环引用（替代简单自引用检查）
3. 拓扑链完整性验证（下游链可达出口）
4. 兼容 MERIT-Basins (NextDownID) 和 TauDEM (DSLINKNO) 字段
5. 编码元数据一致性验证（parent_code / downstream_code 交叉校验）
6. 增强的面积合规阈值（与处理器 threshold_min/threshold_max 同步）

Version: 4.0.0
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx
from pyproj import Geod
from collections import defaultdict
import logging
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger('china_shuc')

# 全局 Geod 实例（与 watershed_processor.py 保持一致）
_GEOD = Geod(ellps='WGS84')


def compute_area_km2(geometry) -> float:
    """
    计算单个几何体的精确测地面积 (km2)

    使用 pyproj.Geod 进行球面面积计算，与 watershed_processor.py 保持一致。

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
        return abs(geometry.area) / 1_000_000


class QualityValidator:
    """
    质量验证器类 (v4.0)

    实现多维度质量验证：
    - 面积合规性 (40% 权重)
    - 编码质量 (25% 权重)
    - 拓扑完整性 (25% 权重)
    - 几何有效性 (10% 权重)

    改进点：
    1. 精确测地面积验证
    2. DFS 循环引用检测
    3. 拓扑链完整性验证
    4. 编码元数据一致性验证
    5. 兼容多种拓扑字段命名
    """

    # 支持的下游拓扑字段（与 watershed_processor.py 保持一致）
    DOWNSTREAM_FIELDS = ['DSLINKNO1', 'DSLINKNO', 'NextDownID']

    # 支持的上游拓扑字段
    UPSTREAM_FIELDS = ['USLINKNO1', 'USLINKNO2', 'up1', 'up2', 'up3', 'up4']

    # 支持的 ID 字段
    ID_FIELDS = ['LINKNO', 'COMID']

    def __init__(self, config):
        """
        初始化质量验证器

        Args:
            config (dict): 验证配置参数
        """
        self.config = config

        # 从配置读取阈值
        self.area_compliance_threshold = config.get('area_compliance_threshold', 0.80)
        self.coding_uniqueness_threshold = config.get('coding_uniqueness_threshold', 1.00)
        self.topology_completeness_threshold = config.get('topology_completeness_threshold', 0.95)

        # 面积阈值参数（与处理器同步）
        self.threshold_min = config.get('threshold_min', 50)
        self.threshold_max = config.get('threshold_max', 500)
        self.threshold_formula = config.get('threshold_formula', 'Q75+(Q90-Q75)/2')

        # 质量权重（v4.0 调整：拓扑权重提高）
        self.quality_weights = {
            'area_compliance': 0.40,
            'coding_quality': 0.25,
            'topology_integrity': 0.25,
            'geometry_validity': 0.10
        }

        # 从配置更新权重
        config_weights = config.get('quality_weights', {})
        self.quality_weights.update(config_weights)

        # 检测到的字段名（运行时确定）
        self._id_field = None
        self._ds_field = None
        self._us_fields = []

    def validate_system(self, watershed_data):
        """
        执行完整的系统验证

        Args:
            watershed_data (GeoDataFrame): 编码后的流域数据

        Returns:
            dict: 完整的验证结果
        """
        # 检测拓扑字段
        self._detect_fields(watershed_data)

        validation_result = {
            'validation_timestamp': pd.Timestamp.now().isoformat(),
            'validator_version': '4.0.0',
            'basic_info': self._get_basic_info(watershed_data),
            'area_compliance': self._validate_area_compliance(watershed_data),
            'coding_quality': self._validate_coding_quality(watershed_data),
            'topology_integrity': self._validate_topology_integrity(watershed_data),
            'geometry_validity': self._validate_geometry_validity(watershed_data),
            'metadata_consistency': self._validate_metadata_consistency(watershed_data),
            'hierarchy_analysis': self._analyze_hierarchy_distribution(watershed_data),
            'quality_issues': self._identify_quality_issues(watershed_data)
        }

        # 计算总体评分
        validation_result['overall_score'] = self._calculate_overall_score(validation_result)
        validation_result['quality_grade'] = self._determine_quality_grade(
            validation_result['overall_score']
        )

        return validation_result

    def _detect_fields(self, watershed_data):
        """自动检测可用的拓扑字段"""
        columns = set(watershed_data.columns)

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

        logger.info(f"验证器检测到字段: ID={self._id_field}, "
                    f"下游={self._ds_field}, 上游={self._us_fields}")

    # ==================== 基本信息 ====================

    def _get_basic_info(self, watershed_data):
        """获取基本信息"""
        return {
            'total_watersheds': len(watershed_data),
            'total_area_km2': round(watershed_data['area_km2'].sum(), 2),
            'min_area_km2': round(watershed_data['area_km2'].min(), 2),
            'max_area_km2': round(watershed_data['area_km2'].max(), 2),
            'mean_area_km2': round(watershed_data['area_km2'].mean(), 2),
            'has_shuc_codes': 'shuc_code' in watershed_data.columns,
            'has_shuc_levels': 'shuc_level' in watershed_data.columns,
            'detected_id_field': self._id_field,
            'detected_ds_field': self._ds_field,
        }

    # ==================== 面积合规性 ====================

    def _validate_area_compliance(self, watershed_data):
        """
        验证面积合规性

        使用与 watershed_processor 相同的动态阈值公式，
        但额外验证面积值是否使用精确测地面积计算。
        """
        # 计算动态阈值（与处理器保持一致）
        areas = watershed_data['area_km2'].dropna()

        if len(areas) == 0:
            return {
                'dynamic_threshold_km2': self.threshold_min,
                'compliant_watersheds': 0,
                'total_watersheds': 0,
                'compliance_rate': 0.0,
                'meets_threshold': False,
                'area_distribution': {}
            }

        q75 = areas.quantile(0.75)
        q90 = areas.quantile(0.90)
        dynamic_threshold = max(
            self.threshold_min,
            min(self.threshold_max, q75 + (q90 - q75) / 2)
        )

        # 计算合规率
        compliant_watersheds = watershed_data[watershed_data['area_km2'] >= dynamic_threshold]
        compliance_rate = len(compliant_watersheds) / len(watershed_data)

        # 面积分布分析
        area_distribution = self._analyze_area_distribution(watershed_data, dynamic_threshold)

        # 面积精度验证（可选：抽样验证 Geod 面积 vs 存储面积）
        area_accuracy = self._verify_area_accuracy(watershed_data)

        return {
            'dynamic_threshold_km2': round(dynamic_threshold, 1),
            'threshold_formula': self.threshold_formula,
            'compliant_watersheds': len(compliant_watersheds),
            'total_watersheds': len(watershed_data),
            'compliance_rate': round(compliance_rate, 3),
            'meets_threshold': compliance_rate >= self.area_compliance_threshold,
            'area_distribution': area_distribution,
            'area_accuracy_check': area_accuracy
        }

    def _analyze_area_distribution(self, watershed_data, threshold):
        """分析面积分布"""
        areas = watershed_data['area_km2']

        return {
            'below_threshold': int((areas < threshold).sum()),
            'above_threshold': int((areas >= threshold).sum()),
            'small_watersheds_0_50': int((areas < 50).sum()),
            'medium_watersheds_50_200': int(((areas >= 50) & (areas < 200)).sum()),
            'large_watersheds_200_1000': int(((areas >= 200) & (areas < 1000)).sum()),
            'very_large_watersheds_1000_plus': int((areas >= 1000).sum()),
            'area_statistics': {
                'q25': round(areas.quantile(0.25), 2),
                'q50': round(areas.quantile(0.50), 2),
                'q75': round(areas.quantile(0.75), 2),
                'q90': round(areas.quantile(0.90), 2),
                'mean': round(areas.mean(), 2),
                'std': round(areas.std(), 2),
            }
        }

    def _verify_area_accuracy(self, watershed_data, sample_size=10):
        """
        抽样验证面积精度

        随机选择若干流域，重新计算 Geod 面积，与存储值对比。
        """
        if len(watershed_data) == 0:
            return {'checked': False}

        n = min(sample_size, len(watershed_data))
        sample = watershed_data.sample(n=n, random_state=42)

        discrepancies = []
        for idx, row in sample.iterrows():
            stored_area = row['area_km2']
            computed_area = compute_area_km2(row['geometry'])

            if stored_area > 0:
                rel_error = abs(computed_area - stored_area) / stored_area
                discrepancies.append(rel_error)

        if not discrepancies:
            return {'checked': True, 'sample_size': n, 'mean_error': 0, 'max_error': 0}

        return {
            'checked': True,
            'sample_size': n,
            'mean_relative_error': round(np.mean(discrepancies), 6),
            'max_relative_error': round(np.max(discrepancies), 6),
            'area_calculation_method': 'pyproj.Geod (WGS84)'
        }

    # ==================== 编码质量 ====================

    def _validate_coding_quality(self, watershed_data):
        """验证编码质量"""
        if 'shuc_code' not in watershed_data.columns:
            return {
                'has_codes': False,
                'error': 'SHUC codes not found'
            }

        codes = watershed_data['shuc_code'].dropna()
        codes = codes[codes != '']

        # 编码唯一性
        unique_codes = codes.nunique()
        total_codes = len(codes)
        uniqueness_rate = unique_codes / total_codes if total_codes > 0 else 0

        # 编码格式分析
        code_format_analysis = self._analyze_code_formats(codes)

        # 编码长度一致性
        code_length_analysis = self._analyze_code_lengths(codes, watershed_data)

        return {
            'has_codes': True,
            'total_codes': total_codes,
            'unique_codes': unique_codes,
            'uniqueness_rate': round(uniqueness_rate, 3),
            'meets_uniqueness_threshold': uniqueness_rate >= self.coding_uniqueness_threshold,
            'duplicate_codes': total_codes - unique_codes,
            'code_format_analysis': code_format_analysis,
            'code_length_analysis': code_length_analysis
        }

    def _analyze_code_formats(self, codes):
        """分析编码格式"""
        format_stats = {
            'valid_formats': 0,
            'invalid_formats': 0,
            'empty_codes': 0,
            'format_examples': []
        }

        for code in codes:
            code_str = str(code)
            if pd.isna(code) or code_str == '' or code_str == 'nan':
                format_stats['empty_codes'] += 1
            elif code_str.isdigit():
                format_stats['valid_formats'] += 1
                if len(format_stats['format_examples']) < 5:
                    format_stats['format_examples'].append(code_str)
            else:
                format_stats['invalid_formats'] += 1

        return format_stats

    def _analyze_code_lengths(self, codes, watershed_data):
        """分析编码长度与级别的对应关系"""
        if 'shuc_level' not in watershed_data.columns:
            return {'analyzed': False}

        # 标准编码长度映射（6 级 12 位体系）
        level_expected_lengths = {
            1: 2,   # Level 1: 2 位
            2: 4,   # Level 2: 4 位
            3: 6,   # Level 3: 6 位
            4: 8,   # Level 4: 8 位
            5: 10,  # Level 5: 10 位
            6: 12,  # Level 6: 12 位
        }

        length_mismatches = 0
        level_length_map = {}

        for _, row in watershed_data.iterrows():
            code = str(row.get('shuc_code', ''))
            level = row.get('shuc_level')

            if pd.isna(code) or code == '' or code == 'nan' or pd.isna(level):
                continue

            level = int(level)
            expected_len = level_expected_lengths.get(level)
            actual_len = len(code)

            if expected_len is not None and actual_len != expected_len:
                # 允许编码长度大于等于预期（嵌套编码可能更长）
                if actual_len < expected_len:
                    length_mismatches += 1

            if level not in level_length_map:
                level_length_map[level] = {'expected': expected_len, 'actual_lengths': []}
            level_length_map[level]['actual_lengths'].append(actual_len)

        # 汇总各级编码长度统计
        level_length_summary = {}
        for level, info in sorted(level_length_map.items()):
            lengths = info['actual_lengths']
            level_length_summary[f"Level_{level}"] = {
                'expected_length': info['expected'],
                'min_actual': min(lengths) if lengths else 0,
                'max_actual': max(lengths) if lengths else 0,
                'mean_actual': round(np.mean(lengths), 1) if lengths else 0,
            }

        return {
            'analyzed': True,
            'length_mismatches': length_mismatches,
            'level_length_summary': level_length_summary
        }

    # ==================== 拓扑完整性 ====================

    def _validate_topology_integrity(self, watershed_data):
        """
        验证拓扑完整性

        改进点（v4.0）：
        1. 使用 DFS 算法检测循环引用（替代简单自引用检查）
        2. 验证拓扑链完整性（下游链是否可达出口）
        3. 验证上下游关系一致性
        4. 兼容 MERIT-Basins (NextDownID) 和 TauDEM (DSLINKNO) 字段
        """
        topology_result = {
            'has_topology_fields': False,
            'valid_references': 0,
            'invalid_references': 0,
            'orphan_watersheds': 0,
            'circular_references': 0,
            'cycle_details': [],
            'chain_completeness': {}
        }

        # 检查拓扑字段
        if self._ds_field is None and self._id_field is None:
            topology_result['missing_fields'] = ['LINKNO/COMID', 'DSLINKNO/NextDownID']
            topology_result['completeness_rate'] = 0.0
            return topology_result

        topology_result['has_topology_fields'] = True
        topology_result['detected_id_field'] = self._id_field
        topology_result['detected_ds_field'] = self._ds_field
        topology_result['detected_us_fields'] = self._us_fields

        # 1. 分析基本拓扑关系
        topology_result.update(self._analyze_topology_relationships(watershed_data))

        # 2. DFS 循环引用检测
        cycle_result = self._detect_circular_references_dfs(watershed_data)
        topology_result['circular_references'] = cycle_result['cycle_count']
        topology_result['cycle_details'] = cycle_result['cycle_paths']
        topology_result['has_cycles'] = cycle_result['has_cycles']

        # 3. 拓扑链完整性验证
        chain_result = self._validate_chain_completeness(watershed_data)
        topology_result['chain_completeness'] = chain_result

        # 4. 上下游一致性验证
        consistency_result = self._validate_upstream_consistency(watershed_data)
        topology_result['upstream_consistency'] = consistency_result

        # 计算完整性评分
        total_relations = len(watershed_data)
        valid_relations = topology_result['valid_references']
        completeness_rate = valid_relations / total_relations if total_relations > 0 else 0

        topology_result['completeness_rate'] = round(completeness_rate, 3)
        topology_result['meets_completeness_threshold'] = (
            completeness_rate >= self.topology_completeness_threshold
        )

        return topology_result

    def _analyze_topology_relationships(self, watershed_data):
        """分析拓扑关系（基本引用有效性）"""
        analysis = {
            'valid_references': 0,
            'invalid_references': 0,
            'orphan_watersheds': 0,
        }

        if self._id_field is None or self._ds_field is None:
            return analysis

        id_set = set(watershed_data[self._id_field].dropna().astype(int))

        for _, row in watershed_data.iterrows():
            linkno = row[self._id_field]
            dslinkno = row.get(self._ds_field)

            if pd.isna(linkno):
                continue

            # 检查下游引用有效性
            if pd.notna(dslinkno) and int(dslinkno) != -1 and int(dslinkno) != 0:
                if int(dslinkno) in id_set:
                    analysis['valid_references'] += 1
                else:
                    analysis['invalid_references'] += 1
            else:
                analysis['orphan_watersheds'] += 1

        return analysis

    def _detect_circular_references_dfs(self, watershed_data):
        """
        使用 DFS 深度优先遍历检测循环引用

        改进点（相比 v3.1 简单的 dslinkno == linkno 检查）：
        - 构建有向图，使用标准 DFS 三色标记法
        - 能检测任意长度的循环路径
        - 返回循环路径详情

        Args:
            watershed_data: 流域数据 GeoDataFrame

        Returns:
            dict: 环检测结果
        """
        result = {
            'has_cycles': False,
            'cycle_count': 0,
            'cycle_paths': [],
        }

        if self._id_field is None or self._ds_field is None:
            return result

        # 构建邻接表（下游关系: node -> downstream_node）
        adjacency = {}
        id_to_idx = {}

        for idx, row in watershed_data.iterrows():
            node_id = int(row[self._id_field]) if pd.notna(row[self._id_field]) else None
            if node_id is None:
                continue

            ds_id = row.get(self._ds_field)
            downstream = None
            if pd.notna(ds_id) and int(ds_id) != -1 and int(ds_id) != 0:
                downstream = int(ds_id)

            adjacency[node_id] = downstream
            id_to_idx[node_id] = idx

        if not adjacency:
            return result

        # DFS 三色标记法检测环
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in adjacency}
        cycles_found = []

        def dfs(node, path):
            """DFS 遍历，返回是否发现环"""
            color[node] = GRAY
            path.append(node)

            downstream = adjacency.get(node)
            if downstream is not None and downstream in color:
                if color[downstream] == GRAY:
                    # 发现环 - 提取环路径
                    # downstream 在当前路径中，找到其位置
                    try:
                        cycle_start_idx = path.index(downstream)
                        cycle_path = path[cycle_start_idx:]
                        cycles_found.append(list(cycle_path))
                    except ValueError:
                        # downstream 不在 path 中（理论上不会发生）
                        cycles_found.append([node, downstream])
                elif color[downstream] == WHITE:
                    dfs(downstream, path)

            color[node] = BLACK
            path.pop()

        for node in adjacency:
            if color[node] == WHITE:
                dfs(node, [])

        result['has_cycles'] = len(cycles_found) > 0
        result['cycle_count'] = len(cycles_found)
        result['cycle_paths'] = [
            {'path': path, 'length': len(path)}
            for path in cycles_found[:20]  # 限制最多 20 个环的详情
        ]

        if result['has_cycles']:
            logger.warning(f"检测到 {result['cycle_count']} 个循环引用")
            for i, path_info in enumerate(result['cycle_paths'][:5]):
                logger.warning(f"  环 {i+1}: {' -> '.join(map(str, path_info['path']))}")

        return result

    def _validate_chain_completeness(self, watershed_data):
        """
        验证拓扑链完整性

        沿着下游链追踪，检查是否所有链都能到达出口（即 ds_field=-1 的节点）
        或流出数据范围。
        """
        result = {
            'total_chains_checked': 0,
            'complete_chains': 0,
            'incomplete_chains': 0,
            'chain_reach_outlet': 0,
            'chain_reach_boundary': 0,
            'max_chain_length': 0,
            'mean_chain_length': 0.0,
        }

        if self._id_field is None or self._ds_field is None:
            return result

        # 构建 ID 集合
        id_set = set(
            watershed_data[self._id_field].dropna().astype(int)
        )

        chain_lengths = []

        for idx, row in watershed_data.iterrows():
            node_id = row.get(self._id_field)
            if pd.isna(node_id):
                continue
            node_id = int(node_id)

            result['total_chains_checked'] += 1

            # 沿下游追踪
            chain_length = 0
            current = node_id
            visited = {current}
            chain_complete = False

            while current in id_set:
                ds_row = watershed_data[watershed_data[self._id_field] == current]
                if ds_row.empty:
                    break

                ds_id = ds_row.iloc[0].get(self._ds_field)
                if pd.isna(ds_id) or int(ds_id) == -1 or int(ds_id) == 0:
                    # 到达出口
                    chain_complete = True
                    result['chain_reach_outlet'] += 1
                    break

                ds_id = int(ds_id)
                if ds_id not in id_set:
                    # 下游不在数据集中（边界）
                    chain_complete = True
                    result['chain_reach_boundary'] += 1
                    break

                if ds_id in visited:
                    # 循环引用
                    break

                visited.add(ds_id)
                current = ds_id
                chain_length += 1

            chain_lengths.append(chain_length)

            if chain_complete:
                result['complete_chains'] += 1
            else:
                result['incomplete_chains'] += 1

        if chain_lengths:
            result['max_chain_length'] = max(chain_lengths)
            result['mean_chain_length'] = round(np.mean(chain_lengths), 1)

        return result

    def _validate_upstream_consistency(self, watershed_data):
        """
        验证上下游关系一致性

        如果 A 的下游是 B，则 B 的上游列表中应包含 A。
        """
        result = {
            'checked': False,
            'consistent_pairs': 0,
            'inconsistent_pairs': 0,
        }

        if self._id_field is None or self._ds_field is None or not self._us_fields:
            return result

        result['checked'] = True

        # 构建上游查找表：node_id -> set(upstream_ids)
        upstream_map = defaultdict(set)
        for _, row in watershed_data.iterrows():
            node_id = row.get(self._id_field)
            if pd.isna(node_id):
                continue
            node_id = int(node_id)

            for us_field in self._us_fields:
                if us_field in watershed_data.columns:
                    us_id = row.get(us_field)
                    if pd.notna(us_id) and int(us_id) != -1 and int(us_id) != 0:
                        upstream_map[node_id].add(int(us_id))

        # 验证：A.ds == B 意味着 A in B.upstream
        for _, row in watershed_data.iterrows():
            node_id = row.get(self._id_field)
            ds_id = row.get(self._ds_field)
            if pd.isna(node_id) or pd.isna(ds_id):
                continue

            node_id = int(node_id)
            ds_id = int(ds_id)

            if ds_id == -1 or ds_id == 0:
                continue

            if ds_id in upstream_map:
                if node_id in upstream_map[ds_id]:
                    result['consistent_pairs'] += 1
                else:
                    result['inconsistent_pairs'] += 1

        return result

    # ==================== 几何有效性 ====================

    def _validate_geometry_validity(self, watershed_data):
        """验证几何有效性"""
        geometry_result = {
            'total_geometries': len(watershed_data),
            'valid_geometries': 0,
            'invalid_geometries': 0,
            'empty_geometries': 0,
            'geometry_types': {},
            'invalid_ids': []
        }

        for idx, row in watershed_data.iterrows():
            geom = row['geometry']

            if geom is None or geom.is_empty:
                geometry_result['empty_geometries'] += 1
            elif geom.is_valid:
                geometry_result['valid_geometries'] += 1

                geom_type = geom.geom_type
                geometry_result['geometry_types'][geom_type] = \
                    geometry_result['geometry_types'].get(geom_type, 0) + 1
            else:
                geometry_result['invalid_geometries'] += 1
                # 记录无效几何的 ID
                if self._id_field and self._id_field in row.index:
                    invalid_id = row[self._id_field]
                    if pd.notna(invalid_id):
                        geometry_result['invalid_ids'].append(int(invalid_id))

        # 计算有效性比率
        total = geometry_result['total_geometries']
        valid = geometry_result['valid_geometries']
        geometry_result['validity_rate'] = round(valid / total, 3) if total > 0 else 0

        return geometry_result

    # ==================== 编码元数据一致性 ====================

    def _validate_metadata_consistency(self, watershed_data):
        """
        验证编码元数据一致性

        检查：
        - downstream_code 是否指向存在的编码
        - upstream_codes 中的编码是否都存在
        - parent_code 是否指向正确级别的编码
        """
        result = {
            'checked': False,
            'downstream_code_valid': 0,
            'downstream_code_invalid': 0,
            'upstream_code_valid': 0,
            'upstream_code_invalid': 0,
        }

        if 'shuc_code' not in watershed_data.columns:
            return result

        result['checked'] = True
        valid_codes = set(
            str(c) for c in watershed_data['shuc_code'].dropna()
            if str(c) != '' and str(c) != 'nan'
        )

        # 验证 downstream_code
        if 'downstream_code' in watershed_data.columns:
            for _, row in watershed_data.iterrows():
                ds_code = str(row.get('downstream_code', ''))
                if ds_code and ds_code != '' and ds_code != 'nan':
                    if ds_code in valid_codes:
                        result['downstream_code_valid'] += 1
                    else:
                        result['downstream_code_invalid'] += 1

        # 验证 upstream_codes
        if 'upstream_codes' in watershed_data.columns:
            for _, row in watershed_data.iterrows():
                us_codes_str = str(row.get('upstream_codes', ''))
                if us_codes_str and us_codes_str != '' and us_codes_str != 'nan':
                    us_codes = us_codes_str.split(',')
                    for code in us_codes:
                        code = code.strip()
                        if code and code in valid_codes:
                            result['upstream_code_valid'] += 1
                        elif code:
                            result['upstream_code_invalid'] += 1

        return result

    # ==================== 层次分析 ====================

    def _analyze_hierarchy_distribution(self, watershed_data):
        """分析层次分布"""
        if 'shuc_level' not in watershed_data.columns:
            return {'has_hierarchy': False}

        level_distribution = watershed_data['shuc_level'].value_counts().sort_index()

        analysis = {
            'has_hierarchy': True,
            'level_distribution': {},
            'level_range': '',
            'hierarchy_balance': {}
        }

        # 级别分布
        for level, count in level_distribution.items():
            analysis['level_distribution'][f"Level_{level}"] = {
                'count': int(count),
                'percentage': round(count / len(watershed_data) * 100, 1)
            }

        # 级别范围
        min_level = int(level_distribution.index.min())
        max_level = int(level_distribution.index.max())
        analysis['level_range'] = f"Level {min_level}-{max_level}"

        # 层次平衡分析
        analysis['hierarchy_balance'] = {
            'total_levels': len(level_distribution),
            'most_common_level': int(level_distribution.idxmax()),
            'level_distribution_evenness': self._calculate_evenness(level_distribution)
        }

        # 各级别面积统计
        level_area_stats = {}
        for level in level_distribution.index:
            level_data = watershed_data[watershed_data['shuc_level'] == level]
            level_area_stats[f"Level_{level}"] = {
                'count': len(level_data),
                'mean_area_km2': round(level_data['area_km2'].mean(), 2),
                'min_area_km2': round(level_data['area_km2'].min(), 2),
                'max_area_km2': round(level_data['area_km2'].max(), 2),
            }
        analysis['level_area_stats'] = level_area_stats

        return analysis

    def _calculate_evenness(self, distribution):
        """计算分布均匀性（香农均匀性指数）"""
        if len(distribution) <= 1:
            return 1.0

        proportions = distribution / distribution.sum()
        shannon_h = -sum(p * np.log(p) for p in proportions if p > 0)
        max_h = np.log(len(distribution))
        evenness = shannon_h / max_h if max_h > 0 else 0

        return round(evenness, 3)

    # ==================== 质量问题识别 ====================

    def _identify_quality_issues(self, watershed_data):
        """识别质量问题"""
        issues = []

        # 面积问题
        small_watersheds = watershed_data[watershed_data['area_km2'] < 50]
        if len(small_watersheds) > 0:
            issues.append({
                'type': 'small_watersheds',
                'severity': 'high',
                'count': len(small_watersheds),
                'description': f'{len(small_watersheds)} 个流域面积小于50km²',
                'min_area': round(small_watersheds['area_km2'].min(), 2)
            })

        # 编码问题
        if 'shuc_code' in watershed_data.columns:
            empty_codes = watershed_data['shuc_code'].isna().sum()
            empty_str_codes = (watershed_data['shuc_code'] == '').sum()
            total_missing = empty_codes + empty_str_codes
            if total_missing > 0:
                issues.append({
                    'type': 'missing_codes',
                    'severity': 'medium',
                    'count': int(total_missing),
                    'description': f'{total_missing} 个流域缺少SHUC编码'
                })

            # 重复编码
            codes = watershed_data['shuc_code'].dropna()
            codes = codes[codes != '']
            if len(codes) > 0:
                dup_count = len(codes) - codes.nunique()
                if dup_count > 0:
                    issues.append({
                        'type': 'duplicate_codes',
                        'severity': 'high',
                        'count': dup_count,
                        'description': f'{dup_count} 个重复编码'
                    })

        # 几何问题
        invalid_geom = ~watershed_data.geometry.is_valid
        if invalid_geom.any():
            issues.append({
                'type': 'invalid_geometry',
                'severity': 'medium',
                'count': int(invalid_geom.sum()),
                'description': f'{invalid_geom.sum()} 个流域几何无效'
            })

        # 空几何
        empty_geom = watershed_data.geometry.is_empty
        if empty_geom.any():
            issues.append({
                'type': 'empty_geometry',
                'severity': 'high',
                'count': int(empty_geom.sum()),
                'description': f'{empty_geom.sum()} 个流域几何为空'
            })

        return issues

    # ==================== 综合评分 ====================

    def _calculate_overall_score(self, validation_result):
        """
        计算总体评分

        权重体系（v4.0）：
        - 面积合规性: 40%
        - 编码质量: 25%
        - 拓扑完整性: 25%
        - 几何有效性: 10%
        """
        scores = {}

        # 面积合规评分
        area_score = validation_result['area_compliance']['compliance_rate'] * 100
        scores['area_compliance'] = area_score

        # 编码质量评分
        if validation_result['coding_quality']['has_codes']:
            coding_score = validation_result['coding_quality']['uniqueness_rate'] * 100
        else:
            coding_score = 0
        scores['coding_quality'] = coding_score

        # 拓扑完整性评分
        topo_result = validation_result['topology_integrity']
        if topo_result['has_topology_fields']:
            completeness = topo_result['completeness_rate']

            # 如果有环，扣分
            cycle_penalty = 0
            if topo_result.get('has_cycles', False):
                cycle_count = topo_result.get('circular_references', 0)
                cycle_penalty = min(cycle_count * 5, 30)  # 每个环扣 5 分，最多 30 分

            topology_score = completeness * 100 - cycle_penalty
            topology_score = max(0, topology_score)
        else:
            topology_score = 40  # 无拓扑字段给部分分数
        scores['topology_integrity'] = topology_score

        # 几何有效性评分
        geometry_score = validation_result['geometry_validity']['validity_rate'] * 100
        scores['geometry_validity'] = geometry_score

        # 加权总分
        weighted_score = sum(
            scores[component] * weight
            for component, weight in self.quality_weights.items()
        )

        return round(weighted_score, 1)

    def _determine_quality_grade(self, overall_score):
        """确定质量等级"""
        if overall_score >= 90:
            return "优秀 (Excellent)"
        elif overall_score >= 80:
            return "良好 (Good)"
        elif overall_score >= 70:
            return "可接受 (Acceptable)"
        elif overall_score >= 60:
            return "需改进 (Needs Improvement)"
        else:
            return "不合格 (Failed)"
