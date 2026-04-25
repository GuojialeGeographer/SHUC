# MERIT Hydro 空间上下文完整性分析与 SHUC 实施方案

## 问题 1：MERIT Hydro 数据的空间上下文完整性

### 1.1 官方变量的空间信息评估

| 变量 | 空间信息类型 | 完整性 | 局限性 |
|:---|:---|:---|:---|
| `dir` (流向) | ✅ 拓扑关系（D8） | 高 | 无显式流域边界 |
| `upa` (上游面积) | ✅ 汇流累积量 | 高 | 无空间参考边界 |
| `elv` (高程) | ✅ 地形约束 | 中 | 已水文修正，非原始DEM |
| `upg` (上游梯度) | ✅ 地形坡度 | 中 | 辅助信息 |
| `wth` (河宽) | ✅ 河道形态 | 低 | 仅河道中心线 |
| `hnd` (HAND) | ✅ 相对高度 | 中 | 依赖排水网络 |

### 1.2 空间上下文的不足

**缺失的关键信息：**
- ❌ **显式流域边界多边形** - 只有栅格ID，无矢量边界
- ❌ **跨区域拓扑连续性** - 30°×30° 包边界处的流域ID不连续
- ❌ **坐标精度说明** - 90m 分辨率，但实际精度未明确
- ❌ **高程基准转换** - EGM96 → WGS84 椭球高需转换

### 1.3 与 MERIT-Basins 的对比

| 维度 | MERIT Hydro (栅格) | MERIT-Basins (向量) |
|:---|:---|:---|
| 流域边界 | ❌ 需矢量化 | ✅ 现成多边形 |
| 拓扑关系 | ⚠️ 需从 dir 推导 | ✅ NextDownID, up1-up4 |
| 面积计算 | ⚠️ 需投影转换 | ✅ 已有 uparea |
| 跨区域连续 | ❌ 需拼接处理 | ✅ 全球统一 COMID |
| 处理复杂度 | 高 | 低 |

**结论：MERIT Hydro 栅格数据**不直接提供完整的空间上下文**，必须通过额外处理或与 MERIT-Basins 结合使用。**

---

## 问题 2：流域边界合并的空间上下文需求

### 2.1 合并所需的核心信息

```
必需信息：
├── 几何边界（多边形）
├── 拓扑关系（上下游）
├── 面积属性（km²）
└── 空间参考（坐标系）

优化信息：
├── 高程约束（防止跨分水岭合并）
├── 河道连通性验证
└── 相邻关系矩阵
```

### 2.2 仅靠 dir + upa 是否足够？

**理论上可行，但工程复杂度高：**

```
dir (流向) → 构建 DAG (有向无环图) → 追踪上下游
upa (面积) → 确定 outlet 位置 → 划分子流域

问题：
1. 需要从 dir 显式构建拓扑图
2. 需要设定阈值确定子流域出口
3. 需要矢量化栅格为多边形
4. 需要处理跨瓦片边界
```

### 2.3 跨区域接边问题

**MERIT Hydro 的 30°×30° 打包策略导致：**

| 问题 | 影响 | 解决方案 |
|:---|:---|:---|
| 包边界流域ID不连续 | 无法直接拼接 | 需重新分配全局唯一ID |
| 流向跨包追踪 | 可能中断 | 需加载相邻包的 dir 数据 |
| 面积累积跨包 | 计算不完整 | 需从上游到下游顺序处理 |

**解决方案：分块处理 + 全局拓扑重建**

---

## 问题 3：DEM 数据在流域边界生成中的作用

### 3.1 是否需要原始 DEM？

**关键判断：MERIT Hydro 的 `elv` 已经是水文修正后的 DEM**

```
原始 DEM → 填洼 → 流向 → 累积量 → 河网 → 流域
                    ↓
        MERIT Hydro elv (已完成水文修正)
```

**结论：不需要额外下载原始 DEM，因为：**

1. MERIT Hydro `elv` 已消除洼地和平坦区
2. `dir` 和 `upa` 已基于修正后的 DEM 计算
3. 重新处理原始 DEM 会引入新的误差

### 3.2 如何用 MERIT 数据去除干扰？

```python
# 示例：识别并排除海洋/无效区域
with rasterio.open('upa.tif') as src:
    upa = src.read(1)
    
    # 排除海洋 (upa = -9999) 和内陆洼地 (upa = 0)
    valid_mask = (upa > 0) & (upa != -9999)
    
    # 排除极小流域（噪声）
    min_area_km2 = 1.0  # 1 km² 阈值
    noise_mask = upa < min_area_km2
    
    final_mask = valid_mask & ~noise_mask
```

### 3.3 瓦片与打包数据的结合策略

