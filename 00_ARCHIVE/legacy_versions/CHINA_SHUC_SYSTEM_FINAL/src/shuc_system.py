#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国SHUC系统主程序 - China SHUC System Main Module
===============================================

这是中国流域层次分级编码系统的主入口程序，实现了:
- 90%面积合规率的智能合并算法
- 完整的4-6级层次编码体系  
- 动态阈值自适应调整
- 全面的质量验证系统

基于美国HUC标准，专门适配中国地理环境的流域分级编码解决方案。

Usage:
    python src/shuc_system.py
    
    # 或在代码中使用:
    from src.shuc_system import ChinaSHUCSystem
    shuc = ChinaSHUCSystem()
    result = shuc.process_watersheds("data/input/demo_watersheds.shp")

Author: China SHUC Development Team
Date: 2025-08-31
Version: 3.1.0 Production Ready
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 导入核心模块
from watershed_processor import WatershedProcessor
from hierarchy_encoder import HierarchyEncoder  
from quality_validator import QualityValidator
from utils import setup_logging, load_config, ensure_directories

class ChinaSHUCSystem:
    """
    中国SHUC系统主类
    
    集成流域处理、层次编码、质量验证的完整解决方案
    实现90%面积合规率，支持4-6级完整层次结构
    """
    
    def __init__(self, config_path=None, output_dir=None):
        """
        初始化SHUC系统
        
        Args:
            config_path (str): 配置文件路径，默认使用 config/shuc_config.json
            output_dir (str): 输出目录，默认为 output/
        """
        self.version = "3.1.0"
        self.start_time = datetime.now()
        
        # 设置路径
        self.project_root = Path(__file__).parent.parent
        self.config_path = config_path or self.project_root / "config" / "shuc_config.json"
        self.output_dir = Path(output_dir) if output_dir else self.project_root / "output"
        
        # 确保输出目录存在
        ensure_directories([self.output_dir])
        
        # 设置日志
        self.logger = setup_logging(self.output_dir / "processing_log.txt")
        
        # 加载配置
        self.config = load_config(self.config_path)
        
        # 初始化核心组件
        self.watershed_processor = WatershedProcessor(self.config['processing'])
        self.hierarchy_encoder = HierarchyEncoder(self.config['hierarchy'])
        self.quality_validator = QualityValidator(self.config['validation'])
        
        # 处理统计
        self.processing_stats = {
            'start_time': self.start_time.isoformat(),
            'version': self.version,
            'config_used': str(self.config_path)
        }
        
        self.logger.info(f"🚀 中国SHUC系统 v{self.version} 初始化完成")
        self.logger.info(f"📁 输出目录: {self.output_dir}")
        self.logger.info(f"⚙️  配置文件: {self.config_path}")
    
    def process_watersheds(self, input_shapefile, output_name=None):
        """
        处理流域数据的主要方法
        
        Args:
            input_shapefile (str): 输入的流域shapefile路径
            output_name (str): 输出文件名前缀，默认为'shuc_watersheds'
            
        Returns:
            ProcessingResult: 包含处理结果和统计信息的对象
        """
        self.logger.info("=" * 60)
        self.logger.info("🎯 开始SHUC流域处理")
        self.logger.info("=" * 60)
        
        output_name = output_name or "shuc_watersheds"
        
        try:
            # 步骤1: 数据预处理和验证
            self.logger.info("📊 步骤1: 数据预处理和验证")
            input_validation = self._validate_input_data(input_shapefile)
            if not input_validation['valid']:
                raise ValueError(f"输入数据验证失败: {input_validation['errors']}")
            
            # 步骤2: 流域智能合并
            self.logger.info("🔄 步骤2: 流域智能合并")
            merge_result = self.watershed_processor.merge_watersheds(input_shapefile)
            
            # 步骤3: 层次编码分配
            self.logger.info("🏷️  步骤3: 层次编码分配") 
            encoding_result = self.hierarchy_encoder.assign_hierarchy(
                merge_result['merged_watersheds']
            )
            
            # 步骤4: 质量验证
            self.logger.info("✅ 步骤4: 质量验证")
            validation_result = self.quality_validator.validate_system(
                encoding_result['encoded_watersheds']
            )
            
            # 步骤5: 保存结果
            self.logger.info("💾 步骤5: 保存处理结果")
            output_files = self._save_results(
                encoding_result['encoded_watersheds'],
                merge_result,
                validation_result,
                output_name
            )
            
            # 生成处理结果对象
            result = ProcessingResult(
                watershed_data=encoding_result['encoded_watersheds'],
                merge_stats=merge_result['statistics'],
                encoding_stats=encoding_result['statistics'],
                validation_result=validation_result,
                output_files=output_files,
                processing_time=time.time() - time.mktime(self.start_time.timetuple()),
                system_config=self.config
            )
            
            # 记录处理统计
            self._log_processing_summary(result)
            
            self.logger.info("=" * 60)
            self.logger.info("🎉 SHUC流域处理完成!")
            self.logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 处理过程中出现错误: {e}")
            raise
    
    def _validate_input_data(self, input_shapefile):
        """验证输入数据"""
        validation_result = {'valid': True, 'errors': [], 'warnings': []}
        
        # 检查文件存在性
        if not Path(input_shapefile).exists():
            validation_result['valid'] = False
            validation_result['errors'].append(f"输入文件不存在: {input_shapefile}")
            return validation_result
        
        try:
            import geopandas as gpd
            gdf = gpd.read_file(input_shapefile)
            
            # 检查数据基本要求
            if len(gdf) == 0:
                validation_result['valid'] = False
                validation_result['errors'].append("输入数据为空")
            
            # 检查必需字段 (根据实际需求调整)
            required_fields = ['LINKNO', 'DSLINKNO1', 'USLINKNO2']  # 示例字段
            missing_fields = [field for field in required_fields if field not in gdf.columns]
            if missing_fields:
                validation_result['warnings'].append(f"缺少推荐字段: {missing_fields}")
            
            self.logger.info(f"✅ 输入数据验证通过: {len(gdf)} 个流域")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"数据读取错误: {e}")
        
        return validation_result
    
    def _save_results(self, watershed_data, merge_result, validation_result, output_name):
        """保存处理结果"""
        output_files = {}
        
        try:
            # 保存主要的流域数据
            watershed_file = self.output_dir / f"{output_name}.shp"
            watershed_data.to_file(watershed_file)
            output_files['watersheds'] = str(watershed_file)
            
            # 保存验证报告
            validation_file = self.output_dir / "validation_report.json"
            with open(validation_file, 'w', encoding='utf-8') as f:
                json.dump(validation_result, f, indent=2, ensure_ascii=False)
            output_files['validation_report'] = str(validation_file)
            
            # 保存处理统计
            stats_file = self.output_dir / "processing_statistics.json"
            processing_stats = {
                **self.processing_stats,
                'merge_statistics': merge_result['statistics'],
                'validation_summary': {
                    'compliance_rate': validation_result['area_compliance']['compliance_rate'],
                    'total_watersheds': validation_result['basic_info']['total_watersheds'],
                    'hierarchy_levels': validation_result['hierarchy_analysis']['level_distribution']
                }
            }
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(processing_stats, f, indent=2, ensure_ascii=False)
            output_files['statistics'] = str(stats_file)
            
            self.logger.info(f"💾 结果已保存到: {self.output_dir}")
            for key, path in output_files.items():
                self.logger.info(f"  - {key}: {Path(path).name}")
                
        except Exception as e:
            self.logger.error(f"保存结果时发生错误: {e}")
            raise
        
        return output_files
    
    def _log_processing_summary(self, result):
        """记录处理摘要"""
        self.logger.info("\n📊 处理摘要:")
        self.logger.info(f"  • 处理前流域数量: {result.merge_stats['original_count']}")
        self.logger.info(f"  • 处理后流域数量: {result.merge_stats['final_count']}")
        self.logger.info(f"  • 数据压缩率: {result.merge_stats['compression_rate']:.1%}")
        self.logger.info(f"  • 面积合规率: {result.validation_result['area_compliance']['compliance_rate']:.1%}")
        self.logger.info(f"  • 层次结构: {result.validation_result['hierarchy_analysis']['level_range']}")
        self.logger.info(f"  • 系统评分: {result.validation_result['overall_score']:.1f}/100")
        self.logger.info(f"  • 处理耗时: {result.processing_time:.1f} 秒")


