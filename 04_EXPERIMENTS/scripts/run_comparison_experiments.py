#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化对比实验框架 - Comparison Experiment Runner
====================================================

支持 Exp 1-4 核心实验的可配置化运行：
- Exp 1: 阈值策略对比（动态 vs 静态 60/80/100/120/150）
- Exp 2: 合并策略对比（拓扑优先 vs 贪婪 vs 随机）
- Exp 3: 拓扑保持验证
- Exp 4: 敏感性分析（分位数参数 / 迭代次数 / 早停阈值）

所有实验参数通过配置文件控制，输出标准化的 JSON + CSV 结果文件。

Usage:
    python run_comparison_experiments.py --input data.shp --experiments 1,2,3,4
    python run_comparison_experiments.py --input data.shp --experiments 1 --thresholds 60,80,100

Version: 4.0.0
"""

import os
import sys
import json
import copy
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from itertools import product
from typing import Dict, List, Any, Optional

import pandas as pd
import geopandas as gpd
import numpy as np

# 添加核心系统路径
CORE_SRC = Path(__file__).resolve().parent.parent.parent / "01_CORE_SYSTEM" / "src"
sys.path.insert(0, str(CORE_SRC))

from watershed_processor import WatershedProcessor, compute_area_km2, compute_areas_batch
from hierarchy_encoder import HierarchyEncoder
from quality_validator import QualityValidator
from utils import setup_logging, load_config

logger = logging.getLogger('china_shuc')


class ComparisonExperimentRunner:
    """
    对比实验运行器

    管理 Exp 1-4 的实验执行、参数配置和结果收集。
    """

    def __init__(self, config_path=None, output_dir=None):
        """
        初始化实验运行器

        Args:
            config_path: 配置文件路径
            output_dir: 实验结果输出目录
        """
        self.config_path = config_path or (
            CORE_SRC.parent / "config" / "shuc_config.json"
        )
        self.config = load_config(self.config_path)

        # 输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_dir) if output_dir else (
            Path(__file__).resolve().parent.parent / "results" / f"experiment_{timestamp}"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 日志
        self.logger = setup_logging(self.output_dir / "experiment_log.txt")

        # 实验结果存储
        self.results = {}

        self.logger.info(f"对比实验框架 v4.0.0 初始化完成")
        self.logger.info(f"输出目录: {self.output_dir}")

    def run_experiment_1(self, input_shapefile: str,
                         custom_thresholds: List[float] = None) -> Dict:
        """
        Exp 1: 阈值策略对比

        比较动态阈值与多种静态阈值的合并效果：
        - 动态: Q75 + (Q90-Q75)/2
        - 静态: 60, 80, 100, 120, 150 km2

        Args:
            input_shapefile: 输入 shapefile 路径
            custom_thresholds: 自定义阈值列表

        Returns:
            实验结果字典
        """
        self.logger.info("=" * 60)
        self.logger.info("Exp 1: 阈值策略对比")
        self.logger.info("=" * 60)

        thresholds = custom_thresholds or self.config.get('experiment', {}).get(
            'threshold_strategies', [60, 80, 100, 120, 150]
        )

        results = []
        base_config = self.config['processing']

        # 1. 动态阈值实验
        self.logger.info("运行动态阈值实验...")
        dynamic_config = copy.deepcopy(base_config)
        dynamic_config['threshold_min'] = 50
        dynamic_config['threshold_max'] = 500

        try:
            processor = WatershedProcessor(dynamic_config)
            merge_result = processor.merge_watersheds(input_shapefile)

            encoder_config = copy.deepcopy(self.config['hierarchy'])
            encoder = HierarchyEncoder(encoder_config)
            encoding_result = encoder.assign_hierarchy(merge_result['merged_watersheds'])

            validator_config = copy.deepcopy(self.config['validation'])
            validator = QualityValidator(validator_config)
            validation_result = validator.validate_system(encoding_result['encoded_watersheds'])

            results.append({
                'strategy': 'dynamic',
                'threshold_value': round(merge_result['dynamic_threshold'], 1),
                'original_count': merge_result['statistics']['original_count'],
                'final_count': merge_result['statistics']['final_count'],
                'compression_rate': merge_result['statistics']['compression_rate'],
                'compliance_rate': merge_result['statistics']['final_compliance_rate'],
                'overall_score': validation_result['overall_score'],
                'quality_grade': validation_result['quality_grade'],
                'iterations': merge_result['statistics']['iterations'],
            })

            self.logger.info(f"  动态阈值={merge_result['dynamic_threshold']:.1f}, "
                           f"合规率={merge_result['statistics']['final_compliance_rate']:.1%}, "
                           f"评分={validation_result['overall_score']}")
        except Exception as e:
            self.logger.error(f"动态阈值实验失败: {e}")
            results.append({'strategy': 'dynamic', 'error': str(e)})

        # 2. 静态阈值实验
        for threshold in thresholds:
            self.logger.info(f"运行静态阈值实验: {threshold} km2...")
            static_config = copy.deepcopy(base_config)
            static_config['threshold_min'] = threshold
            static_config['threshold_max'] = threshold

            try:
                processor = WatershedProcessor(static_config)
                merge_result = processor.merge_watersheds(input_shapefile)

                encoder_config = copy.deepcopy(self.config['hierarchy'])
                encoder = HierarchyEncoder(encoder_config)
                encoding_result = encoder.assign_hierarchy(merge_result['merged_watersheds'])

                validator_config = copy.deepcopy(self.config['validation'])
                validator = QualityValidator(validator_config)
                validation_result = validator.validate_system(encoding_result['encoded_watersheds'])

                results.append({
                    'strategy': f'static_{threshold}',
                    'threshold_value': threshold,
                    'original_count': merge_result['statistics']['original_count'],
                    'final_count': merge_result['statistics']['final_count'],
                    'compression_rate': merge_result['statistics']['compression_rate'],
                    'compliance_rate': merge_result['statistics']['final_compliance_rate'],
                    'overall_score': validation_result['overall_score'],
                    'quality_grade': validation_result['quality_grade'],
                    'iterations': merge_result['statistics']['iterations'],
                })

                self.logger.info(f"  阈值={threshold}, "
                               f"合规率={merge_result['statistics']['final_compliance_rate']:.1%}, "
                               f"评分={validation_result['overall_score']}")
            except Exception as e:
                self.logger.error(f"静态阈值 {threshold} 实验失败: {e}")
                results.append({'strategy': f'static_{threshold}', 'error': str(e)})

        # 保存结果
        experiment_result = {
            'experiment': 'exp1_threshold_comparison',
            'timestamp': datetime.now().isoformat(),
            'results': results
        }

        self._save_experiment_results('exp1_threshold_comparison', experiment_result, results)

        return experiment_result

    def run_experiment_2(self, input_shapefile: str) -> Dict:
        """
        Exp 2: 合并策略对比

        比较三种合并策略：
        - topology_first: 拓扑优先（下游 > 上游 > 空间邻接）
        - greedy: 贪婪策略（按面积最小优先合并到最近邻）
        - random: 随机策略（随机选择合并目标）

        Args:
            input_shapefile: 输入 shapefile 路径

        Returns:
            实验结果字典
        """
        self.logger.info("=" * 60)
        self.logger.info("Exp 2: 合并策略对比")
        self.logger.info("=" * 60)

        strategies = ['topology_first', 'greedy', 'random']
        results = []

        for strategy in strategies:
            self.logger.info(f"运行策略: {strategy}...")

            config = copy.deepcopy(self.config['processing'])
            config['merge_strategy'] = strategy

            try:
                processor = WatershedProcessor(config)
                merge_result = processor.merge_watersheds(input_shapefile)

                encoder_config = copy.deepcopy(self.config['hierarchy'])
                encoder = HierarchyEncoder(encoder_config)
                encoding_result = encoder.assign_hierarchy(merge_result['merged_watersheds'])

                validator_config = copy.deepcopy(self.config['validation'])
                validator = QualityValidator(validator_config)
                validation_result = validator.validate_system(encoding_result['encoded_watersheds'])

                # 统计合并历史
                merge_history = merge_result.get('merge_history', [])
                detailed_history = [h for h in merge_history if 'source_id' in h]
                avg_merge_area = (
                    np.mean([h.get('merged_area', 0) for h in detailed_history])
                    if detailed_history else 0
                )

                results.append({
                    'strategy': strategy,
                    'original_count': merge_result['statistics']['original_count'],
                    'final_count': merge_result['statistics']['final_count'],
                    'compression_rate': merge_result['statistics']['compression_rate'],
                    'compliance_rate': merge_result['statistics']['final_compliance_rate'],
                    'overall_score': validation_result['overall_score'],
                    'quality_grade': validation_result['quality_grade'],
                    'iterations': merge_result['statistics']['iterations'],
                    'total_merges': len(detailed_history),
                    'avg_merge_area_km2': round(avg_merge_area, 2),
                    'topology_cycles': validation_result.get(
                        'topology_integrity', {}
                    ).get('circular_references', 0),
                })

                self.logger.info(f"  {strategy}: 合并={len(detailed_history)}, "
                               f"合规率={merge_result['statistics']['final_compliance_rate']:.1%}, "
                               f"评分={validation_result['overall_score']}")
            except Exception as e:
                self.logger.error(f"策略 {strategy} 实验失败: {e}")
                results.append({'strategy': strategy, 'error': str(e)})

        experiment_result = {
            'experiment': 'exp2_merge_strategy_comparison',
            'timestamp': datetime.now().isoformat(),
            'results': results
        }

        self._save_experiment_results('exp2_merge_strategy_comparison', experiment_result, results)

        return experiment_result

    def run_experiment_3(self, input_shapefile: str) -> Dict:
        """
        Exp 3: 拓扑保持验证

        验证合并操作后拓扑完整性的保持情况：
        - 下游链完整性（所有链能否到达出口）
        - 循环引用检测
        - 上下游一致性

        Args:
            input_shapefile: 输入 shapefile 路径

        Returns:
            实验结果字典
        """
        self.logger.info("=" * 60)
        self.logger.info("Exp 3: 拓扑保持验证")
        self.logger.info("=" * 60)

        results = []
        config = copy.deepcopy(self.config['processing'])

        try:
            # 加载原始数据拓扑
            self.logger.info("分析原始数据拓扑...")
            original_gdf = gpd.read_file(input_shapefile)
            original_topology = self._analyze_raw_topology(original_gdf)

            # 执行合并
            self.logger.info("执行合并...")
            processor = WatershedProcessor(config)
            merge_result = processor.merge_watersheds(input_shapefile)

            merged_gdf = merge_result['merged_watersheds']

            # 编码和验证
            encoder_config = copy.deepcopy(self.config['hierarchy'])
            encoder = HierarchyEncoder(encoder_config)
            encoding_result = encoder.assign_hierarchy(merged_gdf)

            validator_config = copy.deepcopy(self.config['validation'])
            validator = QualityValidator(validator_config)
            validation_result = validator.validate_system(encoding_result['encoded_watersheds'])

            # 提取拓扑指标
            topo_result = validation_result.get('topology_integrity', {})

            results.append({
                'phase': 'after_merge',
                'original_count': merge_result['statistics']['original_count'],
                'final_count': merge_result['statistics']['final_count'],
                'has_topology_fields': topo_result.get('has_topology_fields', False),
                'completeness_rate': topo_result.get('completeness_rate', 0),
                'circular_references': topo_result.get('circular_references', 0),
                'has_cycles': topo_result.get('has_cycles', False),
                'valid_references': topo_result.get('valid_references', 0),
                'invalid_references': topo_result.get('invalid_references', 0),
                'orphan_watersheds': topo_result.get('orphan_watersheds', 0),
                'chain_completeness': topo_result.get('chain_completeness', {}),
                'upstream_consistency': topo_result.get('upstream_consistency', {}),
                'original_topology': original_topology,
            })

            self.logger.info(f"  合并后拓扑完整性: {topo_result.get('completeness_rate', 0):.1%}")
            self.logger.info(f"  循环引用: {topo_result.get('circular_references', 0)}")
            self.logger.info(f"  有效引用: {topo_result.get('valid_references', 0)}")

        except Exception as e:
            self.logger.error(f"拓扑验证实验失败: {e}")
            results.append({'phase': 'after_merge', 'error': str(e)})

        experiment_result = {
            'experiment': 'exp3_topology_preservation',
            'timestamp': datetime.now().isoformat(),
            'results': results
        }

        self._save_experiment_results('exp3_topology_preservation', experiment_result, results)

        return experiment_result

    def run_experiment_4(self, input_shapefile: str) -> Dict:
        """
        Exp 4: 敏感性分析

        参数扫描：
        - 分位数参数 (quantile_low, quantile_high)
        - 最大迭代次数
        - 早停阈值

        Args:
            input_shapefile: 输入 shapefile 路径

        Returns:
            实验结果字典
        """
        self.logger.info("=" * 60)
        self.logger.info("Exp 4: 敏感性分析")
        self.logger.info("=" * 60)

        sensitivity_params = self.config.get('experiment', {}).get(
            'sensitivity_parameters', {}
        )

        q_lows = sensitivity_params.get('quantile_low', [0.50, 0.75])
        q_highs = sensitivity_params.get('quantile_high', [0.85, 0.90, 0.95])
        max_iters = sensitivity_params.get('max_iterations', [20, 50, 100])
        early_stops = sensitivity_params.get('early_stop_threshold', [3, 5, 10])

        results = []

        # 1. 分位数参数扫描
        self.logger.info("4.1 分位数参数扫描...")
        for q_low, q_high in product(q_lows, q_highs):
            label = f"q{q_low:.2f}_q{q_high:.2f}"
            self.logger.info(f"  测试 {label}...")

            config = copy.deepcopy(self.config['processing'])
            config['threshold_formula'] = f'Q{int(q_low*100)}+(Q{int(q_high*100)}-Q{int(q_low*100)})/2'

            try:
                processor = WatershedProcessor(config)
                # 覆盖阈值计算
                areas = pd.Series([compute_area_km2(g) for g in
                                   gpd.read_file(input_shapefile).geometry])
                threshold = max(50, min(500,
                    areas.quantile(q_low) + (areas.quantile(q_high) - areas.quantile(q_low)) / 2))

                merge_result = processor.merge_watersheds(input_shapefile)

                results.append({
                    'parameter': 'quantile',
                    'label': label,
                    'q_low': q_low,
                    'q_high': q_high,
                    'effective_threshold': round(threshold, 1),
                    'final_count': merge_result['statistics']['final_count'],
                    'compression_rate': merge_result['statistics']['compression_rate'],
                    'compliance_rate': merge_result['statistics']['final_compliance_rate'],
                    'iterations': merge_result['statistics']['iterations'],
                })

                self.logger.info(f"    阈值={threshold:.1f}, 合规={merge_result['statistics']['final_compliance_rate']:.1%}")
            except Exception as e:
                self.logger.error(f"    失败: {e}")
                results.append({'parameter': 'quantile', 'label': label, 'error': str(e)})

        # 2. 迭代次数扫描
        self.logger.info("4.2 迭代次数扫描...")
        for max_iter in max_iters:
            label = f"maxiter_{max_iter}"
            self.logger.info(f"  测试 {label}...")

            config = copy.deepcopy(self.config['processing'])
            config['max_iterations'] = max_iter

            try:
                processor = WatershedProcessor(config)
                merge_result = processor.merge_watersheds(input_shapefile)

                results.append({
                    'parameter': 'max_iterations',
                    'label': label,
                    'max_iterations': max_iter,
                    'final_count': merge_result['statistics']['final_count'],
                    'compression_rate': merge_result['statistics']['compression_rate'],
                    'compliance_rate': merge_result['statistics']['final_compliance_rate'],
                    'iterations_used': merge_result['statistics']['iterations'],
                })

                self.logger.info(f"    使用 {merge_result['statistics']['iterations']} 次, "
                               f"合规={merge_result['statistics']['final_compliance_rate']:.1%}")
            except Exception as e:
                self.logger.error(f"    失败: {e}")
                results.append({'parameter': 'max_iterations', 'label': label, 'error': str(e)})

        experiment_result = {
            'experiment': 'exp4_sensitivity_analysis',
            'timestamp': datetime.now().isoformat(),
            'parameters_scanned': {
                'quantile_pairs': list(product(q_lows, q_highs)),
                'max_iterations': max_iters,
            },
            'results': results
        }

        self._save_experiment_results('exp4_sensitivity_analysis', experiment_result, results)

        return experiment_result

    def run_all_experiments(self, input_shapefile: str,
                           experiments: List[int] = None) -> Dict:
        """
        运行所有实验

        Args:
            input_shapefile: 输入数据路径
            experiments: 要运行的实验编号列表，默认全部

        Returns:
            所有实验结果
        """
        all_results = {}
        experiments = experiments or [1, 2, 3, 4]

        self.logger.info(f"开始运行实验: {experiments}")
        start_time = time.time()

        if 1 in experiments:
            all_results['exp1'] = self.run_experiment_1(input_shapefile)

        if 2 in experiments:
            all_results['exp2'] = self.run_experiment_2(input_shapefile)

        if 3 in experiments:
            all_results['exp3'] = self.run_experiment_3(input_shapefile)

        if 4 in experiments:
            all_results['exp4'] = self.run_experiment_4(input_shapefile)

        elapsed = time.time() - start_time
        all_results['meta'] = {
            'total_time_seconds': round(elapsed, 1),
            'experiments_run': experiments,
            'timestamp': datetime.now().isoformat(),
        }

        # 保存汇总
        self._save_summary(all_results)

        self.logger.info(f"所有实验完成，耗时 {elapsed:.1f} 秒")
        return all_results

    # ==================== 内部方法 ====================

    def _analyze_raw_topology(self, gdf: gpd.GeoDataFrame) -> Dict:
        """分析原始数据的拓扑状态"""
        result = {
            'total_features': len(gdf),
            'has_LINKNO': 'LINKNO' in gdf.columns,
            'has_DSLINKNO': any(f in gdf.columns for f in ['DSLINKNO1', 'DSLINKNO']),
            'has_NextDownID': 'NextDownID' in gdf.columns,
        }

        # 简单统计
        if 'LINKNO' in gdf.columns:
            result['unique_ids'] = int(gdf['LINKNO'].nunique())

        ds_field = None
        for f in ['DSLINKNO1', 'DSLINKNO', 'NextDownID']:
            if f in gdf.columns:
                ds_field = f
                break

        if ds_field and 'LINKNO' in gdf.columns:
            id_set = set(gdf['LINKNO'].dropna().astype(int))
            valid_refs = 0
            invalid_refs = 0
            self_refs = 0
            for _, row in gdf.iterrows():
                ds_val = row.get(ds_field)
                linkno = row['LINKNO']
                if pd.notna(ds_val) and int(ds_val) != -1 and int(ds_val) != 0:
                    if int(ds_val) == int(linkno):
                        self_refs += 1
                    elif int(ds_val) in id_set:
                        valid_refs += 1
                    else:
                        invalid_refs += 1

            result['valid_downstream_refs'] = valid_refs
            result['invalid_downstream_refs'] = invalid_refs
            result['self_references'] = self_refs

        return result

    def _save_experiment_results(self, experiment_name: str,
                                 full_result: Dict, tabular_data: List[Dict]):
        """保存实验结果（JSON + CSV）"""
        # JSON 格式
        json_path = self.output_dir / f"{experiment_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(full_result, f, indent=2, ensure_ascii=False, default=str)
        self.logger.info(f"JSON 结果已保存: {json_path.name}")

        # CSV 格式
        if tabular_data:
            df = pd.DataFrame(tabular_data)
            csv_path = self.output_dir / f"{experiment_name}.csv"
            df.to_csv(csv_path, index=False, encoding='utf-8')
            self.logger.info(f"CSV 结果已保存: {csv_path.name}")

    def _save_summary(self, all_results: Dict):
        """保存实验汇总报告"""
        summary_path = self.output_dir / "experiment_summary.json"

        # 提取关键指标
        summary = {
            'timestamp': datetime.now().isoformat(),
            'experiments_run': all_results.get('meta', {}).get('experiments_run', []),
            'total_time_seconds': all_results.get('meta', {}).get('total_time_seconds', 0),
            'key_findings': {},
        }

        # Exp 1 摘要
        if 'exp1' in all_results:
            exp1_results = all_results['exp1'].get('results', [])
            valid_results = [r for r in exp1_results if 'error' not in r]
            if valid_results:
                best = max(valid_results, key=lambda x: x.get('overall_score', 0))
                summary['key_findings']['best_threshold'] = {
                    'strategy': best.get('strategy'),
                    'score': best.get('overall_score'),
                }

        # Exp 2 摘要
        if 'exp2' in all_results:
            exp2_results = all_results['exp2'].get('results', [])
            valid_results = [r for r in exp2_results if 'error' not in r]
            if valid_results:
                best = max(valid_results, key=lambda x: x.get('overall_score', 0))
                summary['key_findings']['best_merge_strategy'] = {
                    'strategy': best.get('strategy'),
                    'score': best.get('overall_score'),
                }

        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

        self.logger.info(f"汇总报告已保存: {summary_path.name}")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='SHUC 对比实验框架 v4.0'
    )
    parser.add_argument(
        '--input', '-i', required=True,
        help='输入 shapefile 路径'
    )
    parser.add_argument(
        '--experiments', '-e', default='1,2,3,4',
        help='要运行的实验编号，逗号分隔 (默认: 1,2,3,4)'
    )
    parser.add_argument(
        '--config', '-c', default=None,
        help='配置文件路径'
    )
    parser.add_argument(
        '--output', '-o', default=None,
        help='输出目录'
    )
    parser.add_argument(
        '--thresholds', '-t', default=None,
        help='自定义阈值列表，逗号分隔 (用于 Exp 1)'
    )

    args = parser.parse_args()

    # 解析参数
    experiments = [int(x.strip()) for x in args.experiments.split(',')]
    custom_thresholds = None
    if args.thresholds:
        custom_thresholds = [float(x.strip()) for x in args.thresholds.split(',')]

    # 初始化运行器
    runner = ComparisonExperimentRunner(
        config_path=args.config,
        output_dir=args.output
    )

    # 运行实验
    if 1 in experiments and custom_thresholds:
        # 如果只运行 Exp 1 且有自定义阈值
        runner.run_experiment_1(args.input, custom_thresholds)
        experiments = [e for e in experiments if e != 1]

    if experiments:
        runner.run_all_experiments(args.input, experiments)

    print(f"\n实验完成！结果保存在: {runner.output_dir}")


if __name__ == "__main__":
    main()