```
Phase 1: 解压 30°×30° 包
  dir_n30e90.tar → 36 个 5°×5° tile (dir)
  upa_n30e90.tar → 36 个 5°×5° tile (upa)

Phase 2: 拼接全国栅格
  rasterio.merge() → china_dir.tif, china_upa.tif

Phase 3: 从 dir 构建全局拓扑
  逐像素追踪流向 → 构建 DAG
  识别 outlet → 生成子流域ID

Phase 4: 矢量化流域边界
  rasterio.features.shapes() → 多边形
```

---

## 问题 4：完整流域边界水文数据生成方案

### 4.1 推荐方案：MERIT-Basins + MERIT Hydro 组合

```
┌─────────────────────────────────────────────────────────┐
│                    数据源组合方案                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MERIT-Basins (向量)                                     │
│  ├── 初始流域边界 (polygon)                             │
│  ├── 拓扑关系 (NextDownID, up1-up4)                     │
│  └── 面积属性 (uparea, unitarea)                        │
│                                                         │
│  MERIT Hydro v1.0.1 (栅格)                              │
│  ├── upa: 面积分布分析、阈值优化                        │
│  ├── elv: 地形约束、合并合理性验证                      │
│  ├── dir: 流向验证、拓扑校验                            │
│  └── wth: 河道形态分析（可选）                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 完整处理流程

```python
# Phase 1: 加载 MERIT-Basins 向量数据
basins = gpd.read_file('MERIT_Basins.shp')

# Phase 2: 坐标系转换与面积计算
# 转换为等积投影
basins_eq = basins.to_crs('ESRI:102008')  # Asia Lambert Azimuthal Equal Area
basins['area_km2'] = basins_eq.geometry.area / 1_000_000

# Phase 3: 拓扑验证
# 检查 NextDownID 是否完整
missing_topology = basins[basins['NextDownID'].isin([-1, 0]) & 
                         (basins['uparea'] > 100)]
print(f"缺失拓扑的流域数: {len(missing_topology)}")

# Phase 4: 加载 MERIT Hydro upa 用于分析
import rasterio
with rasterio.open('china_upa_mosaic.tif') as src:
    upa_raster = src.read(1)
    upa_transform = src.transform
    
    # 提取每个流域的 upa 统计
    for idx, row in basins.iterrows():
        centroid = row.geometry.centroid
        row_idx, col_idx = ~src.index(centroid.x, centroid.y)
        if 0 <= row_idx < upa_raster.shape[0] and \
           0 <= col_idx < upa_raster.shape[1]:
            basins.loc[idx, 'upa_at_outlet'] = upa_raster[row_idx, col_idx]

# Phase 5: SHUC 合并处理
# 见问题 5 的详细方案
```

### 4.3 几何修复与坐标系统一

```python
from shapely.validation import make_valid
from pyproj import Geod

# 方案 A: 使用 make_valid 修复几何
invalid_mask = ~basins.geometry.is_valid
if invalid_mask.any():
    print(f"修复 {invalid_mask.sum()} 个无效几何")
    basins.loc[invalid_mask, 'geometry'] = \
        basins.loc[invalid_mask, 'geometry'].apply(make_valid)

# 方案 B: 使用 Geod 计算大地测量面积（无需投影）
geod = Geod(ellps='WGS84')
for idx, row in basins.iterrows():
    geom = row.geometry
    if geom.geom_type == 'Polygon':
        area_m2, _ = geod.geometry_area_perimeter(geom)
        basins.loc[idx, 'area_km2'] = abs(area_m2) / 1_000_000
    elif geom.geom_type == 'MultiPolygon':
        total_area = sum(geod.geometry_area_perimeter(p)[0] 
                        for p in geom.geoms)
        basins.loc[idx, 'area_km2'] = abs(total_area) / 1_000_000
```

---

## 问题 5：SHUC 6 级 12 位编码系统的数据基础

### 5.1 完整的 6 级编码体系定义

| 级别 | 编码长度 | 面积阈值 | 空间范围 | 示例 |
|:---|:---:|:---|:---|:---|
| Level 1 | 2 位 | >500,000 km² | 一级水系（长江、黄河等） | `01` |
| Level 2 | 4 位 | 50,000-500,000 km² | 二级流域（支流） | `0101` |
| Level 3 | 6 位 | 5,000-50,000 km² | 三级子流域 | `010101` |
| Level 4 | 8 位 | 1,000-5,000 km² | 中流域 | `01010101` |
| Level 5 | 10 位 | 200-1,000 km² | 小流域 | `0101010101` |
| Level 6 | 12 位 | 50-200 km² | 基本单元 | `010101010101` |

### 5.2 动态阈值算法的适用性

```python
def calculate_dynamic_threshold(areas, region_name=None):
    """
    动态阈值计算
    
    公式: threshold = Q75 + (Q90 - Q75) / 2
    
    参数:
        areas: 流域面积序列 (km²)
        region_name: 区域名称（用于日志）
    
    返回:
        threshold: 动态阈值 (km²)
    """
    q75 = areas.quantile(0.75)
    q90 = areas.quantile(0.90)
    
    # 核心公式
    threshold = q75 + (q90 - q75) / 2
    
    # 约束在合理范围
    threshold = max(50, min(1000, threshold))
    
    if region_name:
        print(f"[{region_name}] Q75={q75:.1f}, Q90={q90:.1f}, "
              f"threshold={threshold:.1f} km²")
    
    return threshold