class ProcessingResult:
    """
    处理结果类
    封装了所有处理结果和统计信息
    """
    
    def __init__(self, watershed_data, merge_stats, encoding_stats, validation_result, 
                 output_files, processing_time, system_config):
        self.watershed_data = watershed_data
        self.merge_stats = merge_stats
        self.encoding_stats = encoding_stats
        self.validation_result = validation_result
        self.output_files = output_files
        self.processing_time = processing_time
        self.system_config = system_config
        
        # 便捷访问的属性
        self.watershed_count = merge_stats['final_count']
        self.compliance_rate = validation_result['area_compliance']['compliance_rate']
        self.compression_rate = merge_stats['compression_rate']
        self.overall_score = validation_result['overall_score']
    
    def print_summary(self):
        """打印结果摘要"""
        print("🎯 中国SHUC系统处理结果摘要")
        print("=" * 40)
        print(f"流域数量: {self.watershed_count} 个")
        print(f"面积合规率: {self.compliance_rate:.1%}")
        print(f"数据压缩率: {self.compression_rate:.1%}")
        print(f"系统评分: {self.overall_score:.1f}/100")
        print(f"处理耗时: {self.processing_time:.1f} 秒")
        print("=" * 40)
        print("输出文件:")
        for key, path in self.output_files.items():
            print(f"  • {key}: {Path(path).name}")


def main():
    """
    主函数 - 命令行使用入口
    """
    print("🚀 启动中国SHUC系统 v3.1.0")
    print("世界级流域分级编码解决方案")
    print("=" * 50)
    
    try:
        # 确定输入数据路径
        project_root = Path(__file__).parent.parent
        input_data = project_root / "data" / "input" / "demo_watersheds.shp"
        
        # 检查数据文件
        if not input_data.exists():
            # 尝试从之前的位置复制数据
            old_data_path = project_root.parent / "demo" / "流域.shp"
            if old_data_path.exists():
                import shutil
                input_data.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_data_path, input_data)
                print(f"✅ 已复制示例数据到: {input_data}")
            else:
                print(f"❌ 未找到输入数据文件: {input_data}")
                print(f"请确保数据文件存在或将您的数据文件放置在: {input_data}")
                return False
        
        # 创建SHUC系统并处理
        shuc = ChinaSHUCSystem()
        result = shuc.process_watersheds(str(input_data))
        
        # 打印结果摘要
        print("\n")
        result.print_summary()
        
        print(f"\n🎉 处理完成！所有结果已保存到: {shuc.output_dir}")
        return True
        
    except Exception as e:
        print(f"❌ 处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)