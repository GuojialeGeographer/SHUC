#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
层次编码器 - Hierarchy Encoder
=============================

负责流域层次分配和SHUC编码生成：
- 智能层次分配算法
- 4-6级编码体系
- 基于面积的级别判定

Version: 3.1.0
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class HierarchyEncoder:
    """
    层次编码器类
    
    实现流域层次分配和SHUC编码生成：
    - 基于面积的智能分级
    - 2-bit到12-bit编码体系
    - 层次配额管理
    """
    
    def __init__(self, config):
        """
        初始化层次编码器
        
        Args:
            config (dict): 层次配置参数
        """
        self.config = config
        
        # 分级标准定义
        self.level_definitions = {
            1: {"bits": 2, "min_area": 50000, "description": "大区流域"},
            2: {"bits": 4, "min_area": 10000, "description": "区域流域"},
            3: {"bits": 6, "min_area": 2000, "description": "大流域"},
            4: {"bits": 8, "min_area": 500, "description": "中流域"},
            5: {"bits": 10, "min_area": 100, "description": "小流域"},
            6: {"bits": 12, "min_area": 50, "description": "基本单元"}
        }
        
        # 从配置读取层次参数
        self.level_4_min_area = config.get('level_4_min_area', 1000)
        self.level_5_min_area = config.get('level_5_min_area', 200)
        self.level_6_min_area = config.get('level_6_min_area', 50)
        
        # 更新分级标准
        self.level_definitions[4]["min_area"] = self.level_4_min_area
        self.level_definitions[5]["min_area"] = self.level_5_min_area
        self.level_definitions[6]["min_area"] = self.level_6_min_area
        
        # 层次配额（基于数据规模）
        self.level_quotas = {
            1: 0, 2: 0, 3: 0,     # 数据规模不支持
            4: 3,                 # 大流域 3个
            5: 8,                 # 中流域 8个  
            6: float('inf')       # 基本单元 无限制
        }
    
    def assign_hierarchy(self, watershed_data):
        """
        分配流域层次等级
        
        Args:
            watershed_data (GeoDataFrame): 合并后的流域数据
            
        Returns:
            dict: 包含编码结果和统计信息
        """
        # 1. 基于面积分配初始层次
        watershed_data = self._assign_initial_levels(watershed_data)
        
        # 2. 应用配额限制和优化
        watershed_data = self._apply_quota_optimization(watershed_data)
        
        # 3. 生成SHUC编码
        watershed_data = self._generate_shuc_codes(watershed_data)
        
        # 4. 计算统计信息
        encoding_stats = self._calculate_encoding_statistics(watershed_data)
        
        return {
            'encoded_watersheds': watershed_data,
            'statistics': encoding_stats,
            'level_definitions': self.level_definitions
        }
    
    def _assign_initial_levels(self, watershed_data):
        """基于面积分配初始层次"""
        watershed_data = watershed_data.copy()
        watershed_data['shuc_level'] = 6  # 默认为最小级别
        
        # 按面积分配层次
        for level in sorted(self.level_definitions.keys(), reverse=True):
            if level <= 3:  # 跳过不支持的高级别
                continue
                
            min_area = self.level_definitions[level]['min_area']
            mask = watershed_data['area_km2'] >= min_area
            watershed_data.loc[mask, 'shuc_level'] = level
        
        return watershed_data
    
    def _apply_quota_optimization(self, watershed_data):
        """应用配额限制和优化"""
        watershed_data = watershed_data.copy()
        
        # 统计各级别流域数量
        level_counts = watershed_data['shuc_level'].value_counts().sort_index()
        
        # 应用配额限制
        for level, quota in self.level_quotas.items():
            if level not in level_counts.index or quota == float('inf'):
                continue
            
            current_count = level_counts[level]
            if current_count > quota:
                # 超出配额，降级多余的流域
                excess_count = current_count - quota
                
                # 选择面积最小的流域降级
                level_watersheds = watershed_data[watershed_data['shuc_level'] == level]
                smallest_watersheds = level_watersheds.nsmallest(excess_count, 'area_km2')
                
                # 降级到下一级
                target_level = min(level + 1, 6)
                watershed_data.loc[smallest_watersheds.index, 'shuc_level'] = target_level
        
        return watershed_data
    
    def _generate_shuc_codes(self, watershed_data):
        """生成SHUC编码"""
        watershed_data = watershed_data.copy()
        watershed_data['shuc_code'] = ''
        
        # 按级别分组生成编码
        for level in sorted(watershed_data['shuc_level'].unique()):
            level_watersheds = watershed_data[watershed_data['shuc_level'] == level]
            
            if len(level_watersheds) == 0:
                continue
            
            # 获得编码位数
            bits = self.level_definitions[level]['bits']
            max_code = (2 ** bits) - 1
            
            # 按面积排序分配编码
            level_watersheds_sorted = level_watersheds.sort_values('area_km2', ascending=False)
            
            for i, (idx, row) in enumerate(level_watersheds_sorted.iterrows()):
                if i <= max_code:
                    # 生成编码
                    code = self._format_code(i + 1, bits)
                    watershed_data.loc[idx, 'shuc_code'] = code
                else:
                    # 编码空间不足，使用默认编码
                    code = self._format_code(max_code, bits)
                    watershed_data.loc[idx, 'shuc_code'] = f"{code}_overflow_{i-max_code}"
        
        return watershed_data
    
    def _format_code(self, code_number, bits):
        """格式化编码"""
        # 将数字转换为指定位数的字符串
        max_digits = len(str((2 ** bits) - 1))
        return f"{code_number:0{max_digits}d}"
    
    def _calculate_encoding_statistics(self, watershed_data):
        """计算编码统计信息"""
        stats = {
            'total_watersheds': len(watershed_data),
            'level_distribution': {},
            'encoding_summary': {},
            'level_area_stats': {}
        }
        
        # 级别分布统计
        level_counts = watershed_data['shuc_level'].value_counts().sort_index()
        for level, count in level_counts.items():
            level_desc = self.level_definitions[level]['description']
            stats['level_distribution'][f"Level_{level}"] = {
                'count': int(count),
                'description': level_desc,
                'percentage': round(count / len(watershed_data) * 100, 1)
            }
        
        # 编码摘要
        stats['encoding_summary'] = {
            'unique_codes': watershed_data['shuc_code'].nunique(),
            'total_codes': len(watershed_data),
            'code_uniqueness_rate': watershed_data['shuc_code'].nunique() / len(watershed_data)
        }
        
        # 各级别面积统计
        for level in watershed_data['shuc_level'].unique():
            level_data = watershed_data[watershed_data['shuc_level'] == level]
            stats['level_area_stats'][f"Level_{level}"] = {
                'count': len(level_data),
                'min_area': round(level_data['area_km2'].min(), 2),
                'max_area': round(level_data['area_km2'].max(), 2),
                'mean_area': round(level_data['area_km2'].mean(), 2),
                'total_area': round(level_data['area_km2'].sum(), 2)
            }
        
        # 计算级别范围
        min_level = int(watershed_data['shuc_level'].min())
        max_level = int(watershed_data['shuc_level'].max())
        stats['level_range'] = f"Level {min_level}-{max_level}"
        
        return stats