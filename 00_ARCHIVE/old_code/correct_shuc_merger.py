#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正确的SHUC流域合并系统
=======================

按照真正的SHUC标准实现：
- 第6级流域面积必须≥100km²
- 小流域必须合并到满足条件为止
- 编码从2位（1级）到12位（6级）

Author: Claude Code Assistant
Date: 2025-08-30
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx
from shapely.ops import unary_union
import warnings
warnings.filterwarnings('ignore')

class CorrectSHUCMerger:
    """
    真正的SHUC流域合并系统
    """
    
    def __init__(self, target_area_threshold=100.0):
        """
        参数:
        target_area_threshold : float
            第6级流域的最小面积要求 (默认100km²)
        """
        self.target_area = target_area_threshold
        self.watershed_data = None
        self.topology_graph = None
        self.merge_groups = []
        
    def load_data(self, shapefile_path):
        """加载流域数据"""
        try:
            self.watershed_data = gpd.read_file(shapefile_path)
            
            # 计算面积
            if 'area_km2' not in self.watershed_data.columns:
                if 'Shape_Area' in self.watershed_data.columns:
                    self.watershed_data['area_km2'] = self.watershed_data['Shape_Area'] / 1000000
                elif 'Areakm2' in self.watershed_data.columns:
                    self.watershed_data['area_km2'] = self.watershed_data['Areakm2']
                else:
                    self.watershed_data['area_km2'] = self.watershed_data.geometry.area / 1000000
            
            print(f"✓ 加载了 {len(self.watershed_data)} 个原始流域")
            return True
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
            return False
    
    def analyze_data_distribution(self):
        """分析原始数据分布"""
        areas = self.watershed_data['area_km2']
        
        print(f"\n📊 原始流域面积分析:")
        print(f"  总数量: {len(areas)}")
        print(f"  面积范围: {areas.min():.2f} - {areas.max():.2f} km²")
        print(f"  平均面积: {areas.mean():.2f} km²")
        print(f"  中位数: {areas.median():.2f} km²")
        
        # 按面积分级统计
        small = areas[areas < 50]
        medium = areas[(areas >= 50) & (areas < 100)]
        large = areas[areas >= 100]
        
        print(f"\n🔢 面积分级统计:")
        print(f"  <50km²:   {len(small):3d} 个 ({len(small)/len(areas)*100:.1f}%)")
        print(f"  50-100km²: {len(medium):3d} 个 ({len(medium)/len(areas)*100:.1f}%)")
        print(f"  ≥100km²:   {len(large):3d} 个 ({len(large)/len(areas)*100:.1f}%)")
        print(f"  需要合并: {len(small) + len(medium):3d} 个")
    
    def build_topology_graph(self):
        """构建拓扑图"""
        self.topology_graph = nx.DiGraph()
        
        # 首先创建LINKNO到索引的映射
        linkno_to_idx = {}
        all_linknos = set()
        
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('LINKNO', row.get('gridcode', idx))
            linkno_to_idx[linkno] = idx
            all_linknos.add(linkno)
            
            area = row['area_km2']
            
            # 添加节点
            self.topology_graph.add_node(linkno, 
                                       area=area,
                                       original_idx=idx,
                                       merged=False)
        
        # 然后添加连接关系
        edge_count = 0
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
                
        print(f"✓ 构建拓扑图: {self.topology_graph.number_of_nodes()} 节点, {self.topology_graph.number_of_edges()} 边")
    
    def find_merge_candidates(self, node):
        """为给定节点找合并候选者"""
        candidates = []
        
        # 获取上游和下游节点
        upstream = list(self.topology_graph.predecessors(node))
        downstream = list(self.topology_graph.successors(node))
        
        # 优先选择面积最小的上游节点
        for up_node in upstream:
            if not self.topology_graph.nodes[up_node]['merged']:
                candidates.append((up_node, 'upstream'))
        
        # 如果没有上游，考虑下游
        if not candidates:
            for down_node in downstream:
                if not self.topology_graph.nodes[down_node]['merged']:
                    candidates.append((down_node, 'downstream'))
        
        return candidates
    
    def merge_watersheds_until_target(self):
        """
        核心合并算法：合并小流域直到达到100km²标准
        """
        print(f"\n🔄 开始流域合并 (目标: ≥{self.target_area}km²)")
        print("-" * 50)
        
        merge_count = 0
        iteration = 0
        
        while True:
            iteration += 1
            print(f"第 {iteration} 轮合并:")
            
            # 找到所有需要合并的小流域
            small_watersheds = []
            for node in self.topology_graph.nodes():
                node_data = self.topology_graph.nodes[node]
                if (not node_data['merged'] and 
                    node_data['area'] < self.target_area):
                    small_watersheds.append((node_data['area'], node))
            
            if not small_watersheds:
                print("  ✓ 没有更多需要合并的流域")
                break
            
            print(f"  找到 {len(small_watersheds)} 个需要合并的流域")
            
            # 按面积排序，最小的优先合并
            small_watersheds.sort()
            
            merged_in_round = 0
            
            for area, node in small_watersheds:
                if self.topology_graph.nodes[node]['merged']:
                    continue  # 已经被合并了
                
                # 找合并候选
                candidates = self.find_merge_candidates(node)
                
                if candidates:
                    # 选择最佳候选（面积最小的）
                    best_candidate = None
                    best_area = float('inf')
                    
                    for candidate, direction in candidates:
                        if not self.topology_graph.nodes[candidate]['merged']:
                            candidate_area = self.topology_graph.nodes[candidate]['area']
                            if candidate_area < best_area:
                                best_candidate = candidate
                                best_area = candidate_area
                    
                    if best_candidate:
                        # 执行合并
                        self.perform_merge(node, best_candidate)
                        merge_count += 1
                        merged_in_round += 1
                        
                        new_area = self.topology_graph.nodes[node]['area']
                        print(f"    合并: {node}({area:.1f}) + {best_candidate}({best_area:.1f}) = {new_area:.1f}km²")
            
            print(f"  本轮合并了 {merged_in_round} 次")
            
            if merged_in_round == 0:
                print("  ⚠️  无法进一步合并")
                break
        
        print(f"\n✅ 合并完成! 总共进行了 {merge_count} 次合并")
        return merge_count
    
    def perform_merge(self, primary_node, merge_node):
        """执行两个流域的合并"""
        # 获取几何数据
        primary_idx = self.topology_graph.nodes[primary_node]['original_idx']
        merge_idx = self.topology_graph.nodes[merge_node]['original_idx']
        
        # 合并几何
        geom1 = self.watershed_data.iloc[primary_idx]['geometry']
        geom2 = self.watershed_data.iloc[merge_idx]['geometry'] 
        merged_geom = unary_union([geom1, geom2])
        
        # 更新主节点
        primary_area = self.topology_graph.nodes[primary_node]['area']
        merge_area = self.topology_graph.nodes[merge_node]['area']
        new_area = primary_area + merge_area
        
        self.topology_graph.nodes[primary_node]['area'] = new_area
        self.watershed_data.loc[primary_idx, 'geometry'] = merged_geom
        self.watershed_data.loc[primary_idx, 'area_km2'] = new_area
        
        # 标记被合并的节点
        self.topology_graph.nodes[merge_node]['merged'] = True
        
        # 更新拓扑连接
        self.update_topology_after_merge(primary_node, merge_node)
    
    def update_topology_after_merge(self, primary_node, merged_node):
        """更新合并后的拓扑关系"""
        # 获取被合并节点的连接
        predecessors = list(self.topology_graph.predecessors(merged_node))
        successors = list(self.topology_graph.successors(merged_node))
        
        # 将连接转移到主节点
        for pred in predecessors:
            if pred != primary_node:
                self.topology_graph.add_edge(pred, primary_node)
        
        for succ in successors:
            if succ != primary_node:
                self.topology_graph.add_edge(primary_node, succ)
        
        # 移除被合并节点的连接（但保留节点用于标记）
        edges_to_remove = []
        for edge in self.topology_graph.edges():
            if edge[0] == merged_node or edge[1] == merged_node:
                edges_to_remove.append(edge)
        
        for edge in edges_to_remove:
            self.topology_graph.remove_edge(*edge)
    
    def generate_final_data(self):
        """生成最终的合并结果数据"""
        # 过滤掉被合并的流域
        final_indices = []
        for node in self.topology_graph.nodes():
            if not self.topology_graph.nodes[node]['merged']:
                original_idx = self.topology_graph.nodes[node]['original_idx']
                final_indices.append(original_idx)
        
        final_data = self.watershed_data.iloc[final_indices].copy().reset_index(drop=True)
        
        print(f"\n📋 合并结果统计:")
        print(f"  原始流域数: {len(self.watershed_data)}")
        print(f"  最终流域数: {len(final_data)}")
        print(f"  减少数量: {len(self.watershed_data) - len(final_data)}")
        print(f"  减少比例: {(len(self.watershed_data) - len(final_data)) / len(self.watershed_data) * 100:.1f}%")
        
        return final_data
    
    def analyze_final_results(self, final_data):
        """分析最终结果"""
        areas = final_data['area_km2']
        
        print(f"\n📊 最终流域面积分析:")
        print(f"  数量: {len(areas)}")
        print(f"  面积范围: {areas.min():.2f} - {areas.max():.2f} km²")
        print(f"  平均面积: {areas.mean():.2f} km²")
        print(f"  中位数: {areas.median():.2f} km²")
        
        # 检查是否达到100km²标准
        small = areas[areas < self.target_area]
        large = areas[areas >= self.target_area]
        
        print(f"\n🎯 SHUC标准检查:")
        print(f"  ≥{self.target_area}km²: {len(large):3d} 个 ({len(large)/len(areas)*100:.1f}%)")
        print(f"  <{self.target_area}km²:  {len(small):3d} 个 ({len(small)/len(areas)*100:.1f}%)")
        
        if len(small) > 0:
            print(f"  ⚠️  还有 {len(small)} 个流域面积小于标准")
            print(f"      最小面积: {small.min():.2f}km²")
        else:
            print(f"  ✅ 所有流域都符合≥{self.target_area}km²标准!")
    
    def save_results(self, output_path):
        """保存合并结果"""
        final_data = self.generate_final_data()
        
        try:
            final_data.to_file(output_path)
            print(f"✅ 结果已保存: {output_path}")
            
            # 分析最终结果
            self.analyze_final_results(final_data)
            
            return final_data
        except Exception as e:
            print(f"❌ 保存失败: {e}")
            return None

def main():
    """运行正确的SHUC合并演示"""
    print("🎯 正确的SHUC流域合并系统")
    print("=" * 60)
    
    # 创建合并器
    merger = CorrectSHUCMerger(target_area_threshold=100.0)
    
    # 加载数据
    watershed_file = "之前参考/demo数据/流域.shp"
    if not merger.load_data(watershed_file):
        return
    
    # 分析原始数据
    merger.analyze_data_distribution()
    
    # 构建拓扑
    merger.build_topology_graph()
    
    # 执行合并
    merge_count = merger.merge_watersheds_until_target()
    
    # 保存结果
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"./shuc_results/correct_merge_{timestamp}"
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "merged_watersheds_100km2.shp")
    final_data = merger.save_results(output_file)
    
    if final_data is not None:
        print(f"\n🎉 SHUC合并完成!")
        print(f"📂 结果位置: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()