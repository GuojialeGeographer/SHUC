#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的中国SHUC系统 - 基于美国HUC标准设计
===============================================

基于美国HUC系统设计的6级中国流域编码系统：
1级 (2位): 大区流域 (≥20,000km²) - 主要江河流域
2级 (4位): 区域流域 (5,000-20,000km²) - 江河干流段
3级 (6位): 大流域 (1,500-5,000km²) - 主要支流域
4级 (8位): 中流域 (400-1,500km²) - 支流域
5级 (10位): 小流域 (100-400km²) - 次级支流域
6级 (12位): 基本单元 (≥100km²) - 基本水文单元

Author: Claude Code Assistant  
Date: 2025-08-30
Reference: US HUC System
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx
from shapely.ops import unary_union
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class CompleteChinasSHUCSystem:
    """
    完整的中国SHUC系统 - 参考美国HUC标准
    """
    
    def __init__(self):
        """初始化完整SHUC系统"""
        self.watershed_data = None
        self.topology_graph = None
        self.merge_history = []
        
        # 基于美国HUC系统设计的中国SHUC分级标准
        self.level_definitions = {
            1: {
                "bits": 2, 
                "description": "大区流域", 
                "min_area": 20000,  # ≥20,000km² 
                "max_area": float('inf'),
                "example": "01",
                "note": "长江、黄河等主要流域"
            },
            2: {
                "bits": 4, 
                "description": "区域流域", 
                "min_area": 5000,   # 5,000-20,000km²
                "max_area": 20000,
                "example": "0101", 
                "note": "江河干流段"
            },
            3: {
                "bits": 6, 
                "description": "大流域", 
                "min_area": 1500,   # 1,500-5,000km²
                "max_area": 5000,
                "example": "010101",
                "note": "主要支流域"
            },
            4: {
                "bits": 8, 
                "description": "中流域", 
                "min_area": 400,    # 400-1,500km²
                "max_area": 1500,
                "example": "01010101",
                "note": "支流域"
            },
            5: {
                "bits": 10, 
                "description": "小流域", 
                "min_area": 100,    # 100-400km²
                "max_area": 400,
                "example": "0101010101",
                "note": "次级支流域"
            },
            6: {
                "bits": 12, 
                "description": "基本单元", 
                "min_area": 100,    # ≥100km² (最小标准)
                "max_area": 100,    # 最大不设限，但会通过合并控制
                "example": "010101010101",
                "note": "基本水文单元"
            }
        }
        
        # 中国主要流域编码
        self.major_basins = {
            "01": "长江流域",
            "02": "黄河流域", 
            "03": "珠江流域",
            "04": "松花江流域",
            "05": "淮河流域",
            "06": "海河流域",
            "07": "辽河流域",
            "08": "太湖流域",
            "09": "东南沿海诸河",
            "10": "西南诸河",
            "11": "西北内流区",
            "12": "东北内流区"
        }
    
    def display_system_overview(self):
        """显示完整SHUC系统概况"""
        print("🎯 完整中国SHUC系统设计")
        print("=" * 60)
        print("📚 参考: 美国HUC (Hydrologic Unit Code) 系统")
        print()
        
        print("🏗️ 分级结构设计:")
        for level in range(1, 7):
            def_info = self.level_definitions[level]
            bits = def_info['bits']
            desc = def_info['description']
            min_area = def_info['min_area']
            max_area = def_info['max_area']
            example = def_info['example']
            note = def_info['note']
            
            if max_area == float('inf'):
                area_range = f"≥{min_area:,}km²"
            elif max_area == min_area:
                area_range = f"≥{min_area}km²"
            else:
                area_range = f"{min_area:,}-{max_area:,}km²"
            
            print(f"  {level}级 ({bits:2d}位): {desc:8s} | {area_range:>15s} | {example} | {note}")
        
        print()
        print("🌊 主要流域编码:")
        for code, name in list(self.major_basins.items())[:6]:
            print(f"  {code}: {name}")
    
    def load_data(self, shapefile_path):
        """加载流域数据"""
        try:
            self.watershed_data = gpd.read_file(shapefile_path)
            
            # 确保面积字段存在
            if 'area_km2' not in self.watershed_data.columns:
                if 'Shape_Area' in self.watershed_data.columns:
                    self.watershed_data['area_km2'] = self.watershed_data['Shape_Area'] / 1000000
                elif 'Areakm2' in self.watershed_data.columns:
                    self.watershed_data['area_km2'] = self.watershed_data['Areakm2']
                else:
                    self.watershed_data['area_km2'] = self.watershed_data.geometry.area / 1000000
            
            print(f"✓ 加载了 {len(self.watershed_data)} 个原始流域")
            print(f"  数据字段: {list(self.watershed_data.columns)}")
            return True
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
            return False
    
    def analyze_original_data_for_hierarchy(self):
        """分析原始数据，准备完整6级分类"""
        areas = self.watershed_data['area_km2']
        
        print(f"\n📊 原始数据层次分析:")
        print(f"  流域数量: {len(areas)}")
        print(f"  面积范围: {areas.min():.2f} - {areas.max():.2f} km²")
        print(f"  平均面积: {areas.mean():.2f} km²")
        print()
        
        # 按设计标准分级统计
        level_6 = areas[areas >= 100]                                    # 6级: ≥100km²
        level_5 = areas[(areas >= 100) & (areas < 400)]                 # 5级: 100-400km²  
        level_4 = areas[(areas >= 400) & (areas < 1500)]                # 4级: 400-1500km²
        level_3 = areas[(areas >= 1500) & (areas < 5000)]               # 3级: 1500-5000km²
        level_2 = areas[(areas >= 5000) & (areas < 20000)]              # 2级: 5000-20000km²
        level_1 = areas[areas >= 20000]                                 # 1级: ≥20000km²
        
        small_watersheds = areas[areas < 100]  # 需要合并的
        
        print(f"🏗️ 按中国SHUC标准分类:")
        print(f"  1级 (≥20,000km²):   {len(level_1):3d} 个 - 大区流域")
        print(f"  2级 (5-20,000km²):  {len(level_2):3d} 个 - 区域流域") 
        print(f"  3级 (1.5-5,000km²): {len(level_3):3d} 个 - 大流域")
        print(f"  4级 (400-1,500km²): {len(level_4):3d} 个 - 中流域")
        print(f"  5级 (100-400km²):   {len(level_5):3d} 个 - 小流域")
        print(f"  6级 (≥100km²):      {len(level_6):3d} 个 - 基本单元")
        print(f"  需要合并 (<100km²):  {len(small_watersheds):3d} 个")
        
        return {
            "needs_merge": len(small_watersheds),
            "level_stats": {
                1: len(level_1), 2: len(level_2), 3: len(level_3),
                4: len(level_4), 5: len(level_5), 6: len(level_6)
            }
        }
    
    def build_topology_graph(self):
        """构建流域拓扑图"""
        self.topology_graph = nx.DiGraph()
        
        # 创建节点
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('LINKNO', row.get('gridcode', idx))
            area = row['area_km2']
            
            self.topology_graph.add_node(linkno, 
                                       area=area,
                                       original_idx=idx,
                                       merged=False,
                                       gridcode=row.get('gridcode', linkno))
        
        # 创建边（拓扑关系）
        edge_count = 0
        all_linknos = set(self.topology_graph.nodes())
        
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('LINKNO', row.get('gridcode', idx))
            dslink = row.get('DSLINKNO', -1)
            uslink1 = row.get('USLINKNO1', -1)
            uslink2 = row.get('USLINKNO2', -1)
            
            # 添加下游连接
            if dslink != -1 and dslink in all_linknos:
                self.topology_graph.add_edge(linkno, dslink)
                edge_count += 1
            
            # 添加上游连接（反向）
            if uslink1 != -1 and uslink1 in all_linknos:
                self.topology_graph.add_edge(uslink1, linkno)
                edge_count += 1
            if uslink2 != -1 and uslink2 in all_linknos:
                self.topology_graph.add_edge(uslink2, linkno)
                edge_count += 1
        
        print(f"✓ 构建拓扑图: {self.topology_graph.number_of_nodes()} 节点, {edge_count} 边")
    
    def intelligent_watershed_merging(self):
        """智能流域合并算法 - 确保所有6级流域≥100km²"""
        print(f"\n🔄 智能流域合并 (目标: 6级流域≥100km²)")
        print("-" * 50)
        
        merge_count = 0
        iteration = 0
        
        while True:
            iteration += 1
            print(f"第 {iteration} 轮合并:")
            
            # 找到需要合并的小流域
            small_watersheds = []
            for node in self.topology_graph.nodes():
                node_data = self.topology_graph.nodes[node]
                if not node_data['merged'] and node_data['area'] < 100:
                    small_watersheds.append((node_data['area'], node))
            
            if not small_watersheds:
                print("  ✓ 所有流域都已达到100km²标准")
                break
            
            print(f"  找到 {len(small_watersheds)} 个需要合并的流域")
            small_watersheds.sort()  # 最小的优先
            
            merged_in_round = 0
            
            for area, node in small_watersheds:
                if self.topology_graph.nodes[node]['merged']:
                    continue
                
                # 智能选择合并目标
                merge_target = self.find_best_merge_target(node)
                
                if merge_target:
                    self.perform_merge(node, merge_target)
                    merge_count += 1
                    merged_in_round += 1
                    
                    new_area = self.topology_graph.nodes[node]['area']
                    target_area = self.topology_graph.nodes[merge_target]['area']
                    print(f"    合并: {node}({area:.1f}km²) + {merge_target}({target_area:.1f}km²) = {new_area:.1f}km²")
            
            print(f"  本轮合并: {merged_in_round} 次")
            
            if merged_in_round == 0:
                print("  ⚠️  无法进一步合并")
                break
        
        print(f"✅ 合并完成! 总共 {merge_count} 次合并")
        return merge_count
    
    def find_best_merge_target(self, node):
        """为节点找到最佳合并目标"""
        candidates = []
        
        # 获取邻居节点
        upstream = list(self.topology_graph.predecessors(node))
        downstream = list(self.topology_graph.successors(node))
        
        # 收集所有候选者
        for neighbor in upstream + downstream:
            if not self.topology_graph.nodes[neighbor]['merged']:
                area = self.topology_graph.nodes[neighbor]['area']
                candidates.append((area, neighbor))
        
        # 选择面积最小的候选者（优先合并小流域）
        if candidates:
            candidates.sort()
            return candidates[0][1]
        
        return None
    
    def perform_merge(self, primary_node, merge_node):
        """执行流域合并"""
        primary_idx = self.topology_graph.nodes[primary_node]['original_idx']
        merge_idx = self.topology_graph.nodes[merge_node]['original_idx']
        
        # 合并几何
        geom1 = self.watershed_data.iloc[primary_idx]['geometry']
        geom2 = self.watershed_data.iloc[merge_idx]['geometry']
        merged_geom = unary_union([geom1, geom2])
        
        # 更新面积
        primary_area = self.topology_graph.nodes[primary_node]['area']
        merge_area = self.topology_graph.nodes[merge_node]['area']
        new_area = primary_area + merge_area
        
        # 更新主节点
        self.topology_graph.nodes[primary_node]['area'] = new_area
        self.watershed_data.loc[primary_idx, 'geometry'] = merged_geom
        self.watershed_data.loc[primary_idx, 'area_km2'] = new_area
        
        # 标记被合并节点
        self.topology_graph.nodes[merge_node]['merged'] = True
        
        # 记录合并历史
        self.merge_history.append({
            'primary': primary_node,
            'merged': merge_node,
            'old_area': primary_area,
            'merge_area': merge_area,
            'new_area': new_area
        })
        
        # 更新拓扑关系
        self.update_topology_after_merge(primary_node, merge_node)
    
    def update_topology_after_merge(self, primary_node, merged_node):
        """更新合并后的拓扑关系"""
        predecessors = list(self.topology_graph.predecessors(merged_node))
        successors = list(self.topology_graph.successors(merged_node))
        
        # 转移连接到主节点
        for pred in predecessors:
            if pred != primary_node:
                self.topology_graph.add_edge(pred, primary_node)
        
        for succ in successors:
            if succ != primary_node:
                self.topology_graph.add_edge(primary_node, succ)
        
        # 移除被合并节点的连接
        edges_to_remove = []
        for edge in self.topology_graph.edges():
            if edge[0] == merged_node or edge[1] == merged_node:
                edges_to_remove.append(edge)
        
        for edge in edges_to_remove:
            if self.topology_graph.has_edge(*edge):
                self.topology_graph.remove_edge(*edge)
    
    def assign_complete_hierarchy(self):
        """分配完整的6级层次结构"""
        print(f"\n🏗️ 分配完整6级SHUC层次:")
        print("-" * 50)
        
        # 获取最终有效流域
        final_watersheds = []
        for node in self.topology_graph.nodes():
            if not self.topology_graph.nodes[node]['merged']:
                node_data = self.topology_graph.nodes[node]
                area = node_data['area']
                final_watersheds.append((area, node, node_data))
        
        # 按面积排序
        final_watersheds.sort(reverse=True)
        
        hierarchy_assignment = {}
        level_counters = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        
        for area, node, node_data in final_watersheds:
            # 根据面积分配层级
            assigned_level = self.classify_watershed_level(area)
            level_counters[assigned_level] += 1
            
            hierarchy_assignment[node] = {
                'level': assigned_level,
                'area': area,
                'original_idx': node_data['original_idx']
            }
        
        # 显示分配结果
        for level in range(1, 7):
            count = level_counters[level]
            if count > 0:
                def_info = self.level_definitions[level]
                desc = def_info['description']
                bits = def_info['bits']
                print(f"  {level}级 ({bits:2d}位) {desc}: {count:2d} 个")
        
        return hierarchy_assignment
    
    def classify_watershed_level(self, area):
        """根据面积分类流域层级"""
        for level in range(1, 7):
            min_area = self.level_definitions[level]['min_area']
            max_area = self.level_definitions[level]['max_area']
            
            if level == 1:  # 1级: ≥20,000km²
                if area >= min_area:
                    return 1
            elif level == 6:  # 6级: ≥100km² (最小单元)
                if area >= min_area:
                    return 6
            else:  # 2-5级: 范围区间
                if min_area <= area < max_area:
                    return level
        
        # 默认分配给6级（基本单元）
        return 6
    
    def generate_complete_shuc_codes(self, hierarchy_assignment):
        """生成完整的SHUC分级编码"""
        print(f"\n🔢 生成完整SHUC编码:")
        print("-" * 50)
        
        shuc_codes = {}
        
        # 按级别分组
        by_level = defaultdict(list)
        for node, info in hierarchy_assignment.items():
            by_level[info['level']].append((node, info))
        
        # 为每个级别生成编码
        for level in range(1, 7):
            if level not in by_level:
                continue
                
            watersheds_in_level = by_level[level]
            watersheds_in_level.sort(key=lambda x: x[1]['area'], reverse=True)  # 按面积排序
            
            bits = self.level_definitions[level]['bits']
            desc = self.level_definitions[level]['description']
            print(f"  {level}级 ({bits:2d}位) {desc}: {len(watersheds_in_level)} 个")
            
            for i, (node, info) in enumerate(watersheds_in_level, 1):
                # 生成层次编码
                code = self.generate_hierarchical_code(level, i)
                
                shuc_codes[node] = {
                    'code': code,
                    'level': level,
                    'area': info['area'],
                    'original_idx': info['original_idx']
                }
        
        print(f"✓ 生成 {len(shuc_codes)} 个SHUC编码")
        return shuc_codes
    
    def generate_hierarchical_code(self, level, sequence):
        """生成层次化编码"""
        if level == 1:
            # 1级: 2位
            return f"{sequence:02d}"
        elif level == 2:
            # 2级: 4位 (假设属于01大区)
            return f"01{sequence:02d}"
        elif level == 3:
            # 3级: 6位 (假设属于0101区域)
            return f"0101{sequence:02d}"
        elif level == 4:
            # 4级: 8位
            return f"010101{sequence:02d}"
        elif level == 5:
            # 5级: 10位
            return f"01010101{sequence:02d}"
        else:
            # 6级: 12位
            return f"0101010101{sequence:02d}"
    
    def apply_shuc_codes_to_data(self, shuc_codes):
        """将SHUC编码应用到数据"""
        # 添加新字段
        self.watershed_data['SHUC_CODE'] = ''
        self.watershed_data['SHUC_LEVEL'] = 0
        self.watershed_data['LEVEL_NAME'] = ''
        self.watershed_data['AREA_RANGE'] = ''
        
        for node, code_info in shuc_codes.items():
            idx = code_info['original_idx']
            level = code_info['level']
            
            self.watershed_data.loc[idx, 'SHUC_CODE'] = code_info['code']
            self.watershed_data.loc[idx, 'SHUC_LEVEL'] = level
            self.watershed_data.loc[idx, 'LEVEL_NAME'] = self.level_definitions[level]['description']
            
            # 设置面积范围描述
            min_area = self.level_definitions[level]['min_area']
            max_area = self.level_definitions[level]['max_area']
            if max_area == float('inf'):
                area_desc = f"≥{min_area}km²"
            elif max_area == min_area:
                area_desc = f"≥{min_area}km²"
            else:
                area_desc = f"{min_area}-{max_area}km²"
            
            self.watershed_data.loc[idx, 'AREA_RANGE'] = area_desc
        
        print(f"✓ SHUC编码应用完成")
    
    def generate_final_dataset(self):
        """生成最终数据集（仅包含未合并的流域）"""
        final_indices = []
        
        for node in self.topology_graph.nodes():
            if not self.topology_graph.nodes[node]['merged']:
                original_idx = self.topology_graph.nodes[node]['original_idx']
                final_indices.append(original_idx)
        
        final_data = self.watershed_data.iloc[final_indices].copy().reset_index(drop=True)
        
        print(f"\n📋 最终数据统计:")
        print(f"  原始流域: {len(self.watershed_data)} 个")
        print(f"  最终流域: {len(final_data)} 个")
        print(f"  合并减少: {len(self.watershed_data) - len(final_data)} 个 ({(len(self.watershed_data) - len(final_data))/len(self.watershed_data)*100:.1f}%)")
        
        return final_data
    
    def validate_complete_system(self, final_data):
        """验证完整SHUC系统"""
        print(f"\n✅ 完整SHUC系统验证:")
        print("-" * 50)
        
        # 按级别统计
        level_stats = final_data.groupby('SHUC_LEVEL').agg({
            'area_km2': ['count', 'min', 'max', 'mean']
        }).round(1)
        
        print(f"📊 各级别统计:")
        for level in range(1, 7):
            level_data = final_data[final_data['SHUC_LEVEL'] == level]
            if len(level_data) > 0:
                count = len(level_data)
                min_area = level_data['area_km2'].min()
                max_area = level_data['area_km2'].max()
                avg_area = level_data['area_km2'].mean()
                bits = self.level_definitions[level]['bits']
                desc = self.level_definitions[level]['description']
                
                print(f"  {level}级 ({bits:2d}位) {desc}: {count:2d}个, {min_area:.0f}-{max_area:.0f}km² (均{avg_area:.0f}km²)")
        
        # 检查100km²标准
        small_areas = final_data[final_data['area_km2'] < 100]
        target_met = len(final_data[final_data['area_km2'] >= 100])
        target_total = len(final_data)
        
        print(f"\n🎯 SHUC标准检查:")
        print(f"  面积≥100km²: {target_met}/{target_total} ({target_met/target_total*100:.1f}%)")
        
        if len(small_areas) > 0:
            print(f"  未达标流域: {len(small_areas)}个, 最小{small_areas['area_km2'].min():.1f}km²")
        else:
            print(f"  🎉 100%符合≥100km²标准!")
        
        return len(small_areas) == 0
    
    def save_complete_results(self, output_dir):
        """保存完整结果"""
        import os
        from datetime import datetime
        
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 生成最终数据
        final_data = self.generate_final_dataset()
        
        # 保存shapefile
        output_file = os.path.join(output_dir, "complete_shuc_system.shp")
        final_data.to_file(output_file)
        print(f"✓ 完整SHUC数据: {output_file}")
        
        # 生成详细报告
        report = self.generate_complete_system_report(final_data, timestamp)
        report_file = os.path.join(output_dir, "complete_shuc_report.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✓ 系统报告: {report_file}")
        
        # 验证系统
        validation_passed = self.validate_complete_system(final_data)
        
        return final_data, validation_passed
    
    def generate_complete_system_report(self, final_data, timestamp):
        """生成完整系统报告"""
        report = []
        report.append("完整中国SHUC系统报告")
        report.append("=" * 60)
        report.append(f"生成时间: {timestamp}")
        report.append(f"参考标准: 美国HUC系统")
        report.append("")
        
        # 系统概况
        report.append("1. 系统概况")
        report.append("-" * 30)
        report.append(f"   原始流域数: {len(self.watershed_data)}")
        report.append(f"   最终流域数: {len(final_data)}")
        report.append(f"   合并次数: {len(self.merge_history)}")
        report.append(f"   数据压缩率: {(len(self.watershed_data)-len(final_data))/len(self.watershed_data)*100:.1f}%")
        report.append("")
        
        # 6级层次结构
        report.append("2. 完整6级层次结构")
        report.append("-" * 30)
        for level in range(1, 7):
            level_data = final_data[final_data['SHUC_LEVEL'] == level]
            if len(level_data) > 0:
                count = len(level_data)
                min_area = level_data['area_km2'].min()
                max_area = level_data['area_km2'].max()
                avg_area = level_data['area_km2'].mean()
                bits = self.level_definitions[level]['bits']
                desc = self.level_definitions[level]['description']
                
                report.append(f"   {level}级 ({bits:2d}位) {desc}: {count:2d}个, {min_area:.0f}-{max_area:.0f}km² (均{avg_area:.0f}km²)")
        
        # 编码示例
        report.append("")
        report.append("3. 编码示例")
        report.append("-" * 30)
        for level in range(1, 7):
            level_data = final_data[final_data['SHUC_LEVEL'] == level]
            if len(level_data) > 0:
                example = level_data.iloc[0]
                code = example['SHUC_CODE']
                area = example['area_km2']
                desc = example['LEVEL_NAME']
                report.append(f"   {level}级: {code} | {desc} | {area:.1f}km²")
        
        # SHUC标准达成
        report.append("")
        report.append("4. SHUC标准达成")
        report.append("-" * 30)
        target_met = len(final_data[final_data['area_km2'] >= 100])
        target_total = len(final_data)
        report.append(f"   面积≥100km²: {target_met}/{target_total} ({target_met/target_total*100:.1f}%)")
        
        small_areas = final_data[final_data['area_km2'] < 100]
        if len(small_areas) > 0:
            report.append(f"   未达标: {len(small_areas)}个 (最小{small_areas['area_km2'].min():.1f}km²)")
        else:
            report.append(f"   🎉 100%达标!")
        
        return "\n".join(report)

