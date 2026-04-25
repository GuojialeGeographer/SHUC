#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHUC 2025 - 演示实验运行脚本
============================

本脚本演示如何运行完整的SHUC实验，并展示结果存储位置和内容。
使用演示数据进行实验，展示完整的数据处理流程。

Author: Claude Code Assistant
Date: 2025-08-29
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

def check_demo_data():
    """
    检查演示数据是否存在
    """
    print("=" * 60)
    print("检查演示数据")
    print("=" * 60)
    
    demo_data_path = "之前参考/demo数据/流域.shp"
    
    if os.path.exists(demo_data_path):
        print(f"✓ 找到演示数据: {demo_data_path}")
        
        # 检查相关文件
        base_path = demo_data_path.replace('.shp', '')
        required_files = ['.shp', '.dbf', '.shx', '.prj']
        
        missing_files = []
        for ext in required_files:
            if not os.path.exists(base_path + ext):
                missing_files.append(ext)
        
        if missing_files:
            print(f"⚠️  缺少文件: {missing_files}")
            return False
        else:
            print("✓ Shapefile文件完整")
            return True
    else:
        print(f"❌ 演示数据不存在: {demo_data_path}")
        return False

def create_demo_config():
    """
    创建演示配置文件
    """
    print("\n" + "=" * 60)
    print("创建演示配置文件")
    print("=" * 60)
    
    config = {
        "input_data": {
            "watershed_shapefile": "之前参考/demo数据/流域.shp",
            "river_shapefile": "之前参考/demo数据/水系.shp"
        },
        "processing": {
            "area_threshold": 100.0,
            "min_area_threshold": 80.0,
            "enable_merging": True,
            "enable_encoding": True,
            "enable_validation": True
        },
        "output": {
            "base_directory": "./shuc_results",
            "create_visualizations": True,
            "export_formats": ["shapefile", "geojson"]
        },
        "validation": {
            "topology_check": True,
            "code_validation": True,
            "area_validation": True,
            "geometry_validation": True
        }
    }
    
    config_file = "demo_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 演示配置文件创建完成: {config_file}")
    return config_file

def run_shuc_experiment(watershed_file, config_file):
    """
    运行SHUC实验
    """
    print("\n" + "=" * 60)
    print("运行SHUC实验")
    print("=" * 60)
    
    try:
        # 导入实验运行器
        from shuc_experiment_runner import SHUCExperimentRunner
        
        # 创建实验运行器
        runner = SHUCExperimentRunner(config_file)
        
        # 设置输出目录
        runner.setup_output_directories()
        
        print(f"实验输出目录: {runner.output_dir}")
        
        # 运行完整实验
        runner.run_complete_experiment(watershed_file)
        
        return runner.output_dir
        
    except Exception as e:
        print(f"❌ 实验运行失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def explore_results(output_dir):
    """
    探索实验结果
    """
    print("\n" + "=" * 60)
    print("探索实验结果")
    print("=" * 60)
    
    if not output_dir or not os.path.exists(output_dir):
        print("❌ 实验输出目录不存在")
        return
    
    print(f"实验结果位置: {output_dir}")
    print("\n目录结构:")
    
    # 遍历结果目录
    for root, dirs, files in os.walk(output_dir):
        level = root.replace(output_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            file_size = os.path.getsize(file_path)
            print(f"{subindent}{file} ({file_size:,} bytes)")
    
    # 显示主要结果文件
    key_files = {
        'merged_watersheds/merged_watersheds.shp': '合并后的流域数据',
        'encoded_watersheds/shuc_watersheds.shp': '带SHUC编码的流域数据',
        'validation_results/validation_report.json': '验证报告',
        'reports/experiment_summary.txt': '实验总结报告',
        'reports/experiment_report.json': '详细实验报告'
    }
    
    print(f"\n📁 主要结果文件:")
    for rel_path, description in key_files.items():
        full_path = os.path.join(output_dir, rel_path)
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
            print(f"  ✓ {description}")
            print(f"    路径: {full_path}")
            print(f"    大小: {file_size:,} bytes")
        else:
            print(f"  ❌ {description} (文件不存在)")
    
    # 读取并显示总结报告
    summary_file = os.path.join(output_dir, 'reports', 'experiment_summary.txt')
    if os.path.exists(summary_file):
        print(f"\n📄 实验总结报告:")
        print("-" * 40)
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(content)
        except Exception as e:
            print(f"读取总结报告失败: {e}")

def show_data_access_examples(output_dir):
    """
    展示如何访问和使用结果数据
    """
    print("\n" + "=" * 60)
    print("数据访问示例")
    print("=" * 60)
    
    if not output_dir:
        print("❌ 没有有效的输出目录")
        return
    
    print("🐍 Python代码示例:")
    print("-" * 30)
    
    print(f"""
# 1. 读取合并后的流域数据
import geopandas as gpd

merged_file = "{output_dir}/merged_watersheds/merged_watersheds.shp"
if os.path.exists(merged_file):
    merged_watersheds = gpd.read_file(merged_file)
    print(f"合并后流域数量: {{len(merged_watersheds)}}")

# 2. 读取SHUC编码结果
encoded_file = "{output_dir}/encoded_watersheds/shuc_watersheds.shp"
if os.path.exists(encoded_file):
    shuc_watersheds = gpd.read_file(encoded_file)
    print(f"编码流域数量: {{len(shuc_watersheds)}}")
    print("SHUC编码示例:", shuc_watersheds['SHUC_CODE'].head().tolist())

# 3. 读取验证报告
import json
report_file = "{output_dir}/validation_results/validation_report.json"
if os.path.exists(report_file):
    with open(report_file, 'r') as f:
        validation_results = json.load(f)
    print("验证状态:", validation_results.get('overall_valid', 'Unknown'))
""")
    
    print("\n💡 数据使用建议:")
    print("-" * 30)
    print("1. 使用merged_watersheds.shp作为后续分析的基础数据")
    print("2. shuc_watersheds.shp包含完整的SHUC编码信息")
    print("3. validation_report.json提供数据质量评估")
    print("4. 可视化图表帮助理解数据分布特征")
    print("5. 所有结果支持标准GIS软件（QGIS、ArcGIS等）")

def main():
    """
    主函数 - 运行完整的演示实验
    """
    print("SHUC 2025 - 演示实验运行脚本")
    print("=" * 80)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. 检查演示数据
    if not check_demo_data():
        print("❌ 无法找到演示数据，请确保'之前参考/demo数据/'目录存在")
        return
    
    # 2. 创建演示配置
    config_file = create_demo_config()
    
    # 3. 运行实验
    watershed_file = "之前参考/demo数据/流域.shp"
    output_dir = run_shuc_experiment(watershed_file, config_file)
    
    if output_dir:
        # 4. 探索结果
        explore_results(output_dir)
        
        # 5. 显示数据访问示例
        show_data_access_examples(output_dir)
        
        print("\n" + "=" * 80)
        print("✓ 演示实验完成！")
        print("=" * 80)
        
        print(f"\n📂 实验结果保存在: {output_dir}")
        print("🔍 您可以:")
        print("  1. 在GIS软件中打开.shp文件查看地图")
        print("  2. 查看reports/文件夹中的分析报告")
        print("  3. 使用Python脚本进一步分析数据")
        
    else:
        print("\n❌ 演示实验失败，请检查错误信息")

if __name__ == "__main__":
    main()