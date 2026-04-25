#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MERIT Hydro → SHUC 端到端处理Pipeline (v4.0)
================================================

完整的数据处理流水线，支持两条路线:

路线A: MERIT Hydro 栅格路线（原有）
  Phase 1: 数据准备（瓦片拼接/裁剪）
  Phase 2: 流域提取（栅格矢量化）
  Phase 3: SHUC编码（合并+编码+验证）
  Phase 4: 结果输出

路线B: MERIT-Basins 向量路线（v4.0新增）
  Phase 1: 加载 MERIT-Basins cat_*/riv_* 向量数据
  Phase 2: 构建拓扑图（NextDownID + up1-up4）
  Phase 3: SHUC编码（合并+编码+验证）
  Phase 4: 结果输出

三层混合框架（v4.0+）:
  MERIT-Basins (拓扑骨架) + MERIT Hydro (栅格约束) + DEM (局部精化)

Usage:
    # 路线A: MERIT Hydro 栅格路线
    python merit_to_shuc_pipeline.py --basin yangtze --merit-dir ../../05_DATA/raw/merit_hydro

    # 路线B: MERIT-Basins 向量路线
    python merit_to_shuc_pipeline.py --route merit-basins --basin yangtze --merit-basins-dir /path/to/merit_basins

依赖:
    - GDAL (gdalwarp, gdal_merge.py) -- 仅路线A需要
    - Python: rasterio, geopandas, numpy, networkx, pyproj
    - SHUC核心系统 (01_CORE_SYSTEM/src/)

Version: 4.0.0
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import logging

import numpy as np
import geopandas as gpd
from shapely.geometry import box
from pyproj import Geod

# 添加SHUC核心系统到路径
SHUC_ROOT = Path(__file__).resolve().parent.parent.parent / '01_CORE_SYSTEM'
sys.path.insert(0, str(SHUC_ROOT / 'src'))

from download_merit_hydro import BASIN_BOUNDS
from merit_basins_loader import MERITBasinsLoader

# 全局 Geod 实例
_GEOD = Geod(ellps='WGS84')


