#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国SHUC系统 - 一键运行脚本
============================

快速运行完整的SHUC流域分级编码系统

Usage:
    python run_shuc_system.py

Author: Claude Code Assistant
Date: 2025-08-30
"""

import os
import sys
from shuc_system_final import FinalSHUCSystem

def setup_environment():
    """设置运行环境"""
    print("🔧 环境检查...")
    
    required_packages = ['pandas', 'geopandas', 'networkx', 'shapely']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"  ✗ {package} - 缺失")
    
    if missing_packages:
        print(f"\n❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请安装: pip install pandas geopandas networkx shapely")
        return False
    
    print("✅ 环境检查通过\n")
    return True

def find_input_data():
    """查找输入数据文件"""
    print("📁 查找输入数据...")
    
    # 可能的数据路径
    possible_paths = [
        "data/流域.shp",
        "../之前参考/demo数据/流域.shp", 
        "之前参考/demo数据/流域.shp",
        "./之前参考/demo数据/流域.shp"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"  ✓ 找到数据文件: {path}")
            return path
    
    print("  ❌ 未找到流域.shp数据文件")
    print("  请确保以下任一路径存在数据文件:")
    for path in possible_paths:
        print(f"    - {path}")
    
    return None

def copy_data_to_local():
    """复制数据到本地目录"""
    print("📋 准备数据目录...")
    
    # 创建data目录
    os.makedirs("data", exist_ok=True)
    
    # 查找源数据
    source_file = find_input_data()
    if not source_file or source_file.startswith("data/"):
        return source_file
    
    # 复制相关文件到data目录
    import shutil
    base_name = os.path.splitext(source_file)[0]
    extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg']
    
    copied_files = 0
    for ext in extensions:
        src = base_name + ext
        dst = f"data/流域{ext}"
        
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
                copied_files += 1
                print(f"  ✓ 复制: 流域{ext}")
            except Exception as e:
                print(f"  ⚠️ 复制失败: {src} - {e}")
    
    if copied_files >= 4:  # 至少需要 .shp, .shx, .dbf, .prj
        print(f"  ✅ 数据准备完成: {copied_files} 个文件")
        return "data/流域.shp"
    else:
        print(f"  ⚠️ 数据准备不完整: 仅复制 {copied_files} 个文件")
        return source_file

def display_welcome():
    """显示欢迎信息"""
    print("\n" + "="*60)
    print("🎯 中国SHUC流域分级编码系统")
    print("   China SHUC Watershed Hierarchical Coding System")
    print("="*60)
    print("📚 基于: 美国HUC系统标准")
    print("🎯 目标: 6级完整流域层次结构")  
    print("⚡ 功能: 智能合并 + 分级编码 + 质量验证")
    print("-"*60)

def display_results_summary(validation):
    """显示结果摘要"""
    print("\n" + "="*60)
    print("📊 处理结果摘要")
    print("="*60)
    
    print(f"📈 数据处理:")
    print(f"  原始流域: {validation['total_original']} 个")
    print(f"  最终流域: {validation['total_final']} 个")
    print(f"  压缩率: {validation['compression_rate']}%")
    print(f"  问题修复: {validation['issues_fixed']} 个")
    
    print(f"\n🏗️ 层次结构:")
    for level_key, data in validation['hierarchy_distribution'].items():
        level = int(level_key.split('_')[1])
        level_names = {4: "中流域", 5: "小流域", 6: "基本单元"}
        name = level_names.get(level, f"{level}级")
        print(f"  {level}级 {name}: {data['count']}个 ({data['min_area']:.1f}-{data['max_area']:.1f}km²)")
    
    print(f"\n✅ 质量评估:")
    compliance = validation['area_compliance']
    print(f"  面积合规率: {compliance['compliance_rate']}% ({compliance['compliant_count']}/{compliance['total_count']})")
    
    code_val = validation['code_validation']
    print(f"  编码唯一性: {'✓通过' if code_val['uniqueness'] else '✗失败'} ({code_val['unique_codes']}/{code_val['total_codes']})")
    
    overall = validation['overall_validation']
    print(f"  系统评分: {overall['score']}/100")
    print(f"  整体验证: {'🎉通过' if overall['passed'] else '❌未通过'}")

def display_output_guide():
    """显示输出文件指南"""
    print(f"\n📂 输出文件说明:")
    print(f"-"*40)
    
    output_files = {
        "final_shuc_watersheds.shp": "🗺️ 最终流域数据 (可用GIS软件打开)",
        "system_validation.json": "📋 验证报告 (详细质量指标)", 
        "technical_report.txt": "📄 技术报告 (可读性强的总结)",
        "process_log.txt": "📝 处理日志 (详细处理过程)"
    }
    
    for filename, description in output_files.items():
        filepath = os.path.join("output", filename)
        exists = "✓" if os.path.exists(filepath) else "✗"
        print(f"  {exists} {filename:<25} - {description}")
    
    print(f"\n💡 建议:")
    print(f"  1. 用QGIS/ArcGIS打开 final_shuc_watersheds.shp 查看地图")
    print(f"  2. 查看 technical_report.txt 了解详细结果")
    print(f"  3. 检查 system_validation.json 验证数据质量")

def main():
    """主函数"""
    # 显示欢迎信息
    display_welcome()
    
    # 环境检查
    if not setup_environment():
        return
    
    # 数据准备
    input_file = copy_data_to_local()
    if not input_file:
        print("❌ 无法找到输入数据文件，程序退出")
        return
    
    print("🚀 启动SHUC系统...")
    print("-"*60)
    
    try:
        # 创建并运行SHUC系统
        shuc_system = FinalSHUCSystem(output_dir="output")
        success, final_data, validation = shuc_system.run_complete_system(input_file)
        
        if success:
            # 显示结果摘要
            display_results_summary(validation)
            
            # 显示输出指南
            display_output_guide()
            
            print(f"\n🎉 SHUC系统运行成功!")
            print(f"📍 结果位置: {os.path.abspath('output')}")
            
        else:
            print("❌ SHUC系统运行失败，请检查日志")
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()