#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流域数据预处理工具
==================

在运行SHUC编码之前，对原始流域数据进行预处理：
- 几何修复
- 字段标准化
- 坐标系转换
- 数据质量检查

Usage:
    python preprocess_watersheds.py --input raw_watersheds.shp --output processed_watersheds.shp
    python preprocess_watersheds.py --input MERIT_basin.tif --output basins.shp
"""

import argparse
import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import shape
from shapely.validation import make_valid
import rasterio
from rasterio.features import shapes
import logging


def setup_logger():
    logger = logging.getLogger('preprocess')
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(messages'))
    logger.addHandler(handler)
    return logger


def preprocess_shapefile(input_file, output_file, target_crs=None):
    """预处理Shapefile流域数据"""
    logger = setup_logger()
    logger.info(f"读取流域数据: {input_file}")
    
    gdf = gpd.read_file(input_file)
    logger.info(f"  流域数: {len(gdf)}")
    logger.info(f"  字段: {list(gdf.columns)}")
    logger.info(f"  CRS: {gdf.crs}")
    
    # 1. 修复无效几何
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        logger.info(f"  修复 {invalid.sum()} 个无效几何")
        gdf.loc[invalid, 'geometry'] = gdf.loc[invalid, 'geometry'].apply(make_valid)
    
    # 2. 标准化字段名
    field_mapping = {}
    
    # 面积字段
    area_cols = [c for c in gdf.columns if 'area' in c.lower() or 'Area' in c]
    if 'area_km2' not in gdf.columns:
        if area_cols:
            field_mapping[area_cols[0]] = 'area_km2'
            logger.info(f"  重命名面积字段: {area_cols[0]} -> area_km2")
        else:
            gdf['area_km2'] = gdf.geometry.area / 1_000_000
            logger.info("  计算面积字段: area_km2")
    
    # 拓扑字段
    if 'LINKNO' not in gdf.columns:
        if 'Id' in gdf.columns:
            field_mapping['Id'] = 'LINKNO'
        elif 'FID' in gdf.columns:
            field_mapping['FID'] = 'LINKNO'
        else:
            gdf['LINKNO'] = range(1, len(gdf) + 1)
            logger.info("  创建LINKNO字段")
    
    if 'DSLINKNO' not in gdf.columns and 'DSLINKNO1' not in gdf.columns:
        if 'DownStream' in gdf.columns:
            field_mapping['DownStream'] = 'DSLINKNO'
        elif 'NextDownID' in gdf.columns:
            field_mapping['NextDownID'] = 'DSLINKNO'
        else:
            logger.warning("  缺少下游拓扑字段，合并策略将受限")
    
    if field_mapping:
        gdf = gdf.rename(columns=field_mapping)
    
    # 3. 转换坐标系
    if target_crs:
        gdf = gdf.to_crs(target_crs)
        logger.info(f"  坐标系转换为: {target_crs}")
    
    # 4. 数据清理
    gdf = gdf.dropna(subset=['geometry'])
    
    logger.info(f"处理后流域数: {len(gdf)}")
    logger.info(f"保存到: {output_file}")
    gdf.to_file(output_file)
    
    return gdf


def preprocess_raster_basins(input_raster, output_file):
    """预处理MERIT Basin栅格数据"""
    logger = setup_logger()
    logger.info(f"读取栅格流域: {input_raster}")
    
    with rasterio.open(input_raster) as src:
        data = src.read(1)
        transform = src.transform
        crs = src.crs
        
        nodata = src.nodata if src.nodata else 0
        mask = (data != nodata) & (data != 0)
        
        unique_basins = np.unique(data)
        unique_basins = unique_basins[(unique_basins != nodata) & (unique_basins != 0)]
        
        logger.info(f"  唯一流域ID: {len(unique_basins)}")
        
        results = []
        for geom, value in shapes(data.astype(np.int32), mask=mask, transform=transform):
            if value != 0:
                results.append({
                    'geometry': shape(geom),
                    'basin_id': int(value),
                })
        
        gdf = gpd.GeoDataFrame(results, crs=crs)
        gdf['LINKNO'] = gdf['basin_id']
        gdf['area_km2'] = gdf.geometry.area / 1_000_000
        
        logger.info(f"矢量化完成: {len(gdf)} 个流域")
        logger.info(f"保存到: {output_file}")
        gdf.to_file(output_file)
    
    return gdf


def main():
    parser = argparse.ArgumentParser(description='流域数据预处理')
    parser.add_argument('--input', required=True, help='输入文件')
    parser.add_argument('--output', required=True, help='输出文件')
    parser.add_argument('--crs', type=str, default=None, help='目标坐标系')
    parser.add_argument('--from-raster', action='store_true', help='从栅格数据转换')
    
    args = parser.parse_args()
    
    if args.from_raster:
        preprocess_raster_basins(args.input, args.output)
    else:
        preprocess_shapefile(args.input, args.output, target_crs=args.crs)


if __name__ == '__main__':
    main()
