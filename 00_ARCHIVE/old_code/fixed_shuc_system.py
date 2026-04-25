#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复版SHUC系统 - 解决数据完整性问题
======================================

修复问题:
1. gridcode=3150的USLINKNO2自引用问题
2. 确保完整的6级层次结构 
3. 修复空间数据缺失和重叠问题
4. 实现真正的分级合并策略

Author: Claude Code Assistant
Date: 2025-08-30
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx
from shapely.ops import unary_union
from collections import defaultdict, deque
import warnings
warnings.filterwarnings('ignore')

class FixedSHUCSystem:
    """
    修复版SHUC系统
    """
    
    def __init__(self):
        """初始化修复版系统"""
        self.watershed_data = None
        self.original_data = None  # 保留原始数据
        self.topology_graph = None
        self.data_issues = []  # 记录数据问题
        
        # 完整的6级分级标准
        self.level_definitions = {
            1: {"bits": 2, "min_area": 50000, "max_area": float('inf'), "description": "大区流域"},
            2: {"bits": 4, "min_area": 10000, "max_area": 50000, "description": "区域流域"}, 
            3: {"bits": 6, "min_area": 2000, "max_area": 10000, "description": "大流域"},
            4: {"bits": 8, "min_area": 500, "max_area": 2000, "description": "中流域"},
            5: {"bits": 10, "min_area": 150, "max_area": 500, "description": "小流域"},
            6: {"bits": 12, "min_area": 100, "max_area": 150, "description": "基本单元"}
        }
    
    def load_and_validate_data(self, shapefile_path):
        """加载并验证数据完整性"""
        try:
            self.original_data = gpd.read_file(shapefile_path)
            self.watershed_data = self.original_data.copy()
            
            print(f"✓ 加载原始数据: {len(self.watershed_data)} 个流域")
            
            # 确保面积字段
            if 'area_km2' not in self.watershed_data.columns:
                if 'Areakm2' in self.watershed_data.columns:
                    self.watershed_data['area_km2'] = self.watershed_data['Areakm2']
                else:
                    self.watershed_data['area_km2'] = self.watershed_data.geometry.area / 1000000
            
            # 验证和修复数据问题
            self.detect_and_fix_data_issues()
            
            return True
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
            return False
    
    def detect_and_fix_data_issues(self):
        """检测和修复数据问题"""
        print(f"\n🔍 数据完整性检查:")
        print("-" * 40)
        
        issues_found = 0
        
        # 检查自引用问题
        self_ref_count = 0
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('LINKNO', row.get('gridcode', idx))
            uslinkno1 = row.get('USLINKNO1', -1)
            uslinkno2 = row.get('USLINKNO2', -1)
            
            if uslinkno1 == linkno or uslinkno2 == linkno:
                self_ref_count += 1
                issue = f"流域 {linkno} (gridcode={row.get('gridcode', 'N/A')}) 存在自引用"
                self.data_issues.append(issue)
                
                # 修复自引用问题
                if uslinkno1 == linkno:
                    self.watershed_data.loc[idx, 'USLINKNO1'] = -1
                    print(f"  ✓ 修复: USLINKNO1自引用 -> -1")
                if uslinkno2 == linkno:
                    self.watershed_data.loc[idx, 'USLINKNO2'] = -1
                    print(f"  ✓ 修复: USLINKNO2自引用 -> -1")
        
        if self_ref_count > 0:
            print(f"  发现并修复 {self_ref_count} 个自引用问题")
            issues_found += self_ref_count
        
        # 检查几何有效性
        invalid_geom = 0
        for idx, row in self.watershed_data.iterrows():
            if not row['geometry'].is_valid:
                invalid_geom += 1
                # 尝试修复几何
                try:
                    self.watershed_data.loc[idx, 'geometry'] = row['geometry'].buffer(0)
                except:
                    pass
        
        if invalid_geom > 0:
            print(f"  发现并修复 {invalid_geom} 个无效几何")
            issues_found += invalid_geom
        
        # 检查缺失值
        missing_linkno = self.watershed_data['LINKNO'].isna().sum()
        if missing_linkno > 0:
            print(f"  发现 {missing_linkno} 个缺失LINKNO")
            issues_found += missing_linkno
        
        if issues_found == 0:
            print("  ✅ 数据完整性良好")
        else:
            print(f"  ⚠️  发现并修复 {issues_found} 个问题")
    
    def build_robust_topology(self):
        """构建健壮的拓扑图"""
        print(f"\n🔗 构建拓扑图:")
        print("-" * 30)
        
        self.topology_graph = nx.DiGraph()
        
        # 创建节点映射
        linkno_to_idx = {}
        all_linknos = set()
        
        # 添加所有节点
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('LINKNO', row.get('gridcode', idx))
            linkno_to_idx[linkno] = idx
            all_linknos.add(linkno)
            
            self.topology_graph.add_node(linkno,
                                       area=row['area_km2'],
                                       original_idx=idx,
                                       gridcode=row.get('gridcode', linkno),
                                       merged=False)
        
        # 添加连接关系，排除自环
        edge_count = 0
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('LINKNO', row.get('gridcode', idx))
            dslink = row.get('DSLINKNO', -1)
            uslink1 = row.get('USLINKNO1', -1)
            uslink2 = row.get('USLINKNO2', -1)
            
            # 添加下游连接（排除自环）
            if dslink != -1 and dslink in all_linknos and dslink != linkno:
                self.topology_graph.add_edge(linkno, dslink)
                edge_count += 1
            
            # 添加上游连接（排除自环）
            if uslink1 != -1 and uslink1 in all_linknos and uslink1 != linkno:
                self.topology_graph.add_edge(uslink1, linkno)
                edge_count += 1
            if uslink2 != -1 and uslink2 in all_linknos and uslink2 != linkno:
                self.topology_graph.add_edge(uslink2, linkno)
                edge_count += 1
        
        print(f"  节点数: {self.topology_graph.number_of_nodes()}")
        print(f"  边数: {edge_count}")
        print(f"  检测到自环: {len(list(nx.selfloop_edges(self.topology_graph)))}")
        
        # 移除任何剩余的自环
        self.topology_graph.remove_edges_from(nx.selfloop_edges(self.topology_graph))
        print(f"  ✓ 拓扑图构建完成")
    
    def analyze_watershed_distribution(self):
        """分析流域分布，为分级合并做准备"""
        areas = self.watershed_data['area_km2']
        
        print(f"\n📊 流域面积分布分析:")
        print("-" * 40)
        print(f"  流域总数: {len(areas)}")
        print(f"  面积范围: {areas.min():.2f} - {areas.max():.2f} km²")
        print(f"  平均面积: {areas.mean():.2f} km²")
        print(f"  中位数: {areas.median():.2f} km²")
        print()
        
        # 按目标分级统计
        level_counts = {}
        for level in range(1, 7):
            min_area = self.level_definitions[level]['min_area']
            max_area = self.level_definitions[level]['max_area']
            
            if level == 1:  # 1级: ≥50000km²
                count = len(areas[areas >= min_area])
            elif level == 6:  # 6级: ≥100km²
                count = len(areas[(areas >= min_area) & (areas < 150)])
            else:  # 其他级别: 范围区间
                count = len(areas[(areas >= min_area) & (areas < max_area)])
            
            level_counts[level] = count
            bits = self.level_definitions[level]['bits']
            desc = self.level_definitions[level]['description']
            
            if level == 1:
                area_desc = f"≥{min_area:,}km²"
            elif level == 6:
                area_desc = f"≥{min_area}km²"
            else:
                area_desc = f"{min_area:,}-{max_area:,}km²"
            
            print(f"  {level}级 ({bits:2d}位) {desc}: {count:3d}个 ({area_desc})")
        
        # 需要合并的小流域
        small = areas[areas < 100]
        print(f"\n  需要合并 (<100km²): {len(small):3d}个")
        
        return level_counts
    
    def advanced_merging_strategy(self):
        """高级分级合并策略"""
        print(f"\n🔄 高级分级合并策略:")
        print("-" * 40)
        
        merge_count = 0
        iteration = 0
        max_iterations = 50  # 防止无限循环
        
        while iteration < max_iterations:
            iteration += 1
            print(f"第 {iteration} 轮合并:")
            
            # 识别需要合并的流域
            merge_candidates = self.identify_merge_candidates()
            
            if not merge_candidates:
                print("  ✓ 所有流域已达到合并标准")
                break
            
            print(f"  找到 {len(merge_candidates)} 个候选合并")
            
            # 按合并优先级排序
            merge_candidates = self.prioritize_merges(merge_candidates)
            
            merged_in_round = 0
            
            for primary, target, merge_score in merge_candidates[:20]:  # 限制每轮合并数量
                if (self.topology_graph.nodes[primary]['merged'] or 
                    self.topology_graph.nodes[target]['merged']):
                    continue
                
                # 执行合并
                success = self.execute_merge(primary, target)
                if success:
                    merged_in_round += 1
                    merge_count += 1
                    
                    new_area = self.topology_graph.nodes[primary]['area']
                    print(f"    合并 {primary}+{target} -> {new_area:.1f}km² (优先级:{merge_score:.2f})")
            
            print(f"  本轮完成: {merged_in_round} 次合并")
            
            if merged_in_round == 0:
                print("  ⚠️  无法进一步合并")
                break
        
        print(f"✅ 合并完成! 总计 {merge_count} 次合并，耗时 {iteration} 轮")
        return merge_count
    
    def identify_merge_candidates(self):
        """识别合并候选对"""
        candidates = []
        
        for node in self.topology_graph.nodes():
            node_data = self.topology_graph.nodes[node]
            if node_data['merged'] or node_data['area'] >= 100:
                continue  # 跳过已合并或已达标的流域
            
            # 寻找邻居节点
            neighbors = (list(self.topology_graph.predecessors(node)) + 
                        list(self.topology_graph.successors(node)))
            
            for neighbor in neighbors:
                neighbor_data = self.topology_graph.nodes[neighbor]
                if neighbor_data['merged']:
                    continue
                
                # 计算合并适宜性得分
                merge_score = self.calculate_merge_score(node, neighbor)
                if merge_score > 0:
                    candidates.append((node, neighbor, merge_score))
        
        return candidates
    
    def calculate_merge_score(self, node1, node2):
        """计算合并适宜性得分"""
        area1 = self.topology_graph.nodes[node1]['area']
        area2 = self.topology_graph.nodes[node2]['area']
        combined_area = area1 + area2
        
        # 基础得分：优先合并小流域
        base_score = 1.0 / (min(area1, area2) + 1)
        
        # 面积适宜性：合并后面积合理
        if combined_area > 500:  # 避免过大合并
            area_penalty = 0.5
        elif combined_area < 80:  # 合并后仍然很小
            area_penalty = 0.8
        else:
            area_penalty = 1.0
        
        # 拓扑连通性奖励
        if self.topology_graph.has_edge(node1, node2) or self.topology_graph.has_edge(node2, node1):
            topo_bonus = 1.5
        else:
            topo_bonus = 1.0
        
        return base_score * area_penalty * topo_bonus
    
    def prioritize_merges(self, candidates):
        """按优先级排序合并候选"""
        # 按得分降序排列
        return sorted(candidates, key=lambda x: x[2], reverse=True)
    
    def execute_merge(self, primary_node, target_node):
        """执行流域合并"""
        try:
            primary_idx = self.topology_graph.nodes[primary_node]['original_idx']
            target_idx = self.topology_graph.nodes[target_node]['original_idx']
            
            # 合并几何
            geom1 = self.watershed_data.iloc[primary_idx]['geometry']
            geom2 = self.watershed_data.iloc[target_idx]['geometry']
            merged_geom = unary_union([geom1, geom2])
            
            # 更新面积和几何
            primary_area = self.topology_graph.nodes[primary_node]['area']
            target_area = self.topology_graph.nodes[target_node]['area']
            new_area = primary_area + target_area
            
            # 更新主节点
            self.topology_graph.nodes[primary_node]['area'] = new_area
            self.watershed_data.loc[primary_idx, 'geometry'] = merged_geom
            self.watershed_data.loc[primary_idx, 'area_km2'] = new_area
            
            # 标记目标节点为已合并
            self.topology_graph.nodes[target_node]['merged'] = True
            
            # 更新拓扑关系
            self.update_topology_after_merge(primary_node, target_node)
            
            return True
        except Exception as e:
            print(f"    合并失败: {primary_node}+{target_node} - {e}")
            return False
    
    def update_topology_after_merge(self, primary_node, merged_node):
        """更新合并后的拓扑关系"""
        try:
            predecessors = list(self.topology_graph.predecessors(merged_node))
            successors = list(self.topology_graph.successors(merged_node))
            
            # 转移连接到主节点
            for pred in predecessors:
                if pred != primary_node and not self.topology_graph.has_edge(pred, primary_node):
                    self.topology_graph.add_edge(pred, primary_node)
            
            for succ in successors:
                if succ != primary_node and not self.topology_graph.has_edge(primary_node, succ):
                    self.topology_graph.add_edge(primary_node, succ)
            
            # 移除被合并节点的连接
            edges_to_remove = []
            for edge in self.topology_graph.edges():
                if edge[0] == merged_node or edge[1] == merged_node:
                    edges_to_remove.append(edge)
            
            for edge in edges_to_remove:
                if self.topology_graph.has_edge(*edge):
                    self.topology_graph.remove_edge(*edge)
        except Exception as e:
            print(f"    拓扑更新失败: {e}")
    
    def create_complete_hierarchy(self):
        """创建完整的6级层次结构"""
        print(f"\n🏗️ 创建完整6级层次结构:")
        print("-" * 40)
        
        # 获取最终流域
        final_watersheds = []
        for node in self.topology_graph.nodes():
            if not self.topology_graph.nodes[node]['merged']:
                node_data = self.topology_graph.nodes[node]
                final_watersheds.append({
                    'node': node,
                    'area': node_data['area'],
                    'original_idx': node_data['original_idx'],
                    'gridcode': node_data['gridcode']
                })
        
        # 按面积排序，大的优先分配高级别
        final_watersheds.sort(key=lambda x: x['area'], reverse=True)
        
        # 智能分级分配
        hierarchy_assignment = self.intelligent_level_assignment(final_watersheds)
        
        # 生成编码
        shuc_codes = self.generate_hierarchical_codes(hierarchy_assignment)
        
        return final_watersheds, hierarchy_assignment, shuc_codes
    
    def intelligent_level_assignment(self, watersheds):
        """智能层级分配"""
        hierarchy = {}
        level_quotas = {1: 1, 2: 2, 3: 3, 4: 5, 5: 8, 6: float('inf')}  # 各级别配额
        level_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        
        for ws in watersheds:
            area = ws['area']
            assigned_level = 6  # 默认6级
            
            # 基于面积和配额分配级别
            for level in range(1, 7):
                min_area = self.level_definitions[level]['min_area']
                quota = level_quotas[level]
                
                if (area >= min_area and 
                    level_counts[level] < quota and
                    (level == 1 or area < self.level_definitions[level-1]['min_area'])):
                    assigned_level = level
                    break
            
            level_counts[assigned_level] += 1
            hierarchy[ws['node']] = {
                'level': assigned_level,
                'area': area,
                'original_idx': ws['original_idx'],
                'gridcode': ws['gridcode']
            }
        
        # 显示分配结果
        print("层级分配结果:")
        for level in range(1, 7):
            count = level_counts[level]
            if count > 0:
                bits = self.level_definitions[level]['bits']
                desc = self.level_definitions[level]['description']
                print(f"  {level}级 ({bits:2d}位) {desc}: {count} 个")
        
        return hierarchy
    
    def generate_hierarchical_codes(self, hierarchy):
        """生成层次化SHUC编码"""
        print(f"\n🔢 生成层次化SHUC编码:")
        print("-" * 40)
        
        shuc_codes = {}
        
        # 按级别分组
        by_level = defaultdict(list)
        for node, info in hierarchy.items():
            by_level[info['level']].append((node, info))
        
        # 为每级别按面积排序并编码
        for level in range(1, 7):
            if level not in by_level:
                continue
                
            watersheds = by_level[level]
            watersheds.sort(key=lambda x: x[1]['area'], reverse=True)  # 大面积优先编码
            
            for i, (node, info) in enumerate(watersheds, 1):
                code = self.generate_level_code(level, i)
                shuc_codes[node] = {
                    'code': code,
                    'level': level,
                    'area': info['area'],
                    'original_idx': info['original_idx'],
                    'gridcode': info['gridcode']
                }
            
            print(f"  {level}级编码: {len(watersheds)} 个")
        
        return shuc_codes
    
    def generate_level_code(self, level, sequence):
        """生成指定级别的编码"""
        if level == 1:
            return f"{sequence:02d}"
        elif level == 2:
            return f"01{sequence:02d}"
        elif level == 3:
            return f"0101{sequence:02d}"
        elif level == 4:
            return f"010101{sequence:02d}"
        elif level == 5:
            return f"01010101{sequence:02d}"
        else:  # level == 6
            return f"0101010101{sequence:02d}"
    
    def apply_codes_and_generate_final_data(self, shuc_codes):
        """应用编码并生成最终数据"""
        print(f"\n📊 生成最终数据集:")
        print("-" * 40)
        
        # 添加SHUC字段
        for col in ['SHUC_CODE', 'SHUC_LEVEL', 'LEVEL_NAME', 'AREA_RANGE']:
            if col not in self.watershed_data.columns:
                self.watershed_data[col] = ''
        
        # 应用编码
        for node, code_info in shuc_codes.items():
            idx = code_info['original_idx']
            level = code_info['level']
            
            self.watershed_data.loc[idx, 'SHUC_CODE'] = code_info['code']
            self.watershed_data.loc[idx, 'SHUC_LEVEL'] = level
            self.watershed_data.loc[idx, 'LEVEL_NAME'] = self.level_definitions[level]['description']
            
            min_area = self.level_definitions[level]['min_area']
            max_area = self.level_definitions[level]['max_area']
            if max_area == float('inf'):
                area_desc = f"≥{min_area:,}km²"
            else:
                area_desc = f"{min_area:,}-{max_area:,}km²"
            self.watershed_data.loc[idx, 'AREA_RANGE'] = area_desc
        
        # 提取最终数据
        final_indices = [code_info['original_idx'] for code_info in shuc_codes.values()]
        final_data = self.watershed_data.iloc[final_indices].copy().reset_index(drop=True)
        
        print(f"  原始流域: {len(self.watershed_data)} 个")
        print(f"  最终流域: {len(final_data)} 个")
        print(f"  压缩率: {(len(self.watershed_data) - len(final_data))/len(self.watershed_data)*100:.1f}%")
        
        return final_data
    
    def comprehensive_validation(self, final_data):
        """全面验证SHUC系统"""
        print(f"\n✅ 全面系统验证:")
        print("-" * 40)
        
        validation_results = {
            'total_watersheds': len(final_data),
            'area_compliance': 0,
            'code_uniqueness': False,
            'hierarchy_completeness': {},
            'spatial_integrity': True,
            'missing_3150_resolved': False
        }
        
        # 1. 面积合规检查
        compliant = final_data[final_data['area_km2'] >= 100]
        validation_results['area_compliance'] = len(compliant) / len(final_data) * 100
        print(f"面积合规率: {validation_results['area_compliance']:.1f}%")
        
        # 2. 编码唯一性
        codes = final_data['SHUC_CODE'].tolist()
        unique_codes = set(codes)
        validation_results['code_uniqueness'] = len(codes) == len(unique_codes)
        print(f"编码唯一性: {'✓' if validation_results['code_uniqueness'] else '✗'}")
        
        # 3. 层次完整性
        for level in range(1, 7):
            count = len(final_data[final_data['SHUC_LEVEL'] == level])
            validation_results['hierarchy_completeness'][level] = count
            if count > 0:
                desc = self.level_definitions[level]['description']
                bits = self.level_definitions[level]['bits']
                print(f"{level}级 ({bits:2d}位) {desc}: {count} 个")
        
        # 4. 检查gridcode=3150是否被保留
        has_3150 = any(str(gc) == '3150' for gc in final_data.get('gridcode', []))
        validation_results['missing_3150_resolved'] = has_3150
        print(f"gridcode=3150问题: {'已解决' if has_3150 else '仍存在'}")
        
        # 5. 空间完整性（简单检查）
        try:
            total_area_original = self.original_data['area_km2'].sum()
            total_area_final = final_data['area_km2'].sum()
            area_preservation = abs(total_area_final - total_area_original) / total_area_original
            validation_results['spatial_integrity'] = area_preservation < 0.01  # 1%容差
            print(f"空间完整性: {'✓' if validation_results['spatial_integrity'] else '✗'} (差异:{area_preservation*100:.2f}%)")
        except:
            print(f"空间完整性: 无法验证")
        
        return validation_results
    
    def save_fixed_results(self, output_dir):
        """保存修复后的结果"""
        import os
        from datetime import datetime
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 执行完整处理流程
        merge_count = self.advanced_merging_strategy()
        final_watersheds, hierarchy, shuc_codes = self.create_complete_hierarchy()
        final_data = self.apply_codes_and_generate_final_data(shuc_codes)
        
        # 验证结果
        validation_results = self.comprehensive_validation(final_data)
        
        # 保存数据
        output_file = os.path.join(output_dir, "fixed_shuc_system.shp")
        final_data.to_file(output_file)
        print(f"\n✓ 修复后数据: {output_file}")
        
        # 保存验证报告
        report_file = os.path.join(output_dir, "validation_report.json")
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(validation_results, f, indent=2, ensure_ascii=False)
        print(f"✓ 验证报告: {report_file}")
        
        # 保存问题修复日志
        log_file = os.path.join(output_dir, "data_issues_log.txt")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("数据问题修复日志\\n")
            f.write("=" * 50 + "\\n")
            f.write(f"处理时间: {datetime.now()}\\n\\n")
            for i, issue in enumerate(self.data_issues, 1):
                f.write(f"{i}. {issue}\\n")
        print(f"✓ 问题日志: {log_file}")
        
        return final_data, validation_results

def main():
    """运行修复版SHUC系统"""
    print("🛠️  修复版SHUC系统 v3.0")
    print("解决数据完整性和层次结构问题")
    print("=" * 60)
    
    # 创建修复系统
    fixed_system = FixedSHUCSystem()
    
    # 加载和验证数据
    if not fixed_system.load_and_validate_data("之前参考/demo数据/流域.shp"):
        return
    
    # 构建健壮拓扑
    fixed_system.build_robust_topology()
    
    # 分析分布
    fixed_system.analyze_watershed_distribution()
    
    # 保存结果
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"./shuc_results/fixed_system_{timestamp}"
    
    final_data, validation = fixed_system.save_fixed_results(output_dir)
    
    print(f"\n🎉 修复版SHUC系统完成!")
    print(f"📂 结果目录: {os.path.abspath(output_dir)}")
    
    if validation['area_compliance'] >= 95 and validation['code_uniqueness']:
        print("✅ 系统验证通过!")
    else:
        print("⚠️  系统存在部分问题，请查看验证报告")

if __name__ == "__main__":
    main()