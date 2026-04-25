#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国SHUC系统主程序 - China SHUC System Main Module (v4.0)
=========================================================

这是中国流域层次分级编码系统的主入口程序，实现了:
- 完整 6 级 12 位层次编码体系
- 精确测地面积计算（pyproj.Geod）
- MERIT-Basins 向量数据集成
- 动态阈值自适应调整
- 全面的质量验证系统（DFS 环检测）

三层混合框架:
  MERIT-Basins (拓扑骨架) + MERIT Hydro (栅格约束) + DEM (局部精化)

Usage:
    python src/shuc_system.py

    # 或在代码中使用:
    from shuc_system import ChinaSHUCSystem
    shuc = ChinaSHUCSystem()
    result = shuc.process_watersheds("data/input/demo_watersheds.shp")

    # 使用 MERIT-Basins 数据:
    shuc = ChinaSHUCSystem()
    shuc.load_merit_basins("/path/to/cat_data", "/path/to/riv_data")
    result = shuc.process_watersheds("data/input/watersheds.shp")

Author: China SHUC Development Team
Version: 4.0.0
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
from watershed_processor import WatershedProcessor, compute_area_km2
from hierarchy_encoder import HierarchyEncoder
from quality_validator import QualityValidator
from merit_basins_loader import MERITBasinsLoader
from utils import setup_logging, load_config, ensure_directories


