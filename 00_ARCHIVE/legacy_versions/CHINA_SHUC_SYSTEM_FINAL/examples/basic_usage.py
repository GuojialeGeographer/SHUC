#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础使用示例 - Basic Usage Example
=================================

演示中国SHUC系统的基础使用方法：
- 加载和处理流域数据
- 查看处理结果
- 导出验证报告

运行方式:
    python examples/basic_usage.py
"""

import sys
import os
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shuc_system import ChinaSHUCSystem

def basic_example():
    """基础使用示例"""
    print("🚀 中国SHUC系统 - 基础使用示例")
    print("=" * 50)
    
    try:
        # 1. 创建SHUC系统实例
        print("📋 步骤1: 初始化SHUC系统")
        shuc = ChinaSHUCSystem()
        
        # 2. 设置数据路径
        project_root = Path(__file__).parent.parent
        input_data = project_root / "data" / "input" / "demo_watersheds.shp"
        
        if not input_data.exists():
            print(f"❌ 输入数据文件不存在: {input_data}")
            print("请确保示例数据文件存在")
            return False
        
        print(f"📁 输入数据: {input_data.name}")
        
        # 3. 处理流域数据
        print("\n🔄 步骤2: 处理流域数据")
        result = shuc.process_watersheds(str(input_data))
        
        # 4. 显示处理结果
        print("\n📊 步骤3: 处理结果摘要")
        result.print_summary()
        
        # 5. 详细结果分析
        print("\n📈 步骤4: 详细结果分析")
        print(f"动态阈值: {result.validation_result['area_compliance']['dynamic_threshold_km2']} km²")
        print(f"层次分布: {result.validation_result['hierarchy_analysis']['level_range']}")
        print(f"质量等级: {result.validation_result['quality_grade']}")
        
        # 6. 输出文件信息
        print("\n📁 步骤5: 输出文件")
        for file_type, file_path in result.output_files.items():
            file_size = Path(file_path).stat().st_size / 1024  # KB
            print(f"  • {file_type}: {Path(file_path).name} ({file_size:.1f} KB)")
        
        print("\n🎉 基础示例运行完成！")
        return True
        
    except Exception as e:
        print(f"❌ 运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_validation_details(result):
    """显示验证详情"""
    print("\n🔍 详细验证结果:")
    
    validation = result.validation_result
    
    # 面积合规性
    area_comp = validation['area_compliance']
    print(f"📏 面积合规性:")
    print(f"  - 合规率: {area_comp['compliance_rate']:.1%}")
    print(f"  - 动态阈值: {area_comp['dynamic_threshold_km2']} km²")
    print(f"  - 合规流域: {area_comp['compliant_watersheds']}/{area_comp['total_watersheds']}")
    
    # 编码质量
    if validation['coding_quality']['has_codes']:
        coding = validation['coding_quality']
        print(f"🏷️  编码质量:")
        print(f"  - 唯一性: {coding['uniqueness_rate']:.1%}")
        print(f"  - 编码总数: {coding['total_codes']}")
        print(f"  - 重复编码: {coding['duplicate_codes']}")
    
    # 层次分析
    hierarchy = validation['hierarchy_analysis']
    if hierarchy['has_hierarchy']:
        print(f"🗂️  层次分析:")
        print(f"  - 层次范围: {hierarchy['level_range']}")
        for level, info in hierarchy['level_distribution'].items():
            print(f"  - {level}: {info['count']}个 ({info['percentage']}%)")

if __name__ == "__main__":
    success = basic_example()
    sys.exit(0 if success else 1)