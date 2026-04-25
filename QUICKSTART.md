# SHUC 系统快速启动指南

## 当前状态

✅ **核心系统已验证** - demo数据端到端测试通过
✅ **数据Pipeline就绪** - MERIT Hydro自动化处理脚本已就绪
✅ **生产配置就绪** - 配置文件已适配大规模流域处理

## 下一步行动：数据基础建设

### 第一步：下载 MERIT Hydro 数据

```bash
cd 04_EXPERIMENTS/scripts

# 查看所需瓦片
python download_merit_hydro.py --basin yangtze --list-tiles

# 生成下载脚本
python download_merit_hydro.py --basin yangtze --script > download_yangtze.sh

# 编辑脚本，设置cookie/token
# 然后执行下载
bash download_yangtze.sh
```

**数据说明：**
- 长江流域：32个瓦片，约 10-20 GB
- 淮河流域：6个瓦片，约 2-4 GB  
- 珠江流域：8个瓦片，约 3-5 GB

**数据源注册：**
访问 http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/ 注册获取下载权限

### 第二步：运行 Pipeline 处理

数据下载完成后：

```bash
cd 04_EXPERIMENTS/scripts

# 完整Pipeline（长江流域）
python merit_to_shuc_pipeline.py \
  --basin yangtze \
  --merit-dir ../../05_DATA/raw/merit_hydro \
  --output-dir ../../04_EXPERIMENTS/results/yangtze

# 或者使用预处理+编码分步执行
python preprocess_watersheds.py \
  --input raw_basins.tif \
  --output processed_watersheds.shp \
  --from-raster

cd ../../01_CORE_SYSTEM
python -c "
from src.shuc_system import ChinaSHUCSystem
shuc = ChinaSHUCSystem(config_path='config/shuc_config_production.json')
result = shuc.process_watersheds('../04_EXPERIMENTS/scripts/processed_watersheds.shp')
result.print_summary()
"
```

### 第三步：验证结果

```bash
# 检查输出
ls -lh 04_EXPERIMENTS/results/yangtze/*/05_shuc/

# 查看统计
cat 04_EXPERIMENTS/results/yangtze/*/05_shuc/pipeline_metadata.json
```

## 项目结构

```
SHUC_EXPERIMENT_2025/
├── 01_CORE_SYSTEM/           # 核心系统
│   ├── src/                  # 5个核心模块 (1,697行)
│   ├── config/               # 配置文件
│   │   ├── shuc_config.json           # 开发配置
│   │   └── shuc_config_production.json # 生产配置
│   └── output/               # 处理输出
│
├── 04_EXPERIMENTS/           # 实验系统
│   ├── scripts/              # 处理脚本
│   │   ├── download_merit_hydro.py     # 数据下载
│   │   ├── merit_to_shuc_pipeline.py   # 完整Pipeline
│   │   └── preprocess_watersheds.py    # 数据预处理
│   └── results/              # 实验结果
│
└── 05_DATA/                  # 数据目录
    ├── raw/                  # 原始数据 (待填充)
    ├── processed/            # 处理后数据
    └── reference/            # 参考数据
```

## 核心代码修复记录

### 已修复的 Bug

1. **字段兼容性** - `DSLINKNO1` → `DSLINKNO` 自动适配
2. **GeoDataFrame 空判断** - `if not gdf:` → `if gdf.empty:`
3. **输入路径搜索** - 自动搜索多个可能的数据位置
4. **验证字段检查** - 降低字段要求，兼容不同数据源

### 测试结果

```
流域数量: 140 → 7 (95% 压缩率)
面积合规率: 85.7%
系统评分: 87.1/100
处理耗时: 0.9 秒
```

## 配置文件说明

### 开发配置 (`shuc_config.json`)
- 适用于测试和小规模数据
- level_4 quota: 3
- max_iterations: 50

### 生产配置 (`shuc_config_production.json`)
- 适用于大规模流域处理
- 无 quota 限制
- max_iterations: 100
- max_memory: 16 GB

## 常见问题

### Q: Python 环境问题
A: 使用 anaconda python:
```bash
/Applications/anaconda3/bin/python3
```

### Q: 依赖缺失
A: 安装依赖:
```bash
pip install geopandas rasterio networkx shapely scipy
```

### Q: 数据下载失败
A: 检查:
1. 是否已注册 MERIT Hydro 账号
2. 网络连接是否正常
3. 存储空间是否足够

## 联系与支持

项目文档:
- 02_DOCUMENTATION/  - 实现指南
- 00_ARCHIVE/legacy_documentation/ - 策略文档

核心代码:
- 01_CORE_SYSTEM/src/shuc_system.py - 主入口
- 01_CORE_SYSTEM/src/watershed_processor.py - 流域合并
- 01_CORE_SYSTEM/src/hierarchy_encoder.py - 编码分配
- 01_CORE_SYSTEM/src/quality_validator.py - 质量验证