def setup_pipeline_logger(output_dir):
    """设置Pipeline日志"""
    log_dir = Path(output_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger('merit_pipeline')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s',
                                  datefmt='%H:%M:%S')

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = logging.FileHandler(log_dir / 'pipeline_log.txt', encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def _compute_geod_area(geometry) -> float:
    """计算精确测地面积 (km2)"""
    if geometry is None or geometry.is_empty:
        return 0.0
    try:
        if geometry.geom_type == 'Polygon':
            area_m2, _ = _GEOD.geometry_area_perimeter(geometry)
            return abs(area_m2) / 1_000_000
        elif geometry.geom_type == 'MultiPolygon':
            total = 0.0
            for poly in geometry.geoms:
                a, _ = _GEOD.geometry_area_perimeter(poly)
                total += abs(a)
            return total / 1_000_000
        return 0.0
    except Exception:
        return abs(geometry.area) / 1_000_000


class MERITPipeline:
    """MERIT Hydro / MERIT-Basins 数据处理Pipeline (v4.0)"""

    def __init__(self, basin_key, merit_dir, output_dir, logger,
                 route='merit-hydro', merit_basins_dir=None):
        self.basin_key = basin_key
        self.bounds = BASIN_BOUNDS[basin_key]
        self.merit_dir = Path(merit_dir) if merit_dir else None
        self.output_dir = Path(output_dir)
        self.logger = logger
        self.route = route  # 'merit-hydro' 或 'merit-basins'
        self.merit_basins_dir = Path(merit_basins_dir) if merit_basins_dir else None

        # MERIT-Basins 加载器
        self.merit_basins_loader = None

        # 流域范围
        self.lat_min = self.bounds['lat_min'] - self.bounds['buffer_deg']
        self.lat_max = self.bounds['lat_max'] + self.bounds['buffer_deg']
        self.lon_min = self.bounds['lon_min'] - self.bounds['buffer_deg']
        self.lon_max = self.bounds['lon_max'] + self.bounds['buffer_deg']

        # 目录结构
        self.mosaic_dir = self.output_dir / '01_mosaic'
        self.clipped_dir = self.output_dir / '02_clipped'
        self.network_dir = self.output_dir / '03_network'
        self.watershed_dir = self.output_dir / '04_watersheds'
        self.shuc_dir = self.output_dir / '05_shuc'

        # 创建目录
        for d in [self.mosaic_dir, self.clipped_dir, self.network_dir,
                  self.watershed_dir, self.shuc_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Pipeline初始化: {self.bounds['name_cn']} ({basin_key})")
        self.logger.info(f"路线: {self.route}")
        self.logger.info(f"范围: {self.lat_min}~{self.lat_max}N, "
                        f"{self.lon_min}~{self.lon_max}E")

    # ==================== 路线A: MERIT Hydro 栅格处理 ====================

    def run_phase1_mosaic(self):
        """Phase 1: 拼接MERIT瓦片"""
        import rasterio
        from rasterio.merge import merge as rasterio_merge

        self.logger.info("=" * 50)
        self.logger.info("Phase 1: 数据拼接 (Mosaic)")
        self.logger.info("=" * 50)

        for layer in ['dir', 'upa', 'bas']:
            self.logger.info(f"拼接 {layer} 图层...")

            if self.merit_dir is None:
                self.logger.warning("未指定 MERIT Hydro 数据目录")
                continue

            tile_dir = self.merit_dir / self.basin_key / layer
            if not tile_dir.exists():
                self.logger.warning(f"瓦片目录不存在: {tile_dir}")
                self.logger.warning("请先运行 download_merit_hydro.py 下载数据")
                continue

            tif_files = sorted(tile_dir.glob('*.tif'))
            if not tif_files:
                self.logger.warning(f"未找到 {layer} 的tif文件")
                continue

            self.logger.info(f"  找到 {len(tif_files)} 个瓦片")

            output_file = self.mosaic_dir / f'{self.basin_key}_{layer}_mosaic.tif'
            self._mosaic_tiles(tif_files, output_file)
            self.logger.info(f"  拼接完成: {output_file}")

        return True

    def _mosaic_tiles(self, tif_files, output_file):
        """使用 rasterio 拼接瓦片"""
        import rasterio
        from rasterio.merge import merge as rasterio_merge

        src_files_to_mosaic = []
        for fp in tif_files:
            src = rasterio.open(fp)
            src_files_to_mosaic.append(src)

        mosaic, out_trans = rasterio_merge(src_files_to_mosaic)

        out_meta = src_files_to_mosaic[0].meta.copy()
        out_meta.update({
            'driver': 'GTiff',
            'height': mosaic.shape[1],
            'width': mosaic.shape[2],
            'transform': out_trans,
            'compress': 'lzw',
        })

        with rasterio.open(output_file, 'w', **out_meta) as dest:
            dest.write(mosaic)

        for src in src_files_to_mosaic:
            src.close()

    def run_phase2_clip(self):
        """Phase 2: 裁剪到流域边界"""
        import rasterio

        self.logger.info("=" * 50)
        self.logger.info("Phase 2: 裁剪到流域边界")
        self.logger.info("=" * 50)

        for layer in ['dir', 'upa', 'bas']:
            mosaic_file = self.mosaic_dir / f'{self.basin_key}_{layer}_mosaic.tif'
            if not mosaic_file.exists():
                self.logger.warning(f"跳过 {layer}: 拼接文件不存在")
                continue

            output_file = self.clipped_dir / f'{self.basin_key}_{layer}_clipped.tif'
            self._clip_raster(mosaic_file, output_file)
            self.logger.info(f"  裁剪完成: {output_file}")

        return True

    def _clip_raster(self, input_file, output_file):
        """裁剪栅格到边界"""
        import rasterio

        with rasterio.open(input_file) as src:
            window = rasterio.windows.from_bounds(
                self.lon_min, self.lat_min, self.lon_max, self.lat_max,
                src.transform
            )

            data = src.read(window=window)
            transform = src.window_transform(window)

            meta = src.meta.copy()
            meta.update({
                'height': data.shape[1],
                'width': data.shape[2],
                'transform': transform,
                'compress': 'lzw',
            })

            with rasterio.open(output_file, 'w', **meta) as dst:
                dst.write(data)

    def run_phase3_extract_network(self):
        """
        Phase 3: 从MERIT流向/累积量提取河网和流域
        """
        import rasterio
        from rasterio.features import shapes
        from shapely.geometry import shape

        self.logger.info("=" * 50)
        self.logger.info("Phase 3: 河网和流域提取")
        self.logger.info("=" * 50)

        upa_file = self.clipped_dir / f'{self.basin_key}_upa_clipped.tif'
        bas_file = self.clipped_dir / f'{self.basin_key}_bas_clipped.tif'

        # 策略A: 使用MERIT basin ID直接矢量化
        if bas_file.exists():
            self.logger.info("使用MERIT Basin ID提取初始流域...")
            watershed_vector = self._vectorize_basin_ids(bas_file)

            if watershed_vector is not None:
                output_file = self.watershed_dir / f'{self.basin_key}_initial_watersheds.shp'
                watershed_vector.to_file(output_file)
                self.logger.info(f"  初始流域数: {len(watershed_vector)}")
                self.logger.info(f"  保存到: {output_file}")

        # 策略B: 使用累积量阈值提取河网
        if upa_file.exists():
            self.logger.info("提取河网...")
            for threshold_km2 in [10, 25, 50, 100]:
                stream_vector = self._extract_stream_network(upa_file, threshold_km2)
                if stream_vector is not None and len(stream_vector) > 0:
                    output_file = (self.network_dir /
                                  f'{self.basin_key}_streams_{threshold_km2}km2.shp')
                    stream_vector.to_file(output_file)
                    self.logger.info(f"  阈值{threshold_km2}km²: "
                                   f"{len(stream_vector)} 个河段")

        return True

    def _vectorize_basin_ids(self, bas_file):
        """将MERIT Basin ID栅格矢量化为流域多边形"""
        import rasterio
        from rasterio.features import shapes
        from shapely.geometry import shape

        self.logger.info(f"  矢量化 basin IDs: {bas_file}")

        with rasterio.open(bas_file) as src:
            data = src.read(1)
            transform = src.transform
            crs = src.crs

            nodata = src.nodata if src.nodata else 0
            unique_basins = np.unique(data)
            unique_basins = unique_basins[
                (unique_basins != nodata) & (unique_basins != 0)
            ]

            self.logger.info(f"  唯一流域ID数: {len(unique_basins)}")

            mask = (data != nodata) & (data != 0)

            results = []
            for geom, value in shapes(
                data.astype(np.int32), mask=mask, transform=transform
            ):
                if value != 0:
                    results.append({
                        'geometry': shape(geom),
                        'basin_id': int(value),
                    })

            if not results:
                self.logger.warning("  未提取到流域")
                return None

            gdf = gpd.GeoDataFrame(results, crs=crs)
            # 使用精确测地面积（替代不准确的 WGS84 度坐标面积）
            gdf['area_km2'] = gdf.geometry.apply(_compute_geod_area)

            return gdf

    def _extract_stream_network(self, upa_file, threshold_km2):
        """基于累积量阈值提取河网"""
        import rasterio
        from rasterio.features import shapes
        from shapely.geometry import shape

        with rasterio.open(upa_file) as src:
            data = src.read(1)
            transform = src.transform
            crs = src.crs

            stream_mask = (data >= threshold_km2) & (data > 0)

            if not stream_mask.any():
                return None

            results = []
            for geom, value in shapes(
                stream_mask.astype(np.int8),
                mask=stream_mask,
                transform=transform
            ):
                if value == 1:
                    results.append({'geometry': shape(geom)})

            if not results:
                return None

            return gpd.GeoDataFrame(results, crs=crs)

    # ==================== 路线B: MERIT-Basins 向量处理 ====================

    def run_phase2b_merit_basins(self, bounds=None):
        """
        Phase 2B: MERIT-Basins 向量路线

        直接加载 MERIT-Basins 向量数据，构建拓扑图。
        """
        self.logger.info("=" * 50)
        self.logger.info("Phase 2B: MERIT-Basins 向量数据加载")
        self.logger.info("=" * 50)

        if self.merit_basins_dir is None or not self.merit_basins_dir.exists():
            self.logger.error(
                f"MERIT-Basins 数据目录不存在: {self.merit_basins_dir}"
            )
            return False

        self.merit_basins_loader = MERITBasinsLoader()

        if bounds is None:
            bounds = (self.lon_min, self.lat_min, self.lon_max, self.lat_max)

        # 查找 catchment 数据
        cat_dir = self.merit_basins_dir / 'cat'
        if not cat_dir.exists():
            cat_dir = self.merit_basins_dir

        # 加载 catchments
        try:
            catchments = self.merit_basins_loader.load_catchments(
                str(cat_dir), bounds=bounds
            )
            self.logger.info(f"  加载 {len(catchments)} 个 catchment 单元")
        except Exception as e:
            self.logger.error(f"加载 catchment 失败: {e}")
            return False

        # 构建拓扑
        topology = self.merit_basins_loader.build_topology()
        self.logger.info(
            f"  拓扑: {topology['total_catchments']} 节点, "
            f"{len(topology['outlets'])} 出口, "
            f"环={topology['has_cycles']}"
        )

        # 保存初始流域数据
        output_file = (self.watershed_dir /
                      f'{self.basin_key}_merit_basins_watersheds.shp')
        catchments.to_file(output_file)
        self.logger.info(f"  保存到: {output_file}")

        # 加载 rivers（可选）
        riv_dir = self.merit_basins_dir / 'riv'
        if riv_dir.exists():
            try:
                rivers = self.merit_basins_loader.load_rivers(
                    str(riv_dir), bounds=bounds
                )
                self.logger.info(f"  加载 {len(rivers)} 条河段")
            except Exception as e:
                self.logger.warning(f"加载 river 数据失败（非致命）: {e}")

        return True

    # ==================== Phase 4: SHUC编码（共用） ====================

    def run_phase4_shuc(self, config_path=None, use_merit_basins=False):
        """Phase 4: 运行SHUC编码系统"""
        self.logger.info("=" * 50)
        self.logger.info("Phase 4: SHUC编码")
        self.logger.info("=" * 50)

        # 查找初始流域数据（根据路线不同）
        if use_merit_basins:
            watershed_file = (self.watershed_dir /
                            f'{self.basin_key}_merit_basins_watersheds.shp')
        else:
            watershed_file = (self.watershed_dir /
                            f'{self.basin_key}_initial_watersheds.shp')

        if not watershed_file.exists():
            self.logger.error(f"初始流域文件不存在: {watershed_file}")
            return False

        try:
            from shuc_system import ChinaSHUCSystem
        except ImportError:
            self.logger.error(
                "无法导入SHUC核心系统。请确保 01_CORE_SYSTEM/src/ 在路径中。"
            )
            return False

        if config_path is None:
            config_path = SHUC_ROOT / 'config' / 'shuc_config.json'

        output_name = f'{self.basin_key}_shuc_watersheds'
        shuc = ChinaSHUCSystem(
            config_path=str(config_path),
            output_dir=str(self.shuc_dir)
        )

        # 如果有 MERIT-Basins 拓扑数据，传递给系统
        if use_merit_basins and self.merit_basins_loader is not None:
            shuc.merit_basins = self.merit_basins_loader

        result = shuc.process_watersheds(
            str(watershed_file),
            output_name=output_name,
            use_merit_basins=use_merit_basins
        )

        result.print_summary()

        # 保存Pipeline元数据
        meta = {
            'basin': self.basin_key,
            'basin_name': self.bounds['name_cn'],
            'route': self.route,
            'processed_at': datetime.now().isoformat(),
            'original_watersheds': result.merge_stats['original_count'],
            'final_watersheds': result.watershed_count,
            'compliance_rate': float(result.compliance_rate),
            'overall_score': float(result.overall_score),
            'quality_grade': result.quality_grade,
            'version': '4.0.0',
        }

        meta_file = self.shuc_dir / 'pipeline_metadata.json'
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)

        self.logger.info(f"Pipeline元数据: {meta_file}")

        return True

    # ==================== 完整Pipeline ====================

    def run_full_pipeline(self, start_phase=1, config_path=None):
        """运行完整的处理Pipeline"""
        start_time = datetime.now()
        self.logger.info(f"开始完整Pipeline处理: {self.bounds['name_cn']}")
        self.logger.info(f"路线: {self.route}")
        self.logger.info(f"起始阶段: Phase {start_phase}")

        try:
            if self.route == 'merit-basins':
                # MERIT-Basins 向量路线
                if start_phase <= 2:
                    self.run_phase2b_merit_basins()
                if start_phase <= 4:
                    self.run_phase4_shuc(config_path, use_merit_basins=True)
            else:
                # MERIT Hydro 栅格路线（原有）
                if start_phase <= 1:
                    self.run_phase1_mosaic()
                if start_phase <= 2:
                    self.run_phase2_clip()
                if start_phase <= 3:
                    self.run_phase3_extract_network()
                if start_phase <= 4:
                    self.run_phase4_shuc(config_path, use_merit_basins=False)

            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Pipeline完成！总耗时: {elapsed:.1f}秒")

            return True

        except Exception as e:
            self.logger.error(f"Pipeline失败: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='MERIT Hydro / MERIT-Basins → SHUC 处理Pipeline (v4.0)'
    )
    parser.add_argument('--basin', type=str, required=True,
                       choices=['yangtze', 'huai', 'pearl', 'all'],
                       help='目标流域')
    parser.add_argument('--route', type=str, default='merit-hydro',
                       choices=['merit-hydro', 'merit-basins'],
                       help='数据处理路线 (默认: merit-hydro)')
    parser.add_argument('--merit-dir', type=str,
                       default='../../05_DATA/raw/merit_hydro',
                       help='MERIT Hydro原始数据目录')
    parser.add_argument('--merit-basins-dir', type=str, default=None,
                       help='MERIT-Basins 向量数据目录')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='输出目录 (默认: ../../04_EXPERIMENTS/results/{basin})')
    parser.add_argument('--start-phase', type=int, default=1,
                       choices=[1, 2, 3, 4],
                       help='从哪个Phase开始 (用于断点续跑)')
    parser.add_argument('--config', type=str, default=None,
                       help='SHUC配置文件路径')

    args = parser.parse_args()

    if args.route == 'merit-basins' and args.merit_basins_dir is None:
        parser.error('使用 merit-basins 路线需要指定 --merit-basins-dir')

    basins = list(BASIN_BOUNDS.keys()) if args.basin == 'all' else [args.basin]

    for basin_key in basins:
        output_dir = (args.output_dir or
                     f'../../04_EXPERIMENTS/results/{basin_key}')
        output_dir = Path(output_dir) / datetime.now().strftime('%Y%m%d_%H%M%S')

        logger = setup_pipeline_logger(output_dir)
        pipeline = MERITPipeline(
            basin_key, args.merit_dir, output_dir, logger,
            route=args.route,
            merit_basins_dir=args.merit_basins_dir
        )
        pipeline.run_full_pipeline(
            start_phase=args.start_phase,
            config_path=args.config
        )


if __name__ == '__main__':
    main()
