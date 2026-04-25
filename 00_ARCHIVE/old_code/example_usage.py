#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHUC 2025 - 使用示例脚本（整合参考资料版）
=============================================

本脚本演示了如何使用SHUC 2025系统进行流域处理和编码。
整合了之前参考文件夹中的积累代码、案例数据和算法经验。

基于参考资料:
- SHUC项目.ipynb: TauDEM基础流域数据生产流程
- 子流域合并.ipynb: 流域合并算法实现
- 流域-demo-s1.ipynb: 演示数据分析案例
- demo数据/流域.shp: 实际流域数据案例

Author: Claude Code Assistant
Date: 2025-08-29
"""

import os
import sys
import pandas as pd
import geopandas as gpd
from datetime import datetime

# 导入SHUC模块
from improved_watershed_merger import WatershedMerger
from shuc_encoder import SHUCEncoder
from shuc_validator import SHUCValidator
from shuc_experiment_runner import SHUCExperimentRunner


def create_sample_data():
    """
    创建示例测试数据（模拟真实流域数据结构）
    """
    print("创建示例测试数据...")
    
    # 这里创建一个简化的示例数据结构
    # 在实际使用中，您应该使用真实的流域shapefile数据
    sample_data = {
        'ANY_LINKNO': [1, 2, 3, 4, 5, 6, 7, 8],
        'ANY_DSLINK': [2, 3, -1, 5, 6, 7, 8, -1],
        'ANY_USLINK': [-1, 1, 2, -1, 4, 5, 6, 7],
        'ANY_USLI_1': [-1, -1, -1, -1, -1, -1, -1, -1],
        'ANY_strmOr': [1, 1, 2, 1, 1, 2, 2, 3],
        'area_km2': [45.5, 65.2, 120.3, 85.1, 55.8, 95.6, 110.2, 200.5]
    }
    
    df = pd.DataFrame(sample_data)
    print("示例数据创建完成:")
    print(df)
    return df


def load_demo_data():
    """
    加载演示数据（基于参考文件夹中的实际流域数据）
    """
    print("加载演示流域数据...")
    
    demo_data_path = "之前参考/demo数据/流域.shp"
    
    if os.path.exists(demo_data_path):
        try:
            # 基于参考资料中的实际数据结构
            gdf = gpd.read_file(demo_data_path)
            print(f"✓ 成功加载演示数据: {len(gdf)} 个流域")
            print(f"数据字段: {list(gdf.columns)}")
            print(f"坐标系统: {gdf.crs}")
            return gdf
        except Exception as e:
            print(f"加载演示数据失败: {e}")
    
    # 如果演示数据不可用，创建基于参考资料的模拟数据
    print("创建基于参考案例的模拟数据...")
    
    # 基于子流域合并.ipynb中的实际案例数据结构
    sample_data = {
        'LINKNO': [3022, 3134, 3150, 3390, 5742, 6814, 7358, 3118, 7646],
        'DSLINKNO': [5742, 5742, 7646, 7358, 6814, 7358, 7646, 6814, -1],
        'USLINKNO1': [-1, -1, -1, -1, 3134, 5742, 6814, -1, 7358],
        'USLINKNO2': [-1, -1, -1, -1, 3022, 3118, 3390, -1, 3150],
        'strmOrder': [1, 1, 1, 1, 2, 2, 2, 2, 2],
        'area_km2': [27.95, 12.38, 20.21, 17.95, 25.51, 14.67, 10.33, 11.90, 6.16]
    }
    
    df = pd.DataFrame(sample_data)
    print("基于参考案例的模拟数据创建完成:")
    print(df)
    return df


def demonstrate_reference_algorithm():
    """
    演示基于参考资料的流域合并算法
    （基于子流域合并.ipynb中的核心算法）
    """
    print("\n" + "="*60)
    print("参考算法演示 - 基于参考资料的流域连接分析")
    print("="*60)
    
    # 模拟参考资料中的流域连接集合分析方法
    demo_data = [
        {'LINKNO': 3022, 'DSLINKNO': 5742, 'USLINKNO1': -1, 'USLINKNO2': -1},
        {'LINKNO': 3134, 'DSLINKNO': 5742, 'USLINKNO1': -1, 'USLINKNO2': -1},
        {'LINKNO': 5742, 'DSLINKNO': 6814, 'USLINKNO1': 3134, 'USLINKNO2': 3022},
        {'LINKNO': 6814, 'DSLINKNO': 7358, 'USLINKNO1': 5742, 'USLINKNO2': 3118},
    ]
    
    print("\n构建流域连接集合（基于参考算法）:")
    
    # 实现参考资料中的集合构建逻辑
    for watershed in demo_data:
        linkno = watershed['LINKNO']
        dslink = watershed['DSLINKNO']
        uslink1 = watershed['USLINKNO1']
        uslink2 = watershed['USLINKNO2']
        
        # 构建连接集合（参考子流域合并.ipynb的方法）
        connections = {linkno}
        if dslink != -1:
            connections.add(dslink)
        if uslink1 != -1:
            connections.add(uslink1)
        if uslink2 != -1:
            connections.add(uslink2)
        
        print(f"流域 {linkno}: 连接集合 = {connections}")
    
    print("\n✓ 参考算法演示完成")


def example_with_demo_data():
    """
    使用演示数据的完整示例
    """
    print("\n" + "="*60)
    print("使用演示数据的完整流程示例")
    print("="*60)
    
    try:
        # 加载演示数据
        demo_data = load_demo_data()
        
        if isinstance(demo_data, gpd.GeoDataFrame):
            print(f"\n✓ 演示数据加载成功，包含 {len(demo_data)} 个流域")
            print("数据预览:")
            print(demo_data.head())
            
            # 数据统计
            if 'Shape_Area' in demo_data.columns:
                area_stats = demo_data['Shape_Area'].describe()
                print(f"\n流域面积统计 (m²):")
                print(f"  平均面积: {area_stats['mean']:.0f}")
                print(f"  最小面积: {area_stats['min']:.0f}")
                print(f"  最大面积: {area_stats['max']:.0f}")
        else:
            print("\n使用模拟数据进行演示")
            
    except Exception as e:
        print(f"\n演示数据处理错误: {e}")


def example_step_by_step():
    """
    分步执行示例 - 演示每个模块的独立使用
    """
    print("\n" + "="*60)
    print("SHUC 2025 分步执行示例")
    print("="*60)
    
    # 注意：这个示例使用模拟数据，实际使用时请替换为真实的shapefile路径
    print("\n⚠️  注意：此示例使用模拟数据进行演示")
    print("实际使用时，请将 'your_watershed_data.shp' 替换为真实的shapefile路径\n")
    
    # 步骤1: 演示流域合并算法初始化
    print("步骤1: 初始化流域合并器")
    print("-" * 30)
    merger = WatershedMerger(area_threshold=100.0, min_area_threshold=80.0)
    print(f"✓ 流域合并器初始化完成")
    print(f"  - 面积阈值: {merger.area_threshold} km²")
    print(f"  - 最小面积阈值: {merger.min_area_threshold} km²")
    
    # 在实际使用中的代码示例：
    print("\n实际使用代码:")
    print("merger.load_data('your_watershed_data.shp')")
    print("stats = merger.run_merging_algorithm()")
    print("merger.save_results('merged_watersheds.shp')")
    
    # 步骤2: 演示SHUC编码器初始化
    print("\n步骤2: 初始化SHUC编码器")
    print("-" * 30)
    encoder = SHUCEncoder()
    print(f"✓ SHUC编码器初始化完成")
    print(f"  - 支持主要流域: {len(encoder.major_basins)} 个")
    print(f"  - 编码层次: 6 级")
    print(f"  - 编码长度: 12 位")
    
    # 显示主要流域编码
    print("  - 主要流域编码:")
    for code, name in list(encoder.major_basins.items())[:5]:
        print(f"    {code}: {name}")
    print("    ... (更多)")
    
    # 步骤3: 演示验证器初始化
    print("\n步骤3: 初始化验证器")
    print("-" * 30)
    validator = SHUCValidator()
    print(f"✓ 验证器初始化完成")
    print(f"  - 支持拓扑验证")
    print(f"  - 支持编码格式验证")
    print(f"  - 支持面积阈值验证")
    print(f"  - 支持几何完整性验证")


def example_configuration_setup():
    """
    配置文件设置示例
    """
    print("\n" + "="*60)
    print("SHUC 2025 配置文件示例")
    print("="*60)
    
    # 创建不同场景的配置示例
    configurations = {
        "小流域处理": {
            "processing": {
                "area_threshold": 50.0,
                "min_area_threshold": 30.0,
                "enable_merging": True
            }
        },
        "中等流域处理": {
            "processing": {
                "area_threshold": 100.0,
                "min_area_threshold": 80.0,
                "enable_merging": True
            }
        },
        "大流域处理": {
            "processing": {
                "area_threshold": 200.0,
                "min_area_threshold": 150.0,
                "enable_merging": True
            }
        }
    }
    
    for scenario, config in configurations.items():
        print(f"\n{scenario}配置:")
        print(f"  - 面积阈值: {config['processing']['area_threshold']} km²")
        print(f"  - 最小面积: {config['processing']['min_area_threshold']} km²")


def example_output_analysis():
    """
    输出结果分析示例
    """
    print("\n" + "="*60)
    print("SHUC 2025 输出结果分析示例")
    print("="*60)
    
    print("\n典型输出目录结构:")
    print("shuc_results/")
    print("├── shuc_experiment_20250829_143022/")
    print("│   ├── merged_watersheds/")
    print("│   │   ├── merged_watersheds.shp")
    print("│   │   ├── merged_watersheds.dbf")
    print("│   │   └── merged_watersheds.shx")
    print("│   ├── encoded_watersheds/")
    print("│   │   ├── shuc_watersheds.shp")
    print("│   │   └── shuc_watersheds.geojson")
    print("│   ├── validation_results/")
    print("│   │   └── validation_report.json")
    print("│   ├── visualizations/")
    print("│   │   ├── area_distribution.png")
    print("│   │   └── basin_distribution.png")
    print("│   └── reports/")
    print("│       ├── experiment_report.json")
    print("│       └── experiment_summary.txt")
    
    print("\n典型验证报告内容:")
    print("- 拓扑一致性: ✓ PASS")
    print("- SHUC编码唯一性: ✓ PASS") 
    print("- 面积合规性: ✓ 98.5% (PASS)")
    print("- 几何完整性: ✓ PASS")
    print("- 总体状态: ✓ VALID")


def example_troubleshooting():
    """
    常见问题排查示例
    """
    print("\n" + "="*60)
    print("SHUC 2025 常见问题排查")
    print("="*60)
    
    issues_solutions = {
        "数据加载失败": [
            "检查文件路径是否正确",
            "确认shapefile完整性（.shp, .dbf, .shx文件都存在）",
            "验证数据坐标系统", 
            "检查必要字段是否存在"
        ],
        "拓扑验证失败": [
            "检查上下游关系数据完整性",
            "查找循环引用问题",
            "确认流域连通性",
            "验证LINKNO字段唯一性"
        ],
        "编码重复错误": [
            "重新运行编码算法",
            "检查输入数据重复记录",
            "调整流域层次参数",
            "验证拓扑关系正确性"
        ],
        "面积验证不通过": [
            "调整area_threshold参数",
            "检查面积计算单位",
            "重新运行合并算法",
            "验证几何数据有效性"
        ]
    }
    
    for issue, solutions in issues_solutions.items():
        print(f"\n问题: {issue}")
        print("解决方案:")
        for i, solution in enumerate(solutions, 1):
            print(f"  {i}. {solution}")


def main():
    """
    主函数 - 运行所有示例（整合参考资料版）
    """
    print("SHUC 2025 使用示例演示 - 整合参考资料版")
    print("=" * 80)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📚 基于参考资料:")
    print("- TauDEM流域数据生产流程")
    print("- 流域合并算法实现")
    print("- 实际案例数据分析")
    
    try:
        # 运行参考算法演示
        demonstrate_reference_algorithm()
        
        # 运行演示数据示例
        example_with_demo_data()
        
        # 运行原有示例
        example_step_by_step()
        example_configuration_setup()
        example_output_analysis()
        example_troubleshooting()
        
        print("\n" + "="*80)
        print("✓ 示例演示完成！")
        print("="*80)
        
        print("\n下一步操作建议:")
        print("1. 使用演示数据: python example_usage.py")
        print("2. 准备您的流域shapefile数据")
        print("3. 创建配置文件: python shuc_experiment_runner.py --create-config")
        print("4. 编辑配置文件指定数据路径")
        print("5. 运行完整实验: python shuc_experiment_runner.py watersheds.shp config.json")
        
        print("\n📁 参考数据位置:")
        print("- 演示数据: 之前参考/demo数据/流域.shp")
        print("- 参考代码: 之前参考/*.ipynb")
        
    except ImportError as e:
        print(f"\n⚠️  模块导入错误: {e}")
        print("请确保所有SHUC模块文件都在当前目录中:")
        print("- improved_watershed_merger.py")
        print("- shuc_encoder.py")
        print("- shuc_validator.py")
        print("- shuc_experiment_runner.py")
        
    except Exception as e:
        print(f"\n❌ 示例运行错误: {e}")
        print("请检查代码和环境配置")


if __name__ == "__main__":
    main()