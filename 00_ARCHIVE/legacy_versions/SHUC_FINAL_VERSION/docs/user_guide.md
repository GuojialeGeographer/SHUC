# 中国SHUC系统使用指南

## 🚀 快速开始

### 一键运行
```bash
cd SHUC_FINAL_VERSION
python run_shuc_system.py
```

### 系统要求
- Python 3.8+
- 依赖包: `pandas`, `geopandas`, `networkx`, `shapely`

## 📁 输入数据要求

### 必需文件
- `流域.shp` - 主要数据文件
- `流域.shx` - 索引文件
- `流域.dbf` - 属性数据
- `流域.prj` - 投影信息

### 必需字段
| 字段名 | 类型 | 描述 | 示例 |
|--------|------|------|------|
| LINKNO | 整数 | 流域唯一标识 | 3150 |
| DSLINKNO | 整数 | 下游流域ID | 7870 |  
| USLINKNO1 | 整数 | 上游流域ID1 | 7358 |
| USLINKNO2 | 整数 | 上游流域ID2 | -1 |
| Areakm2 | 浮点 | 流域面积(km²) | 21.35 |
| gridcode | 整数 | 网格编码 | 3150 |

### 数据质量要求
- 几何体必须有效
- 不允许自引用 (USLINKNO ≠ LINKNO)
- 面积值必须为正数
- 拓扑关系完整

## 🔧 运行参数配置

### 基础配置
```python
# 创建SHUC系统实例
shuc_system = FinalSHUCSystem(
    output_dir="output"  # 输出目录
)
```

### 高级配置
```python
# 修改分级标准
shuc_system.level_definitions[6]['min_area'] = 80  # 修改6级最小面积为80km²

# 调整合并参数
max_iterations = 25  # 最大迭代次数
merge_limit = 20     # 每轮最大合并数
```

## 📊 输出文件说明

### 核心输出文件

#### 1. `final_shuc_watersheds.shp`
- **类型**: ESRI Shapefile  
- **描述**: 最终流域数据，包含SHUC编码
- **推荐软件**: QGIS, ArcGIS, FME

**新增字段说明:**
```
SHUC_CODE    : SHUC编码 (如: 010101010101)
SHUC_LEVEL   : 流域级别 (1-6)  
LEVEL_NAME   : 级别名称 (如: 基本单元)
LEVEL_DESC   : 级别描述 (如: 基本水文单元)
```

#### 2. `system_validation.json`
- **类型**: JSON格式
- **描述**: 详细验证报告
- **用途**: 质量评估和问题诊断

**主要指标:**
```json
{
  "area_compliance": {
    "compliance_rate": 91.7,      // 面积合规率
    "compliant_count": 11,        // 合规流域数
    "total_count": 12             // 总流域数
  },
  "code_validation": {
    "uniqueness": true,           // 编码唯一性
    "total_codes": 12,            // 编码总数
    "unique_codes": 12            // 唯一编码数
  },
  "overall_validation": {
    "passed": true,               // 整体验证结果
    "score": 95.8                 // 系统评分(0-100)
  }
}
```

#### 3. `technical_report.txt`
- **类型**: 纯文本
- **描述**: 人类可读的技术报告
- **内容**: 系统概况、层次分布、质量评估、编码示例

#### 4. `process_log.txt`
- **类型**: 纯文本  
- **描述**: 详细处理日志
- **用途**: 问题诊断和过程追踪

## 🎯 结果解读

### 质量评估标准

#### 1. 面积合规率
- **优秀**: ≥95% 
- **良好**: 90-95%
- **合格**: 85-90%
- **需改进**: <85%

#### 2. 编码唯一性
- **通过**: 100%无重复
- **失败**: 存在重复编码

#### 3. 系统评分
- **A级**: 90-100分 - 系统运行优秀
- **B级**: 80-90分 - 系统运行良好  
- **C级**: 70-80分 - 系统基本合格
- **D级**: <70分 - 需要检查问题

### 典型结果示例

#### 成功案例
```
📊 处理结果摘要
原始流域: 140 个 → 最终流域: 12 个
压缩率: 91.4% | 问题修复: 5 个

🏗️ 层次结构:
4级 中流域: 1个 (628.5km²)
5级 小流域: 5个 (144.9-335.8km²)  
6级 基本单元: 6个 (109.2-121.1km²)

✅ 质量评估:
面积合规率: 91.7% (11/12)
编码唯一性: ✓通过 (12/12)
系统评分: 95.8/100 
整体验证: 🎉通过
```

## 🔍 问题诊断

### 常见问题及解决方案

#### 1. 数据加载失败
**现象**: `❌ 数据加载失败: No such file or directory`
**原因**: 找不到输入文件
**解决**: 
- 检查文件路径是否正确
- 确保所有配套文件(.shp, .shx, .dbf, .prj)存在
- 验证文件权限

#### 2. 面积合规率低
**现象**: `面积合规率: 65.2%`
**原因**: 合并算法未充分执行
**解决**:
- 增加迭代次数: `max_iterations = 40`
- 降低面积阈值: `min_area = 80`
- 检查数据拓扑连通性

#### 3. 编码重复
**现象**: `编码唯一性: ✗失败`
**原因**: 编码生成算法异常
**解决**:
- 检查输入数据LINKNO唯一性
- 重新运行完整流程
- 查看process_log.txt详细错误

#### 4. 系统评分低
**现象**: `系统评分: 45.2/100`
**原因**: 多项指标未达标
**解决**:
- 逐一检查validation报告各项指标
- 针对性调整系统参数
- 改善输入数据质量

## 🛠️ 高级用法

### 自定义分级标准
```python
# 修改6级流域面积阈值
system.level_definitions[6]['min_area'] = 80

# 添加自定义流域分类
system.major_basins['13'] = '自定义流域'
```

### 批处理多个数据集
```python
input_files = ['区域1.shp', '区域2.shp', '区域3.shp']
for file in input_files:
    success, data, validation = system.run_complete_system(file)
    print(f"{file}: {'成功' if success else '失败'}")
```

### 结果后处理
```python
import geopandas as gpd

# 读取结果
result = gpd.read_file('output/final_shuc_watersheds.shp')

# 按级别分离
level_5 = result[result['SHUC_LEVEL'] == 5]
level_6 = result[result['SHUC_LEVEL'] == 6]

# 导出特定级别
level_5.to_file('output/level_5_watersheds.shp')
```

## 📞 技术支持

### 系统信息
- **版本**: 3.0 Final
- **更新**: 2025-08-30
- **作者**: Claude Code Assistant

### 问题反馈
遇到问题时，请提供以下信息：
1. 系统版本和运行环境
2. 输入数据特征(文件大小、流域数量、坐标系)
3. 错误信息和日志文件
4. 期望的结果描述

### 性能参考
- **小型数据集** (<100流域): <10秒
- **中型数据集** (100-500流域): 10-60秒  
- **大型数据集** (500-2000流域): 1-10分钟
- **内存使用**: 通常<1GB

---

**使用愉快！如有问题，请查看技术报告或联系支持团队。** 🎯