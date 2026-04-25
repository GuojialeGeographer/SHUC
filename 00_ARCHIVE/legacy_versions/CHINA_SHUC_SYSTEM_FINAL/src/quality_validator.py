#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
质量验证器 - Quality Validator
=============================

负责SHUC系统的全面质量验证：
- 面积合规性检查
- 编码唯一性验证
- 拓扑完整性检查
- 几何有效性验证
- 综合评分系统

Version: 3.1.0
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class QualityValidator:
    """
    质量验证器类
    
    实现多维度质量验证：
    - 面积合规性 (40%权重)
    - 编码质量 (30%权重)
    - 拓扑完整性 (20%权重)
    - 几何有效性 (10%权重)
    """
    
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
        
        # 质量权重
        self.quality_weights = {
            'area_compliance': 0.40,
            'coding_quality': 0.30,
            'topology_integrity': 0.20,
            'geometry_validity': 0.10
        }
        
        # 从配置更新权重
        config_weights = config.get('quality_weights', {})
        self.quality_weights.update(config_weights)
    
    def validate_system(self, watershed_data):
        """
        执行完整的系统验证
        
        Args:
            watershed_data (GeoDataFrame): 编码后的流域数据
            
        Returns:
            dict: 完整的验证结果
        """
        validation_result = {
            'validation_timestamp': pd.Timestamp.now().isoformat(),
            'basic_info': self._get_basic_info(watershed_data),
            'area_compliance': self._validate_area_compliance(watershed_data),
            'coding_quality': self._validate_coding_quality(watershed_data),
            'topology_integrity': self._validate_topology_integrity(watershed_data),
            'geometry_validity': self._validate_geometry_validity(watershed_data),
            'hierarchy_analysis': self._analyze_hierarchy_distribution(watershed_data),
            'quality_issues': self._identify_quality_issues(watershed_data)
        }
        
        # 计算总体评分
        validation_result['overall_score'] = self._calculate_overall_score(validation_result)
        validation_result['quality_grade'] = self._determine_quality_grade(validation_result['overall_score'])
        
        return validation_result
    
    def _get_basic_info(self, watershed_data):
        """获取基本信息"""
        return {
            'total_watersheds': len(watershed_data),
            'total_area_km2': round(watershed_data['area_km2'].sum(), 2),
            'min_area_km2': round(watershed_data['area_km2'].min(), 2),
            'max_area_km2': round(watershed_data['area_km2'].max(), 2),
            'mean_area_km2': round(watershed_data['area_km2'].mean(), 2),
            'has_shuc_codes': 'shuc_code' in watershed_data.columns,
            'has_shuc_levels': 'shuc_level' in watershed_data.columns
        }
    
    def _validate_area_compliance(self, watershed_data):
        """验证面积合规性"""
        # 计算动态阈值（与处理器保持一致）
        areas = watershed_data['area_km2'].dropna()
        q75 = areas.quantile(0.75)
        q90 = areas.quantile(0.90)
        dynamic_threshold = max(50, min(100, q75 + (q90 - q75) / 2))
        
        # 计算合规率
        compliant_watersheds = watershed_data[watershed_data['area_km2'] >= dynamic_threshold]
        compliance_rate = len(compliant_watersheds) / len(watershed_data)
        
        # 面积分布分析
        area_distribution = self._analyze_area_distribution(watershed_data, dynamic_threshold)
        
        return {
            'dynamic_threshold_km2': round(dynamic_threshold, 1),
            'compliant_watersheds': len(compliant_watersheds),
            'total_watersheds': len(watershed_data),
            'compliance_rate': round(compliance_rate, 3),
            'meets_threshold': compliance_rate >= self.area_compliance_threshold,
            'area_distribution': area_distribution
        }
    
    def _analyze_area_distribution(self, watershed_data, threshold):
        """分析面积分布"""
        areas = watershed_data['area_km2']
        
        return {
            'below_threshold': len(areas[areas < threshold]),
            'above_threshold': len(areas[areas >= threshold]),
            'small_watersheds_0_50': len(areas[areas < 50]),
            'medium_watersheds_50_200': len(areas[(areas >= 50) & (areas < 200)]),
            'large_watersheds_200_plus': len(areas[areas >= 200]),
            'area_statistics': {
                'q25': round(areas.quantile(0.25), 2),
                'q50': round(areas.quantile(0.50), 2),
                'q75': round(areas.quantile(0.75), 2),
                'q90': round(areas.quantile(0.90), 2)
            }
        }
    
    def _validate_coding_quality(self, watershed_data):
        """验证编码质量"""
        if 'shuc_code' not in watershed_data.columns:
            return {
                'has_codes': False,
                'error': 'SHUC codes not found'
            }
        
        codes = watershed_data['shuc_code'].dropna()
        
        # 编码唯一性
        unique_codes = codes.nunique()
        total_codes = len(codes)
        uniqueness_rate = unique_codes / total_codes if total_codes > 0 else 0
        
        # 编码格式分析
        code_format_analysis = self._analyze_code_formats(codes)
        
        return {
            'has_codes': True,
            'total_codes': total_codes,
            'unique_codes': unique_codes,
            'uniqueness_rate': round(uniqueness_rate, 3),
            'meets_uniqueness_threshold': uniqueness_rate >= self.coding_uniqueness_threshold,
            'duplicate_codes': total_codes - unique_codes,
            'code_format_analysis': code_format_analysis
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
            if pd.isna(code) or code == '':
                format_stats['empty_codes'] += 1
            elif str(code).isdigit():
                format_stats['valid_formats'] += 1
                if len(format_stats['format_examples']) < 5:
                    format_stats['format_examples'].append(str(code))
            else:
                format_stats['invalid_formats'] += 1
        
        return format_stats
    
    def _validate_topology_integrity(self, watershed_data):
        """验证拓扑完整性"""
        topology_result = {
            'has_topology_fields': False,
            'valid_references': 0,
            'invalid_references': 0,
            'orphan_watersheds': 0,
            'circular_references': 0
        }
        
        # 检查拓扑字段存在
        topo_fields = ['LINKNO', 'DSLINKNO1', 'USLINKNO2']
        missing_fields = [f for f in topo_fields if f not in watershed_data.columns]
        
        if missing_fields:
            topology_result['missing_fields'] = missing_fields
            topology_result['completeness_rate'] = 0.0
            return topology_result
        
        topology_result['has_topology_fields'] = True
        
        # 分析拓扑关系
        topology_result.update(self._analyze_topology_relationships(watershed_data))
        
        # 计算完整性评分
        total_relations = len(watershed_data)
        valid_relations = topology_result['valid_references']
        completeness_rate = valid_relations / total_relations if total_relations > 0 else 0
        
        topology_result['completeness_rate'] = round(completeness_rate, 3)
        topology_result['meets_completeness_threshold'] = completeness_rate >= self.topology_completeness_threshold
        
        return topology_result
    
    def _analyze_topology_relationships(self, watershed_data):
        """分析拓扑关系"""
        analysis = {
            'valid_references': 0,
            'invalid_references': 0,
            'orphan_watersheds': 0,
            'circular_references': 0
        }
        
        linkno_set = set(watershed_data['LINKNO'].dropna())
        
        for _, row in watershed_data.iterrows():
            linkno = row['LINKNO']
            dslinkno = row['DSLINKNO1']
            
            # 检查下游引用有效性
            if pd.notna(dslinkno) and dslinkno != -1:
                if dslinkno in linkno_set:
                    analysis['valid_references'] += 1
                    
                    # 检查循环引用
                    if dslinkno == linkno:
                        analysis['circular_references'] += 1
                else:
                    analysis['invalid_references'] += 1
            else:
                analysis['orphan_watersheds'] += 1
        
        return analysis
    
    def _validate_geometry_validity(self, watershed_data):
        """验证几何有效性"""
        geometry_result = {
            'total_geometries': len(watershed_data),
            'valid_geometries': 0,
            'invalid_geometries': 0,
            'empty_geometries': 0,
            'geometry_types': {}
        }
        
        for _, row in watershed_data.iterrows():
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
        
        # 计算有效性比率
        total = geometry_result['total_geometries']
        valid = geometry_result['valid_geometries']
        geometry_result['validity_rate'] = round(valid / total, 3) if total > 0 else 0
        
        return geometry_result
    
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
        
        return analysis
    
    def _calculate_evenness(self, distribution):
        """计算分布均匀性"""
        if len(distribution) <= 1:
            return 1.0
        
        # 使用香农均匀性指数
        proportions = distribution / distribution.sum()
        shannon_h = -sum(p * np.log(p) for p in proportions if p > 0)
        max_h = np.log(len(distribution))
        evenness = shannon_h / max_h if max_h > 0 else 0
        
        return round(evenness, 3)
    
    def _identify_quality_issues(self, watershed_data):
        """识别质量问题"""
        issues = []
        
        # 面积问题
        small_watersheds = watershed_data[watershed_data['area_km2'] < 50]
        if len(small_watersheds) > 0:
            issues.append({
                'type': 'small_watersheds',
                'count': len(small_watersheds),
                'description': f'{len(small_watersheds)} 个流域面积小于50km²'
            })
        
        # 编码问题
        if 'shuc_code' in watershed_data.columns:
            empty_codes = watershed_data['shuc_code'].isna().sum()
            if empty_codes > 0:
                issues.append({
                    'type': 'missing_codes',
                    'count': empty_codes,
                    'description': f'{empty_codes} 个流域缺少SHUC编码'
                })
        
        # 几何问题
        invalid_geom = ~watershed_data.geometry.is_valid
        if invalid_geom.any():
            issues.append({
                'type': 'invalid_geometry',
                'count': invalid_geom.sum(),
                'description': f'{invalid_geom.sum()} 个流域几何无效'
            })
        
        return issues
    
    def _calculate_overall_score(self, validation_result):
        """计算总体评分"""
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
        if validation_result['topology_integrity']['has_topology_fields']:
            topology_score = validation_result['topology_integrity']['completeness_rate'] * 100
        else:
            topology_score = 50  # 部分分数
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
        else:
            return "需要改进 (Needs Improvement)"