#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级功能演示 - Advanced Demo
===========================

演示中国SHUC系统的高级功能：
- 自定义配置参数
- 详细的结果分析
- 数据质量诊断
- 可视化展示

运行方式:
    python examples/advanced_demo.py
"""

import sys
import os
import json
from pathlib import Path
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shuc_system import ChinaSHUCSystem
from utils import validate_shapefile

def advanced_demo():
    """高级功能演示"""
    print("🚀 中国SHUC系统 - 高级功能演示")
    print("=" * 60)
    
    try:
        # 1. 自定义配置演示
        print("⚙️  步骤1: 自定义配置演示")
        custom_config_demo()
        
        # 2. 数据质量分析演示
        print("\n🔍 步骤2: 数据质量分析")
        data_quality_analysis_demo()
        
        # 3. 批量处理演示
        print("\n📦 步骤3: 批量处理演示")
        batch_processing_demo()
        
        # 4. 结果对比分析
        print("\n📊 步骤4: 结果对比分析")
        comparison_analysis_demo()
        
        print("\n🎉 高级功能演示完成！")
        return True
        
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def custom_config_demo():
    """自定义配置演示"""
    print("创建自定义配置...")
    
    # 创建保守配置
    conservative_config = {
        "processing": {
            "target_compliance_rate": 0.70,  # 较低的目标合规率
            "merge_strategy": "conservative", # 保守合并
            "max_iterations": 20,
            "enable_early_stopping": False
        },
        "hierarchy": {
            "level_4_min_area": 2000,  # 提高阈值
            "level_5_min_area": 500,
            "level_6_min_area": 100
        }
    }
    
    # 创建激进配置
    aggressive_config = {
        "processing": {
            "target_compliance_rate": 0.95,  # 更高的目标合规率
            "merge_strategy": "aggressive",   # 激进合并
            "max_iterations": 100,
            "enable_early_stopping": True
        },
        "hierarchy": {
            "level_4_min_area": 500,   # 降低阈值
            "level_5_min_area": 100,
            "level_6_min_area": 30
        }
    }
    
    print("✅ 自定义配置创建完成")
    print(f"  - 保守配置: 目标合规率 {conservative_config['processing']['target_compliance_rate']:.0%}")
    print(f"  - 激进配置: 目标合规率 {aggressive_config['processing']['target_compliance_rate']:.0%}")

def data_quality_analysis_demo():
    """数据质量分析演示"""
    project_root = Path(__file__).parent.parent
    input_data = project_root / "data" / "input" / "demo_watersheds.shp"
    
    if not input_data.exists():
        print("❌ 示例数据不存在，跳过质量分析")
        return
    
    print(f"分析数据文件: {input_data.name}")
    
    # 使用工具函数验证数据
    validation_result = validate_shapefile(input_data)
    
    print("📋 数据质量报告:")
    print(f"  ✅ 文件存在: {validation_result['exists']}")
    print(f"  ✅ 可读性: {validation_result['readable']}")
    print(f"  📊 记录数量: {validation_result['record_count']}")
    print(f"  🗺️  包含几何: {validation_result['has_geometry']}")
    print(f"  🌐 坐标系: {validation_result['crs']}")
    print(f"  📋 字段数量: {len(validation_result['columns'])}")
    
    if validation_result['errors']:
        print("⚠️  发现问题:")
        for error in validation_result['errors']:
            print(f"    - {error}")
    
    # 详细数据分析
    if validation_result['readable']:
        analyze_watershed_data(input_data)

def analyze_watershed_data(shapefile_path):
    """详细分析流域数据"""
    try:
        gdf = gpd.read_file(shapefile_path)
        
        print("\n📈 详细数据分析:")
        
        # 面积分析
        if 'Areakm2' in gdf.columns:
            areas = gdf['Areakm2']
            print(f"📏 面积统计:")
            print(f"  - 最小面积: {areas.min():.2f} km²")
            print(f"  - 最大面积: {areas.max():.2f} km²")
            print(f"  - 平均面积: {areas.mean():.2f} km²")
            print(f"  - 中位数面积: {areas.median():.2f} km²")
            
            # 面积分布
            small_count = len(areas[areas < 50])
            medium_count = len(areas[(areas >= 50) & (areas < 200)])
            large_count = len(areas[areas >= 200])
            
            print(f"📊 面积分布:")
            print(f"  - 小流域 (<50km²): {small_count} 个 ({small_count/len(areas)*100:.1f}%)")
            print(f"  - 中流域 (50-200km²): {medium_count} 个 ({medium_count/len(areas)*100:.1f}%)")
            print(f"  - 大流域 (>200km²): {large_count} 个 ({large_count/len(areas)*100:.1f}%)")
        
        # 拓扑分析
        if 'LINKNO' in gdf.columns and 'DSLINKNO1' in gdf.columns:
            linkno_count = gdf['LINKNO'].nunique()
            valid_downstream = gdf['DSLINKNO1'].notna().sum()
            
            print(f"🔗 拓扑关系:")
            print(f"  - 唯一流域编号: {linkno_count}")
            print(f"  - 有效下游连接: {valid_downstream}/{len(gdf)} ({valid_downstream/len(gdf)*100:.1f}%)")
        
    except Exception as e:
        print(f"数据分析出错: {e}")

def batch_processing_demo():
    """批量处理演示"""
    print("模拟批量处理场景...")
    
    # 模拟多个配置的批量处理
    configurations = [
        {"name": "默认配置", "compliance_target": 0.80},
        {"name": "高质量配置", "compliance_target": 0.90},
        {"name": "极高质量配置", "compliance_target": 0.95}
    ]
    
    print("📦 批量处理配置:")
    for config in configurations:
        print(f"  - {config['name']}: 目标合规率 {config['compliance_target']:.0%}")
    
    print("✅ 批量处理配置准备完成")
    print("💡 实际应用中，可以循环处理不同区域的流域数据")

def comparison_analysis_demo():
    """结果对比分析演示"""
    print("模拟不同策略的结果对比...")
    
    # 模拟不同策略的结果
    results_comparison = {
        "保守策略": {
            "合规率": 0.75,
            "流域数量": 35,
            "压缩率": 0.75,
            "处理时间": 8.5
        },
        "标准策略": {
            "合规率": 0.90,
            "流域数量": 20,
            "压缩率": 0.86,
            "处理时间": 12.3
        },
        "激进策略": {
            "合规率": 0.95,
            "流域数量": 15,
            "压缩率": 0.89,
            "处理时间": 18.7
        }
    }
    
    print("📊 策略对比分析:")
    print("策略名称".ljust(12) + "合规率".ljust(8) + "流域数量".ljust(8) + "压缩率".ljust(8) + "耗时(秒)")
    print("-" * 50)
    
    for strategy, metrics in results_comparison.items():
        print(f"{strategy.ljust(12)}"
              f"{metrics['合规率']:.1%}".ljust(8)
              f"{metrics['流域数量']}个".ljust(8)
              f"{metrics['压缩率']:.1%}".ljust(8)
              f"{metrics['处理时间']:.1f}s")
    
    print("\n💡 分析结论:")
    print("  - 激进策略获得最高质量，但耗时最长")
    print("  - 标准策略在质量和效率间取得平衡")
    print("  - 保守策略处理快速，但质量相对较低")

def create_simple_visualization():
    """创建简单的可视化图表"""
    try:
        # 创建示例数据的可视化
        strategies = ['保守策略', '标准策略', '激进策略']
        compliance_rates = [0.75, 0.90, 0.95]
        processing_times = [8.5, 12.3, 18.7]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # 合规率对比
        ax1.bar(strategies, compliance_rates, color=['orange', 'green', 'blue'])
        ax1.set_title('不同策略的面积合规率对比')
        ax1.set_ylabel('合规率')
        ax1.set_ylim(0, 1)
        
        # 处理时间对比
        ax2.bar(strategies, processing_times, color=['orange', 'green', 'blue'])
        ax2.set_title('不同策略的处理时间对比')
        ax2.set_ylabel('处理时间 (秒)')
        
        plt.tight_layout()
        
        # 保存图表
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        chart_file = output_dir / "strategy_comparison.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        
        print(f"📊 可视化图表已保存: {chart_file}")
        
    except ImportError:
        print("⚠️  matplotlib未安装，跳过可视化演示")
    except Exception as e:
        print(f"可视化创建出错: {e}")

if __name__ == "__main__":
    success = advanced_demo()
    
    # 尝试创建可视化
    create_simple_visualization()
    
    sys.exit(0 if success else 1)