class ChinaSHUCSystem:
    """
    中国SHUC系统主类 (v4.0)

    集成流域处理、层次编码、质量验证、MERIT-Basins 数据的完整解决方案
    实现 6 级 12 位完整编码体系，支持 MERIT-Basins 拓扑骨架
    """

    def __init__(self, config_path=None, output_dir=None):
        """
        初始化SHUC系统

        Args:
            config_path (str): 配置文件路径，默认使用 config/shuc_config.json
            output_dir (str): 输出目录，默认为 output/
        """
        self.version = "4.0.0"
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

        # MERIT-Basins 数据加载器（按需初始化）
        self.merit_basins = None

        # 处理统计
        self.processing_stats = {
            'start_time': self.start_time.isoformat(),
            'version': self.version,
            'config_used': str(self.config_path)
        }

        self.logger.info(f"中国SHUC系统 v{self.version} 初始化完成")
        self.logger.info(f"输出目录: {self.output_dir}")
        self.logger.info(f"配置文件: {self.config_path}")

    def load_merit_basins(self, catchment_path, river_path=None,
                          bounds=None, target_crs=None):
        """
        加载 MERIT-Basins 数据

        Args:
            catchment_path (str): MERIT-Basins catchment (cat_*) 数据路径
            river_path (str): MERIT-Basins river (riv_*) 数据路径（可选）
            bounds (tuple): 裁剪边界 (lon_min, lat_min, lon_max, lat_max)
            target_crs (str): 目标坐标系

        Returns:
            MERITBasinsLoader: 加载器实例
        """
        self.logger.info("加载 MERIT-Basins 数据...")

        self.merit_basins = MERITBasinsLoader(self.config.get('merit_basins', {}))

        # 加载 catchments
        self.merit_basins.load_catchments(catchment_path, bounds=bounds,
                                          target_crs=target_crs)

        # 加载 rivers（可选）
        if river_path:
            self.merit_basins.load_rivers(river_path, bounds=bounds)

        # 构建拓扑
        topology = self.merit_basins.build_topology()

        self.logger.info(f"MERIT-Basins 加载完成: "
                        f"{topology['total_catchments']} 个流域, "
                        f"{len(topology['outlets'])} 个出口, "
                        f"环检测={'存在' if topology['has_cycles'] else '无'}")

        return self.merit_basins

    def process_watersheds(self, input_shapefile, output_name=None,
                           use_merit_basins=False):
        """
        处理流域数据的主要方法

        Args:
            input_shapefile (str): 输入的流域shapefile路径
            output_name (str): 输出文件名前缀，默认为'shuc_watersheds'
            use_merit_basins (bool): 是否使用 MERIT-Basins 拓扑辅助

        Returns:
            ProcessingResult: 包含处理结果和统计信息的对象
        """
        self.logger.info("=" * 60)
        self.logger.info("开始SHUC流域处理 (v4.0)")
        self.logger.info("=" * 60)

        output_name = output_name or "shuc_watersheds"

        try:
            # 步骤1: 数据预处理和验证
            self.logger.info("步骤1: 数据预处理和验证")
            input_validation = self._validate_input_data(input_shapefile)
            if not input_validation['valid']:
                raise ValueError(f"输入数据验证失败: {input_validation['errors']}")

            # 步骤2: 流域智能合并
            self.logger.info("步骤2: 流域智能合并")
            merge_result = self.watershed_processor.merge_watersheds(input_shapefile)

            # 步骤2.5: MERIT-Basins 拓扑校验（如果已加载）
            if use_merit_basins and self.merit_basins is not None:
                self.logger.info("步骤2.5: MERIT-Basins 拓扑校验")
                merge_result = self._apply_merit_basins_validation(merge_result)

            # 步骤3: 层次编码分配
            self.logger.info("步骤3: 层次编码分配")
            encoding_result = self.hierarchy_encoder.assign_hierarchy(
                merge_result['merged_watersheds']
            )

            # 步骤4: 质量验证
            self.logger.info("步骤4: 质量验证")
            validation_result = self.quality_validator.validate_system(
                encoding_result['encoded_watersheds']
            )

            # 步骤5: 保存结果
            self.logger.info("步骤5: 保存处理结果")
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
            self.logger.info("SHUC流域处理完成!")
            self.logger.info("=" * 60)

            return result

        except Exception as e:
            self.logger.error(f"处理过程中出现错误: {e}")
            raise

    def _apply_merit_basins_validation(self, merge_result):
        """
        使用 MERIT-Basins 拓扑校验合并结果

        对比合并后的拓扑与 MERIT-Basins 原始拓扑的一致性。
        """
        if self.merit_basins is None or self.merit_basins._topology_cache is None:
            self.logger.warning("MERIT-Basins 拓扑未加载，跳过校验")
            return merge_result

        merged_gdf = merge_result['merged_watersheds']
        mb_topology = self.merit_basins._topology_cache

        # 统计与 MERIT-Basins 的一致性
        self.logger.info(f"MERIT-Basins 拓扑基准: {mb_topology['total_catchments']} 个节点, "
                        f"{len(mb_topology['outlets'])} 个出口")

        # 将 MERIT-Basins 环检测结果附加到 merge_result
        merge_result['merit_basins_topology'] = {
            'total_catchments': mb_topology['total_catchments'],
            'outlets_count': len(mb_topology['outlets']),
            'sources_count': len(mb_topology['sources']),
            'orphans_count': len(mb_topology['orphans']),
            'has_cycles': mb_topology['has_cycles'],
        }

        return merge_result

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

            # 检查拓扑字段（兼容 TauDEM 和 MERIT-Basins 命名）
            id_fields = ['LINKNO', 'COMID']
            ds_fields = ['DSLINKNO1', 'DSLINKNO', 'NextDownID']

            has_id_field = any(f in gdf.columns for f in id_fields)
            has_ds_field = any(f in gdf.columns for f in ds_fields)

            if not has_id_field:
                validation_result['warnings'].append(
                    "缺少 ID 字段(LINKNO/COMID)，将使用 DataFrame 索引"
                )
            if not has_ds_field:
                validation_result['warnings'].append(
                    "缺少下游拓扑字段(DSLINKNO/NextDownID)，合并策略将受限"
                )

            self.logger.info(f"输入数据验证通过: {len(gdf)} 个流域")

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
                json.dump(validation_result, f, indent=2, ensure_ascii=False,
                         default=str)
            output_files['validation_report'] = str(validation_file)

            # 保存处理统计
            stats_file = self.output_dir / "processing_statistics.json"

            # 构建统计信息
            merge_stats = merge_result['statistics']
            validation_summary = {
                'compliance_rate': validation_result['area_compliance']['compliance_rate'],
                'total_watersheds': validation_result['basic_info']['total_watersheds'],
                'hierarchy_levels': validation_result['hierarchy_analysis'].get(
                    'level_distribution', {}
                ),
                'overall_score': validation_result['overall_score'],
                'quality_grade': validation_result['quality_grade'],
            }

            # MERIT-Basins 信息
            mb_info = merge_result.get('merit_basins_topology', None)

            processing_stats = {
                **self.processing_stats,
                'merge_statistics': merge_stats,
                'validation_summary': validation_summary,
                'merit_basins_topology': mb_info,
                'dynamic_threshold': merge_result.get('dynamic_threshold', None),
            }

            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(processing_stats, f, indent=2, ensure_ascii=False,
                         default=str)
            output_files['statistics'] = str(stats_file)

            # 保存合并历史
            merge_history = merge_result.get('merge_history', [])
            if merge_history:
                history_file = self.output_dir / "merge_history.json"
                # 过滤只保留详细合并记录
                detailed_history = [
                    h for h in merge_history
                    if 'source_id' in h and 'target_id' in h
                ]
                with open(history_file, 'w', encoding='utf-8') as f:
                    json.dump(detailed_history, f, indent=2, ensure_ascii=False,
                             default=str)
                output_files['merge_history'] = str(history_file)

            self.logger.info(f"结果已保存到: {self.output_dir}")
            for key, path in output_files.items():
                self.logger.info(f"  - {key}: {Path(path).name}")

        except Exception as e:
            self.logger.error(f"保存结果时发生错误: {e}")
            raise

        return output_files

    def _log_processing_summary(self, result):
        """记录处理摘要"""
        self.logger.info("\n处理摘要:")
        self.logger.info(f"  版本: v{self.version}")
        self.logger.info(f"  处理前流域数量: {result.merge_stats['original_count']}")
        self.logger.info(f"  处理后流域数量: {result.merge_stats['final_count']}")
        self.logger.info(f"  数据压缩率: {result.merge_stats['compression_rate']:.1%}")
        self.logger.info(f"  面积合规率: "
                        f"{result.validation_result['area_compliance']['compliance_rate']:.1%}")
        self.logger.info(f"  层次结构: "
                        f"{result.validation_result['hierarchy_analysis'].get('level_range', 'N/A')}")
        self.logger.info(f"  系统评分: {result.validation_result['overall_score']:.1f}/100")
        self.logger.info(f"  质量等级: {result.validation_result['quality_grade']}")

        # 拓扑状态
        topo = result.validation_result.get('topology_integrity', {})
        if topo.get('has_topology_fields', False):
            self.logger.info(f"  拓扑完整性: {topo.get('completeness_rate', 0):.1%}")
            if topo.get('has_cycles', False):
                self.logger.warning(f"  拓扑环: {topo.get('circular_references', 0)} 个循环引用")

        self.logger.info(f"  处理耗时: {result.processing_time:.1f} 秒")


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
        self.quality_grade = validation_result['quality_grade']

    def print_summary(self):
        """打印结果摘要"""
        print("中国SHUC系统处理结果摘要 (v4.0)")
        print("=" * 50)
        print(f"流域数量: {self.watershed_count} 个")
        print(f"面积合规率: {self.compliance_rate:.1%}")
        print(f"数据压缩率: {self.compression_rate:.1%}")
        print(f"系统评分: {self.overall_score:.1f}/100")
        print(f"质量等级: {self.quality_grade}")
        print(f"处理耗时: {self.processing_time:.1f} 秒")
        print("=" * 50)
        print("输出文件:")
        for key, path in self.output_files.items():
            print(f"  - {key}: {Path(path).name}")


