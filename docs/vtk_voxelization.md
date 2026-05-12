# VTK 体素化：vtkPolyDataToImageStencil 行为说明

> 查找日期：2026-05-11
> 来源：
> - VTK 官方 API 文档：https://vtk.org/doc/nightly/html/classvtkPolyDataToImageStencil.html
> - VTK 源码（GitHub）：https://github.com/Kitware/VTK/blob/master/Imaging/Stencil/vtkPolyDataToImageStencil.cxx
> - VTK 源码头文件：https://github.com/Kitware/VTK/blob/master/Imaging/Stencil/vtkPolyDataToImageStencil.h
> - VTK 用户邮件列表：https://public.kitware.com/pipermail/vtkusers/2018-September/102730.html

---

## 1. 算法原理（源码推断）

`vtkPolyDataToImageStencil` **不是**传统射线投射（ray casting）。实际算法：

1. 按 Z 切片遍历 polydata
2. 对每个 Z 平面做 2D 光栅化（polygon scan conversion）
3. 记录每条扫描线上多边形边的 X 交点
4. 通过 `vtkImageStencilRaster` 确定 inside/outside（偶-奇规则或类似机制，源码中未显式文档化）

---

## 2. 开放网格（open mesh）的行为

**官方文档无明确警告，但源码中有"补救"逻辑**：

源码明确检测"loose ends"（degree-1 顶点），并尝试用距离+方向启发式算法将断开的端点连接。这意味着：

- 开放网格**不会直接报错**，而是被"悄悄修复"
- 修复结果**不可预测**，取决于端点的位置和方向
- **结论：开放网格的体素化结果是未定义行为（undefined behavior）**

### 本项目影响

`Mold_Female_Conformal` 经 `_add_sprue_and_vents` 的 `vtkBooleanOperationPolyDataFilter` 钻孔后变为开放网格。直接体素化会触发 loose-end 修复逻辑，导致 `vF & vSkin` 出现错误的 45 cm³。

**修复方案（已实施）**：在体素化前用 `vtkFillHolesFilter` 临时封孔：

```python
fill = vtk.vtkFillHolesFilter()
fill.SetInputData(F); fill.SetHoleSize(1e6); fill.Update()
norm = vtk.vtkPolyDataNormals()
norm.SetInputData(fill.GetOutput())
norm.ConsistencyOn(); norm.AutoOrientNormalsOn(); norm.SplittingOff(); norm.Update()
vF = _voxelize_3d(norm.GetOutput(), ...)
```

`vtkFillHolesFilter` 没有官方文档明确推荐用于此用途，但被 3D Slicer 社区讨论中作为"robust conversion"预处理步骤提及。

---

## 3. 空心壳（hollow shell）的 inside/outside 判断

**官方文档未说明**，从源码分析结论如下：

对一个空心壳（外表面 + 内表面构成的封闭 polydata）：

| 区域 | 判断结果 |
|------|---------|
| 外部（exterior） | outside |
| 外壳材料（shell material，两面之间） | **inside** ✓ |
| 内腔（hollow cavity） | outside（内表面翻转了 inside/outside 状态） |

**结论：偶-奇扫描规则下，空心壳的体素化结果是正确的** — `~flat` 反转后，`vF = True` 仅代表壳体材料，不包含内腔和外部。

**注意**：这一行为依赖法向量方向一致（`vtkPolyDataNormals` with `ConsistencyOn + AutoOrientNormalsOn`）。若法向量不一致，内表面可能不会正确翻转状态。

---

## 4. vCavity / Dice 指标的正确计算方式

**旧公式（错误）**：
```python
vCavity = vExpanded & ~vB & ~vSkin
Dice = 2 * (vB & vCavity).sum() / ...  # vCavity 定义排除 vB → 永远=0
```

**新公式（正确）**：
```python
vCavity = vExpanded & ~vF  # 实际内腔 = 扩展区域内不属于模具材料的空间
Dice = 2 * (vB & vCavity).sum() / (vB.sum() + vCavity.sum())
Ratio = vCavity.sum() / vB.sum()
```

物理含义：`vCavity` = 用此模具浇铸后铸件实际占据的空间；`Dice(vB, vCavity)` = 铸件与设计 bolus 的重合度。

---

## 5. 穿模指标（mold∩skin）的正确计算方式

**旧指标**：`vF & vSkin`（整个模具壳体材料与皮肤的重叠）

**问题**：新阴模设计（不减 skin）的外壳底板主动入皮 `shell_mm`，是预期行为，此指标永远触发警告。

**新指标**：`vCavity & vSkin`（内腔空间与皮肤的重叠）

物理含义：铸出的 bolus 空间是否入侵皮肤。bolus 设计在 skin 表面之上，正常情况下 `vCavity & vSkin ≈ 0`，阈值 `<0.5 cm³` 仍然有效。

---

## 6. 未解决的不确定性

| 问题 | 状态 |
|------|------|
| `vtkImageStencilRaster` 精确的 inside/outside 规则（偶-奇 vs winding） | 未在官方文档中说明，需源码深挖 |
| `vtkFillHolesFilter` 是否保证填充后网格法向量正确 | 未官方说明，已在代码中加 `vtkPolyDataNormals` 后处理 |
| 非常小的 sprue/vent 孔径是否影响封孔质量 | 未验证，`HoleSize=1e6` 应可覆盖所有实际孔径 |

---

## 变更历史

| 日期 | 改动 | 依据 |
|------|------|------|
| 2026-05-11 | 体素化前加 vtkFillHolesFilter；vCavity 改为 vExpanded & ~vF；穿模改为 vCavity & vSkin | 源码分析：开放网格触发 loose-end 修复 → 结果未定义 |
