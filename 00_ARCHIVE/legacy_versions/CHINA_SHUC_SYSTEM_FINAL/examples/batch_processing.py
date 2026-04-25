#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批处理示例 - Batch Processing Example
====================================

演示如何批量处理多个流域数据文件：
- 批量处理多个数据集
- 不同配置策略对比
- 结果汇总和分析
- 性能基准测试

运行方式:
    python examples/batch_processing.py
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shuc_system import ChinaSHUCSystem
from utils import calculate_processing_time

class BatchProcessor:
    """
    批处理器类
    
    支持多种批处理场景：
    - 多数据集处理
    - 多配置对比
    - 性能基准测试
    """
    
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else Path("output") / "batch_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.batch_results = []
        self.start_time = datetime.now()
    
    def process_multiple_configurations(self, input_data, configurations):
        """
        使用多种配置处理相同数据
        
        Args:
            input_data (str): 输入数据路径
            configurations (list): 配置列表
        """
        print("🔄 批量配置处理开始...")
        
        for i, config_info in enumerate(configurations, 1):
            print(f"\n📋 处理配置 {i}/{len(configurations)}: {config_info['name']}")
            
            try:
                # 创建临时配置文件
                temp_config = self._create_temp_config(config_info['config'])
                
                # 创建SHUC系统实例
                shuc = ChinaSHUCSystem(
                    config_path=temp_config,
                    output_dir=self.output_dir / f"config_{i}"
                )
                
                # 记录开始时间
                config_start = time.time()
                
                # 处理数据
                result = shuc.process_watersheds(
                    input_data, 
                    output_name=f"{config_info['name']}_watersheds"
                )
                
                # 记录结果
                processing_time = time.time() - config_start
                self.batch_results.append({
                    'config_name': config_info['name'],
                    'config_number': i,
                    'watershed_count': result.watershed_count,
                    'compliance_rate': result.compliance_rate,
                    'compression_rate': result.compression_rate,
                    'overall_score': result.overall_score,
                    'processing_time': processing_time,
                    'output_files': result.output_files
                })
                
                print(f"✅ 配置 {i} 处理完成: {result.compliance_rate:.1%} 合规率")
                
            except Exception as e:
                print(f"❌ 配置 {i} 处理失败: {e}")
                self.batch_results.append({
                    'config_name': config_info['name'],
                    'config_number': i,
                    'error': str(e),
                    'success': False
                })
        
        return self.batch_results
    
    def _create_temp_config(self, config_dict):
        """创建临时配置文件"""
        temp_config_file = self.output_dir / f"temp_config_{datetime.now().strftime('%H%M%S')}.json"
        
        with open(temp_config_file, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        return temp_config_file
    
    def generate_comparison_report(self):
        """生成对比报告"""
        if not self.batch_results:
            print("❌ 没有批处理结果可供分析")
            return
        
        print("\n📊 批处理结果对比分析")
        print("=" * 80)
        
        # 成功处理的结果
        successful_results = [r for r in self.batch_results if r.get('success', True)]
        
        if not successful_results:
            print("❌ 没有成功的处理结果")
            return
        
        # 创建结果DataFrame用于分析
        df = pd.DataFrame(successful_results)
        
        # 基本统计
        print("📈 基本统计信息:")
        print(f"  • 成功处理配置: {len(successful_results)}/{len(self.batch_results)}")
        print(f"  • 平均合规率: {df['compliance_rate'].mean():.1%}")
        print(f"  • 平均压缩率: {df['compression_rate'].mean():.1%}")
        print(f"  • 平均处理时间: {df['processing_time'].mean():.1f} 秒")
        
        # 详细对比表
        print("\n📋 详细对比表:")
        print("配置名称".ljust(20) + "合规率".ljust(10) + "流域数".ljust(8) + "压缩率".ljust(10) + "评分".ljust(8) + "耗时(s)")
        print("-" * 70)
        
        for result in successful_results:
            print(
                f"{result['config_name'][:18].ljust(20)}"
                f"{result['compliance_rate']:.1%}".ljust(10)
                f"{result['watershed_count']}".ljust(8)
                f"{result['compression_rate']:.1%}".ljust(10)
                f"{result['overall_score']:.1f}".ljust(8)
                f"{result['processing_time']:.1f}"
            )
        
        # 最佳配置推荐
        self._recommend_best_configuration(df)
        
        # 保存报告
        self._save_comparison_report(df)
    
    def _recommend_best_configuration(self, df):
        """推荐最佳配置"""
        print("\n🎯 配置推荐:")
        
        # 最高合规率
        best_compliance_idx = df['compliance_rate'].idxmax()
        best_compliance = df.loc[best_compliance_idx]
        print(f"  🥇 最高合规率: {best_compliance['config_name']} ({best_compliance['compliance_rate']:.1%})")
        
        # 最快处理速度
        fastest_idx = df['processing_time'].idxmin()
        fastest = df.loc[fastest_idx]
        print(f"  ⚡ 最快处理: {fastest['config_name']} ({fastest['processing_time']:.1f}秒)")
        
        # 最高评分
        best_score_idx = df['overall_score'].idxmax()
        best_score = df.loc[best_score_idx]
        print(f"  🏆 最高评分: {best_score['config_name']} ({best_score['overall_score']:.1f}分)")
        
        # 综合推荐 (合规率权重0.4，评分权重0.4，速度权重0.2，速度取倒数)
        df['composite_score'] = (
            df['compliance_rate'] * 0.4 + 
            df['overall_score'] / 100 * 0.4 + 
            (1 / df['processing_time']) * 20 * 0.2  # 速度标准化
        )
        
        best_overall_idx = df['composite_score'].idxmax()
        best_overall = df.loc[best_overall_idx]
        print(f"  ⭐ 综合推荐: {best_overall['config_name']} (综合得分: {best_overall['composite_score']:.3f})")
    
    def _save_comparison_report(self, df):
        """保存对比报告"""
        try:
            # 保存CSV格式
            csv_file = self.output_dir / "batch_comparison_report.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8')
            
            # 保存JSON格式
            json_file = self.output_dir / "batch_comparison_report.json"
            report_data = {
                'batch_summary': {
                    'total_configurations': len(self.batch_results),
                    'successful_configurations': len(df),
                    'batch_start_time': self.start_time.isoformat(),
                    'batch_end_time': datetime.now().isoformat()
                },
                'results': df.to_dict('records'),
                'statistics': {
                    'avg_compliance_rate': df['compliance_rate'].mean(),
                    'avg_compression_rate': df['compression_rate'].mean(),
                    'avg_overall_score': df['overall_score'].mean(),
                    'avg_processing_time': df['processing_time'].mean()
                }
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 对比报告已保存:")
            print(f"  • CSV格式: {csv_file}")
            print(f"  • JSON格式: {json_file}")
            
        except Exception as e:
            print(f"❌ 保存对比报告失败: {e}")

def main():
    """主函数 - 批处理演示"""
    print("🚀 中国SHUC系统 - 批处理演示")
    print("=" * 60)
    
    # 检查输入数据
    project_root = Path(__file__).parent.parent
    input_data = project_root / "data" / "input" / "demo_watersheds.shp"
    
    if not input_data.exists():
        print(f"❌ 输入数据文件不存在: {input_data}")
        return False
    
    # 定义多种配置策略
    configurations = [
        {
            "name": "快速处理",
            "config": {
                "processing": {
                    "target_compliance_rate": 0.70,
                    "merge_strategy": "conservative",
                    "max_iterations": 20
                },
                "hierarchy": {
                    "level_4_min_area": 1500,
                    "level_5_min_area": 300,
                    "level_6_min_area": 80
                }
            }
        },
        {
            "name": "标准处理",
            "config": {
                "processing": {
                    "target_compliance_rate": 0.85,
                    "merge_strategy": "balanced",
                    "max_iterations": 35
                },
                "hierarchy": {
                    "level_4_min_area": 1000,
                    "level_5_min_area": 200,
                    "level_6_min_area": 50
                }
            }
        },
        {
            "name": "高质量处理",
            "config": {
                "processing": {
                    "target_compliance_rate": 0.90,
                    "merge_strategy": "aggressive",
                    "max_iterations": 50
                },
                "hierarchy": {
                    "level_4_min_area": 800,
                    "level_5_min_area": 150,
                    "level_6_min_area": 40
                }
            }
        },
        {
            "name": "极致质量处理",
            "config": {
                "processing": {
                    "target_compliance_rate": 0.95,
                    "merge_strategy": "aggressive",
                    "max_iterations": 80
                },
                "hierarchy": {
                    "level_4_min_area": 600,
                    "level_5_min_area": 100,
                    "level_6_min_area": 30
                }
            }
        }
    ]
    
    # 创建批处理器
    batch_processor = BatchProcessor()
    
    try:
        # 执行批处理
        results = batch_processor.process_multiple_configurations(input_data, configurations)
        
        # 生成对比报告
        batch_processor.generate_comparison_report()
        
        print("\n🎉 批处理演示完成！")
        print(f"📁 所有结果保存在: {batch_processor.output_dir}")
        
        return True
        
    except Exception as e:
        print(f"❌ 批处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)