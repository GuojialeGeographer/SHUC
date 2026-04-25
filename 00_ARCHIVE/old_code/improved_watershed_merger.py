#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Improved Watershed Merging Algorithm for SHUC System
====================================================

This module implements an improved algorithm for merging small watersheds 
based on topological relationships and area thresholds.

Author: Claude Code Assistant
Date: 2025-08-29
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon
from collections import deque, defaultdict
import networkx as nx
import warnings

warnings.filterwarnings('ignore')


class WatershedMerger:
    """
    Advanced watershed merging algorithm with topological analysis
    """
    
    def __init__(self, area_threshold=100.0, min_area_threshold=80.0):
        """
        Initialize the watershed merger
        
        Parameters:
        -----------
        area_threshold : float
            Area threshold in km² above which watersheds won't be merged
        min_area_threshold : float
            Minimum acceptable area after merging
        """
        self.area_threshold = area_threshold
        self.min_area_threshold = min_area_threshold
        self.topology_graph = None
        self.watershed_data = None
        
    def load_data(self, shapefile_path):
        """
        Load watershed shapefile data
        
        Parameters:
        -----------
        shapefile_path : str
            Path to the watershed shapefile
        """
        try:
            self.watershed_data = gpd.read_file(shapefile_path)
            # Calculate area in km² (use existing area if available)
            if 'area_km2' not in self.watershed_data.columns:
                if 'Shape_Area' in self.watershed_data.columns:
                    self.watershed_data['area_km2'] = self.watershed_data['Shape_Area'] / 1000000
                elif 'Areakm2' in self.watershed_data.columns:
                    self.watershed_data['area_km2'] = self.watershed_data['Areakm2']
                else:
                    self.watershed_data['area_km2'] = self.watershed_data.geometry.area / 1000000
            print(f"Loaded {len(self.watershed_data)} watersheds")
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False
    
    def build_topology_graph(self):
        """
        Build a directed graph representing watershed topology
        """
        self.topology_graph = nx.DiGraph()
        
        for idx, row in self.watershed_data.iterrows():
            # 支持多种字段名格式（ANY_前缀或直接字段名）
            linkno = row.get('ANY_LINKNO', row.get('LINKNO', row.get('gridcode')))
            dslink = row.get('ANY_DSLINK', row.get('DSLINKNO', -1)) 
            uslink1 = row.get('ANY_USLINK', row.get('USLINKNO1', -1))
            uslink2 = row.get('ANY_USLI_1', row.get('USLINKNO2', -1))
            stream_order = row.get('ANY_strmOr', row.get('strmOrder', 1))
            area = row['area_km2']
            
            # Add node with attributes
            self.topology_graph.add_node(linkno, 
                                       area=area,
                                       stream_order=stream_order,
                                       index=idx,
                                       merged=False)
            
            # Add downstream edge
            if dslink != -1:
                self.topology_graph.add_edge(linkno, dslink, relation='downstream')
            
            # Add upstream edges
            if uslink1 != -1:
                self.topology_graph.add_edge(uslink1, linkno, relation='upstream')
            if uslink2 != -1:
                self.topology_graph.add_edge(uslink2, linkno, relation='upstream')
        
        print(f"Built topology graph with {self.topology_graph.number_of_nodes()} nodes")
        print(f"and {self.topology_graph.number_of_edges()} edges")
    
    def find_merge_candidates(self, linkno):
        """
        Find potential watersheds to merge with given watershed
        
        Parameters:
        -----------
        linkno : int
            Link number of the target watershed
            
        Returns:
        --------
        list : List of candidate link numbers for merging
        """
        candidates = []
        
        if linkno not in self.topology_graph:
            return candidates
        
        node_data = self.topology_graph.nodes[linkno]
        
        # Only consider small watersheds for merging
        if node_data['area'] >= self.area_threshold:
            return candidates
        
        # Find downstream watershed
        downstream_nodes = [n for n in self.topology_graph.successors(linkno)]
        
        # Find upstream watersheds
        upstream_nodes = [n for n in self.topology_graph.predecessors(linkno)]
        
        # Prioritize merging with upstream watersheds if they are smaller
        for upstream in upstream_nodes:
            upstream_data = self.topology_graph.nodes[upstream]
            if (upstream_data['area'] < self.area_threshold and 
                upstream_data['stream_order'] <= node_data['stream_order'] and
                not upstream_data['merged']):
                candidates.append(upstream)
        
        # Consider downstream if no suitable upstream found
        if not candidates:
            for downstream in downstream_nodes:
                downstream_data = self.topology_graph.nodes[downstream]
                if (downstream_data['stream_order'] >= node_data['stream_order'] and
                    not downstream_data['merged']):
                    candidates.append(downstream)
        
        return candidates
    
    def merge_watersheds(self, primary_linkno, merge_list):
        """
        Merge watersheds and update topology
        
        Parameters:
        -----------
        primary_linkno : int
            Primary watershed to keep
        merge_list : list
            List of watersheds to merge into primary
        """
        primary_idx = self.topology_graph.nodes[primary_linkno]['index']
        
        # Collect geometries and areas to merge
        geometries = [self.watershed_data.iloc[primary_idx].geometry]
        total_area = self.watershed_data.iloc[primary_idx]['area_km2']
        
        for linkno in merge_list:
            idx = self.topology_graph.nodes[linkno]['index']
            geometries.append(self.watershed_data.iloc[idx].geometry)
            total_area += self.watershed_data.iloc[idx]['area_km2']
            
            # Mark as merged
            self.topology_graph.nodes[linkno]['merged'] = True
        
        # Create merged geometry
        from shapely.ops import unary_union
        merged_geometry = unary_union(geometries)
        
        # Update primary watershed
        self.watershed_data.iloc[primary_idx, self.watershed_data.columns.get_loc('geometry')] = merged_geometry
        self.watershed_data.iloc[primary_idx, self.watershed_data.columns.get_loc('area_km2')] = total_area
        
        # Update graph node
        self.topology_graph.nodes[primary_linkno]['area'] = total_area
        
        # Update topology connections
        self._update_topology_after_merge(primary_linkno, merge_list)
        
        return total_area
    
    def _update_topology_after_merge(self, primary_linkno, merged_list):
        """
        Update graph topology after merging watersheds
        """
        for linkno in merged_list:
            # Transfer connections from merged watersheds to primary
            predecessors = list(self.topology_graph.predecessors(linkno))
            successors = list(self.topology_graph.successors(linkno))
            
            for pred in predecessors:
                if pred != primary_linkno and pred not in merged_list:
                    self.topology_graph.add_edge(pred, primary_linkno, relation='upstream')
            
            for succ in successors:
                if succ != primary_linkno and succ not in merged_list:
                    self.topology_graph.add_edge(primary_linkno, succ, relation='downstream')
            
            # Remove merged node
            self.topology_graph.remove_node(linkno)
    
    def run_merging_algorithm(self):
        """
        Execute the complete watershed merging algorithm
        
        Returns:
        --------
        dict : Summary statistics of the merging process
        """
        if self.watershed_data is None:
            raise ValueError("No watershed data loaded")
        
        if self.topology_graph is None:
            self.build_topology_graph()
        
        # Create priority queue: smaller watersheds first
        small_watersheds = []
        for linkno in self.topology_graph.nodes():
            node_data = self.topology_graph.nodes[linkno]
            if node_data['area'] < self.area_threshold:
                small_watersheds.append((node_data['area'], linkno))
        
        small_watersheds.sort()  # Sort by area (smallest first)
        
        merge_count = 0
        total_merged = 0
        
        for area, linkno in small_watersheds:
            # Skip if already merged
            if self.topology_graph.nodes[linkno].get('merged', False):
                continue
            
            # Find merge candidates
            candidates = self.find_merge_candidates(linkno)
            
            if candidates:
                # Select best candidate (prefer smallest that creates viable watershed)
                best_candidate = None
                best_combined_area = 0
                
                for candidate in candidates:
                    candidate_area = self.topology_graph.nodes[candidate]['area']
                    combined_area = area + candidate_area
                    
                    if (combined_area >= self.min_area_threshold and 
                        (best_candidate is None or combined_area < best_combined_area)):
                        best_candidate = candidate
                        best_combined_area = combined_area
                
                if best_candidate:
                    merged_area = self.merge_watersheds(linkno, [best_candidate])
                    merge_count += 1
                    total_merged += 1
                    
                    print(f"Merged watersheds {linkno} and {best_candidate}: "
                          f"{area:.2f}km² + {self.topology_graph.nodes[best_candidate]['area']:.2f}km² "
                          f"= {merged_area:.2f}km²")
        
        # Clean up merged watersheds from dataframe
        merged_indices = []
        for linkno in list(self.topology_graph.nodes()):
            if self.topology_graph.nodes[linkno].get('merged', False):
                idx = self.topology_graph.nodes[linkno]['index']
                merged_indices.append(idx)
        
        # Remove merged watersheds
        self.watershed_data = self.watershed_data.drop(merged_indices).reset_index(drop=True)
        
        stats = {
            'original_count': len(small_watersheds),
            'merges_performed': merge_count,
            'final_count': len(self.watershed_data),
            'watersheds_merged': total_merged,
            'average_final_area': self.watershed_data['area_km2'].mean(),
            'min_area': self.watershed_data['area_km2'].min(),
            'max_area': self.watershed_data['area_km2'].max()
        }
        
        return stats
    
    def save_results(self, output_path):
        """
        Save merged watersheds to shapefile
        
        Parameters:
        -----------
        output_path : str
            Output shapefile path
        """
        try:
            self.watershed_data.to_file(output_path, driver='ESRI Shapefile')
            print(f"Results saved to {output_path}")
            return True
        except Exception as e:
            print(f"Error saving results: {e}")
            return False
    
    def generate_report(self, stats):
        """
        Generate a summary report
        """
        print("\n" + "="*50)
        print("WATERSHED MERGING SUMMARY REPORT")
        print("="*50)
        print(f"Original number of watersheds: {stats['original_count']}")
        print(f"Merging operations performed: {stats['merges_performed']}")
        print(f"Final number of watersheds: {stats['final_count']}")
        print(f"Total watersheds eliminated: {stats['watersheds_merged']}")
        print(f"Reduction percentage: {(stats['watersheds_merged']/stats['original_count']*100):.1f}%")
        print(f"\nArea Statistics (km²):")
        print(f"  Average area: {stats['average_final_area']:.2f}")
        print(f"  Minimum area: {stats['min_area']:.2f}")
        print(f"  Maximum area: {stats['max_area']:.2f}")
        print("="*50)


def main():
    """
    Example usage of the WatershedMerger class
    """
    # Example usage
    merger = WatershedMerger(area_threshold=100.0, min_area_threshold=80.0)
    
    # This would need to be updated with the actual path to your data
    # if merger.load_data("/path/to/your/watershed_data.shp"):
    #     stats = merger.run_merging_algorithm()
    #     merger.generate_report(stats)
    #     merger.save_results("/path/to/output/merged_watersheds.shp")
    
    print("WatershedMerger class initialized successfully!")
    print("Please load your data using merger.load_data(path) to begin processing.")


if __name__ == "__main__":
    main()