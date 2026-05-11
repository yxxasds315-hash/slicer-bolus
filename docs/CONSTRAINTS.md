# 开发约束规范

本文件规定在 slicer-bolus 项目中进行**重大改动**前必须遵守的流程，目的是避免因对 Slicer API、VTK 行为或医疗算法的误判而引入错误。

---

## 什么算"重大改动"

以下任一类型的改动均属重大改动：

- 涉及 Slicer SegmentEditor 效果（Margin、Logical operators、Hollow、Smoothing 等）的参数或调用方式
- 涉及 VTK 管线（vtkImageStencil、vtkPolyDataToImageStencil、vtkBooleanOperationPolyDataFilter 等）
- 涉及体素布尔运算、labelmap 操作、坐标系转换
- 涉及验证指标（Dice、MHD、HD95、体积比）的计算逻辑
- 涉及模具几何（阴模、注料口、排气孔）的生成逻辑
- 删除或替换已有的多步骤流水线步骤

---

## 重大改动前必须执行的流程

### 第一步：检索 `docs/` 文件夹

先在 `docs/` 中查找是否已有相关研究记录：

| 文件 | 内容 |
|------|------|
| `slicer_compliance_review.md` | 官方文档对照审查，记录每个 API/效果的正确用法 |
| `mold_generation.md` | 阴模生成设计决策与官方参考 |
| `segment_editor.md` | Segment Editor 官方文档摘录 |
| `scripting_segmentation.md` | Slicer segmentation 脚本示例 |
| `scripting_models.md` | Slicer model 脚本示例 |
| `scripting_volumes.md` | Slicer volume 脚本示例 |
| `coordinate_systems.md` | 坐标系说明（RAS/LPS/IJK） |

如果找到相关记录，**以文件中的结论为准**，不需要重新查找。

### 第二步：如未找到，查找官方文档和社区

按以下来源顺序查找：

1. **Slicer 官方文档**：https://slicer.readthedocs.io
   - Script Repository（最实用）：https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/
   - Segment Editor 模块：https://slicer.readthedocs.io/en/latest/user_guide/modules/segmenteditor.html
2. **Slicer Discourse 社区**：https://discourse.slicer.org
   - 搜索具体 API 名称或行为关键词
3. **Slicer GitHub**：https://github.com/Slicer/Slicer
   - 直接查看 Effect 源码中的 `setParameter` 参数名
4. **VTK 官方文档**：https://vtk.org/doc/nightly/html/
   - 针对具体 VTK 类的方法行为

### 第三步：将查找结果写入 `docs/`

查找结束后，**在实现代码之前**，将结论写入对应的 `docs/` 文件：

- 已有文件适合：直接追加新章节
- 无合适文件：新建专题文件（命名格式：`主题_关键词.md`，全小写，下划线）
- 每条记录必须包含：
  - 来源 URL
  - 官方原文摘录（英文）
  - 中文结论
  - 对本项目的影响说明

### 第四步：实现代码

有了 `docs/` 中的依据后再动代码。代码注释引用文档文件（例：`# 见 docs/mold_generation.md §2`）。

---

## 违反此流程的后果（历史案例）

| 改动 | 未查文档的后果 |
|------|---------------|
| `vtkImageStencil.SetBackgroundValue(1)` | 全图 mask 取反，Dice=0，排查耗时 1 天 |
| `SUBTRACT skin` 用于阴模底板防穿模 | 底面被挖穿，marching cubes 补出碎面，需二次修复 |
| `vtkBooleanOperationPolyDataFilter` 轴对齐几何 | 返回 0 个点，触发错误 fallback，排查耗时半天 |

---

## 不需要走此流程的改动

- 前端 UI 文字、颜色、布局调整
- 日志 / 错误消息文字修改
- 配置默认值调整（thickness_mm、shell 等数值）
- 增删 API 路由（逻辑不涉及 Slicer/VTK）
- 纯 Python 数据处理（与 Slicer/VTK 无关）
