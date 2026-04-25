# China SHUC 详细实施手册

> 从数据下载到最终编码的每一步操作指南
> 版本：v1.0 | 日期：2025-04-02

---

## 目录

1. [整体流程概览](#1-整体流程概览)
2. [Phase 1: 数据准备（详细步骤）](#2-phase-1-数据准备详细步骤)
3. [Phase 2: 数据拼接策略详解](#3-phase-2-数据拼接策略详解)
4. [Phase 3: TauDEM处理（Windows）](#4-phase-3-taudem处理windows)
5. [Phase 4: SHUC优化（Python）](#5-phase-4-shuc优化python)
6. [常见问题与解决方案](#6-常见问题与解决方案)

---

## 1. 整体流程概览

### 1.1 完整流程图（细化版）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        China SHUC 完整实施流程                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: 数据准备 (2-3天)                                                  │
│  ─────────────────────────                                                  │
│  Step 1.1 确定处理范围 → 下载大流域边界 shapefile                          │
│  Step 1.2 确定DEM瓦片 → 下载SRTM/MERIT瓦片                                 │
│  Step 1.3 数据完整性检查 → 验证瓦片无缺失                                  │
│                                                                             │
│  Phase 2: 数据拼接 (1天)                                                    │
│  ───────────────────────                                                    │
│  Step 2.1 选择拼接工具 → Python GDAL / QGIS / ArcGIS                      │
│  Step 2.2 执行拼接 → 生成大区域DEM                                         │
│  Step 2.3 裁剪到边界+缓冲区 → 减少处理量                                   │
│                                                                             │
│  Phase 3: TauDEM处理 (Windows工作站, 1-2天/流域)                           │
│  ──────────────────────────────────────────────                             │
│  Step 3.1 环境配置 → 安装TauDEM 5.3.7                                      │
│  Step 3.2 PitRemove → 填洼                                                 │
│  Step 3.3 D8FlowDir → 流向计算                                             │
│  Step 3.4 AreaD8 → 累积量计算                                              │
│  Step 3.5 Threshold → 河网提取（设定阈值）                                 │
│  Step 3.6 StreamNet → 生成河段网络（含拓扑关系）                           │
│  Step 3.7 Watershed → 流域划分                                             │
│  Step 3.8 结果验证 → 检查拓扑关系完整性                                    │
│                                                                             │
│  Phase 4: SHUC优化 (Python, 4-6小时)                                        │
│  ───────────────────────────────────                                        │
│  Step 4.1 读取TauDEM输出 → 加载streamnet.shp                               │
│  Step 4.2 构建拓扑网络 → NetworkX有向图                                    │
│  Step 4.3 初始流域合并 → 动态阈值算法                                      │
│  Step 4.4 层级编码分配 → SHUC-2到SHUC-12                                   │
│  Step 4.5 拓扑关系更新 → 保持上下游关系                                    │
│  Step 4.6 结果导出 → Shapefile + 属性表                                    │
│                                                                             │
│  Phase 5: 验证与质量控制 (1天)                                              │
│  ─────────────────────────────                                              │
│  Step 5.1 目视检查 → 样本流域验证                                          │
│  Step 5.2 统计验证 → 面积分布、数量合理性                                  │
│  Step 5.3 拓扑验证 → 检查循环引用、孤立节点                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 关键决策点

```
实施前必须做的决策：
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  决策1: 数据选择                                                            │
│  ├── 选项A: SRTM 30m（原始，需完整TauDEM流程）                              │
│  ├── 选项B: MERIT 90m（已预处理，省时间）                                   │
│  └── 推荐: 先用MERIT测试流程，再考虑SRTM细化                               │
│                                                                             │
│  决策2: 拼接策略（关键！）                                                  │
│  ├── 方案A: 先拼接成大DEM，再整体处理                                       │
│  │   └── 适合：单个大流域（如长江）                                         │
│  │   └── 内存需求：~10-20GB                                                │
│  │                                                                           │
│  ├── 方案B: 瓦片分别处理，最后合并拓扑关系                                  │
│  │   └── 适合：全国范围或多个流域                                           │
│  │   └── 内存需求：~2-4GB/瓦片                                              │
│  │                                                                           │
│  └── 推荐: 方案A（长江流域用方案A，其他视情况而定）                         │
│                                                                             │
│  决策3: 拼接工具                                                            │
│  ├── 选项A: Python GDAL（推荐，可自动化）                                   │
│  ├── 选项B: QGIS（图形界面，适合检查）                                      │
│  ├── 选项C: ArcGIS Pro（功能强，但收费）                                    │
│  └── 推荐: Python GDAL为主，QGIS辅助检查                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase 1: 数据准备（详细步骤）

### 2.1 Step 1.1: 确定处理范围

```
操作步骤：

1. 获取大流域边界
   ┌─────────────────────────────────────────────────────────────────┐
   │  来源选项：                                                      │
   │  A. HydroSHEDS Basin Level 2（推荐）                            │
   │     网址: https://www.hydrosheds.org/products/hydrobasins       │
   │     文件: hybas_as_lev02_v1c.shp                                │
   │                                                                   │
   │  B. 中国水利部官方流域边界（如果有渠道获取）                    │
   │                                                                   │
   │  C. 自定义绘制（不推荐，工作量大）                              │
   └─────────────────────────────────────────────────────────────────┘

2. 提取目标流域（以长江为例）
   
   Python代码：
   ```python
   import geopandas as gpd
   
   # 读取全球流域边界
   basins = gpd.read_file('hybas_as_lev02_v1c.shp')
   
   # 筛选长江流域（HYBAS_ID为长江的ID）
   # 长江流域ID需要查表确定，这里假设为1070000010
   yangtze = basins[basins['HYBAS_ID'] == 1070000010]
   
   # 保存
   yangtze.to_file('yangtze_boundary.shp')
   
   # 查看范围
   print(yangtze.total_bounds)  # [minx, miny, maxx, maxy]
   # 示例输出: [89.5, 24.5, 122.5, 35.5]
   ```

3. 确定缓冲区（关键！）
   ```python
   # 添加50km缓冲区，确保边界流域完整
   yangtze_buffer = yangtze.buffer(0.5)  # 约50km（0.5度粗略估算）
   yangtze_buffer.to_file('yangtze_boundary_50km_buffer.shp')
   ```
```

### 2.2 Step 1.2: 下载DEM瓦片

```
操作步骤：

1. 确定需要下载的SRTM瓦片
   
   长江流域范围（示例）：
   - 经度：90°E - 122°E
   - 纬度：25°N - 35°N
   
   SRTM瓦片命名规则：srtm_XX_YY.zip
   - XX: 经度（1度一个瓦片）
   - YY: 纬度（1度一个瓦片）
   
   需要下载的瓦片（示例）：
   srtm_90_25.zip 到 srtm_122_35.zip
   约 32×10 = 320 个瓦片

2. 批量下载脚本

   Python代码：
   ```python
   import urllib.request
   import os
   
   def download_srtm(lon, lat, output_dir='data/srtm_tiles'):
       """下载单个SRTM瓦片"""
       
       # SRTM 1 Arc-Second 下载地址
       url = f"https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/"
       filename = f"N{lat:02d}E{lon:03d}.SRTMGL1.hgt.zip"
       
       full_url = url + filename
       output_path = os.path.join(output_dir, filename)
       
       if os.path.exists(output_path):
           print(f"已存在: {filename}")
           return
       
       try:
           print(f"下载: {filename}")
           urllib.request.urlretrieve(full_url, output_path)
       except Exception as e:
           print(f"下载失败 {filename}: {e}")
   
   # 批量下载长江流域
   for lon in range(90, 123):  # 90E-122E
       for lat in range(25, 36):  # 25N-35N
           download_srtm(lon, lat)
   
   print("下载完成！")
   ```

3. 或使用USGS Earth Explorer批量下载
   - 网址: https://earthexplorer.usgs.gov/
   - 方法: 绘制多边形范围 → 批量下载

4. 解压瓦片
   ```bash
   # 批量解压
   for zip in data/srtm_tiles/*.zip; do
       unzip -q "$zip" -d data/srtm_unzipped/
   done
   ```
```

### 2.3 Step 1.3: 数据完整性检查

```
操作步骤：

1. 检查瓦片数量
   ```python
   import os
   import rasterio
   from rasterio.plot import show
   
   tiles_dir = 'data/srtm_unzipped'
   tiles = [f for f in os.listdir(tiles_dir) if f.endswith('.hgt') or f.endswith('.tif')]
   
   print(f"瓦片数量: {len(tiles)}")
   print(f"预期数量: 320")
   
   if len(tiles) < 320:
       print("警告：瓦片缺失！")
       # 列出缺失的瓦片
   ```

2. 检查瓦片完整性（无损坏）
   ```python
   import rasterio
   
   corrupt_tiles = []
   for tile in tiles:
       try:
           with rasterio.open(os.path.join(tiles_dir, tile)) as src:
               _ = src.read(1)  # 尝试读取
       except Exception as e:
           corrupt_tiles.append((tile, str(e)))
   
   if corrupt_tiles:
       print(f"损坏的瓦片: {corrupt_tiles}")
       print("需要重新下载")
   else:
       print("所有瓦片完好")
   ```

3. 可视化检查（使用QGIS）
   - 打开QGIS
   - 加载所有瓦片（拖入）
   - 检查是否有空白/缺失区域
   - 检查瓦片间是否有缝隙
```

---

## 3. Phase 2: 数据拼接策略详解

### 3.1 拼接策略对比

```
三种拼接策略深度对比：
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  策略A: 先拼接成大DEM，再整体处理（推荐用于单一大流域）                     │
│  ────────────────────────────────────────────────────────                   │
│                                                                             │
│  流程：                                                                      │
│  瓦片1 + 瓦片2 + ... + 瓦片N → 大DEM.tif → TauDEM处理                      │
│                                                                             │
│  优点：                                                                      │
│  ✓ 处理简单，一次完成                                                       │
│  ✓ 没有瓦片边界问题                                                         │
│  ✓ 拓扑关系完整                                                             │
│                                                                             │
│  缺点：                                                                      │
│  ✗ 内存需求大（长江流域~10-20GB）                                          │
│  ✗ 如果出错需要全部重跑                                                     │
│  ✗ 拼接耗时（几小时）                                                       │
│                                                                             │
│  适用场景：                                                                  │
│  • 单个大流域（如长江）                                                     │
│  • 内存充足（>32GB）                                                        │
│  • 追求简单可靠                                                             │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  策略B: 瓦片分别处理，最后合并拓扑（适合全国范围）                          │
│  ────────────────────────────────────────────────                           │
│                                                                             │
│  流程：                                                                      │
│  瓦片1 → TauDEM → 拓扑1                                                      │
│  瓦片2 → TauDEM → 拓扑2                                                      │
│  ...                                                                         │
│  瓦片N → TauDEM → 拓扑N                                                      │
│  合并：拓扑1 + 拓扑2 + ... + 拓扑N → 全国拓扑网络                           │
│                                                                             │
│  优点：                                                                      │
│  ✓ 内存需求小（每瓦片~2-4GB）                                              │
│  ✓ 可并行处理（多机/多进程）                                                │
│  ✓ 单个瓦片出错不影响其他                                                   │
│                                                                             │
│  缺点：                                                                      │
│  ✗ 瓦片边界处拓扑关系需要特殊处理                                           │
│  ✗ 合并逻辑复杂                                                             │
│  ✗ 需要开发合并代码                                                         │
│                                                                             │
│  适用场景：                                                                  │
│  • 全国范围（900万+km²）                                                    │
│  • 计算资源有限                                                             │
│  • 有并行计算能力                                                           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  策略C: 一景一景生成，不拼接（适合试验/小区域）                             │
│  ─────────────────────────────────────────────                            │
│                                                                             │
│  流程：                                                                      │
│  每个瓦片独立生成SHUC → 得到碎片化的编码                                    │
│  （编码不连续，无法形成完整体系）                                           │
│                                                                             │
│  评价：                                                                      │
│  ✗ 不推荐！无法建立完整的SHUC编码体系                                       │
│  ✗ 瓦片间流域关系断裂                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 推荐方案及理由

```
针对你的情况（长江流域）推荐：策略A（先拼接再处理）

理由：
1. 长江流域是一个完整水系，需要整体处理
2. 你有Windows工作站，内存应该足够
3. 策略A最简单可靠，减少边界问题
4. TauDEM在Windows上处理大文件稳定

如果内存不足（<16GB）：
→ 改用策略B，但开发成本增加
```

### 3.3 拼接工具选择

```
三种工具详细对比：
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  工具1: Python + rasterio（推荐）                                           │
│  ────────────────────────────────                                           │
│                                                                             │
│  安装：                                                                      │
│  pip install rasterio geopandas numpy                                       │
│  （Windows上可能需要conda安装rasterio）                                     │
│                                                                             │
│  代码：                                                                      │
│  ```python                                                                   │
│  import rasterio                                                             │
│  from rasterio.merge import merge                                            │
│  import glob                                                                 │
│  import os                                                                   │
│                                                                             │
│  # 获取所有瓦片路径                                                          │
│  tile_paths = glob.glob('data/srtm_unzipped/*.hgt')                         │
│                                                                             │
│  # 打开所有瓦片                                                              │
│  src_files = [rasterio.open(path) for path in tile_paths]                   │
│                                                                             │
│  # 合并（使用mosaic方法，自动处理重叠）                                      │
│  mosaic, out_transform = merge(src_files)                                   │
│                                                                             │
│  # 保存                                                                      │
│  out_meta = src_files[0].meta.copy()                                        │
│  out_meta.update({                                                           │
│      "driver": "GTiff",                                                      │
│      "height": mosaic.shape[1],                                              │
│      "width": mosaic.shape[2],                                               │
│      "transform": out_transform,                                             │
│      "compress": "lzw"  # 压缩节省空间                                       │
│  })                                                                          │
│                                                                             │
│  with rasterio.open('data/yangtze_dem_mosaic.tif', 'w', **out_meta) as dest:│
│      dest.write(mosaic)                                                     │
│                                                                             │
│  # 关闭文件                                                                  │
│  for src in src_files:                                                       │
│      src.close()                                                             │
│  ```                                                                         │
│                                                                             │
│  优点：                                                                      │
│  ✓ 可自动化，批量处理                                                       │
│  ✓ 可嵌入到完整流程中                                                       │
│  ✓ 免费开源                                                                 │
│                                                                             │
│  缺点：                                                                      │
│  ✗ 需要Python环境                                                           │
│  ✗ 大文件可能内存溢出（需要分块写入）                                       │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  工具2: QGIS（推荐用于检查和辅助）                                          │
│  ────────────────────────────────                                           │
│                                                                             │
│  操作步骤：                                                                  │
│  1. 打开QGIS                                                                 │
│  2. Raster → Miscellaneous → Merge...                                       │
│  3. 选择所有瓦片文件                                                        │
│  4. 设置输出文件                                                            │
│  5. 点击Run                                                                 │
│                                                                             │
│  优点：                                                                      │
│  ✓ 图形界面，直观易懂                                                       │
│  ✓ 可实时预览结果                                                           │
│  ✓ 方便检查拼接质量                                                         │
│                                                                             │
│  缺点：                                                                      │
│  ✗ 不易自动化                                                               │
│  ✗ 大量瓦片时操作繁琐                                                       │
│                                                                             │
│  适用场景：                                                                  │
│  • 首次拼接，检查质量                                                       │
│  • 小批量瓦片                                                               │
│  • 可视化验证                                                               │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  工具3: ArcGIS Pro（功能强大，但收费）                                      │
│  ───────────────────────────────────                                        │
│                                                                             │
│  工具：Mosaic To New Raster                                                 │
│                                                                             │
│  优点：                                                                      │
│  ✓ 功能最强大                                                               │
│  ✓ 大文件处理优化好                                                         │
│  ✓ 企业级稳定性                                                             │
│                                                                             │
│  缺点：                                                                      │
│  ✗ 需要ArcGIS Pro license（昂贵）                                           │
│  ✗ 不易自动化                                                               │
│                                                                             │
│  适用场景：                                                                  │
│  • 已有license                                                              │
│  • 生产环境                                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 推荐的组合方案

```
推荐组合：Python（自动化）+ QGIS（检查）

实施流程：
1. 用Python批量拼接（自动化，可复现）
2. 在QGIS中打开检查（目视验证）
3. 如有问题，用QGIS修复
4. 确认无误后进入下一步

具体步骤：
Step 1: Python拼接
  $ python scripts/mosaic_tiles.py --input data/srtm_unzipped/ --output data/yangtze_dem.tif

Step 2: QGIS检查
  - 打开yangtze_dem.tif
  - 加载流域边界对比
  - 检查是否有空洞/缝隙
  - 检查高程值是否合理（0-8000m）

Step 3: 裁剪（减少处理量）
  $ python scripts/clip_to_boundary.py \
      --dem data/yangtze_dem.tif \
      --boundary data/yangtze_boundary_50km_buffer.shp \
      --output data/yangtze_dem_clipped.tif
```

---

## 4. Phase 3: TauDEM处理（Windows）

### 4.1 环境配置

```
Windows环境配置步骤：

Step 1: 下载TauDEM
  - 官网: https://hydrology.usu.edu/taudem/taudem5/
  - 下载: TauDEM 5.3.7 Complete Installer
  - 安装: 默认路径 C:\Program Files\TauDEM\

Step 2: 配置环境变量
  右键"此电脑" → 属性 → 高级系统设置 → 环境变量
  在Path中添加: C:\Program Files\TauDEM\

Step 3: 验证安装
  打开CMD:
  > pitremove
  应该显示帮助信息，而不是"命令未找到"

Step 4: 准备数据目录
  创建: D:\SHUC_Project\data\
  创建: D:\SHUC_Project\output\
  （建议用D盘，避免C盘空间不足）
```

### 4.2 完整TauDEM命令序列

```
完整处理脚本（Windows CMD/Batch）：

@echo off
set DEM=D:\SHUC_Project\data\yangtze_dem_clipped.tif
set OUTDIR=D:\SHUC_Project\output\yangtze
echo Starting TauDEM processing for Yangtze River Basin...

REM Step 1: Pit Remove (填洼)
echo Step 1/8: Pit Remove...
pitremove -z %DEM% -fel %OUTDIR%\fel.tif
if errorlevel 1 goto error

REM Step 2: D8 Flow Direction (流向)
echo Step 2/8: D8 Flow Direction...
d8flowdir -fel %OUTDIR%\fel.tif -p %OUTDIR%\p.tif -sd8 %OUTDIR%\sd8.tif
if errorlevel 1 goto error

REM Step 3: D8 Flow Accumulation (累积量)
echo Step 3/8: D8 Flow Accumulation...
aread8 -p %OUTDIR%\p.tif -ad8 %OUTDIR%\ad8.tif
if errorlevel 1 goto error

REM Step 4: Stream Definition (河网定义)
REM 使用阈值1000 pixels (~0.8 km2 at 90m)
echo Step 4/8: Stream Definition...
threshold -ssa %OUTDIR%\ad8.tif -src %OUTDIR%\src.tif -thresh 1000
if errorlevel 1 goto error

REM Step 5: Stream Reach (河段网络 - 生成拓扑关系！)
echo Step 5/8: Stream Reach and Watershed...
streamnet -fel %OUTDIR%\fel.tif -p %OUTDIR%\p.tif -ad8 %OUTDIR%\ad8.tif ^
          -src %OUTDIR%\src.tif -ord %OUTDIR%\ord.tif -tree %OUTDIR%\tree.txt ^
          -coord %OUTDIR%\coord.txt -net %OUTDIR%\streamnet.shp ^
          -w %OUTDIR%\w.tif
if errorlevel 1 goto error

echo Success! Output files in %OUTDIR%
goto end

:error
echo Error occurred!
pause
exit /b 1

:end
pause
```

### 4.3 输出文件说明

```
TauDEM输出文件清单：

必需文件：
├── streamnet.shp      ★ 河段网络（含拓扑关系USLINKNO/DSLINKNO）
├── w.tif              ★ 流域栅格（每个流域有唯一ID）
└── fel.tif            填洼后DEM（用于后续处理）

辅助文件：
├── p.tif              流向栅格（D8编码）
├── ad8.tif            累积量栅格
├── src.tif            河网栅格
├── ord.tif            河流等级（Strahler等级）
├── tree.txt           河段树结构（文本格式）
└── coord.txt          河段坐标信息

关键字段说明（streamnet.shp）：
├── LINKNO      - 河段唯一ID
├── USLINKNO1   - 上游河段1（-1表示无上游，即源头）
├── USLINKNO2   - 上游河段2（-1表示无第二个上游）
├── DSLINKNO    - 下游河段（-1表示无下游，即出口）
├── Order       - Strahler河流等级
├── Length      - 河段长度（km）
├── Area        - 流域面积（km²）
└── geometry    - 河段几何（LineString）

这些字段就是完整的空间上下文关系！
```

---

## 5. Phase 4: SHUC优化（Python）

### 5.1 读取TauDEM输出

```python
# read_taudem_output.py
import geopandas as gpd
import rasterio
import numpy as np
import networkx as nx
from shapely.geometry import shape
import pandas as pd

def read_taudem_output(streamnet_path, watershed_path):
    """
    读取TauDEM输出并构建拓扑网络
    """
    # 读取河段网络（含拓扑关系）
    streams = gpd.read_file(streamnet_path)
    
    print(f"读取了 {len(streams)} 个河段")
    print(f"字段: {streams.columns.tolist()}")
    
    # 显示拓扑关系示例
    print("\n拓扑关系示例:")
    print(streams[['LINKNO', 'USLINKNO1', 'USLINKNO2', 'DSLINKNO']].head(10))
    
    # 读取流域栅格
    with rasterio.open(watershed_path) as src:
        watershed_raster = src.read(1)
        watershed_transform = src.transform
        
    print(f"\n流域栅格大小: {watershed_raster.shape}")
    print(f"唯一流域ID数: {len(np.unique(watershed_raster)) - 1}")  # 减去0（背景）
    
    return streams, watershed_raster, watershed_transform

# 构建NetworkX图
def build_topology_graph(streams_df):
    """
    从TauDEM输出构建有向图（上下游关系）
    """
    G = nx.DiGraph()
    
    # 添加节点（河段）
    for idx, row in streams_df.iterrows():
        G.add_node(row['LINKNO'], 
                   area=row.get('Area', 0),
                   length=row.get('Length', 0),
                   geometry=row.geometry)
    
    # 添加边（上下游关系）
    # 从上游指向下游
    for idx, row in streams_df.iterrows():
        linkno = row['LINKNO']
        dslink = row['DSLINKNO']
        
        if dslink != -1:  # -1表示没有下游（出口）
            G.add_edge(linkno, dslink)
    
    print(f"\n拓扑网络构建完成:")
    print(f"节点数: {G.number_of_nodes()}")
    print(f"边数: {G.number_of_edges()}")
    
    # 找到源头（没有入边的节点）
    sources = [n for n in G.nodes() if G.in_degree(n) == 0]
    print(f"源头数量: {len(sources)}")
    
    # 找到出口（没有出边的节点）
    outlets = [n for n in G.nodes() if G.out_degree(n) == 0]
    print(f"出口数量: {len(outlets)}")
    
    return G, sources, outlets

# 使用示例
if __name__ == '__main__':
    streams, watershed_raster, transform = read_taudem_output(
        'output/yangtze/streamnet.shp',
        'output/yangtze/w.tif'
    )
    
    G, sources, outlets = build_topology_graph(streams)
```

### 5.2 SHUC优化算法

```python
# shuc_optimizer.py
import networkx as nx
import numpy as np
from collections import defaultdict

class SHUCOptimizer:
    """
    SHUC编码优化器
    基于TauDEM生成的拓扑关系进行动态合并
    """
    
    def __init__(self, topology_graph, min_area_threshold=50):
        self.G = topology_graph
        self.min_area = min_area_threshold
        self.merge_history = []
        
    def calculate_dynamic_threshold(self, node_areas):
        """
        计算动态阈值
        Q75 + (Q90 - Q75) / 2
        """
        areas = np.array(list(node_areas.values()))
        q75 = np.percentile(areas, 75)
        q90 = np.percentile(areas, 90)
        
        threshold = min(80, max(50, q75 + (q90 - q75) / 2))
        return threshold
    
    def optimize(self, target_compliance=0.9, max_iterations=50):
        """
        SHUC优化主算法
        """
        print("开始SHUC优化...")
        
        # 获取当前所有流域面积
        node_areas = {n: self.G.nodes[n].get('area', 0) 
                      for n in self.G.nodes()}
        
        # 计算动态阈值
        dynamic_threshold = self.calculate_dynamic_threshold(node_areas)
        print(f"动态阈值: {dynamic_threshold:.1f} km²")
        
        iteration = 0
        while iteration < max_iterations:
            # 找出小于阈值的流域
            small_watersheds = [n for n, area in node_areas.items() 
                               if area < dynamic_threshold]
            
            if len(small_watersheds) < 5:
                print(f"剩余小流域数量({len(small_watersheds)})少于5，停止")
                break
            
            # 计算合规率
            compliance = sum(1 for a in node_areas.values() 
                           if a >= dynamic_threshold) / len(node_areas)
            
            if compliance >= target_compliance:
                print(f"合规率 {compliance:.1%} 达到目标，停止")
                break
            
            # 执行一轮合并（最合理的合并策略）
            merged = self._merge_round(small_watersheds, node_areas, dynamic_threshold)
            
            if not merged:
                print("本轮无合并发生，停止")
                break
            
            iteration += 1
            print(f"迭代 {iteration}: 合并 {len(merged)} 个流域，"
                  f"当前合规率 {compliance:.1%}")
        
        print(f"优化完成，总迭代次数: {iteration}")
        return self.G, node_areas
    
    def _merge_round(self, small_watersheds, node_areas, threshold):
        """
        执行一轮合并
        """
        merged = []
        
        # 按面积从小到大排序（优先合最小的）
        small_watersheds.sort(key=lambda n: node_areas[n])
        
        for node in small_watersheds:
            if node not in self.G.nodes():
                continue  # 已被合并
            
            # 找到最佳合并候选
            candidates = self._find_merge_candidates(node, node_areas, threshold)
            
            if candidates:
                # 选择最佳候选（面积最接近阈值的）
                best = min(candidates, 
                          key=lambda n: abs(node_areas[n] + node_areas[node] - threshold))
                
                # 执行合并
                self._merge_nodes(node, best, node_areas)
                merged.append((node, best))
        
        return merged
    
    def _find_merge_candidates(self, node, node_areas, threshold):
        """
        寻找可合并的候选流域
        策略：优先上游小流域，其次下游兼容流域
        """
        candidates = []
        
        # 上游邻居
        for pred in self.G.predecessors(node):
            if pred in node_areas:
                combined = node_areas[node] + node_areas[pred]
                if combined < threshold * 1.5:  # 合并后不超过阈值太多
                    candidates.append(pred)
        
        return candidates
    
    def _merge_nodes(self, node1, node2, node_areas):
        """
        合并两个流域节点
        """
        # 更新面积
        new_area = node_areas[node1] + node_areas[node2]
        node_areas[node1] = new_area
        del node_areas[node2]
        
        # 更新图结构（保留node1，删除node2）
        # 将node2的上下游关系转移给node1
        for pred in list(self.G.predecessors(node2)):
            if pred != node1:
                self.G.add_edge(pred, node1)
        
        for succ in list(self.G.successors(node2)):
            if succ != node1:
                self.G.add_edge(node1, succ)
        
        self.G.remove_node(node2)
        
        # 记录历史
        self.merge_history.append((node1, node2, new_area))
    
    def assign_shuc_codes(self, basin_code='01'):
        """
        分配SHUC编码
        从出口向上游遍历，按层级分配编码
        """
        codes = {}
        
        # 找到出口（最下游）
        outlets = [n for n in self.G.nodes() if self.G.out_degree(n) == 0]
        
        for outlet in outlets:
            # BFS遍历，从出口向上游
            queue = [(outlet, basin_code)]  # (节点, 编码前缀)
            visited = set()
            
            while queue:
                node, prefix = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                
                # 分配编码
                if node not in codes:
                    codes[node] = prefix
                
                # 获取上游节点
                upstreams = list(self.G.predecessors(node))
                
                # 按面积排序，大的给小编码
                upstreams.sort(key=lambda n: self.G.nodes[n].get('area', 0), 
                             reverse=True)
                
                for i, up in enumerate(upstreams, 1):
                    new_prefix = prefix + f"{i:02d}"
                    if len(new_prefix) < 12:  # 最多12位
                        queue.append((up, new_prefix))
        
        return codes
```

---

## 6. 常见问题与解决方案

### 6.1 拼接问题

```
问题1: 瓦片间有缝隙（NoData）
原因: 瓦片边界没有重叠
解决:
  - SRTM瓦片本身应该无缝
  - 如果出现缝隙，用邻近值填充
  - Python代码:
    ```python
    from scipy import ndimage
    
    # 填充NoData
    nodata_mask = (mosaic == nodata_value)
    mosaic_filled = ndimage.distance_transform_edt(
        nodata_mask, 
        return_distances=False,
        return_indices=True
    )
    mosaic[nodata_mask] = mosaic[mosaic_filled[0][nodata_mask], 
                                  mosaic_filled[1][nodata_mask]]
    ```

问题2: 内存溢出（大文件）
解决:
  - 使用分块处理
  - 降低数据类型（Float32 -> Float32，不必要Float64）
  - 或者改用策略B（瓦片分别处理）
```

### 6.2 TauDEM问题

```
问题1: pitremove运行极慢
原因: 大DEM文件，洼地多
解决:
  - 确保DEM已经是最小化（裁剪后）
  - 或者使用更小的测试区域先验证
  - 考虑使用SSD硬盘

问题2: streamnet报错"No streams found"
原因: 阈值设置过高，没有河流被识别
解决:
  - 降低阈值（如从5000降到1000）
  - 检查ad8.tif是否正常生成

问题3: 拓扑关系不完整（有孤立节点）
解决:
  - 检查是否有NoData区域
  - 确保DEM覆盖完整
```

---

## 总结

### 详细实施检查清单

```
实施前准备：
□ 确认Windows工作站可用
□ 安装TauDEM 5.3.7
□ 安装Python环境（rasterio, geopandas, networkx）
□ 准备存储空间（建议>100GB）

Phase 1 - 数据准备（2-3天）：
□ 下载流域边界（HydroSHEDS）
□ 确定缓冲区（50km）
□ 下载DEM瓦片（SRTM/MERIT）
□ 验证瓦片完整性

Phase 2 - 数据拼接（1天）：
□ Python拼接脚本准备
□ 执行拼接
□ QGIS检查质量
□ 裁剪到边界+缓冲区

Phase 3 - TauDEM处理（1-2天）：
□ 运行完整命令序列
□ 检查streamnet.shp生成
□ 验证拓扑关系（USLINKNO/DSLINKNO）

Phase 4 - SHUC优化（4-6小时）：
□ Python读取TauDEM输出
□ 构建拓扑网络
□ 运行动态阈值合并
□ 分配SHUC编码
□ 导出结果

验证：
□ 目视检查样本流域
□ 统计验证（数量、面积分布）
□ 拓扑验证（无循环、无孤立）
```

---

**这个详细方案是否满足你的需求？需要我提供完整的Python脚本吗？**