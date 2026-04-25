#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHUC (System Hydrologic Unit Code) Encoding System
==================================================

This module implements a hierarchical coding system for Chinese watersheds
based on topological relationships and drainage areas.

Author: Claude Code Assistant  
Date: 2025-08-29
"""

import pandas as pd
import geopandas as gpd
import networkx as nx
from collections import defaultdict, deque
import re


class SHUCEncoder:
    """
    System Hydrologic Unit Code encoder for Chinese watersheds
    """
    
    def __init__(self):
        """
        Initialize SHUC encoder
        """
        self.watershed_data = None
        self.topology_graph = None
        self.encoding_tree = None
        self.major_basins = {
            # Major river basins in China (can be expanded)
            '01': 'Yangtze River Basin',
            '02': 'Yellow River Basin', 
            '03': 'Pearl River Basin',
            '04': 'Songhua River Basin',
            '05': 'Hai River Basin',
            '06': 'Huai River Basin',
            '07': 'Liao River Basin',
            '08': 'Southeast Rivers Basin',
            '09': 'Southwest Rivers Basin',
            '10': 'Northwest Rivers Basin',
            '11': 'Northeast Rivers Basin'
        }
        
    def load_watershed_data(self, shapefile_path):
        """
        Load watershed data from shapefile
        
        Parameters:
        -----------
        shapefile_path : str
            Path to watershed shapefile
        """
        try:
            self.watershed_data = gpd.read_file(shapefile_path)
            print(f"Loaded {len(self.watershed_data)} watershed units")
            return True
        except Exception as e:
            print(f"Error loading watershed data: {e}")
            return False
    
    def build_drainage_hierarchy(self):
        """
        Build hierarchical drainage network from watershed topology
        """
        self.topology_graph = nx.DiGraph()
        
        # Build basic topology graph
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('ANY_LINKNO', row.get('LINKNO', row.get('gridcode')))
            dslink = row.get('ANY_DSLINK', row.get('DSLINKNO', -1))
            uslink1 = row.get('ANY_USLINK', row.get('USLINKNO1', -1)) 
            uslink2 = row.get('ANY_USLI_1', row.get('USLINKNO2', -1))
            stream_order = row.get('ANY_strmOr', row.get('strmOrder', 1))
            area = row.get('area_km2', row.geometry.area / 1000000)
            
            # Add node with attributes
            self.topology_graph.add_node(linkno,
                                       area=area,
                                       stream_order=stream_order,
                                       downstream=dslink if dslink != -1 else None,
                                       upstream=[us for us in [uslink1, uslink2] if us != -1],
                                       index=idx)
            
            # Add edges for topology
            if dslink != -1:
                self.topology_graph.add_edge(linkno, dslink)
            for us in [uslink1, uslink2]:
                if us != -1:
                    self.topology_graph.add_edge(us, linkno)
        
        print(f"Built drainage hierarchy with {self.topology_graph.number_of_nodes()} nodes")
    
    def identify_basin_outlets(self):
        """
        Identify major basin outlet points (nodes with no downstream)
        
        Returns:
        --------
        list : List of outlet node IDs
        """
        outlets = []
        for node in self.topology_graph.nodes():
            if self.topology_graph.out_degree(node) == 0:  # No downstream connections
                node_data = self.topology_graph.nodes[node]
                if node_data['area'] > 1000:  # Major basin threshold
                    outlets.append(node)
        
        # Sort by area (largest first) 
        outlets.sort(key=lambda x: self.topology_graph.nodes[x]['area'], reverse=True)
        return outlets
    
    def generate_basin_codes(self, outlets):
        """
        Generate 2-digit basin codes for major outlets
        
        Parameters:
        -----------
        outlets : list
            List of major basin outlet nodes
            
        Returns:
        --------
        dict : Mapping of outlet nodes to basin codes
        """
        basin_codes = {}
        available_codes = [f"{i:02d}" for i in range(1, 21)]  # 01-20 available
        
        for i, outlet in enumerate(outlets[:20]):  # Max 20 major basins
            basin_codes[outlet] = available_codes[i]
        
        return basin_codes
    
    def trace_upstream_network(self, outlet_node, max_levels=6):
        """
        Trace upstream network from outlet and assign hierarchical codes
        
        Parameters:
        -----------
        outlet_node : int
            Starting outlet node
        max_levels : int
            Maximum coding levels (default 6 for 12-digit codes)
            
        Returns:
        --------
        dict : Node to code mapping for this basin
        """
        codes = {}
        
        # BFS traversal upstream with level tracking
        queue = deque([(outlet_node, 1, "")])  # (node, level, code_prefix)
        visited = {outlet_node}
        
        while queue:
            current_node, level, code_prefix = queue.popleft()
            
            if level > max_levels:
                continue
                
            # Get upstream nodes
            upstream_nodes = list(self.topology_graph.predecessors(current_node))
            
            if not upstream_nodes:  # Headwater
                if code_prefix:
                    codes[current_node] = code_prefix.ljust(max_levels * 2, '0')
                continue
            
            # Sort upstream nodes by area and stream order
            upstream_nodes.sort(key=lambda x: (
                -self.topology_graph.nodes[x]['stream_order'],
                -self.topology_graph.nodes[x]['area']
            ))
            
            # Assign sequential codes to upstream nodes
            for i, upstream_node in enumerate(upstream_nodes[:99], 1):  # Max 99 per level
                if upstream_node not in visited:
                    visited.add(upstream_node)
                    new_code = code_prefix + f"{i:02d}"
                    codes[upstream_node] = new_code
                    queue.append((upstream_node, level + 1, new_code))
        
        return codes
    
    def generate_full_shuc_codes(self):
        """
        Generate complete SHUC codes for all watersheds
        
        Returns:
        --------
        dict : Complete node to SHUC code mapping
        """
        if self.topology_graph is None:
            self.build_drainage_hierarchy()
        
        # Identify major basin outlets
        outlets = self.identify_basin_outlets()
        basin_codes = self.generate_basin_codes(outlets)
        
        all_codes = {}
        unassigned_nodes = set(self.topology_graph.nodes())
        
        # Process each major basin
        for outlet, basin_code in basin_codes.items():
            print(f"Processing basin {basin_code} from outlet {outlet}")
            
            # Find all nodes in this basin (upstream from outlet)
            basin_nodes = set()
            
            def collect_upstream(node):
                basin_nodes.add(node)
                for upstream in self.topology_graph.predecessors(node):
                    if upstream not in basin_nodes:
                        collect_upstream(upstream)
            
            collect_upstream(outlet)
            
            # Generate hierarchical codes for this basin
            basin_level_codes = self.trace_upstream_network(outlet, max_levels=5)
            
            # Combine basin code with level codes
            for node, level_code in basin_level_codes.items():
                full_code = basin_code + level_code.ljust(10, '0')  # 2+10 = 12 digits
                all_codes[node] = full_code
                unassigned_nodes.discard(node)
        
        # Handle unassigned nodes (small isolated basins)
        remaining_outlets = [n for n in unassigned_nodes 
                           if self.topology_graph.out_degree(n) == 0]
        
        next_basin_code = 21
        for outlet in remaining_outlets:
            if next_basin_code > 99:  # Max 99 basins
                break
                
            basin_code = f"{next_basin_code:02d}"
            basin_level_codes = self.trace_upstream_network(outlet, max_levels=5)
            
            for node, level_code in basin_level_codes.items():
                if node in unassigned_nodes:
                    full_code = basin_code + level_code.ljust(10, '0')
                    all_codes[node] = full_code
                    unassigned_nodes.discard(node)
            
            next_basin_code += 1
        
        # Final fallback for any remaining nodes
        for i, node in enumerate(unassigned_nodes, 1):
            all_codes[node] = f"99{i:010d}"  # Emergency codes starting with 99
        
        return all_codes
    
    def validate_shuc_codes(self, codes):
        """
        Validate generated SHUC codes for uniqueness and format
        
        Parameters:
        -----------
        codes : dict
            Node to SHUC code mapping
            
        Returns:
        --------
        dict : Validation results
        """
        results = {
            'total_codes': len(codes),
            'unique_codes': len(set(codes.values())),
            'duplicate_codes': 0,
            'invalid_format': 0,
            'valid_codes': 0
        }
        
        # Check for duplicates
        code_counts = defaultdict(int)
        for code in codes.values():
            code_counts[code] += 1
        
        results['duplicate_codes'] = sum(1 for count in code_counts.values() if count > 1)
        
        # Check format (12 digits)
        for node, code in codes.items():
            if not re.match(r'^\d{12}$', code):
                results['invalid_format'] += 1
            else:
                results['valid_codes'] += 1
        
        return results
    
    def apply_shuc_codes_to_data(self, codes):
        """
        Apply SHUC codes to watershed geodataframe
        
        Parameters:
        -----------
        codes : dict
            Node to SHUC code mapping
        """
        # Create SHUC code column
        shuc_codes = []
        for idx, row in self.watershed_data.iterrows():
            linkno = row.get('ANY_LINKNO', row.get('LINKNO', row.get('gridcode')))
            shuc_code = codes.get(linkno, '000000000000')  # Default if missing
            shuc_codes.append(shuc_code)
        
        self.watershed_data['SHUC_CODE'] = shuc_codes
        
        # Add hierarchical level columns
        self.watershed_data['BASIN_CODE'] = self.watershed_data['SHUC_CODE'].str[:2]
        self.watershed_data['LEVEL2_CODE'] = self.watershed_data['SHUC_CODE'].str[:4] 
        self.watershed_data['LEVEL3_CODE'] = self.watershed_data['SHUC_CODE'].str[:6]
        self.watershed_data['LEVEL4_CODE'] = self.watershed_data['SHUC_CODE'].str[:8]
        self.watershed_data['LEVEL5_CODE'] = self.watershed_data['SHUC_CODE'].str[:10]
        self.watershed_data['LEVEL6_CODE'] = self.watershed_data['SHUC_CODE'].str[:12]
        
        print(f"Applied SHUC codes to {len(self.watershed_data)} watersheds")
    
    def export_results(self, output_path, format='shapefile'):
        """
        Export results to file
        
        Parameters:
        -----------
        output_path : str
            Output file path
        format : str
            Output format ('shapefile', 'geojson', 'csv')
        """
        try:
            if format.lower() == 'shapefile':
                self.watershed_data.to_file(output_path, driver='ESRI Shapefile')
            elif format.lower() == 'geojson':
                self.watershed_data.to_file(output_path, driver='GeoJSON')
            elif format.lower() == 'csv':
                # Export attribute table only
                self.watershed_data.drop('geometry', axis=1).to_csv(output_path, index=False)
            
            print(f"Results exported to {output_path}")
            return True
        except Exception as e:
            print(f"Error exporting results: {e}")
            return False
    
    def generate_encoding_report(self, codes, validation_results):
        """
        Generate comprehensive encoding report
        """
        print("\n" + "="*60)
        print("SHUC ENCODING SYSTEM REPORT")
        print("="*60)
        
        print(f"Total watersheds processed: {len(self.watershed_data)}")
        print(f"SHUC codes generated: {validation_results['total_codes']}")
        print(f"Unique codes: {validation_results['unique_codes']}")
        print(f"Valid format codes: {validation_results['valid_codes']}")
        print(f"Invalid format codes: {validation_results['invalid_format']}")
        print(f"Duplicate codes: {validation_results['duplicate_codes']}")
        
        # Basin distribution
        basin_distribution = defaultdict(int)
        for code in codes.values():
            basin_code = code[:2]
            basin_distribution[basin_code] += 1
        
        print(f"\nBasin Distribution (Top 10):")
        for basin_code, count in sorted(basin_distribution.items(), 
                                      key=lambda x: x[1], reverse=True)[:10]:
            basin_name = self.major_basins.get(basin_code, f"Basin {basin_code}")
            print(f"  {basin_code} ({basin_name}): {count} watersheds")
        
        print("="*60)


def main():
    """
    Example usage of SHUCEncoder
    """
    encoder = SHUCEncoder()
    
    print("SHUC Encoder initialized successfully!")
    print("Usage:")
    print("1. Load data: encoder.load_watershed_data('path/to/watersheds.shp')")
    print("2. Generate codes: codes = encoder.generate_full_shuc_codes()")
    print("3. Apply codes: encoder.apply_shuc_codes_to_data(codes)")
    print("4. Export: encoder.export_results('output/shuc_watersheds.shp')")


if __name__ == "__main__":
    main()