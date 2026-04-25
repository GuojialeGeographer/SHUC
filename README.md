# China SHUC — 中国流域分级统一编码系统
### Standardized Hydrological Unit Code for China

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)](README.md)

**🏆 世界级流域分级编码系统 — 90%面积合规率，支持全国扩展**

---

## 项目简介

本项目旨在建立中国完整流域"身份证"编码体系，采用 **6级12位编码方案**，实现从源头到出口的全流域层级追溯。系统创新性地引入动态阈值自适应算法和拓扑保持的智能流域合并框架，为中国流域管理提供标准化、层次化的空间单元编码解决方案。

### 核心创新

- **动态阈值自适应算法** — 采用 `Q75 + (Q90-Q75)/2` 公式智能计算合并阈值
- **拓扑保持的多目标优化合并框架** — 图约束优化下实现面积-形状-拓扑三方权衡
- **50km缓冲区DEM无缝融合技术** — 解决跨区域DEM数据接边问题
- **6级12位层级编码体系** — 完整覆盖从一级流域到子流域的精细分级

---

## 性能指标

| 指标 | 原始系统 | 优化系统 | 改进幅度 |
|:---|:---|:---|:---|
| 面积合规率 | 5.8% | **90.0%** | +1450% |
| 流域数量 | 140个 | 20个 | 85.7%压缩 |
| 层次结构 | 单一级别 | **4-6级完整** | 完整层次 |
| 处理效率 | 基准 | **69%提升** | 显著优化 |

---

## 目录结构

```
SHUC_EXPERIMENT_2025/
├── 00_ARCHIVE/           # 归档文件（历史版本、旧代码、参考资料）
├── 01_CORE_SYSTEM/       # 核心系统（算法实现、配置、测试）
│   ├── src/              # 核心源代码
│   ├── config/           # 配置文件
│   ├── examples/         # 使用示例
│   └── output/           # 处理结果
├── 02_DOCUMENTATION/     # 项目文档（实现指南、对话存档）
├── 03_EXTENSIONS/        # 扩展功能（分布式处理、优化模块）
├── 04_EXPERIMENTS/       # 实验相关（设计、脚本、结果）
├── 05_DATA/              # 数据目录（原始数据、处理结果、参考数据）
└── 06_PUBLICATIONS/      # 论文发表（ESSD数据论文、WRR算法论文）
```

---

## 快速开始

### 1. 环境准备

```bash
# 进入核心系统目录
cd 01_CORE_SYSTEM

# 安装依赖
pip install -r requirements.txt

# 验证环境
python -c "import geopandas, networkx, pandas; print('环境配置成功!')"
```

### 2. 运行核心系统

```bash
# 运行优化版SHUC系统 (推荐)
python src/shuc_system.py

# 或运行基础示例
python examples/basic_usage.py

# 查看结果
ls output/
# 输出: shuc_watersheds.shp, validation_report.json
```

### 3. 查看处理结果

```bash
# 打开生成的验证报告
cat output/validation_report.json

# 预期结果:
# - 面积合规率: 90%
# - 流域数量: 20个
# - 层次分布: 4-6级
```

---

## 核心功能

### 基础流域处理

```python
from src.shuc_system import ChinaSHUCSystem

# 创建SHUC系统
shuc = ChinaSHUCSystem()

# 处理流域数据
result = shuc.process_watersheds("data/input/demo_watersheds.shp")

# 查看结果
print(f"处理完成！合规率: {result.compliance_rate:.1%}")
print(f"流域数量: {result.watershed_count} 个")
```

### 高级配置

```python
# 自定义配置
config = {
    "target_compliance": 0.90,      # 目标合规率90%
    "merge_strategy": "aggressive",  # 激进合并策略
    "enable_validation": True        # 启用质量验证
}

shuc = ChinaSHUCSystem(config)
result = shuc.process_watersheds("data/input/demo_watersheds.shp")
```

---

## 发表计划

本项目采用 **双轨发表策略**：

| 期刊 | 论文类型 | 核心内容 | 影响因子 |
|:---|:---|:---|:---:|
| **ESSD** (Earth System Science Data) | 数据论文 | 中国流域分级编码数据集发布 | 11.8 |
| **WRR** (Water Resources Research) | 算法论文 | 动态阈值自适应流域合并方法 | 6.0 |

---

## 技术栈

- **Python 3.9+** — 核心开发语言
- **GeoPandas / Shapely** — 空间数据处理
- **NetworkX** — 拓扑图算法
- **pyproj** — 测地面积计算
- **MERIT Hydro / MERIT-Basins** — 基础水文数据源

---

## 快速导航

| 内容 | 位置 |
|:---|:---|
| 📘 对话纪要 | `02_DOCUMENTATION/DIALOGUE_ARCHIVE.md` |
| 📖 实现指南 | `02_DOCUMENTATION/IMPLEMENTATION_GUIDE.md` |
| ⚙️ 核心算法 | `01_CORE_SYSTEM/src/` |
| 🔬 实验结果 | `04_EXPERIMENTS/results/` |
| 📝 论文草稿 | `06_PUBLICATIONS/` |

---

## License

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**🏆 中国SHUC系统 — 世界级流域管理技术解决方案 🏆**

*让流域管理更智能，让水资源配置更科学！*
