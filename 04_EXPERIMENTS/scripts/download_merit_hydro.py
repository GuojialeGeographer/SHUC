#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MERIT Hydro 数据下载工具
========================

自动下载 MERIT Hydro 全球水文数据集的关键图层：
- elv: elevation (DEM)
- dir: flow direction
- upa: upstream drainage area (accumulation)
- bas: basin ID (基线流域边界)

数据源: Yamazaki et al. (2019) MERIT Hydro
URL: http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/

三大目标流域:
- 长江流域 (Yangtze): 纬度24-36N, 经度90-122E
- 淮河流域 (Huai): 纬度31-35N, 经度112-121E
- 珠江流域 (Pearl): 纬度21-27N, 经度102-117E

Usage:
    python download_merit_hydro.py --basin yangtze --layers dir,upa,bas
    python download_merit_hydro.py --basin all --layers all
    python download_merit_hydro.py --list-tiles  # 列出所需瓦片

Note:
    MERIT Hydro 需要注册账号获取下载权限。
    请先访问 http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/ 注册。
    本脚本提供 wget/curl 下载命令模板，需要手动填入cookie或token。
"""

import os
import sys
import json
import argparse
from pathlib import Path
from itertools import product


# ============================================================
# 流域边界定义 (经纬度范围)
# ============================================================
BASIN_BOUNDS = {
    'yangtze': {
        'name_cn': '长江流域',
        'name_en': 'Yangtze River Basin',
        'lat_min': 24, 'lat_max': 36,
        'lon_min': 90, 'lon_max': 122,
        'buffer_deg': 1.0,
        'expected_watersheds': 15000,
        'shuc_prefix': '01',
    },
    'huai': {
        'name_cn': '淮河流域',
        'name_en': 'Huai River Basin',
        'lat_min': 31, 'lat_max': 35,
        'lon_min': 112, 'lon_max': 121,
        'buffer_deg': 1.0,
        'expected_watersheds': 5000,
        'shuc_prefix': '05',
    },
    'pearl': {
        'name_cn': '珠江流域',
        'name_en': 'Pearl River Basin',
        'lat_min': 21, 'lat_max': 27,
        'lon_min': 102, 'lon_max': 117,
        'buffer_deg': 1.0,
        'expected_watersheds': 8000,
        'shuc_prefix': '03',
    },
}

# MERIT Hydro 瓦片命名规则
# 纬度: 60S-60N (5度分块), 60N-90N (特殊处理)
# 经度: 180W-180E (5度分块)
# 文件名格式: {layer}/xxxdyyyLf.xxx (d=N/S, L=lat, f=lon)
MERIT_LAYERS = {
    'elv': 'elevation',
    'dir': 'flow direction',
    'upa': 'upstream area',
    'wth': 'channel width',
    'elen': 'channel length',
    'bas': 'basin ID',
}

BASE_URL = 'http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/distributed/v1.2'


def get_merit_tiles(lat_min, lat_max, lon_min, lon_max):
    """
    根据经纬度范围生成所需的 MERIT Hydro 瓦片名称
    
    MERIT Hydro 瓦片命名:
    - 5度分块: lat 60S-60N, lon 180W-180E
    - 格式: {n|s}{lat_zero_padded}{e|w}{lon_zero_padded}
    - 例: n30e110 表示 30-35N, 110-115E
    """
    tiles = []
    
    # 生成纬度分块 (5度间隔)
    lat_start = int(lat_min // 5) * 5
    lat_end = int(lat_max // 5) * 5 + 5
    
    # 生成经度分块 (5度间隔) 
    lon_start = int(lon_min // 5) * 5
    lon_end = int(lon_max // 5) * 5 + 5
    
    for lat_base in range(lat_start, lat_end, 5):
        for lon_base in range(lon_start, lon_end, 5):
            # 纬度方向
            if lat_base >= 0:
                lat_part = f"n{lat_base:02d}"
            else:
                lat_part = f"s{abs(lat_base):02d}"
            
            # 经度方向
            if lon_base >= 0:
                lon_part = f"e{lon_base:03d}"
            else:
                lon_part = f"w{abs(lon_base):03d}"
            
            tile_name = f"{lat_part}{lon_part}"
            tiles.append({
                'name': tile_name,
                'lat_range': f"{lat_base}~{lat_base+5}",
                'lon_range': f"{lon_base}~{lon_base+5}",
            })
    
    return tiles


def generate_download_commands(basin_key, layers, output_dir):
    """生成下载命令"""
    if basin_key == 'all':
        basins = list(BASIN_BOUNDS.keys())
    else:
        basins = [basin_key]
    
    commands = []
    
    for basin in basins:
        bounds = BASIN_BOUNDS[basin]
        
        # 加缓冲区
        lat_min = bounds['lat_min'] - bounds['buffer_deg']
        lat_max = bounds['lat_max'] + bounds['buffer_deg']
        lon_min = bounds['lon_min'] - bounds['buffer_deg']
        lon_max = bounds['lon_max'] + bounds['buffer_deg']
        
        tiles = get_merit_tiles(lat_min, lat_max, lon_min, lon_max)
        
        if layers == ['all']:
            download_layers = list(MERIT_LAYERS.keys())
        else:
            download_layers = layers
        
        basin_dir = Path(output_dir) / basin
        
        commands.append({
            'basin': basin,
            'name_cn': bounds['name_cn'],
            'tiles': tiles,
            'layers': download_layers,
            'output_dir': str(basin_dir),
            'bounds': {
                'lat': [lat_min, lat_max],
                'lon': [lon_min, lon_max],
            }
        })
    
    return commands


def print_download_script(commands):
    """打印可执行的下载脚本"""
    print("#!/bin/bash")
    print("# MERIT Hydro 数据下载脚本")
    print("# 自动生成 - 请先在下方设置您的登录凭证")
    print()
    print("# ============================================================")
    print("# 步骤0: 设置登录信息")
    print("# ============================================================")
    print("# 请访问以下URL注册并获取下载权限:")
    print("# http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/")
    print("#")
    print("# 设置cookie文件 (从浏览器导出):")
    print('# COOKIE_FILE="$HOME/.merit_cookies.txt"')
    print('# TOKEN=""  # 如果需要token')
    print()
    
    for cmd in commands:
        print(f"# ============================================================")
        print(f"# 流域: {cmd['name_cn']} ({cmd['basin']})")
        print(f"# 瓦片数: {len(cmd['tiles'])}")
        print(f"# 输出目录: {cmd['output_dir']}")
        print(f"# ============================================================")
        print()
        print(f"mkdir -p {cmd['output_dir']}")
        print()
        
        for layer in cmd['layers']:
            layer_dir = f"{cmd['output_dir']}/{layer}"
            print(f"mkdir -p {layer_dir}")
            print(f"echo 'Downloading {MERIT_LAYERS.get(layer, layer)} for {cmd['name_cn']}...'")
            
            for tile in cmd['tiles']:
                filename = f"{tile['name']}.tar.gz"
                url = f"{BASE_URL}/{layer}/{filename}"
                print(f"# Tile: {tile['name']} (lat {tile['lat_range']}, lon {tile['lon_range']})")
                print(f"wget -c -P {layer_dir} {url}")
                # 或者用 curl:
                # print(f"curl -C - -o {layer_dir}/{filename} {url}")
            
            print(f"echo 'Extracting {layer}...'")
            print(f"cd {layer_dir} && for f in *.tar.gz; do tar -xzf $f; done && cd -")
            print()
    
    print("# ============================================================")
    print("# 下载完成!")
    print("# ============================================================")


def print_tile_info(commands):
    """打印瓦片信息"""
    for cmd in commands:
        print(f"\n{'='*60}")
        print(f"流域: {cmd['name_cn']} ({cmd['basin']})")
        print(f"范围: lat {cmd['bounds']['lat'][0]}~{cmd['bounds']['lat'][1]}N, "
              f"lon {cmd['bounds']['lon'][0]}~{cmd['bounds']['lon'][1]}E")
        print(f"所需瓦片数: {len(cmd['tiles'])}")
        print(f"数据图层: {', '.join(cmd['layers'])}")
        print(f"{'='*60}")
        
        print(f"\n瓦片列表:")
        for i, tile in enumerate(cmd['tiles'], 1):
            print(f"  {i:2d}. {tile['name']:12s}  "
                  f"lat {tile['lat_range']:>8s}  "
                  f"lon {tile['lon_range']:>9s}")


def main():
    parser = argparse.ArgumentParser(
        description='MERIT Hydro 数据下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python download_merit_hydro.py --list-tiles
  python download_merit_hydro.py --basin yangtze --layers dir,upa,bas
  python download_merit_hydro.py --basin all --layers all --output ../05_DATA/raw
  python download_merit_hydro.py --basin yangtze --script > download_yangtze.sh
        """
    )
    
    parser.add_argument('--basin', type=str, default='all',
                       choices=['yangtze', 'huai', 'pearl', 'all'],
                       help='目标流域 (default: all)')
    parser.add_argument('--layers', type=str, default='dir,upa,bas',
                       help='数据图层，逗号分隔 (default: dir,upa,bas)')
    parser.add_argument('--output', type=str, default='../05_DATA/raw/merit_hydro',
                       help='输出目录')
    parser.add_argument('--list-tiles', action='store_true',
                       help='列出所需瓦片信息')
    parser.add_argument('--script', action='store_true',
                       help='生成下载脚本')
    
    args = parser.parse_args()
    
    # 解析图层参数
    if args.layers == 'all':
        layers = ['all']
    else:
        layers = [l.strip() for l in args.layers.split(',')]
    
    # 生成下载信息
    commands = generate_download_commands(args.basin, layers, args.output)
    
    if args.list_tiles:
        print_tile_info(commands)
    elif args.script:
        print_download_script(commands)
    else:
        # 默认: 打印瓦片信息 + 生成脚本
        print_tile_info(commands)
        print(f"\n\n提示: 使用 --script 参数生成可执行的下载脚本")
        print(f"  python {sys.argv[0]} --basin {args.basin} --script > download_{args.basin}.sh")
        print(f"\n数据下载后，运行Pipeline处理:")
        print(f"  python merit_to_shuc_pipeline.py --basin {args.basin}")


if __name__ == '__main__':
    main()
