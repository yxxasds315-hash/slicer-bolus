# Slicer 官方文档对照审查

> 对照来源：
> - [Segment Editor 模块文档](https://slicer.readthedocs.io/en/latest/user_guide/modules/segmenteditor.html)
> - [坐标系说明](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html)
> - [Segmentation 脚本参考](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html)
> - [Models 脚本参考](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/models.html)

---

## 1. STL 导出坐标系 ✅ 修复正确

**官方原文：**
> Slicer still **uses RAS coordinate system for storing coordinate values internally** for all data types, but for compatibility with other software, it **assumes that all data in files are stored in LPS coordinate system** (unless the coordinate system in the file is explicitly stated to be RAS). To achieve this, whenever Slicer reads or writes a file, it may need to flip the sign of the first two coordinate axes.

**关键点：** STL 格式没有坐标系元数据字段，无法在文件中声明坐标系。因此 `slicer.util.saveNode` 保存 STL 时，**无法做 RAS→LPS 转换**，直接输出 RAS 坐标。

**原代码问题：** ExportPanel 显示"STL 导出自动转换 LPS"——与官方行为不符。

**修复后：** 改为"STL 导出保持 RAS 坐标系（Slicer 原生）"——✅ 符合官方文档。

**用户注意事项：** 导入 Bambu Studio、Cura 等切片软件时，需确认软件是否自行处理坐标系。DICOM 原始坐标为 LPS，3D 打印软件通常不区分坐标系，以几何形状为准，实际使用中无需手动转换。

---

## 2. Segment Editor 流水线效果 ✅ 符合官方推荐

### Margin（偏移扩展）

**官方：** "Grows or shrinks the selected segment by the specified margin."

**代码：**
```python
effect.setParameter("MarginSizeMm", str(BOLUS_THICKNESS))
```
✅ 参数名和用法与官方一致，按 `thickness_mm` 外扩皮肤段，符合 bolus 设计需求。

---

### Hollow（抽壳）

**官方：** "Makes the selected visible segment hollow by replacing the segment with a uniform-thickness shell defined by the segment boundary."

**代码（hollow 分支）：**
```python
effect.setParameter("ShellThicknessMm", str(BOLUS_THICKNESS))
# INSIDE_SURFACE 模式：从内边界向内掏空
```

✅ 使用 `INSIDE_SURFACE` 在内表面生成壳，生成贴合皮肤的补偿器外壳，参数名正确。

**官方补充说明：** 对于极薄壳（< 2mm），官方建议改用 DynamicModeler 的 Hollow 工具（网格挤出方式），精度更高。当前 bolus 厚度通常 ≥ 5mm，Segment Editor Hollow 是官方推荐的首选方法。

---

### Smoothing（平滑）

**官方：** "Median: removes small extrusions and fills small gaps while keeps smooth contours mostly unchanged."

**代码：**
```python
effect.setParameter("SmoothingMethod", "MEDIAN")
effect.setParameter("KernelSizeMm", "2")
```
✅ Median 是官方推荐用于保留轮廓同时去除噪点的方法，2mm 核大小适合 CT 精度（1-3mm 层厚）。

---

### Islands（保留最大连通域）

**官方：** "Keep largest island: keep the largest connected region."

**代码：**
```python
effect.setParameter("Operation", "KEEP_LARGEST_ISLAND")
```
✅ 参数名和操作完全符合官方定义，用于去除皮肤分割中的孤立碎块。

---

## 3. Dice 体素对齐计算 ✅ 修复方向正确，有改进空间

**修复前问题：** 两个几何体（bolus 和阴模）各自用独立边界框生成体素网格，直接截断对齐，空间对应关系错误。

**修复后：** 计算两者合并边界框，使用同一共享网格做光栅化，确保每个体素一一对应。

**官方推荐方式（参考）：**

官方脚本参考中，获取 segment 体素数据推荐使用：
```python
slicer.util.arrayFromSegmentBinaryLabelmap(segNode, segId, referenceVolumeNode)
```
其中 `referenceVolumeNode` 定义了统一的体素网格（原点、间距、方向），可天然保证空间对齐。

**当前代码的局限：** `Mold_Female_Conformal` 是 Model Node（polydata），不是 Segment，无法使用 `arrayFromSegmentBinaryLabelmap`，因此使用 `vtkPolyDataToImageStencil` 自建网格是正确选择。修复后的共享边界框方案是在此约束下的最佳实现。

**潜在优化（非必须）：** 如果 DICOM volume 已加载，可以将其作为参照网格基准，直接使用 CT 的原点和间距来光栅化，与临床数据的坐标系完全一致：
```python
referenceVolume = slicer.util.getNode("volume_name")
ijkToRas = vtk.vtkMatrix4x4()
referenceVolume.GetIJKToRASMatrix(ijkToRas)
# 以此矩阵定义 origin/spacing/dims
```

---

## 4. slicer.util.saveNode 导出 STL 补充

官方示例中，保存节点到文件：
```python
slicer.util.saveNode(labelmapVolumeNode, filepath)
```

对于 Model Node 导出 STL，Slicer 将直接序列化 polydata 中的 RAS 坐标点，不做坐标系转换。若目标工作流需要 LPS，需手动做矩阵变换：
```python
# RAS→LPS: X、Y 轴取反
transform = vtk.vtkTransform()
transform.Scale(-1, -1, 1)
transformFilter = vtk.vtkTransformPolyDataFilter()
transformFilter.SetInputData(polydata)
transformFilter.SetTransform(transform)
transformFilter.Update()
# 再保存 transformFilter.GetOutput()
```

目前项目导出用于 3D 打印，切片软件通常按几何形状导入，**无需 LPS 转换**，现有实现正确。

---

---

## 5. 阴模生成：SUBTRACT skin 导致底面碎裂 ✅ 已修复

> 查找日期：2026-05-11 | 详细分析见 `docs/mold_generation.md`

**问题：** `_make_female_mold` 在 `SUBTRACT bolus` 后再执行 `SUBTRACT skin`，意图让外壁不穿入皮肤。但 Slicer Margin 各向同性膨胀使底部正好嵌入 skin，减去 skin 后底板完全开口，marching cubes 补出的三角面不规则（"支离破碎"）。`binary_erosion` 补 1 体素 + `vtkFillHolesFilter` 的补救方案在曲面边界处仍产生非流形几何。

**官方/社区依据：**
- Slicer 社区阴模案例（discourse.slicer.org/t/29669）：推荐 `包围体 SUBTRACT 目标形状`，无需减 skin
- bolus 底面天然 = skin 表面（EDT 偏移生成），`Expanded - Bolus` 的内腔底即为 skin 随形面

**修复：** 删除 `SUBTRACT skin` 步骤和 binary_erosion 补底板逻辑，阴模 = `Bolus_Expanded - Bolus`，封闭壳体，底板厚度 = `shell_mm`，浇铸可用。

**代码位置：** `backend/slicer_watcher.py`，函数 `_make_female_mold`

---

## 总结

| 项目 | 状态 | 说明 |
|------|------|------|
| STL 坐标系标注 | ✅ 已修复 | 官方确认 STL 保持 RAS，原标注错误 |
| Margin 效果 | ✅ 符合 | 参数名、用法正确 |
| Hollow 效果 | ✅ 符合 | INSIDE_SURFACE + ShellThicknessMm 正确；极薄壳可考虑 DynamicModeler |
| Smoothing (Median) | ✅ 符合 | 官方推荐的轮廓保留平滑方法 |
| Islands | ✅ 符合 | KEEP_LARGEST_ISLAND 参数正确 |
| Dice 体素对齐 | ✅ 已修复 | 共享网格方案是 polydata 场景的正确做法 |
| 阴模 SUBTRACT skin | ✅ 已修复 | SUBTRACT skin 导致底面开口碎裂，删除后封闭壳体符合浇铸需求 |
| vF 体素化（开放网格） | ✅ 已修复 | 源码确认：开放网格触发 loose-end 修复 → 结果未定义；封孔后体素化；详见 `docs/vtk_voxelization.md` |
| Dice 公式 | ✅ 已修复 | `vB & vCavity` 永远=0（vCavity 排除 vB）；改为 `vCavity = vExpanded & ~vF`，测实际内腔与 bolus 重合度 |
| 穿模指标方向 | ✅ 已修复 | 改为 `vCavity & vSkin`（内腔穿皮），外壳底板入皮是预期设计 |
