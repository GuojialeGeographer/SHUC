#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块 - Utility Functions
==============================

提供SHUC系统的通用工具函数：
- 日志设置
- 配置管理
- 文件操作
- 数据验证

Version: 3.1.0
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
import geopandas as gpd
import pandas as pd

def setup_logging(log_file_path=None, log_level=logging.INFO):
    """
    设置日志系统
    
    Args:
        log_file_path (str): 日志文件路径
        log_level: 日志级别
        
    Returns:
        logging.Logger: 配置好的日志器
    """
    logger = logging.getLogger('china_shuc')
    logger.setLevel(log_level)
    
    # 清除已有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定了文件路径）
    if log_file_path:
        ensure_directories([Path(log_file_path).parent])
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def load_config(config_path, default_config=None):
    """
    加载配置文件
    
    Args:
        config_path (str): 配置文件路径
        default_config (dict): 默认配置
        
    Returns:
        dict: 配置字典
    """
    if default_config is None:
        default_config = get_default_config()
    
    try:
        config_path = Path(config_path)
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 合并默认配置
            merged_config = deep_merge_dict(default_config, config)
            return merged_config
        else:
            # 配置文件不存在，创建默认配置文件
            ensure_directories([config_path.parent])
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 已创建默认配置文件: {config_path}")
            return default_config
            
    except Exception as e:
        print(f"⚠️  配置文件加载失败，使用默认配置: {e}")
        return default_config

def get_default_config():
    """获取默认配置"""
    return {
        "processing": {
            "target_compliance_rate": 0.90,
            "merge_strategy": "aggressive",
            "max_iterations": 50,
            "enable_early_stopping": True
        },
        "hierarchy": {
            "level_4_min_area": 1000,
            "level_5_min_area": 200,
            "level_6_min_area": 50
        },
        "validation": {
            "area_compliance_threshold": 0.80,
            "coding_uniqueness_threshold": 1.00,
            "topology_completeness_threshold": 0.95,
            "quality_weights": {
                "area_compliance": 0.40,
                "coding_quality": 0.30,
                "topology_integrity": 0.20,
                "geometry_validity": 0.10
            }
        }
    }

def deep_merge_dict(base_dict, update_dict):
    """
    深度合并字典
    
    Args:
        base_dict (dict): 基础字典
        update_dict (dict): 更新字典
        
    Returns:
        dict: 合并后的字典
    """
    result = base_dict.copy()
    
    for key, value in update_dict.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result

def ensure_directories(dir_paths):
    """
    确保目录存在
    
    Args:
        dir_paths (list): 目录路径列表
    """
    for dir_path in dir_paths:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

def validate_shapefile(shapefile_path):
    """
    验证shapefile文件
    
    Args:
        shapefile_path (str): shapefile路径
        
    Returns:
        dict: 验证结果
    """
    result = {
        'valid': False,
        'exists': False,
        'readable': False,
        'record_count': 0,
        'has_geometry': False,
        'crs': None,
        'bounds': None,
        'columns': [],
        'errors': []
    }
    
    try:
        shapefile_path = Path(shapefile_path)
        
        # 检查文件存在
        if not shapefile_path.exists():
            result['errors'].append(f"文件不存在: {shapefile_path}")
            return result
        
        result['exists'] = True
        
        # 尝试读取文件
        gdf = gpd.read_file(shapefile_path)
        result['readable'] = True
        
        # 基本信息
        result['record_count'] = len(gdf)
        result['columns'] = list(gdf.columns)
        result['has_geometry'] = 'geometry' in gdf.columns
        
        if result['has_geometry']:
            result['crs'] = str(gdf.crs) if gdf.crs else 'Unknown'
            try:
                result['bounds'] = list(gdf.total_bounds)
            except:
                result['bounds'] = None
        
        # 检查数据质量
        if result['record_count'] == 0:
            result['errors'].append("数据为空")
        
        if not result['has_geometry']:
            result['errors'].append("缺少几何字段")
        
        # 如果没有严重错误，标记为有效
        if not result['errors']:
            result['valid'] = True
        
    except Exception as e:
        result['errors'].append(f"文件读取错误: {e}")
    
    return result

def format_file_size(size_bytes):
    """
    格式化文件大小
    
    Args:
        size_bytes (int): 字节数
        
    Returns:
        str: 格式化的文件大小
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def calculate_processing_time(start_time, end_time=None):
    """
    计算处理时间
    
    Args:
        start_time (datetime): 开始时间
        end_time (datetime): 结束时间，默认为当前时间
        
    Returns:
        dict: 处理时间信息
    """
    if end_time is None:
        end_time = datetime.now()
    
    duration = end_time - start_time
    total_seconds = duration.total_seconds()
    
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    
    return {
        'total_seconds': total_seconds,
        'hours': hours,
        'minutes': minutes,
        'seconds': seconds,
        'formatted': f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    }

def export_results_summary(result, output_file):
    """
    导出结果摘要
    
    Args:
        result: 处理结果对象
        output_file (str): 输出文件路径
    """
    summary = {
        'processing_summary': {
            'original_watershed_count': result.merge_stats['original_count'],
            'final_watershed_count': result.watershed_count,
            'compression_rate': f"{result.compression_rate:.1%}",
            'area_compliance_rate': f"{result.compliance_rate:.1%}",
            'overall_quality_score': f"{result.overall_score:.1f}/100",
            'processing_time_seconds': result.processing_time
        },
        'output_files': result.output_files,
        'system_configuration': result.system_config,
        'validation_details': result.validation_result
    }
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"✅ 结果摘要已导出到: {output_file}")
    except Exception as e:
        print(f"❌ 导出结果摘要失败: {e}")

def print_system_info():
    """打印系统信息"""
    print("🔧 系统环境信息:")
    
    # Python版本
    import sys
    print(f"  • Python版本: {sys.version.split()[0]}")
    
    # 关键依赖包版本
    packages = ['geopandas', 'pandas', 'numpy', 'shapely', 'networkx']
    for package in packages:
        try:
            module = __import__(package)
            version = getattr(module, '__version__', 'Unknown')
            print(f"  • {package}: {version}")
        except ImportError:
            print(f"  • {package}: 未安装")
    
    print()

def validate_input_args():
    """验证命令行参数"""
    import sys
    
    # 检查基本运行条件
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        return False
    
    # 检查关键依赖
    required_packages = ['geopandas', 'pandas', 'networkx', 'shapely']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少必需的依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

if __name__ == "__main__":
    # 工具函数测试
    print("🧪 测试工具函数...")
    
    # 测试配置加载
    config = get_default_config()
    print(f"✅ 默认配置加载成功: {len(config)} 个配置组")
    
    # 测试日志设置
    logger = setup_logging()
    logger.info("日志系统测试")
    
    print("🎉 工具函数测试完成！")