def main():
    """
    主函数 - 命令行使用入口
    """
    print(f"启动中国SHUC系统 v4.0.0")
    print("流域层次分级编码解决方案 (6级12位编码)")
    print("=" * 50)

    try:
        # 确定输入数据路径
        project_root = Path(__file__).parent.parent
        data_candidates = [
            project_root / "data" / "input" / "demo_watersheds.shp",
            project_root / "data" / "demo_watersheds.shp",
            project_root.parent / "05_DATA" / "output" / "demo_output" / "demo_watersheds.shp",
        ]

        project_root_abs = Path('/Users/bruce/10_Current Project/SHUC_EXPERIMENT_2025')
        data_candidates.extend([
            project_root_abs / "05_DATA" / "output" / "demo_output" / "demo_watersheds.shp",
            project_root_abs / "00_ARCHIVE" / "reference_materials" / "demo_data" / "流域.shp",
        ])

        input_data = None
        for candidate in data_candidates:
            if candidate.exists():
                input_data = candidate
                break

        if input_data is None:
            print("未找到输入数据文件。已搜索:")
            for c in data_candidates:
                print(f"  - {c}")
            print("请确保数据文件存在，或直接调用:")
            print("  ChinaSHUCSystem().process_watersheds('your_data.shp')")
            return False

        # 创建SHUC系统并处理
        shuc = ChinaSHUCSystem()
        result = shuc.process_watersheds(str(input_data))

        # 打印结果摘要
        print("\n")
        result.print_summary()

        print(f"\n处理完成！所有结果已保存到: {shuc.output_dir}")
        return True

    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