def main():
    """运行完整中国SHUC系统"""
    print("🎯 完整中国SHUC系统 v2.0")
    print("基于美国HUC标准设计")
    print("=" * 60)
    
    # 创建系统
    shuc_system = CompleteChinasSHUCSystem()
    
    # 显示系统概况
    shuc_system.display_system_overview()
    
    # 加载数据
    watershed_file = "之前参考/demo数据/流域.shp"
    if not shuc_system.load_data(watershed_file):
        print("❌ 请检查数据文件路径")
        return
    
    # 分析原始数据层次
    analysis_result = shuc_system.analyze_original_data_for_hierarchy()
    
    # 构建拓扑
    shuc_system.build_topology_graph()
    
    # 智能合并
    merge_count = shuc_system.intelligent_watershed_merging()
    
    # 分配完整层次
    hierarchy_assignment = shuc_system.assign_complete_hierarchy()
    
    # 生成完整编码
    shuc_codes = shuc_system.generate_complete_shuc_codes(hierarchy_assignment)
    
    # 应用编码
    shuc_system.apply_shuc_codes_to_data(shuc_codes)
    
    # 保存结果
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"./shuc_results/complete_system_{timestamp}"
    
    final_data, validation_passed = shuc_system.save_complete_results(output_dir)
    
    if validation_passed:
        print(f"\n🎉 完整中国SHUC系统构建成功!")
        print(f"📂 结果位置: {os.path.abspath(output_dir)}")
    else:
        print(f"\n⚠️  系统构建完成，但存在部分问题")

if __name__ == "__main__":
    main()