# 示例：分区计算阈值
for basin in ['yangtze', 'huai', 'pearl']:
    sub_areas = basins[basins['region'] == basin]['area_km2']
    threshold = calculate_dynamic_threshold(sub_areas, basin)
```

### 5.3 SHUC 编码生成流程

```python
class SHUCEncoder:
    def __init__(self):
        self.level_definitions = {
            1: {'bits': 2,  'min_area': 500000},
            2: {'bits': 4,  'min_area': 50000},
            3: {'bits': 6,  'min_area': 5000},
            4: {'bits': 8,  'min_area': 1000},
            5: {'bits': 10, 'min_area': 200},
            6: {'bits': 12, 'min_area': 50},
        }
    
    def assign_levels(self, gdf):
        """分配层级"""
        for idx, row in gdf.iterrows():
            area = row['area_km2']
            for level in sorted(self.level_definitions.keys(), reverse=True):
                if area >= self.level_definitions[level]['min_area']:
                    gdf.loc[idx, 'shuc_level'] = level
                    break
        
        return gdf
    
    def generate_codes(self, gdf):
        """生成 SHUC 编码"""
        # 基于拓扑关系和层级生成层级编码
        # 需要上游流域的编码来确定本级编码
        pass
```

---

## 问题 6：网关边界数据的空间上下文分析

### 6.1 网关边界数据的问题

如果"网关边界"指的是流域出口的断面数据，那么：

| 问题 | 影响 | 解决方案 |
|:---|:---|:---|
| 坐标系统一 | 可能与流域边界不一致 | 统一转换到同一 CRS |
| 空间精度 | 点位 vs 多边形 | 缓冲区分析验证 |
| 拓扑关联 | 网关是否属于某流域 | 空间连接 (sjoin) |

### 6.2 一致性保证机制

```python
# 验证网关与流域边界的空间一致性
from shapely.ops import nearest_points

def validate_gateway_consistency(gateways, basins):
    """验证网关是否在流域边界内或边界上"""
    results = []
    
    for gw in gateways.iterrows():
        gw_geom = gw[1].geometry
        
        # 查找最近的流域
        nearest_basin = basins[basins.geometry.distance(gw_geom).idxmin()]
        
        # 计算距离
        dist = gw_geom.distance(nearest_basin.geometry)
        
        # 判断是否在流域内
        within = nearest_basin.geometry.contains(gw_geom)
        
        results.append({
            'gateway_id': gw[1].gateway_id,
            'basin_id': nearest_basin.LINKNO,
            'distance_m': dist,
            'within_basin': within,
        })
    
    return gpd.GeoDataFrame(results)
```

---

## 最终推荐实施方案

### 数据源配置

```
1. MERIT-Basins (向量)
   - 下载: https://www.reachhydro.org/home/params/merit-basins
   - 包含: 流域边界 + 拓扑关系 + 面积属性
   - 用途: 作为 SHUC 的基础骨架

2. MERIT Hydro v1.0.1 (栅格)
   - 下载: https://global-hydrodynamics.github.io/MERIT_Hydro/
   - 包含: dir, upa, elv, upg, wth, hnd
   - 用途: 面积分析、阈值优化、地形验证
   - 许可: CC BY-NC 4.0 / ODbL 1.0

3. 中国国界数据 (矢量)
   - 来源: 国家基础地理信息中心
   - 用途: 裁剪全国范围
```

### 处理流程

```
Phase 1: 数据准备 (1-2 天)
  ├── 下载 MERIT-Basins 向量数据
  ├── 下载 MERIT Hydro (6 个 package × 2 变量)
  ├── 解压并拼接全国 upa 栅格
  └── 加载并验证数据完整性

Phase 2: 数据预处理 (1 天)
  ├── 坐标系转换 (EPSG:4326 → 等积投影)
  ├── 面积计算 (Geod 或投影后计算)
  ├── 几何修复 (make_valid)
  └── 拓扑验证 (NextDownID 完整性检查)

Phase 3: 流域合并 (2-3 天)
  ├── 计算动态阈值 (全国 + 分区)
  ├── 构建拓扑图 (基于 NextDownID)
  ├── 执行迭代合并
  └── 合并后拓扑更新

Phase 4: 编码分配 (1 天)
  ├── 层级分配 (基于面积阈值)
  ├── SHUC 编码生成
  └── 编码唯一性验证

