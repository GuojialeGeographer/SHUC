# China SHUC 项目全面审计报告

> 审计日期：2026-04-04
> 审计范围：项目结构、技术成熟度、文档完整度、论文准备度
> 审计目标：为冲击高水平SCI期刊（ESSD + WRR）提供项目状态基线和重组方案

---

## 目录

1. [项目状态量化评估](#1-项目状态量化评估)
2. [内容分类与处置建议](#2-内容分类与处置建议)
3. [目录结构重组方案](#3-目录结构重组方案)
4. [项目进度汇报](#4-项目进度汇报)
5. [MERIT Hydro 数据获取策略评审](#5-merit-hydro-数据获取策略评审)
6. [决策支持](#6-决策支持)
7. [执行路线图](#7-执行路线图)

---

## 1. 项目状态量化评估

### 1.1 整体概况

| 指标 | 数值 |
|:---|:---|
| 项目总大小 | 14 MB |
| 文件总数 | 221 个 |
| Python 代码行数 | ~5,063 行（核心 1,697 + 扩展 3,366） |
| 文档总量 | ~350 KB（12+ 个 Markdown 文档） |
| 项目时间跨度 | 2025-08-30 ~ 2026-04-04（约7个月） |
| 目标期刊 | ESSD（IF 11.8）+ WRR（IF 6.0） |

### 1.2 四维量化评分

| 维度 | 评分 | 满分 | 说明 |
|:---|:---:|:---:|:---|
| **技术成熟度** | **82** | 100 | 核心算法完成，小规模验证通过；但缺少万级验证和跨地形测试 |
| **文档完整度** | **55** | 100 | 内容丰富但严重分散，12+ 文档有大量重叠，缺乏精炼终稿 |
| **代码组织度** | **45** | 100 | 重组已完成约60%；01/04已填充，05/06仍为空壳 |
| **论文准备度** | **25** | 100 | 策略规划完善，但论文初稿、对比实验、图表均为零 |
| **综合健康度** | **52** | 100 | 前期开发扎实，后半程（实验 + 论文）严重滞后 |

### 1.3 重组执行状态评估

上次重组（PROJECT_AUDIT 中规划）完成度约 **60%**：

```
已完成：
  [x] 00_ARCHIVE/ — 旧代码（11个py）和旧文档（INDEX.md）已归档
  [x] 03_EXTENSIONS/ — 从 SHUC_FINAL_VERSION 复制了扩展代码和文档
  [x] 02_DOCUMENTATION/ — 部分文档已移入（DIALOGUE_ARCHIVE, IMPLEMENTATION_GUIDE 等）
  [x] 04_EXPERIMENTS/ — 实验脚本（3个py）和历史结果已迁入
  [x] README.md — 已更新为新结构

未完成（关键缺失）：
  [ ] 01_CORE_SYSTEM/ — 空目录！核心代码未迁移
  [ ] 05_DATA/ — 空目录！数据目录未建立
  [ ] 06_PUBLICATIONS/ — 空目录！论文目录未建立
  [ ] 根目录残留 — 7个大型md文档 + 1个py文件 + 2个json配置仍在根目录
  [ ] SHUC_FINAL_VERSION/ 和 CHINA_SHUC_SYSTEM_FINAL/ 仍未整合
  [ ] 文档整合（12个 -> 3-4个）完全未执行
```

### 1.4 项目发展时间线

```
Phase 1: 原型开发期（2025-08-30）
  标志性文件：shuc_encoder.py, improved_watershed_merger.py, shuc_validator.py
  状态：核心算法已验证，140 -> 20 流域测试通过
  价值：核心代码，仍有参考价值

Phase 2: 系统优化期（2025-08-31）
  标志性文件：shuc_system_final.py, shuc_system_optimized.py, seamless_dem_processor.py
  状态：系统成熟，优化版本完成，90%合规率达成
  价值：生产就绪代码，最重要版本

Phase 3: 工程化包装期（2025-09-06）
  标志性文件：CHINA_SHUC_SYSTEM_FINAL/ 完整目录
  状态：工程化包装，文档完善
  价值：对外发布版本，最规整

Phase 4: 论文规划期（2026-04-01 ~ 2026-04-02）
  标志性文件：10+ 篇策略分析文档（共 ~350KB）
  状态：策略规划完成，实验设计完成
  价值：规划文档，需进一步精炼

Phase 5: 实验准备期（2026-04-03 ~ 04-04）
  标志性文件：download_merit_hydro.py, merit_to_shuc_pipeline.py, preprocess_watersheds.py
  状态：数据获取脚本已编写，pipeline已设计
  价值：进入实验执行阶段的前置准备
```

---

## 2. 内容分类与处置建议

### 2.1 高价值 — 核心保留

| 文件/目录 | 大小 | 价值说明 |
|:---|:---:|:---|
| `CHINA_SHUC_SYSTEM_FINAL/src/`（5个py） | 59KB, 1697行 | **最工程化的核心代码**，模块化拆分，论文代码附录最佳版本 |
| `CHINA_SHUC_SYSTEM_FINAL/config/` | 2KB | 完整配置体系 |
| `CHINA_SHUC_SYSTEM_FINAL/examples/` | 24KB | 3个使用示例 |
| `CHINA_SHUC_SYSTEM_FINAL/README.md` | — | 对外展示入口 |
| `03_EXTENSIONS/shuc_system_optimized.py` | 27KB, 663行 | **90%合规率**的核心优化版 |
| `03_EXTENSIONS/seamless_dem_processor.py` | 38KB, 915行 | DEM无缝处理（论文创新点3） |
| `03_EXTENSIONS/distributed_shuc_framework.py` | 27KB, 776行 | 分布式框架（可扩展性展示） |
| `04_EXPERIMENTS/scripts/`（3个py） | 32KB | 数据获取与处理 pipeline |
| `02_DOCUMENTATION/DIALOGUE_ARCHIVE.md` | 11KB | 关键决策记录，不可丢失 |
| `02_DOCUMENTATION/IMPLEMENTATION_GUIDE.md` | 52KB | 最完整的实施指南 |

### 2.2 有重叠但有价值 — 需要整合

| 文件/组 | 大小 | 处置建议 |
|:---|:---:|:---|
| **根目录7个大型md**（共 ~260KB） | | |
| `GAP_ANALYSIS_AND_ROADMAP.md` | 48KB | 精华提取 -> `PROJECT_MASTER.md`，原文归档 |
| `STRATEGIC_RETHINK.md` | 40KB | 核心决策已融入 DIALOGUE_ARCHIVE，原文归档 |
| `DATA_SOURCE_DECISION_ANALYSIS.md` | 40KB | MERIT Hydro 决策已确定，原文归档 |
| `ALGORITHM_PAPER_STRATEGY.md` | 40KB | 整合进 `PUBLICATION_STRATEGY.md` |
| `NATURE_WATER_FEASIBILITY_ANALYSIS.md` | 32KB | 整合进 `PUBLICATION_STRATEGY.md` |
| `DATA_JOURNAL_STRATEGY.md` | 32KB | 整合进 `PUBLICATION_STRATEGY.md` |
| `TAUDEM_WORKFLOW_CLARIFICATION.md` | 28KB | 技术细节，整合进实施手册 |
| **03_EXTENSIONS 中的重复文档** | | |
| `FINAL_SUMMARY.md` | 6KB | 与多个版本重复，保留 CHINA 版 |
| `README.md` | 4KB | 与 CHINA_SHUC_SYSTEM_FINAL 重复 |
| `optimization_*.md`（3个） | 18KB | 历史记录，归档 |
| `SHUC_FINAL_VERSION/` 整个目录 | 8.4MB | 大部分已在 03_EXTENSIONS 和 CHINA 中，含独有 seamless_output |
| `02_DOCUMENTATION/PROJECT_DOCUMENTATION.md` | 37KB | 与 DIALOGUE_ARCHIVE 重叠 |

### 2.3 历史版本 — 归档保留

| 文件/目录 | 处置 |
|:---|:---|
| `00_ARCHIVE/old_code/`（11个py） | 已归档，保持不动 |
| `00_ARCHIVE/old_docs/INDEX.md` | 已归档，保持不动 |
| `shuc_results/`（5个实验结果目录） | 已迁入 `04_EXPERIMENTS/results/prototype_140_watersheds/` |
| `之前参考/`（notebook + demo数据） | 待移入 `00_ARCHIVE/reference_materials/` |
| `SHUC_FINAL_VERSION/seamless_output/` | 已迁入 `04_EXPERIMENTS/results/seamless_processing/` |
| `SHUC_FINAL_VERSION/output*/` | 已迁入 `04_EXPERIMENTS/results/` |

### 2.4 可删除/清理

| 文件/目录 | 原因 |
|:---|:---|
| `__pycache__/`（根目录） | 编译缓存，应加入 .gitignore |
| `.DS_Store`（多处） | macOS 系统文件 |
| `shuc_validator.py`（根目录） | 已有 CHINA_SHUC_SYSTEM_FINAL/src/quality_validator.py 替代 |
| `demo_config.json` + `shuc_config_template.json`（根目录） | 已有 CHINA_SHUC_SYSTEM_FINAL/config/ 替代 |
| `03_EXTENSIONS/` 中重复的 README.md 和 FINAL_SUMMARY.md | 保留 CHINA 版 |
| `04_EXPERIMENTS/scripts/__pycache__/` | 编译缓存 |

---

## 3. 目录结构重组方案

### 3.1 当前目录状态（审计时点）

```
SHUC_EXPERIMENT_2025/
  [OK] 00_ARCHIVE/          old_code/(11py), old_docs/(INDEX.md)
  [!!] 01_CORE_SYSTEM/      空目录
  [OK] 02_DOCUMENTATION/    DIALOGUE_ARCHIVE.md, IMPLEMENTATION_GUIDE.md, 等6文件
  [OK] 03_EXTENSIONS/       5个py + 7个md
  [OK] 04_EXPERIMENTS/      scripts/(3py), results/(4子目录), experiment_design/
  [!!] 05_DATA/             空目录
  [!!] 06_PUBLICATIONS/     空目录
  [!!] 根目录残留           7个大型md + shuc_validator.py + 2个json + README.md
  [!!] CHINA_SHUC_SYSTEM_FINAL/  未整合
  [!!] SHUC_FINAL_VERSION/       未整合
  [!!] 之前参考/                 未归档
  [!!] shuc_results/             部分已迁但原目录残留
  [!!] __pycache__/              未清理
```

### 3.2 目标目录结构

```
SHUC_EXPERIMENT_2025/
|
|-- README.md                              # 项目主入口
|-- .gitignore                             # Git 忽略配置
|
|-- 00_ARCHIVE/                            # 归档（不干扰主流程）
|   |-- old_code/                          #   已有：11个旧版 py
|   |-- old_docs/                          #   已有：INDEX.md
|   |-- reference_materials/               #   新建：原始参考资料
|   |   |-- notebooks/                     #     <- 之前参考/*.ipynb
|   |   |-- demo_data/                     #     <- 之前参考/demo数据/
|   |   +-- 基本信息.docx                  #     <- 之前参考/基本信息.docx
|   |-- legacy_versions/                   #   新建：旧版完整系统
|   |   +-- SHUC_FINAL_VERSION/            #     <- 整个目录迁入
|   +-- legacy_documentation/              #   新建：已整合的旧文档
|       |-- STRATEGIC_RETHINK.md
|       |-- DATA_SOURCE_DECISION_ANALYSIS.md
|       |-- TAUDEM_WORKFLOW_CLARIFICATION.md
|       +-- PROJECT_AUDIT_AND_REORGANIZATION.md
|
|-- 01_CORE_SYSTEM/                        # 核心（最重要）
|   |-- src/                               #   <- CHINA_SHUC_SYSTEM_FINAL/src/
|   |   |-- shuc_system.py                 #      主程序（334行）
|   |   |-- watershed_processor.py         #      流域处理器（376行）
|   |   |-- hierarchy_encoder.py           #      层级编码器（218行）
|   |   |-- quality_validator.py           #      质量验证器（410行）
|   |   +-- utils.py                       #      工具函数（359行）
|   |-- config/                            #   <- CHINA_SHUC_SYSTEM_FINAL/config/
|   |   |-- shuc_config.json
|   |   +-- validation_config.json
|   |-- examples/                          #   <- CHINA_SHUC_SYSTEM_FINAL/examples/
|   |   |-- basic_usage.py
|   |   |-- advanced_demo.py
|   |   +-- batch_processing.py
|   |-- tests/                             #   新建
|   |   +-- __init__.py
|   +-- requirements.txt                   #   <- CHINA_SHUC_SYSTEM_FINAL/requirements.txt
|
|-- 02_DOCUMENTATION/                      # 文档（整合后）
|   |-- PROJECT_MASTER.md                  #   新建：合并项目总览 + 差距分析 + 路线图
|   |-- PUBLICATION_STRATEGY.md            #   新建：合并期刊策略
|   |-- IMPLEMENTATION_GUIDE.md            #   保留：最完整的实施指南
|   |-- DIALOGUE_ARCHIVE.md                #   保留：关键决策记录
|   +-- ARCHIVED_DOCS/                     #   已归档但保留原文的文档
|       |-- COMPLETE_EXPERIMENT_PLAN.md
|       |-- DETAILED_IMPLEMENTATION_MANUAL.md
|       |-- FINAL_SUMMARY.md
|       +-- PROJECT_DOCUMENTATION.md
|
|-- 03_EXTENSIONS/                         # 扩展功能
|   |-- shuc_system_optimized.py           #   90%合规率优化版
|   |-- seamless_dem_processor.py          #   DEM 无缝处理
|   |-- distributed_shuc_framework.py      #   分布式框架
|   |-- shuc_system_final.py              #   完整功能版
|   |-- run_shuc_system.py                #   运行脚本
|   +-- docs/                             #   扩展功能文档
|       |-- technical_architecture_design.md
|       |-- comprehensive_project_framework.md
|       +-- china_expansion_analysis.md
|
|-- 04_EXPERIMENTS/                        # 实验
|   |-- experiment_design/                 #   实验设计方案
|   |-- scripts/                           #   实验脚本
|   |   |-- download_merit_hydro.py
|   |   |-- merit_to_shuc_pipeline.py
|   |   +-- preprocess_watersheds.py
|   +-- results/                           #   历史实验结果
|       |-- prototype_140_watersheds/      #     140流域原型实验
|       |-- seamless_processing/           #     DEM无缝处理结果
|       |-- final_output/                  #     最终输出
|       +-- optimized_output/              #     优化输出
|
|-- 05_DATA/                               # 数据
|   |-- raw/                               #   原始数据（MERIT Hydro 等）
|   |-- processed/                         #   处理后数据
|   |-- reference/                         #   <- CHINA_SHUC_SYSTEM_FINAL/data/reference/
|   +-- output/                            #   最终输出
|
+-- 06_PUBLICATIONS/                       # 论文
    |-- ESSD_data_paper/                   #   ESSD 数据论文
    |   |-- draft/
    |   |-- figures/
    |   +-- supplementary/
    |-- WRR_algorithm_paper/               #   WRR 算法论文
    |   |-- draft/
    |   |-- figures/
    |   +-- supplementary/
    +-- shared_materials/                  #   共享材料
        |-- cover_letter/
        +-- reviewer_suggestions/
```

### 3.3 具体迁移步骤

**Phase A：核心系统迁移（最优先）**
```
操作：将 CHINA_SHUC_SYSTEM_FINAL 的核心代码复制到 01_CORE_SYSTEM
源：CHINA_SHUC_SYSTEM_FINAL/src/       -> 01_CORE_SYSTEM/src/
源：CHINA_SHUC_SYSTEM_FINAL/config/    -> 01_CORE_SYSTEM/config/
源：CHINA_SHUC_SYSTEM_FINAL/examples/  -> 01_CORE_SYSTEM/examples/
源：CHINA_SHUC_SYSTEM_FINAL/requirements.txt -> 01_CORE_SYSTEM/
新建：01_CORE_SYSTEM/tests/__init__.py
```

**Phase B：旧系统归档**
```
操作：将 SHUC_FINAL_VERSION 整体移入归档
源：SHUC_FINAL_VERSION/ -> 00_ARCHIVE/legacy_versions/SHUC_FINAL_VERSION/
源：之前参考/ -> 00_ARCHIVE/reference_materials/
```

**Phase C：根目录文档归位**
```
操作：将根目录7个大 md 文件归档
源：STRATEGIC_RETHINK.md -> 00_ARCHIVE/legacy_documentation/
源：DATA_SOURCE_DECISION_ANALYSIS.md -> 00_ARCHIVE/legacy_documentation/
源：TAUDEM_WORKFLOW_CLARIFICATION.md -> 00_ARCHIVE/legacy_documentation/
源：PROJECT_AUDIT_AND_REORGANIZATION.md -> 00_ARCHIVE/legacy_documentation/
源：GAP_ANALYSIS_AND_ROADMAP.md -> 02_DOCUMENTATION/（待整合入 PROJECT_MASTER.md）
源：ALGORITHM_PAPER_STRATEGY.md -> 02_DOCUMENTATION/（待整合入 PUBLICATION_STRATEGY.md）
源：NATURE_WATER_FEASIBILITY_ANALYSIS.md -> 02_DOCUMENTATION/（待整合入 PUBLICATION_STRATEGY.md）
源：DATA_JOURNAL_STRATEGY.md -> 02_DOCUMENTATION/（待整合入 PUBLICATION_STRATEGY.md）
```

**Phase D：数据与论文目录建立**
```
操作：建立 05_DATA 和 06_PUBLICATIONS 子目录
新建：05_DATA/raw/
新建：05_DATA/processed/
新建：05_DATA/reference/（从 CHINA_SHUC_SYSTEM_FINAL/data/reference/ 复制）
新建：05_DATA/output/
新建：06_PUBLICATIONS/ESSD_data_paper/draft/
新建：06_PUBLICATIONS/ESSD_data_paper/figures/
新建：06_PUBLICATIONS/WRR_algorithm_paper/draft/
新建：06_PUBLICATIONS/WRR_algorithm_paper/figures/
```

**Phase E：清理**
```
操作：删除冗余文件
删除：__pycache__/（根目录）
删除：shuc_validator.py（根目录，已有替代）
删除：demo_config.json + shuc_config_template.json（根目录，已有替代）
删除：04_EXPERIMENTS/scripts/__pycache__/
移动：CHINA_SHUC_SYSTEM_FINAL/ -> 00_ARCHIVE/legacy_versions/（核心代码已复制到01后）
清理：03_EXTENSIONS/ 中的重复 md（FINAL_SUMMARY.md, README.md, optimization_*.md）
```

### 3.4 重组后预期效果

| 指标 | 重组前 | 重组后 | 改善 |
|:---|:---:|:---:|:---:|
| 根目录文件/目录数 | 17个 | 2个（README.md + .gitignore） | -88% |
| 空壳目录 | 3个（01/05/06） | 0个 | -100% |
| 文档重叠率 | ~60% | <10% | 显著降低 |
| 核心代码可发现性 | 需3层嵌套目录 | 直接 01_CORE_SYSTEM/ | 大幅提升 |
| 论文工作就绪度 | 0% | 框架就绪 | 质变 |

---

## 4. 项目进度汇报

### 4.1 技术成果完成度

| 模块 | 完成度 | 详情 |
|:---|:---:|:---|
| **核心算法** | 90% | 动态阈值自适应、拓扑保持合并、SHUC 6级12位编码 — 全部实现并验证 |
| **系统实现** | 85% | 小规模验证（140 -> 20 流域）完成，90%合规率；缺少万级规模测试 |
| **扩展能力** | 70% | 分布式框架、DEM无缝处理代码完成，但仅demo验证，未大规模运行 |
| **论文准备** | 20% | 策略规划完善，pipeline脚本已写；论文初稿0%、对比实验0%、图表0% |

### 4.2 关键差距（当前 -> 高水平SCI）

```
当前成果                              高水平SCI要求
--------------                       ------------
140个流域（单一区域）       ->->->   10,000+ 流域（3+ 大流域/多地形）
90%合规率（单次）           ->->->   系统对比实验 + 统计显著性检验
概念验证代码               ->->->   工程级开源代码（测试 + 文档 + CI）
策略规划文档               ->->->   完整论文初稿 + 图表 + 投稿材料
0个应用案例                ->->->   2-3个深度应用案例
pipeline 脚本已编写         ->->->   pipeline 实际运行并产出结果
```

### 4.3 剩余工作量与优先级

**P0 — 必须完成（投稿前提）：**

| 任务 | 预估工作量 | 当前状态 |
|:---|:---:|:---:|
| MERIT Hydro 数据下载（bas + upa） | 中 | 脚本已写，待执行 |
| 大规模流域处理（30,000+ 流域） | 大 | pipeline 已设计，待运行 |
| 对比实验（静态阈值 / 合并策略 / 敏感性） | 大 | 设计完成，执行 0% |
| ESSD 数据论文初稿 | 大 | 未开始 |
| WRR 算法论文初稿 | 大 | 未开始 |

**P1 — 重要但可并行：**

| 任务 | 预估工作量 | 当前状态 |
|:---|:---:|:---:|
| 项目目录重组（本方案） | 小 | 待执行 |
| Zenodo 数据上传 | 小 | 未开始 |
| GitHub 开源仓库 | 小 | 未开始 |
| 对比实验图表制作 | 中 | 未开始 |

**P2 — 可后延：**

| 任务 | 预估工作量 | 当前状态 |
|:---|:---:|:---:|
| 应用案例（洪水/水资源） | 大 | 未开始 |
| 代码测试套件 | 中 | 未开始 |
| Docker 容器化 | 小 | 未开始 |

---

## 5. MERIT Hydro 数据获取策略评审

### 5.1 对当前下载脚本的评价

当前 `04_EXPERIMENTS/scripts/download_merit_hydro.py` 已经是一个结构良好的脚本：

**优点：**
- 支持3个目标流域（长江、淮河、珠江）的瓦片计算
- 支持 `--list-tiles` 和 `--script` 两种模式
- 考虑了 1度缓冲区
- 默认图层 `dir,upa,bas` 选择合理

**待改进：**
- MERIT Hydro v1.2 的 URL 可能需要验证是否仍可访问（该数据集较老）
- 缺少下载进度追踪和断点续传的完善处理
- 瓦片命名规则需要与实际服务器端验证

### 5.2 UPA vs BAS 价值分析

**UPA（上游累积面积）的价值 — 同意获取：**

UPA 确实比 BAS 更具核心价值，原因：

1. **SHUC 动态阈值算法的直接输入** — 公式 `Q75 + (Q90-Q75)/2` 需要基于面积分布计算，UPA 提供每个像素的上游累积面积
2. **河网密度信息** — 不同气候区河网密度差异大，UPA 可量化这种差异
3. **合并决策依据** — SHUC 核心创新在于动态调整，需要理解每个区域的面积分布特征
4. **跨区域对比实验** — 有 UPA 才能做不同地形区的算法性能评估
5. **论文图表支撑** — 面积分布直方图、分位数分析图等需要 UPA 数据

**BAS（基线流域ID）的价值：**

- BAS 提供预定义的流域边界，是初始流域提取的基础
- 但 BAS 是固定边界，SHUC 的创新在于动态调整
- BAS 用于快速获取初始流域划分，然后 SHUC 在此基础上优化

### 5.3 全国策略 vs 单流域策略

**推荐：全国策略（bas + upa 全国数据）**

理由充分：

```
单流域策略的问题：
  - 每个流域单独处理，参数一致性难以保证
  - 跨流域对比缺乏统一基准
  - 论文中"可推广性"论证薄弱

全国策略的优势：
  + 参数一致性 — 统一算法处理，消除"每个流域单独调参"的审稿质疑
  + 跨区域可比性 — 直接对比山地 vs 丘陵 vs 平原的算法表现
  + 论文说服力 — "覆盖中国主要流域"比"3个独立案例"更有力
  + 数据产品价值 — 全国数据集作为 ESSD 数据论文的主体内容
  + 编码体系统一性 — 长江/淮河/珠江使用同一套 SHUC 编码规则
```

### 5.4 推荐下载方案

**方案 B：全国 bas + upa + dir（推荐）**

需要下载的 MERIT Hydro 图层及瓦片：

| 图层 | 用途 | 必要性 |
|:---|:---|:---:|
| `bas` | 流域边界提取（初始划分） | 必须 |
| `upa` | 面积分布分析、阈值优化、对比实验 | 必须 |
| `dir` | 流向数据（拓扑关系推导） | 必须 |
| `elv` | 高程数据（可视化、地形分类） | 可选 |

覆盖中国全境所需的瓦片包（5度分块）：

| 包名 | 范围 | 覆盖区域 |
|:---|:---|:---|
| `n00e090` | 0-5N, 90-95E | 南海（可选） |
| `n05e090` ~ `n55e090` | 5-60N, 90-95E | 西部边境 |
| `n00e095` ~ `n55e095` | 各纬度, 95-100E | 西部 |
| ... | ... | ... |
| `n20e100` ~ `n50e120` | 主体中国范围 | **核心区域** |
| ... | ... | ... |

实际操作建议：
- 先下载核心区域（长江/淮河/珠江覆盖范围）的 `bas + upa + dir`
- 约 20-30 个瓦片 x 3个图层 = 60-90 个 tar 包
- 总下载量估计：15-30 GB
- 后续根据需要扩展到全国

### 5.5 关键注意事项

1. **MERIT Hydro 版本**：确认使用 v1.2 还是更新的版本（如 MERIT Hydro-Vector）
2. **数据访问权限**：需要在 http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/ 注册
3. **磁盘空间**：预留至少 50GB 用于原始数据 + 处理中间结果
4. **处理环境**：大规模处理需要足够内存（建议 16GB+）和磁盘 IO
5. **坐标系统**：MERIT Hydro 使用 WGS84，与 SHUC 系统兼容

---

## 6. 决策支持

### 决策1：旧代码保留策略

| 选项 | 描述 | 利 | 弊 |
|:---:|:---|:---|:---|
| **A** | 全部删除 | 最干净，无干扰 | 无法回溯历史算法思路 |
| **B** | 移入 00_ARCHIVE（推荐） | 保留历史、不干扰主流程 | 占用少量磁盘空间 |
| **C** | 保持现状 | 零操作成本 | 继续干扰工作流 |

**推荐 B**：对于论文项目，保留演进历史有助于应对审稿人追问。旧代码归档不删除，需要时可回溯。

### 决策2：核心版本选择

| 选项 | 描述 | 适用场景 |
|:---:|:---|:---|
| **A** | 仅用 CHINA_SHUC_SYSTEM_FINAL | 快速简洁，工程化最好 |
| **B** | 仅用 SHUC_FINAL_VERSION | 功能最全（含 optimized/seamless） |
| **C** | 两者结合（推荐） | 取 CHINA 的工程化 + SHUC 的功能性 |

**推荐 C**：`01_CORE_SYSTEM` 使用 CHINA 版的 src/（模块化好，1697行），扩展功能从 SHUC_FINAL_VERSION 提取到 `03_EXTENSIONS`。

### 决策3：文档整合方式

| 选项 | 描述 | 利 | 弊 |
|:---:|:---|:---|:---|
| **A** | AI 自动合并为 3-4 个精炼文档 | 快速，立即可用 | 可能丢失细节，需人工审核 |
| **B** | 手动逐个整合 | 质量最高 | 耗时长，可能拖延 |
| **C** | 先归档旧文档，新建精炼版（推荐） | 保留原文 + 产出新文档 | 工作量适中 |

**推荐 C**：将根目录 7 个大 md 先移入 `00_ARCHIVE/legacy_documentation/`，然后基于精华内容新建 `PROJECT_MASTER.md` 和 `PUBLICATION_STRATEGY.md`。原文不丢失，新文档精炼。

### 决策4：是否立即执行重组

| 选项 | 描述 | 利 | 弊 |
|:---:|:---|:---|:---|
| **A** | 立即执行（推荐） | 消除混乱，为后续工作铺路 | 需约 30 分钟操作时间 |
| **B** | 先做实验，论文完成后再整理 | 不中断研究节奏 | 在混乱中工作效率低 |
| **C** | 保持现状 | 零风险 | 根目录残留文件继续干扰 |

**推荐 A**：重组是"一次性痛苦、长期受益"的操作。上次重组已完成 60%，完成剩余 40% 工作量不大。重组后进入实验/论文阶段效率更高。

### 决策5：论文策略最终确认

| 选项 | 描述 | IF 总和 | 成功率 |
|:---:|:---|:---:|:---:|
| **A** | ESSD（数据）+ WRR（算法）（推荐） | ~18 | >75% |
| **B** | 单投 WRR | ~6 | ~60% |
| **C** | ESSD + WRR + Nature Water 冲刺 | ~30+ | <40% |

**推荐 A**：风险收益比最优。两篇论文相互引用形成学术闭环。数据论文先行（ESSD 审稿周期较短），为算法论文提供数据引用基础。

### 决策6：MERIT Hydro 数据获取范围

| 选项 | 描述 | 数据量 | 适用场景 |
|:---:|:---|:---:|:---|
| **A** | 仅 3 大流域 bas | ~5-10 GB | 快速验证，最省钱 |
| **B** | 全国 bas + upa + dir（推荐） | ~15-30 GB | 论文需要对比实验 |
| **C** | 全国所有图层 | ~50+ GB | 最完整但冗余 |

**推荐 B**：论文需要 UPA 做对比实验和敏感性分析。`dir` 提供流向数据用于拓扑推导。`elv` 可选（不影响核心算法）。

---

## 7. 执行路线图

### 7.1 总体路线（以终为始）

```
终点：ESSD + WRR 双论文发表
  |
  +-- Step 5: 论文投稿与审稿
  |     |-- ESSD 数据论文投稿
  |     |-- WRR 算法论文投稿
  |     +-- 审稿回复与修改
  |
  +-- Step 4: 论文撰写
  |     |-- ESSD 论文初稿（Background, Methods, Data Records）
  |     |-- WRR 论文初稿（Introduction, Methods, Results）
  |     +-- 图表制作（至少 8-10 张核心图）
  |
  +-- Step 3: 实验执行（当前瓶颈）
  |     |-- MERIT Hydro 数据下载与拼接
  |     |-- 大规模流域处理（30,000+ 流域）
  |     |-- 对比实验（静态阈值 / 合并策略 / 敏感性分析）
  |     +-- 结果分析与统计检验
  |
  +-- Step 2: 项目重组（本次任务）
  |     |-- 目录结构整理
  |     |-- 核心代码迁移到 01_CORE_SYSTEM
  |     |-- 文档整合（12个 -> 4个）
  |     +-- 论文目录框架建立
  |
  +-- Step 1: 数据获取准备（已完成）
        |-- download_merit_hydro.py（已完成）
        |-- merit_to_shuc_pipeline.py（已完成）
        +-- preprocess_watersheds.py（已完成）
```

### 7.2 关键里程碑

| 阶段 | 里程碑 | 验收标准 | 状态 |
|:---|:---|:---|:---:|
| Step 2 | 项目重组完成 | 01-06 目录全部填充，根目录仅留 README | 待执行 |
| Step 3a | 数据获取完成 | MERIT Hydro bas+upa+dir 全部下载 | 待执行 |
| Step 3b | 大规模处理完成 | 30,000+ 流域成功处理 | 待执行 |
| Step 3c | 对比实验完成 | 11 个实验结果文件生成 | 待执行 |
| Step 4a | ESSD 初稿完成 | 用户审阅通过 | 待执行 |
| Step 4b | WRR 初稿完成 | 用户审阅通过 | 待执行 |
| Step 5a | ESSD 投稿 | 收到投稿编号 | 待执行 |
| Step 5b | WRR 投稿 | 收到投稿编号 | 待执行 |

### 7.3 风险识别与应对

| 风险 | 概率 | 影响 | 应对策略 |
|:---|:---:|:---:|:---|
| MERIT Hydro 服务器访问受限 | 中 | 高 | 提前注册，准备镜像源或代理 |
| 大规模处理内存不足 | 中 | 中 | 分瓦片处理，使用流式处理 |
| 动态阈值在大流域表现不佳 | 低 | 高 | 回退到半自动模式，人工调整 |
| 论文被拒 | 中 | 中 | Plan B: 改投 JoH / HESS / Sci. Data |
| 时间超期 | 高 | 中 | 并行推进，优先完成对比实验 |

---

## 附录 A：文件清单（审计时点）

### 根目录文件

```
ALGORITHM_PAPER_STRATEGY.md        40KB   算法论文策略
CHINA_SHUC_SYSTEM_FINAL/          436KB   对外发布版系统
DATA_JOURNAL_STRATEGY.md           32KB   数据期刊策略
DATA_SOURCE_DECISION_ANALYSIS.md   40KB   数据源决策分析
GAP_ANALYSIS_AND_ROADMAP.md        48KB   差距分析与路线图
NATURE_WATER_FEASIBILITY_ANALYSIS.md 32KB Nature Water 可行性分析
PROJECT_AUDIT_AND_REORGANIZATION.md 28KB 项目审计文档
README.md                          4KB    项目入口
SHUC_FINAL_VERSION/               8.4MB   最成熟代码版本
STRATEGIC_RETHINK.md               40KB   战略重新定位
TAUDEM_WORKFLOW_CLARIFICATION.md   28KB   TauDEM 工作流说明
__pycache__/                       80KB   编译缓存（可删）
demo_config.json                   1KB    演示配置（可删）
之前参考/                          3.1MB   原始参考资料
shuc_config_template.json          1KB    配置模板（可删）
shuc_results/                      1.2MB   历史实验结果（已迁但残留）
shuc_validator.py                  20KB   验证器（已有替代，可删）
```

### 01_CORE_SYSTEM/

```
（空目录 — 待填充）
```

### 02_DOCUMENTATION/

```
COMPLETE_EXPERIMENT_PLAN.md        48KB   完整实验计划
DIALOGUE_ARCHIVE.md                11KB   对话纪要
DETAILED_IMPLEMENTATION_MANUAL.md  45KB   详细实施手册
FINAL_SUMMARY.md                   6KB    最终总结
IMPLEMENTATION_GUIDE.md            52KB   实施指南
PROJECT_DOCUMENTATION.md           37KB   项目文档
```

### 03_EXTENSIONS/

```
FINAL_SUMMARY.md                   6KB    最终总结（重复）
README.md                          4KB    说明（重复）
china_expansion_analysis.md        12KB   扩展分析
comprehensive_project_framework.md 17KB  项目框架
distributed_shuc_framework.py      27KB   分布式框架
optimization_comparison_report.md  7KB    优化对比报告
optimization_plan.md               5KB    优化计划
run_shuc_system.py                 7KB    运行脚本
seamless_dem_processor.py          38KB   DEM 无缝处理
shuc_system_final.py               31KB   完整系统
shuc_system_optimized.py           27KB   优化系统
technical_architecture_design.md   18KB   架构设计
```

### 04_EXPERIMENTS/

```
experiment_design/                  （目录已创建）
results/
  final_output/                     最终输出（shp + validation）
  optimized_output/                 优化输出（shp + validation）
  prototype_140_watersheds/         140 流域原型实验（5个子实验）
  seamless_processing/              DEM 无缝处理结果
scripts/
  download_merit_hydro.py           10KB   MERIT 下载工具
  merit_to_shuc_pipeline.py         17KB   MERIT->SHUC pipeline
  preprocess_watersheds.py          5KB    预处理脚本
```

---

*本审计报告基于 2026-04-04 项目状态编写。所有文件路径、大小和行数均为审计时点的实际值。*
