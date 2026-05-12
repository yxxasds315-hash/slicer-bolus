# 阴模生成：官方参考与设计决策

> 查找日期：2026-05-11
> 来源：
> - Slicer Discourse: https://discourse.slicer.org/t/negative-mold-of-an-stl/29669
> - Slicer Discourse: https://discourse.slicer.org/t/using-segment-editor-effects-programmatically/11561
> - Slicer Discourse: https://discourse.slicer.org/t/isotropic-expansion/39492
> - Slicer Discourse: https://discourse.slicer.org/t/logical-operators/17132

---

## 1. 阴模生成的官方/社区推荐方式

**官方文档未提供专门的阴模生成流程**，Slicer 没有内置"negative mold"功能。

**社区推荐做法**（discourse.slicer.org/t/29669）：

> Create a "container" segment (bounding box or custom shape), then use Logical operators SUBTRACT to cut out the target shape, yielding a negative mold.

中文结论：
- 创建包围体 segment（外壳）
- SUBTRACT 目标形状（bolus）→ 得到阴模内腔
- 本项目实现：`Bolus_Expanded`（外壳）SUBTRACT `Bolus`（内腔）= **正确，符合社区建议**

---

## 2. 是否需要 SUBTRACT skin（防穿模）

### 问题背景

Slicer Margin 效果是**各向同性**膨胀（isotropic），不区分方向。对 bolus（贴 skin 放置）做 Margin 膨胀时，扩展会同时向 skin 方向延伸 `shell_mm`。

旧代码在 SUBTRACT bolus 后还执行 `SUBTRACT skin`，意图是防止阴模外壁穿入患者皮肤。

### 为什么 SUBTRACT skin 是错的（浇铸模具场景）

| | 减 skin | 不减 skin |
|---|---|---|
| 几何结果 | 底面被整个挖穿，marching cubes 自动补平底，补出的面不规则（"支离破碎"） | 封闭完整壳体，底板厚度 = `shell_mm` |
| 内腔底面 | bolus 腔正确，但底板缺失 | bolus 腔正确，底板完整 |
| 浇铸可用性 | 底面开口，浇铸液体从底部漏出 | 底面封闭，可正常浇铸 |
| 外壳底面 | 贴 skin 表面（破损） | 入 skin `shell_mm`（正常底板厚度，临床可接受） |

**关键认知**：bolus 的底面天然就是 skin 表面（bolus 由 skin 通过 EDT 偏移生成，底面贴 skin）。`Bolus_Expanded - Bolus` 的内腔底面 = bolus 底面 = skin 表面。不需要额外裁切来"对齐 skin"。

### 结论

**不执行 SUBTRACT skin**。阴模 = `Bolus_Expanded - Bolus`，封闭壳体，内腔正确，底板完整，符合浇铸模具设计要求。

---

## 3. binary_erosion 补底板方案（已废弃）

### 背景

在某次修复中引入了 `scipy.ndimage.binary_erosion` 补皮肤表面体素的方案，试图在 SUBTRACT skin 之后补回底板。

### 为什么废弃

1. `binary_erosion` 只补 1 个体素厚度，对 1mm CT 体素足够，但对 2mm+ 体素可能不够
2. 补出的体素与残余的洞口边界不完全衔接，marching cubes 生成的多边形在边界处重叠或非流形
3. `vtkFillHolesFilter(HoleSize=1e6)` 对不规则洞口（曲面皮肤边界）补出的三角面质量差
4. 根因错误：SUBTRACT skin 本身就不应该执行

### 正确替代

见 §2：直接不执行 SUBTRACT skin，无需补底板。

---

## 4. 程序化调用 SegmentEditor 效果的推荐 API

**来源**：https://discourse.slicer.org/t/using-segment-editor-effects-programmatically/11561

**官方推荐模式（社区确认）**：

```python
segEditorWidget = slicer.qMRMLSegmentEditorWidget()
segEditorWidget.setMRMLScene(slicer.mrmlScene)
segEditorWidget.setMRMLSegmentEditorNode(segEditorNode)
segEditorWidget.setSegmentationNode(segNode)
segEditorWidget.setSourceVolumeNode(refVolume)
segEditorWidget.setActiveEffectByName("Logical operators")
effect = segEditorWidget.activeEffect()
effect.setParameter("Operation", "SUBTRACT")
effect.setParameter("ModifierSegmentID", targetSegId)
effect.self().onApply()
```

**注意事项**：
- 没有公开的参数文档，需查阅对应 Effect 的 Python 源码
- `OverwriteMode = OverwriteNone` 防止效果意外修改其他 segment
- 操作完成后必须调用 `setActiveEffectByName("")` 释放 effect，否则可能残留状态

**本项目中用 `_safe_get_effect()` 封装了上述模式，与官方推荐一致。**

---

## 5. Margin 效果的各向同性说明

**来源**：https://discourse.slicer.org/t/isotropic-expansion/39492

官方 Margin 效果说明："Grows or shrinks the selected segment by the specified margin."

社区注意事项：
- Margin 在体素网格中是各向同性的（所有方向同等膨胀）
- 临床 CT 体素通常不是各向同性（in-plane 约 0.35-1mm，axial 约 0.6-2.5mm）
- 结果：轴向扩展量受体素间距影响，实际几何膨胀量在不同方向可能有 1-2 体素的差异
- **影响**：`Bolus_Expanded` 底部（axial 方向）的实际膨胀量可能略小于 `shell_mm`，但对阴模底板厚度影响在 ±1 体素范围内，临床可接受

---

## 变更历史

| 日期 | 改动 | 原因 |
|------|------|------|
| 2026-05-11 | 删除 `SUBTRACT skin` 步骤和 binary_erosion 补底板 | 底面被挖穿，补面碎裂；根因是 SUBTRACT skin 不适用于浇铸模具场景 |