Phase 5: 质量验证 (1 天)
  ├── 面积合规率检查
  ├── 拓扑完整性验证
  ├── 几何有效性检查
  └── 生成验证报告

Phase 6: 成果输出 (0.5 天)
  ├── 导出 SHUC 编码矢量
  ├── 生成统计报告
  └── 可视化成果
```

### 关键技术保障

```
✅ 空间参考: WGS84 → 等积投影 (ESRI:102008)
✅ 面积计算: Geod.geometry_area_perimeter() 或投影后计算
✅ 几何修复: shapely.make_valid() 替代 buffer(0)
✅ 拓扑关系: 直接使用 MERIT-Basins 的 NextDownID
✅ 坐标系统一: 全链路使用同一 CRS
✅ 内存优化: 分块处理、避免全图矢量化
```

---

## 总结

| 问题 | 结论 | 方案 |
|:---|:---|:---|
| MERIT Hydro 空间上下文 | ❌ 不完整 | 结合 MERIT-Basins |
| 仅靠 dir+upa 是否足够 | ⚠️ 理论可行，工程复杂 | 使用 MERIT-Basins 拓扑 |
| 是否需要原始 DEM | ❌ 不需要 | MERIT elv 已水文修正 |
| 完整处理流程 | ✅ 已设计 | 6 Phase 方案 |
| SHUC 编码体系 | ⚠️ 需完善 Level 1-3 | 已补充完整定义 |
| 网关边界一致性 | ⚠️ 需验证 | 空间连接验证 |

**最终推荐：MERIT-Basins (拓扑骨架) + MERIT Hydro (栅格分析) + SHUC 算法 (合并优化)**
---

# 结论先行

**MERIT Hydro v1.0.1 作为高质量全球水文栅格底图，具备“基础空间参考”和“水文路由核心变量”，但它并不具备用于全国流域边界合并与分级编码所需的完整空间上下文。**  
它已经提供了 WGS84、EGM96、约 90 m 分辨率、统一瓦片组织、`dir/elv/upa/upg/wth/hnd` 等重要信息，但**缺少**直接可用的 basin mask、显式上下游拓扑、河口类型、分汊处理、河湖分离、海岸窄通道判别等关键上下文；官方也明确列出了分汊、海岸、冰川、海平面以下区域等已知问题。因此，如果目标是构建中国尺度、可合并、可编码、可验证的 SHUC 流域体系，**最稳妥方案不是“只用 MERIT Hydro”**，而是采用一个**混合框架**：  
**MERIT-Basins 作为拓扑骨架，MERIT Hydro 作为高分辨率栅格水文约束，DEM 作为局部精化与质量控制依据。** [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://www.reachhydro.org/home/params/merit-basins) [Source](https://deltares.github.io/hydromt/v0.5.0/_examples/delineate_basin.html)

---

## 参考示意图

**MERIT Hydro 瓦片组织示意**  
![MERIT Hydro tiling scheme](https://global-hydrodynamics.github.io/assets/merit_hydro/MERIT_tile.png)  
MERIT Hydro 以 5°×5° tile 存储，并打包为 30°×30° package，这对全国分块拼接与边界接边非常重要。 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

**MERIT-Plus 针对内流/外流与海岸连通性的处理流程图**  
![MERIT-Plus workflow](https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2238/10781961/bd639d552fbb/41597_2023_2875_Fig1_HTML.jpg)  
这张图很直观地说明：仅靠基础 flow direction 并不足以完整表达复杂海岸与内流空间上下文，必须引入额外规则与判别流程。 [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/)

---

# 1. MERIT Hydro 的空间上下文完整性：够不够用？

## 1.1 它“有”的空间上下文

MERIT Hydro 官方主产品提供了相当重要的基础空间上下文：  
它有统一的水平参考系统 **WGS84**，垂直参考 **EGM96 geoid**，分辨率为 **3 arc-second（约 90 m）**，变量包括 `dir`、`elv`、`upa`、`upg`、`wth`、`hnd`，并采用一致的 **5°×5° tile + 30°×30° package** 组织方式。这些信息足以支持全国一致的栅格拼接、流向分析、汇流分析、河网提取和局部流域划分。 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

换句话说，如果你的任务只是做“高分辨率流向/汇流分析”或“从点位自动圈定上游流域”，MERIT Hydro 是一个非常强的基础数据源。HydroMT 的示例也说明，基于 MERIT Hydro 的 flow direction 数据可以开展 basin delineation，但它同时指出：实际高效划分时，通常还会扩展一个 **basin mask layer** 和 basin index vector，这本身就说明“原始 MERIT Hydro 单独使用时，空间上下文还不够完整”。 [Source](https://deltares.github.io/hydromt/v0.5.0/_examples/delineate_basin.html)

## 1.2 它“没有”的空间上下文

真正的问题在于：**MERIT Hydro 主发布版并没有直接提供一个官方标准的 basin mask / basin polygon / downstream linkage 框架。**  
官方变量里没有 `bas`，也没有像 `NextDownID`、`up1-up4` 这样的显式河网拓扑字段。也就是说，它提供的是“水文栅格语义”，但不是“现成可合并的流域拓扑单元”。 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://www.reachhydro.org/home/params/merit-basins)

更重要的是，官方已知问题正好指向你最关心的“空间上下文缺口”：

- **Channel bifurcations**：每个像元只允许一个下游方向，三角洲、漫滩、辫状河处理不佳；
- **Water body inconsistencies**：DEM 陆海掩膜和水体数据不一致；
- **River/lake separation**：河流与湖泊未被充分区分；
- **Below sea-level areas**：海平面以下区域表现不佳；
- **Flow direction over glaciers**：冰川区流向不可靠；
- 干旱洼地在高水位偶连时会导致 **watershed boundaries uncertain**。 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

这意味着：  
**MERIT Hydro 对“水文路由”很强，但对“流域边界合并所需的完整空间上下文”并不充分。**

## 1.3 与 [MERIT-Basins](https://www.reachhydro.org/home/params/merit-basins) 相比，它缺什么？

MERIT-Basins 是从 MERIT-Hydro 派生的**向量水文数据库**，它直接提供：

- `COMID`
- `unitarea`
- `uparea`
- `NextDownID`
- `up1`–`up4`
- `maxup`
- `order`
- `lengthkm`
- `slope_taudem`

这类字段是做“上下游关系维护、单元流域合并、分级编码”的天然骨架。它还按 **Pfafstetter level 1 / 2** 分区组织，这对全国分块处理非常有启发。相比之下，MERIT Hydro 原始栅格更像“底层连续场”，而 MERIT-Basins 更像“结构化拓扑网络”。 [Source](https://www.reachhydro.org/home/params/merit-basins)

**因此：**
- 如果你要做**水文编码系统**，MERIT-Basins 更适合作为骨架；
- 如果你要做**边界精化与局部纠偏**，MERIT Hydro 和 DEM 更适合作为约束层。 [Source](https://www.reachhydro.org/home/params/merit-basins) [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

---

# 2. 流域边界合并到底需要哪些空间上下文？

## 2.1 合并不是“面积足够”这么简单

流域边界合并至少需要以下 8 类上下文信息：

1. **统一 CRS / datum / 像元对齐**
2. **稳定的 basin/unit ID**
3. **上下游拓扑关系**
4. **共享边界与邻接关系**
5. **pour point / outlet 位点**
6. **海岸 / 湖泊 / 内流外流判别**
7. **几何有效性与无缝接边**
8. **面积、长度、坡降等约束指标**

仅靠 `dir + upa`，理论上可以派生很多信息，但工程上并不意味着“直接够用”。你仍然需要 basin mask、出口点、边界栅格、邻接矩阵、海岸上下文和质量控制机制。MERIT-Plus 的论文就明确说明：**upstream area 和 basin ID mask 可以从 flow direction 派生**，但同时也强调，单靠简单邻域判断并不能可靠地区分内流/外流，因为海岸窄通道、三角洲低地、大河宽水面和 DEM 误差都会干扰结果。 [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/)

## 2.2 `dir + upa` 是否足够？

**结论：对“初步划分”来说，基本足够；对“全国可靠合并与编码”来说，不够。** [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/) [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

原因是：

- `dir` 给你的是单下游方向，但对分汊区天然不足；
- `upa` 给你的是集水规模，但不告诉你边界几何是否干净；
- 你仍然需要知道哪个 basin 与哪个 basin 共享边界、共享多长边、哪个是真正下游宿主、海岸口门是否为外流口等。 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/)

所以工程上更稳的判断是：

- **`dir + upa` = 必要但不充分**
- **`dir + upa + basin mask + outlet logic + adjacency + DEM QA` = 接近可用**
- **`MERIT-Basins topology + MERIT Hydro raster + DEM local refinement` = 最可控**

## 2.3 跨区域接边、几何有效性、拓扑保持怎么处理？

### 栅格接边
MERIT Hydro 官方 tile 组织是一致的，但拼接时仍要保证：
- 同波段数
- 同数据类型
- 同 CRS
- 同 nodata 语义
- 像元边界对齐

`rasterio.merge` 官方就明确要求输入栅格需具有相同 band 数、dtype 和 CRS；旋转或翻转栅格不能直接 merge。 [Source](https://rasterio.readthedocs.io/en/stable/api/rasterio.merge.html)

### 拓扑保持
合并顺序建议固定为：
1. 明确下游宿主；
2. 若无下游，则查最大上游；
3. 再查真实共享边界邻居；
4. 最后才允许“最近邻”兜底。  
否则很容易产生水文上不连通的“飞地合并”。

### 几何有效性
合并后的 polygon 需要统一做有效性检查。现代做法优先使用 `GeoSeries.make_valid()`，而不是传统 `buffer(0)`。GeoPandas 官方已提供 `make_valid`。 [Source](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoSeries.make_valid.html)

---

# 3. DEM 在流域边界生成里是不是“必须的”？

## 3.1 严格说：不是所有步骤都必须，但要做“精确边界”，几乎离不开 DEM

如果你只想快速得到一个全国可运行的水文编码框架，**MERIT-Basins + MERIT Hydro** 就可以先落地。  
但如果你的目标是：

- 精化边界；
- 处理内流/外流歧义；
- 修复海岸、山口、冰川、湖群、分汊区；
- 论证“边界合理性”；

那么 DEM 几乎是必需的，因为它提供了**分水岭、洼地、山口、坡降、出口高差**等几何与地形证据。 [Source](https://hydrology.usu.edu/taudem/taudem5/TauDEM5DelineatingASingleWatershed.pdf)

## 3.2 DEM 怎么“去除其他数据源干扰”？

需要强调一点：**DEM 不是自动消噪神器**。  
它本身也会有坑洼、桥梁、堤坝、插值误差、低地平坦区问题，所以必须先做水文预处理。TauDEM 的标准流程非常明确：

- Pit Remove
- D8 Flow Direction
- D8 Contributing Area
- Stream Definition by Threshold
- Move Outlets to Streams
- Stream Reach and Watershed
- Watershed Grid to Shapefile [Source](https://hydrology.usu.edu/taudem/taudem5/TauDEM5DelineatingASingleWatershed.pdf)

这个流程的启示是：  
**不要把 DEM 当原始真值直接用，而要把它当“需经过水文整饰的地形约束层”。**

更合理的用法是：

- 用 MERIT Hydro 的 `dir/upa/elv` 作为全球一致底层；
- 用 DEM 在争议区重算或校验分水线；
- 用河网烧入、出口吸附、低洼区处理来减少干扰。 [Source](https://hydrology.usu.edu/taudem/taudem5/TauDEM5DelineatingASingleWatershed.pdf) [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

## 3.3 MERIT Hydro 与 DEM 怎么结合？

最佳实践不是“二选一”，而是分工：

- **MERIT Hydro `dir/upa/elv`**：全国一致、已水文校正、适合大范围骨架分析；
- **原始/区域高精度 DEM**：局部纠偏与边界精化；
- **MERIT-Basins**：向量拓扑骨架。 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://www.reachhydro.org/home/params/merit-basins)

对中国来说，建议按 **Pfaf-L2 / 一级水系区 / 30° package** 分块处理，然后在块内结合 DEM 精化，再统一拼接。

---

# 4. 一个完整、可行、技术上可靠的生成方案

下面给你一个建议采用的 **Hybrid Hydro Fabric** 方案。

---

## Phase A：建立全国统一基础水文底座

### A1. 数据层
- MERIT Hydro v1.0.1：`dir`, `upa`, `elv`, 可选 `wth`, `hnd`
- MERIT-Basins：`riv_*`, `cat_*`
- 中国边界 / 海岸线 / 湖泊面
- 高精度 DEM（全国或重点区）
- 可选高精海岸线与水体矢量 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://www.reachhydro.org/home/params/merit-basins) [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/)

### A2. 栅格标准化
- 统一 CRS：存储层面保留 EPSG:4326，分析层面按需求投影
- 统一 nodata
- 检查 tile 对齐
- 使用 `rasterio.merge` 进行变量拼接 [Source](https://rasterio.readthedocs.io/en/stable/api/rasterio.merge.html)

### A3. 分块策略
不要整国一次性矢量化。  
`rasterio.features.shapes` 官方明确警告：内存消耗与多边形数量和复杂度成正比，全国尺度直接 polygonize 风险很高。 [Source](https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html)

建议分块依据：
- Pfaf-L2 basin
- 中国一级水系区
- 30°×30° 包
- 或 5°×5° tile

---

## Phase B：构建初始流域单元与拓扑图

### B1. 首选方案：以 [MERIT-Basins](https://www.reachhydro.org/home/params/merit-basins) 为骨架
使用 `cat_*` 作为初始 unit catchment，使用 `riv_*` 中的 `NextDownID`, `up1-up4`, `maxup` 构建有向图。  
这样可以避免从全国 90 m 栅格直接推导所有 basin 邻接与拓扑，极大降低工程风险。 [Source](https://www.reachhydro.org/home/params/merit-basins)

### B2. 补充栅格约束
将 MERIT Hydro 的 `upa/elv/dir` 回填到 unit catchment 或 outlet 点上，形成每个单元的：
- `unitarea`
- `uparea`
- `elev_out`
- `slope`
- `coast_flag`
- `endorheic_flag`
- `boundary_confidence`

### B3. DEM 局部重划
在以下高风险区触发 DEM 重划：
- 三角洲 / 分汊平原
- 海岸低地
- 湖群密集区
- 冰川区
- 内流盆地边缘
- 高原洼地 / 偶连区域 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/)

---

## Phase C：边界精化与合并规则

### C1. 合并候选筛选
只对满足以下条件的单元启动合并：
- 面积低于级别阈值
- 共享边界存在
- 不会打断主干上下游
- outlet / pour point 合理
- 非特殊保护区（湖泊、内流、海岸口门等）

### C2. 合并优先级
推荐你保留这个顺序，但要更严格定义：

1. **明确下游宿主**
2. **最大上游宿主**
3. **最长共享边界邻居**
4. **最低鞍部 / 最低边界高程邻居**
5. **最近邻兜底（仅限极少数失败案例）**

这里第 3、4 项比“纯最近邻”更重要，因为它们更接近水文与地形逻辑。

### C3. 内流/外流特殊处理
MERIT-Plus 的经验非常关键：  
不能只用“是否接触 nodata 海洋像元”来判定内流外流，因为亚网格海岸通道、三角洲低地、大河宽水面都可能误导判断。应采用：

- 河口聚类
- 海岸连通性判定
- 必要时高精海岸线辅助
- endorheic 独立标识，不轻易并入 exorheic [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/)

---

## Phase D：几何、面积、投影与质量控制

### D1. 面积计算
不要在 EPSG:4326 下直接 `geometry.area`。  
GeoPandas 官方明确警告：在 geographic CRS（度单位）下，面积可能无效。 [Source](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoSeries.area.html)

建议两种路线：

- 全国统计：投影到等积 CRS 后计算；
- 精准发表级结果：用 `pyproj.Geod.geometry_area_perimeter()` 计算测地面积。该方法支持 `Polygon` 和 `MultiPolygon`。 [Source](https://pyproj4.github.io/pyproj/stable/api/geod.html)

### D2. 几何修复
优先：

```python
gdf.geometry = gdf.geometry.make_valid()
```

而不是默认 `buffer(0)`。 [Source](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoSeries.make_valid.html)

### D3. 拓扑一致性检查
必须检查：
- overlap = 0
- gap 最小化
- outlet 唯一
- 下游指针无环
- 共享边界一致
- 上下游面积单调性

### D4. 边界一致性输出
对每个单元输出质量标签：
- `geom_valid`
- `topo_valid`
- `coast_sensitive`
- `delta_sensitive`
- `endorheic_flag`
- `source_lineage`
- `revision_level`

---

# 5. SHUC 6级12位编码系统如何建立？

## 5.1 先修正一个设计歧义

你之前的描述里，“6级”与“4-6-8-10-12位”是不一致的，因为后者只有 5 种长度。  
所以在正式实施前，必须先选一种一致方案：

### 推荐方案 A：真正 6 级、6 个长度
- L1：2 位
- L2：4 位
- L3：6 位
- L4：8 位
- L5：10 位
- L6：12 位

### 备选方案 B：保留 4-6-8-10-12，但把“6级”改成“5级编码 + 1个层级属性字段”
如果你坚持原格式，这是更自洽的表述。

从国家标准化和系统实现角度，我更推荐 **A**。它更清楚，也更容易和层级树对应。

## 5.2 建议的各级空间基础

建议各级来源如下：

- **L1**：全国一级水系区 / 外流海域区 + 内流区
- **L2**：二级大流域（可参考 Pfaf-L1/L2 与中国水系认知融合）
- **L3**：区域性子流域
- **L4**：≥1000 km²
- **L5**：≥200 km²
- **L6**：≥50 km²

其中 L1-L3 应主要依赖**稳定水文拓扑 + 专家规则**，L4-L6 才适合更多采用面积阈值和动态合并。

## 5.3 动态阈值公式还适不适用？

你的公式：

\[
threshold = Q75 + \frac{Q90 - Q75}{2}
\]

**可以保留，但不建议全国统一一次性计算。**  
原因是中国流域尺度受气候、地形、内流/外流特征影响极大。更合理的策略是：

- 按 L2 大流域或气候水文区分区计算；
- 在每个分区内求 `Q75/Q90`；
- 再做局部动态阈值；
- 叠加绝对下限约束（如 50 km² / 200 km² / 1000 km²）。

这样既保留自适应，又避免“全国统一阈值把西北和东南混为一谈”。

## 5.4 SHUC 编码生成逻辑建议

每个单元至少保存：

- `shuc_code`
- `shuc_level`
- `parent_code`
- `downstream_code`
- `upstream_count`
- `area_km2`
- `region_code`
- `endorheic_flag`

编码生成遵循：

1. 先建立层级树；
2. 再按下游主干排序；
3. 支流按汇流面积或流序排序；
4. 保证同级唯一、父子嵌套、上下游可追踪。

---

# 6. “网关边界数据”是否也会有同类空间上下文问题？

如果这里的“网关边界数据”是指你现有的某类分区边界、管理边界、接口边界或业务边界数据，那么**答案基本是会的**。  
任何已有边界数据，只要不是在统一水文拓扑、统一 CRS、统一海岸/湖泊处理规则下生成的，就可能存在以下问题：

- CRS 或 datum 不明确
- 面积单位不一致
- 接边不严密
- overlap / gap
- shared edge 不一致
- 与流域出口或河网主干不匹配
- 版本血缘不清晰

这些问题和你现在对流域边界的担忧本质上是一样的。

## 6.1 如何评估网关边界数据完整性？

建议建立一个统一评估框架：

### 空间参考完整性
- CRS 是否明示
- 横纵基准是否清楚
- 是否存在未投影经纬度直接算面积

### 几何完整性
- `is_valid`
- overlap / gap
- multipart 比例
- 自交 / 重复点

### 拓扑一致性
- 边界是否共享
- 是否存在悬挂边
- 是否与河网、流域边界相容

### 语义一致性
- ID 是否唯一
- 层级是否完整
- 是否可与 SHUC 父子树对应

## 6.2 一致性保证机制

建议你建立一个“单一水文底座 + 单一边界生产线”：

- 所有边界从同一 hydro fabric 派生
- 所有面积从同一方法计算
- 所有几何用同一修复与检查规则
- 所有共享边界从同一分割结果继承
- 所有版本都保留 lineage metadata

这样网关边界、流域边界、编码边界就不会各自漂移。

---

# 最终推荐实施方案

## 推荐架构：三层混合式

### 第 1 层：全国统一骨架
以 [MERIT-Basins](https://www.reachhydro.org/home/params/merit-basins) 为基础，建立全国 unit catchment + river reach 拓扑图。 [Source](https://www.reachhydro.org/home/params/merit-basins)

### 第 2 层：高分辨率栅格约束
以 [MERIT Hydro](https://global-hydrodynamics.github.io/MERIT_Hydro/) 的 `dir/upa/elv` 作为流向、汇流和高程约束，补充边界判定和面积统计。 [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

### 第 3 层：DEM 局部精化
在海岸、三角洲、内流、高原湖盆、冰川区等高风险区域，用 TauDEM 流程或同类 DEM 水文处理流程局部重划。 [Source](https://hydrology.usu.edu/taudem/taudem5/TauDEM5DelineatingASingleWatershed.pdf)

---

## 推荐流水线

### Step 1：数据准备
- 下载并拼接中国覆盖区 MERIT Hydro
- 下载 MERIT-Basins 对应分区
- 准备中国边界、海岸线、湖泊、水库、DEM [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://www.reachhydro.org/home/params/merit-basins)

### Step 2：构建全国 hydro fabric
- 用 MERIT-Basins 建图
- 回填 MERIT Hydro 栅格属性
- 识别高风险单元 [Source](https://www.reachhydro.org/home/params/merit-basins) [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/)

### Step 3：局部 DEM 精化
- Pit remove
- flow direction
- contributing area
- stream definition
- outlet snapping
- watershed polygon [Source](https://hydrology.usu.edu/taudem/taudem5/TauDEM5DelineatingASingleWatershed.pdf)

### Step 4：边界合并与规则引擎
- 拓扑优先
- 邻接约束
- 海岸/内流保护
- 几何修复
- 面积重算 [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781961/) [Source](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoSeries.make_valid.html) [Source](https://pyproj4.github.io/pyproj/stable/api/geod.html)

### Step 5：SHUC 编码
- 先确定 6 级定义
- 再生成父子树
- 最后分配 12 位编码
- 输出质量标签与 lineage metadata

### Step 6：质量验证
核心指标建议至少包括：

- 面积合规率
- 几何有效率
- 拓扑完整率
- 编码唯一率
- 内流/外流判定正确率
- 跨块接边一致率
- 与河网主干一致率

---

# 我给你的最终判断

## 如果你的目标是“论文 + 数据产品 + 国家级标准支撑”
那最可靠的技术路线不是：

**只拿 MERIT Hydro 栅格直接全国矢量化 + 合并**

而是：

**MERIT-Basins 拓扑骨架 + MERIT Hydro 高分辨率约束 + DEM 局部精化 + 统一投影/面积/几何/质量控制 + 再做 SHUC 编码。**

这是当前最稳、最容易解释、最能发表、也最适合工程落地的方案。 [Source](https://www.reachhydro.org/home/params/merit-basins) [Source](https://global-hydrodynamics.github.io/MERIT_Hydro/) [Source](https://hydrology.usu.edu/taudem/taudem5/TauDEM5DelineatingASingleWatershed.pdf)
