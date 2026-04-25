#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHUC Experiment Runner
======================

Main script for running complete SHUC watershed processing experiments.
Integrates merging, encoding, and validation workflows.

Author: Claude Code Assistant
Date: 2025-08-29
"""

import os
import sys
import time
import json
from datetime import datetime
import pandas as pd
import geopandas as gpd

# Import our custom modules
from improved_watershed_merger import WatershedMerger
from shuc_encoder import SHUCEncoder
from shuc_validator import SHUCValidator


class SHUCExperimentRunner:
    """
    Main experiment runner for SHUC processing pipeline
    """
    
    def __init__(self, config_file=None):
        """
        Initialize experiment runner
        
        Parameters:
        -----------
        config_file : str, optional
            Path to configuration file
        """
        self.config = self._load_config(config_file)
        self.results = {}
        self.start_time = None
        
    def _load_config(self, config_file):
        """
        Load configuration settings
        """
        default_config = {
            'input_data': {
                'watershed_shapefile': None,
                'river_shapefile': None,
                'dem_file': None
            },
            'processing': {
                'area_threshold': 100.0,
                'min_area_threshold': 80.0,
                'max_stream_order': 6,
                'enable_merging': True,
                'enable_encoding': True,
                'enable_validation': True
            },
            'output': {
                'base_directory': './shuc_results',
                'create_visualizations': True,
                'export_formats': ['shapefile', 'geojson']
            },
            'validation': {
                'topology_check': True,
                'code_validation': True,
                'area_validation': True,
                'geometry_validation': True
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                # Merge with defaults
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
                print("Using default configuration")
        
        return default_config
    
    def setup_output_directories(self):
        """
        Create output directory structure
        """
        base_dir = self.config['output']['base_directory']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.output_dir = os.path.join(base_dir, f"shuc_experiment_{timestamp}")
        
        directories = [
            self.output_dir,
            os.path.join(self.output_dir, 'merged_watersheds'),
            os.path.join(self.output_dir, 'encoded_watersheds'), 
            os.path.join(self.output_dir, 'validation_results'),
            os.path.join(self.output_dir, 'visualizations'),
            os.path.join(self.output_dir, 'reports')
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        print(f"Created output directories in: {self.output_dir}")
    
    def run_merging_experiment(self, input_shapefile):
        """
        Run watershed merging experiment
        
        Parameters:
        -----------
        input_shapefile : str
            Path to input watershed shapefile
            
        Returns:
        --------
        str : Path to merged watersheds output
        """
        print("\n" + "="*50)
        print("STEP 1: WATERSHED MERGING")
        print("="*50)
        
        merger = WatershedMerger(
            area_threshold=self.config['processing']['area_threshold'],
            min_area_threshold=self.config['processing']['min_area_threshold']
        )
        
        # Load data
        if not merger.load_data(input_shapefile):
            raise Exception("Failed to load watershed data for merging")
        
        # Run merging algorithm
        merge_stats = merger.run_merging_algorithm()
        merger.generate_report(merge_stats)
        
        # Save results
        merged_output = os.path.join(self.output_dir, 'merged_watersheds', 'merged_watersheds.shp')
        merger.save_results(merged_output)
        
        self.results['merging'] = {
            'statistics': merge_stats,
            'output_file': merged_output,
            'processing_time': time.time() - self.step_start_time
        }
        
        return merged_output
    
    def run_encoding_experiment(self, input_shapefile):
        """
        Run SHUC encoding experiment
        
        Parameters:
        -----------
        input_shapefile : str
            Path to input watershed shapefile
            
        Returns:
        --------
        str : Path to encoded watersheds output
        """
        print("\n" + "="*50)
        print("STEP 2: SHUC ENCODING")
        print("="*50)
        
        encoder = SHUCEncoder()
        
        # Load data
        if not encoder.load_watershed_data(input_shapefile):
            raise Exception("Failed to load watershed data for encoding")
        
        # Generate SHUC codes
        codes = encoder.generate_full_shuc_codes()
        validation_results = encoder.validate_shuc_codes(codes)
        
        # Apply codes to data
        encoder.apply_shuc_codes_to_data(codes)
        encoder.generate_encoding_report(codes, validation_results)
        
        # Save results
        encoded_output = os.path.join(self.output_dir, 'encoded_watersheds', 'shuc_watersheds.shp')
        encoder.export_results(encoded_output, format='shapefile')
        
        # Also export as GeoJSON if requested
        if 'geojson' in self.config['output']['export_formats']:
            geojson_output = os.path.join(self.output_dir, 'encoded_watersheds', 'shuc_watersheds.geojson')
            encoder.export_results(geojson_output, format='geojson')
        
        self.results['encoding'] = {
            'total_codes': len(codes),
            'validation_results': validation_results,
            'output_file': encoded_output,
            'processing_time': time.time() - self.step_start_time
        }
        
        return encoded_output
    
    def run_validation_experiment(self, input_shapefile):
        """
        Run validation experiment
        
        Parameters:
        -----------
        input_shapefile : str
            Path to SHUC-encoded watershed shapefile
        """
        print("\n" + "="*50)
        print("STEP 3: VALIDATION & QUALITY ASSURANCE")
        print("="*50)
        
        validator = SHUCValidator()
        
        # Load data
        if not validator.load_data(input_shapefile):
            raise Exception("Failed to load watershed data for validation")
        
        # Run comprehensive validation
        validation_results = validator.run_comprehensive_validation()
        validator.generate_validation_report(validation_results)
        
        # Create visualizations if enabled
        if self.config['output']['create_visualizations']:
            viz_dir = os.path.join(self.output_dir, 'visualizations')
            validator.create_validation_visualizations(viz_dir)
        
        # Export validation report
        report_path = os.path.join(self.output_dir, 'validation_results', 'validation_report.json')
        validator.export_validation_report(report_path, format='json')
        
        self.results['validation'] = {
            'results': validation_results,
            'report_file': report_path,
            'processing_time': time.time() - self.step_start_time
        }
        
        return validation_results
    
    def run_complete_experiment(self, watershed_shapefile):
        """
        Run complete SHUC processing experiment
        
        Parameters:
        -----------
        watershed_shapefile : str
            Path to input watershed shapefile
        """
        self.start_time = time.time()
        
        print("="*70)
        print("SHUC COMPLETE PROCESSING EXPERIMENT")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Input file: {watershed_shapefile}")
        print(f"Output directory: {self.output_dir}")
        
        try:
            current_shapefile = watershed_shapefile
            
            # Step 1: Watershed Merging
            if self.config['processing']['enable_merging']:
                self.step_start_time = time.time()
                current_shapefile = self.run_merging_experiment(current_shapefile)
            
            # Step 2: SHUC Encoding  
            if self.config['processing']['enable_encoding']:
                self.step_start_time = time.time()
                current_shapefile = self.run_encoding_experiment(current_shapefile)
            
            # Step 3: Validation
            if self.config['processing']['enable_validation']:
                self.step_start_time = time.time()
                self.run_validation_experiment(current_shapefile)
            
            # Generate final summary report
            self.generate_final_report()
            
            print("\n" + "="*70)
            print("EXPERIMENT COMPLETED SUCCESSFULLY!")
            print("="*70)
            
        except Exception as e:
            print(f"\nEXPERIMENT FAILED: {e}")
            print("Check the error logs and input data.")
            raise
    
    def generate_final_report(self):
        """
        Generate comprehensive final report
        """
        total_time = time.time() - self.start_time
        
        report = {
            'experiment_info': {
                'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_processing_time': total_time,
                'output_directory': self.output_dir,
                'configuration': self.config
            },
            'results': self.results
        }
        
        # Save detailed report
        report_file = os.path.join(self.output_dir, 'reports', 'experiment_report.json')
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate summary report
        summary_file = os.path.join(self.output_dir, 'reports', 'experiment_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("SHUC EXPERIMENT SUMMARY REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Experiment completed in {total_time:.2f} seconds\n")
            f.write(f"Output directory: {self.output_dir}\n\n")
            
            if 'merging' in self.results:
                merge_stats = self.results['merging']['statistics']
                f.write("MERGING RESULTS:\n")
                f.write(f"  Original watersheds: {merge_stats.get('original_count', 'N/A')}\n")
                f.write(f"  Final watersheds: {merge_stats.get('final_count', 'N/A')}\n")
                f.write(f"  Merges performed: {merge_stats.get('merges_performed', 'N/A')}\n")
                f.write(f"  Processing time: {self.results['merging']['processing_time']:.2f}s\n\n")
            
            if 'encoding' in self.results:
                f.write("ENCODING RESULTS:\n")
                f.write(f"  SHUC codes generated: {self.results['encoding']['total_codes']}\n")
                f.write(f"  Processing time: {self.results['encoding']['processing_time']:.2f}s\n\n")
            
            if 'validation' in self.results:
                val_results = self.results['validation']['results']
                f.write("VALIDATION RESULTS:\n")
                f.write(f"  Overall status: {'PASS' if val_results.get('overall_valid') else 'FAIL'}\n")
                f.write(f"  Processing time: {self.results['validation']['processing_time']:.2f}s\n\n")
        
        print(f"\nFinal reports saved:")
        print(f"  Detailed: {report_file}")
        print(f"  Summary: {summary_file}")


def create_sample_config():
    """
    Create a sample configuration file
    """
    config = {
        "input_data": {
            "watershed_shapefile": "/path/to/your/watershed_data.shp",
            "river_shapefile": "/path/to/your/river_data.shp"
        },
        "processing": {
            "area_threshold": 100.0,
            "min_area_threshold": 80.0,
            "enable_merging": True,
            "enable_encoding": True,
            "enable_validation": True
        },
        "output": {
            "base_directory": "./shuc_results",
            "create_visualizations": True,
            "export_formats": ["shapefile", "geojson"]
        }
    }
    
    with open('shuc_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("Sample configuration saved to: shuc_config.json")
    print("Edit this file with your specific paths and settings.")


def main():
    """
    Main entry point for SHUC experiments
    """
    if len(sys.argv) < 2:
        print("SHUC Experiment Runner")
        print("Usage:")
        print("  python shuc_experiment_runner.py <watershed_shapefile> [config_file]")
        print("  python shuc_experiment_runner.py --create-config")
        print("\nExamples:")
        print("  python shuc_experiment_runner.py /path/to/watersheds.shp")
        print("  python shuc_experiment_runner.py /path/to/watersheds.shp shuc_config.json")
        return
    
    if sys.argv[1] == '--create-config':
        create_sample_config()
        return
    
    watershed_file = sys.argv[1]
    config_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(watershed_file):
        print(f"Error: Watershed file not found: {watershed_file}")
        return
    
    # Initialize and run experiment
    runner = SHUCExperimentRunner(config_file)
    runner.setup_output_directories()
    runner.run_complete_experiment(watershed_file)


if __name__ == "__main__":
    main()