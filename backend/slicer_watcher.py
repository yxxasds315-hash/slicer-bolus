"""
Slicer 文件桥接 — 支持 Markups ROI 区域剪切 + 平滑 STL 导出
"""
import json, os, time

CONFIG_FILE = "/tmp/bolus_config.json"
RESULT_FILE = "/tmp/bolus_result.json"
STATUS_FILE = "/tmp/bolus_status.json"
LOG_FILE    = "/tmp/bolus_logs.jsonl"

# ── Segment 命名空间（全局唯一，各步骤统一引用） ──
SEG = {
    "node":               "BolusSegmentation",
    "skin":               "Skin",
    "cutter":             "Cutter_Mask",
    "temp_air":           "__Temp_Outside_Air__",
    "temp_bolus_expanded": "__Bolus_Expanded__",
}

def _bolus_name(thickness_mm: float) -> str:
    """由厚度推导补偿器 segment 名称，全流程统一。

    强制 float 化避免 int/float 混入导致 5 → 'Bolus_5mm' vs 5.0 → 'Bolus_5.0mm' 不一致。
    """
    return f"Bolus_{float(thickness_mm)}mm"


def _safe_get_effect(widget, name):
    """安全获取 SegmentEditor 效果，失败时抛出明确错误"""
    widget.setActiveEffectByName(name)
    effect = widget.activeEffect()
    if not effect:
        raise RuntimeError(f"'{name}' 效果不可用，请确认 Slicer SegmentEditor 模块已加载")
    return effect


def to_log(level, msg):
    entry = json.dumps({"timestamp": time.strftime("%H:%M:%S"), "level": level, "message": msg})
    try:
        with open(LOG_FILE, "a") as f: f.write(entry + "\n")
    except: pass
    print(f"[{level}] {msg}")


def update_status():
    import slicer
    s = {"volumes": [], "segmentations": [], "rois": [], "models": [], "nodes_total": 0}
    try:
        for v in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
            dims = list(v.GetImageData().GetDimensions()) if v.GetImageData() else [0,0,0]
            spac = [round(x, 2) for x in (v.GetSpacing() or [1,1,1])]
            s["volumes"].append({"name": v.GetName(), "id": v.GetID(), "dimensions": dims, "spacing_mm": spac, "has_image": v.GetImageData() is not None})

        for seg in slicer.util.getNodesByClass("vtkMRMLSegmentationNode"):
            names = [seg.GetSegmentation().GetNthSegment(i).GetName() for i in range(seg.GetSegmentation().GetNumberOfSegments())] if seg.GetSegmentation() else []
            s["segmentations"].append({"name": seg.GetName(), "id": seg.GetID(), "segments": names})

        # 检测 Markups ROI 节点
        for roi in slicer.util.getNodesByClass("vtkMRMLMarkupsROINode"):
            center = [0,0,0]; size = [0,0,0]
            roi.GetCenterWorld(center); roi.GetSizeWorld(size)
            radius = [s / 2 for s in size]
            s["rois"].append({"name": roi.GetName(), "id": roi.GetID(), "center": [round(c,1) for c in center], "radius": [round(r,1) for r in radius]})

        s["nodes_total"] = slicer.mrmlScene.GetNumberOfNodes()

        for m in slicer.util.getNodesByClass("vtkMRMLModelNode"):
            poly = m.GetPolyData()
            s["models"].append({"name": m.GetName(), "id": m.GetID(), "vertices": poly.GetNumberOfPoints() if poly else 0})
    except Exception as e:
        s["error"] = str(e)
    try:
        with open(STATUS_FILE, "w") as f: json.dump(s, f)
    except: pass
    return s


def execute_pipeline(config):
    import slicer, vtk

    d = config
    to_log("info", f"========== 开始 (thickness={d.get('thickness_mm', 5)}mm) ==========")

    # Step 1: 确认数据 (DICOM 已由预览步骤加载)
    to_log("info", "[1/5] 确认数据...")
    vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if not vols: raise RuntimeError("场景中无体积数据")
    vol = vols[0]
    to_log("info", f"  体积: {vol.GetName()}")

    # Step 2: 校验已有分割节点
    to_log("info", "[2/5] 校验分割节点...")

    seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if not seg_node or not seg_node.IsA("vtkMRMLSegmentationNode"):
        raise RuntimeError(f"未找到 {SEG['node']} 节点, 请先在步骤2中执行预览分割")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName(SEG["skin"])
    if not skin_id:
        raise RuntimeError(f"未找到 {SEG['skin']} 段, 请重新运行预览步骤")
    to_log("info", f"  校验通过: {SEG['skin']} 段存在")

    # ── 自动边界检查: 确保 volume 有足够空间容纳全流程膨胀 ──
    # 全流程最大外扩 = bolus Margin + 阴模 shell 膨胀
    _shell = d.get("mold_shell_thickness_mm", 4.0)
    _required_margin = d["thickness_mm"] + _shell + 3.0  # +3mm 光栅化安全余量

    skin_poly = vtk.vtkPolyData()
    seg_node.GetClosedSurfaceRepresentation(skin_id, skin_poly)
    if skin_poly.GetNumberOfPoints() == 0:
        seg_node.CreateClosedSurfaceRepresentation()
        seg_node.GetClosedSurfaceRepresentation(skin_id, skin_poly)
    skin_bounds = [0]*6
    skin_poly.GetBounds(skin_bounds)
    vol_bounds = [0]*6
    vol.GetRASBounds(vol_bounds)

    tight_axes = []
    for i, axis in enumerate(["X", "Y", "Z"]):
        lo_gap = skin_bounds[i*2]   - vol_bounds[i*2]
        hi_gap = vol_bounds[i*2+1]  - skin_bounds[i*2+1]
        lo_ok  = lo_gap >= _required_margin
        hi_ok  = hi_gap >= _required_margin
        if not lo_ok or not hi_ok:
            tight_axes.append(f"{axis}(低{lo_gap:.0f}/高{hi_gap:.0f}mm, 需≥{_required_margin:.0f}mm)")

    if tight_axes:
        to_log("warning", f"  ⚠ Volume 边界不足, bolus/模具可能被裁切: {', '.join(tight_axes)}")
        to_log("warning", f"  ⚠ 建议: 减小 bolus 厚度或增大扫描 FOV")
    else:
        to_log("info", f"  边界检查通过: 各轴距 volume 边界 ≥{_required_margin:.0f}mm")

    # Step 3: 补偿器设计
    design_method = d.get("design_method", "hollow")
    to_log("info", f"[3/5] 补偿器设计 (thickness={d['thickness_mm']}mm, method={design_method})...")

    BOLUS_THICKNESS = d["thickness_mm"]
    bolus_name = _bolus_name(BOLUS_THICKNESS)

    old_bolus = seg.GetSegmentIdBySegmentName(bolus_name)
    if old_bolus:
        seg.RemoveSegment(old_bolus)
    bolus_id = seg.AddEmptySegment(bolus_name, bolus_name, (0.2, 0.6, 0.9))

    roi_nodes = slicer.util.getNodesByClass("vtkMRMLMarkupsROINode")
    roi_mode = d.get("roi_mode", "full_skin")
    if roi_mode == "slicer_roi":
        if not roi_nodes:
            raise RuntimeError("ROI 模式为 'slicer_roi' 但未检测到 Markups ROI 节点。请返回第 3 步在 Slicer 中创建 ROI，或切换为「全部皮肤」模式。")
        roi = roi_nodes[0]
        to_log("info", f"  使用 ROI: {roi.GetName()}")
        bounds = [0]*6
        roi.GetRASBounds(bounds)
    else:
        to_log("info", "  无 ROI，使用皮肤边界作为默认裁切区域")
        skin_poly = vtk.vtkPolyData()
        seg_node.GetClosedSurfaceRepresentation(skin_id, skin_poly)
        if skin_poly.GetNumberOfPoints() == 0:
            seg_node.CreateClosedSurfaceRepresentation()
            seg_node.GetClosedSurfaceRepresentation(skin_id, skin_poly)
        if skin_poly.GetNumberOfPoints() == 0:
            raise RuntimeError("皮肤表面数据为空，无法获取边界。请确认分割结果有效并已生成 3D 表面表示。")
        bounds = [0]*6
        skin_poly.GetBounds(bounds)

    sizes = [bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]]
    min_axis = sizes.index(min(sizes))
    safe_depth = BOLUS_THICKNESS * 2 + 15.0
    if sizes[min_axis] < safe_depth:
        center = (bounds[min_axis*2 + 1] + bounds[min_axis*2]) / 2.0
        bounds[min_axis*2] = center - safe_depth / 2.0
        bounds[min_axis*2 + 1] = center + safe_depth / 2.0

    # cutter 在所有轴上外扩 2x bolus 厚度，确保膨胀后的 bolus 完全落入裁切范围
    for i in range(3):
        bounds[i*2] -= BOLUS_THICKNESS * 2
        bounds[i*2 + 1] += BOLUS_THICKNESS * 2

    cube = vtk.vtkCubeSource()
    cube.SetBounds(bounds)
    cube.Update()

    old_cutter = seg.GetSegmentIdBySegmentName(SEG["cutter"])
    if old_cutter:
        seg.RemoveSegment(old_cutter)
    cutter_id = seg_node.AddSegmentFromClosedSurfaceRepresentation(cube.GetOutput(), SEG["cutter"], [1, 0, 0])
    seg.CreateRepresentation(slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName())
    to_log("info", "  Cutter 掩膜已创建并光栅化")

    import numpy as np
    from scipy.ndimage import distance_transform_edt, label as _scipy_label

    # 体素间距: Slicer 返回 (x,y,z)，numpy 数组轴序为 (z,y,x)
    sx, sy, sz = vol.GetSpacing()
    spacing_zyx = (sz, sy, sx)
    to_log("info", f"  体素间距 x={sx:.2f} y={sy:.2f} z={sz:.2f} mm")

    skin_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, skin_id, vol).astype(bool)
    to_log("info", f"  Skin 数组 shape={skin_arr.shape}")

    # 检查 skin 是否实心化：连通体分析 ~skin，最大分量=外部空气，其余=内腔
    _air_labeled, _n_air = _scipy_label(~skin_arr)
    if _n_air > 1:
        _air_sizes = np.bincount(_air_labeled.ravel())[1:]
        _internal_vox = int(_air_sizes.sum() - _air_sizes.max())
        _internal_cm3 = _internal_vox * sx * sy * sz / 1000
        if _internal_cm3 > 5.0:
            to_log("warning", f"  ⚠ 检测到 {_n_air - 1} 处内部气腔 ({_internal_cm3:.1f} cm³)")
            to_log("warning", "  ⚠ EDT 会把鼻窦/气管等内腔计为皮肤外侧，产生伪影 bolus")
            to_log("warning", "  ⚠ 建议先执行「实心化」步骤再继续")

    # EDT: 每个皮肤外侧体素到皮肤表面的精确欧氏距离（mm）
    to_log("info", "  [EDT] 计算精确欧氏距离变换...")
    edt = distance_transform_edt(~skin_arr, sampling=spacing_zyx)

    # Bolus = 皮肤外侧 且 距皮肤表面 ≤ thickness_mm（两种 design_method 结果一致）
    bolus_arr = (edt > 0) & (edt <= BOLUS_THICKNESS)
    to_log("info", f"  Bolus 初始体积: {bolus_arr.sum()} 体素")

    # 应用 ROI cutter 掩膜
    cutter_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, cutter_id, vol).astype(bool)
    seg.RemoveSegment(cutter_id)
    bolus_arr &= cutter_arr
    to_log("info", f"  裁切后体积: {bolus_arr.sum()} 体素")

    # 保留最大连通体（替代 Islands KEEP_LARGEST_ISLAND）
    labeled, n_components = _scipy_label(bolus_arr)
    if n_components == 0:
        raise RuntimeError("Bolus 生成失败: EDT 结果为空，请检查皮肤分割和 ROI")
    if n_components > 1:
        sizes = np.bincount(labeled.ravel())[1:]
        bolus_arr = labeled == (np.argmax(sizes) + 1)
        to_log("info", f"  Islands: {n_components} 个连通体 → 保留最大 ({sizes.max()} 体素)")

    slicer.util.updateSegmentBinaryLabelmapFromArray(
        bolus_arr.astype(np.int8), seg_node, bolus_id, vol
    )
    to_log("info", "  [EDT] Bolus 已写入 Slicer")
    seg_node.CreateClosedSurfaceRepresentation()

    polyData = vtk.vtkPolyData()
    seg_node.GetClosedSurfaceRepresentation(bolus_id, polyData)
    pts = polyData.GetNumberOfPoints()
    if pts == 0:
        raise RuntimeError("Bolus 生成失败: 网格顶点为 0, ROI 可能偏离皮肤表面")

    # 空间尺寸（轴对齐包围盒，RAS mm）
    b = polyData.GetBounds()
    bounds_mm = [round(b[1]-b[0], 1), round(b[3]-b[2], 1), round(b[5]-b[4], 1)]

    # 实际体积（闭合曲面 → vtkMassProperties，mm³ → cm³）
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(polyData); tri.Update()
    mass = vtk.vtkMassProperties()
    mass.SetInputData(tri.GetOutput()); mass.Update()
    volume_cm3 = round(mass.GetVolume() / 1000.0, 1)

    to_log("success", f"Bolus 已生成: {bolus_name} ({pts} 顶点) "
                      f"尺寸 {bounds_mm[0]}×{bounds_mm[1]}×{bounds_mm[2]}mm "
                      f"体积 {volume_cm3}cm³")

    return [{"node": seg_node.GetID(), "bolus": bolus_name, "vertices": pts,
             "bounds_mm": bounds_mm, "volume_cm3": volume_cm3}]


def execute_preview(config):
    import slicer, vtk
    from DICOMLib import DICOMUtils

    d = config
    to_log("info", "========== 预览: 加载数据 + 皮肤分割 ==========")

    to_log("info", "[1/3] 加载数据...")
    vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if d.get("dicom_dir") == "__slicer__":
        if not vols: raise RuntimeError("Slicer 中无体积数据")
    else:
        with DICOMUtils.TemporaryDICOMDatabase() as db:
            DICOMUtils.importDicom(d["dicom_dir"], db)
            for puid in db.patients():
                DICOMUtils.loadPatientByUID(puid)
        slicer.app.processEvents()
        vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if not vols: raise RuntimeError("未找到体积数据")
    vol = vols[0]
    to_log("info", f"  体积: {vol.GetName()}")

    to_log("info", "[2/3] 皮肤分割...")

    old = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if old:
        slicer.mrmlScene.RemoveNode(old)

    seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    seg_node.SetName(SEG["node"])
    seg_node.CreateDefaultDisplayNodes()
    seg_node.SetReferenceImageGeometryParameterFromVolumeNode(vol)

    skin_id = seg_node.GetSegmentation().AddEmptySegment(SEG["skin"], SEG["skin"], (0.2, 0.8, 0.3))
    seg = seg_node.GetSegmentation()

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorWidget.setSourceVolumeNode(vol)
    editorNode.SetSelectedSegmentID(skin_id)

    try:
        effect = _safe_get_effect(editorWidget, "Threshold")
        effect.setParameter("MinimumThreshold", "-300")
        effect.setParameter("MaximumThreshold", "3000")
        effect.self().onApply()
        to_log("info", "  阈值分割完成 (HU -300 ~ 3000)")
    finally:
        editorWidget.setActiveEffectByName("")
        editorWidget.setMRMLScene(None)
        slicer.mrmlScene.RemoveNode(editorNode)

    seg_node.CreateClosedSurfaceRepresentation()
    display = seg_node.GetDisplayNode()
    display.SetVisibility3D(True)
    display.SetOpacity3D(0.5)
    lm = slicer.app.layoutManager()
    for dv in range(lm.threeDViewCount):
        lm.threeDWidget(dv).threeDView().resetFocalPoint()
    to_log("success", "阈值初筛完成 — 请检查是否需要剪裁床板")

    return [{"node": seg_node.GetID(), "name": seg_node.GetName(), "skin_segment": skin_id}]


def execute_activate_scissors(config):
    import slicer

    to_log("info", "========== 激活 Scissors 剪裁工具 ==========")

    seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if not seg_node:
        raise RuntimeError("未找到分割节点, 请先运行预览")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName(SEG["skin"])
    if not skin_id:
        raise RuntimeError(f"未找到 {SEG['skin']} 段")

    vol = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")[0]

    slicer.util.selectModule("SegmentEditor")
    slicer.app.processEvents()

    ed = slicer.modules.segmenteditor.widgetRepresentation().self().editor
    ed.setSegmentationNode(seg_node)
    ed.setSourceVolumeNode(vol)
    ed.setActiveEffectByName("Scissors")

    def _restore():
        lm = slicer.app.layoutManager()
        lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
    qt.QTimer.singleShot(300, _restore)

    to_log("success", "Scissors 已激活 — 在 2D 视图中切断粘连, 完成后点「完成剪裁」")

    return [{"node": seg_node.GetID(), "status": "scissors_active"}]


def execute_finalize_preview(config):
    import slicer

    d = config
    to_log("info", "========== 完成分割: 去杂讯 + 平滑 ==========")

    seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if not seg_node:
        raise RuntimeError("未找到分割节点")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName(SEG["skin"])
    if not skin_id:
        raise RuntimeError(f"未找到 {SEG['skin']} 段")

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorNode.SetSelectedSegmentID(skin_id)

    try:
        effect = _safe_get_effect(editorWidget, "Islands")
        effect.setParameter("Operation", "KEEP_LARGEST_ISLAND")
        effect.self().onApply()
        to_log("info", "  去杂讯完成 (保留最大岛)")

        effect = _safe_get_effect(editorWidget, "Smoothing")
        effect.setParameter("SmoothingMethod", d.get("smoothing_method", "MEDIAN"))
        effect.setParameter("KernelSizeMm", str(d.get("smoothing_kernel_mm", 3.0)))
        effect.self().onApply()
        seg_node.CreateClosedSurfaceRepresentation()
        to_log("info", f"  平滑完成")
    finally:
        editorWidget.setActiveEffectByName("")
        editorWidget.setMRMLScene(None)
        slicer.mrmlScene.RemoveNode(editorNode)

    try:
        med = slicer.modules.segmenteditor.widgetRepresentation().self().editor
        med.setActiveEffect(None)
    except:
        pass

    seg_node.CreateClosedSurfaceRepresentation()
    seg_node.GetDisplayNode().SetVisibility3D(True)
    seg_node.GetDisplayNode().SetOpacity3D(0.5)

    lm = slicer.app.layoutManager()
    for dv in range(lm.threeDViewCount):
        lm.threeDWidget(dv).threeDView().resetFocalPoint()
    to_log("success", "分割完成 — 3D 皮肤已显示")

    return [{"node": seg_node.GetID(), "name": seg_node.GetName(), "skin_segment": skin_id}]


def execute_solidify(config):
    """实心化: 形态学闭合密封气道 → 外部空气掩膜 → 保留最大岛 → 反转填充内部空腔."""
    import slicer

    to_log("info", "========== 实心化: 填充内部空腔 ==========")

    seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if not seg_node:
        raise RuntimeError(f"未找到 {SEG['node']} 节点, 请先运行预览")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName(SEG["skin"])
    if not skin_id:
        raise RuntimeError(f"未找到 {SEG['skin']} 段")

    vol = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")[0]

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)

    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorWidget.setSourceVolumeNode(vol)
    editorNode.SetSelectedSegmentID(skin_id)

    def apply_effect(name, params: dict):
        eff = _safe_get_effect(editorWidget, name)
        for k, v in params.items():
            eff.setParameter(k, v)
        eff.self().onApply()

    try:
        to_log("info", "[1/4] 形态学闭合 — 密封气道开口...")
        apply_effect("Smoothing", {
            "SmoothingMethod": "MORPHOLOGICAL_CLOSING",
            "KernelSizeMm": "6.0",
        })

        to_log("info", "[2/4] 构建外部空气掩膜...")
        AIR_NAME = SEG["temp_air"]
        existing_air_id = seg.GetSegmentIdBySegmentName(AIR_NAME)
        if existing_air_id:
            seg.RemoveSegment(existing_air_id)

        air_id = seg.AddEmptySegment(AIR_NAME, AIR_NAME)
        editorNode.SetSelectedSegmentID(air_id)

        apply_effect("Logical operators", {"Operation": "COPY", "ModifierSegmentID": skin_id})
        apply_effect("Logical operators", {"Operation": "INVERT", "ModifierSegmentID": ""})

        to_log("info", "[3/4] 移除内部空腔 (气管/鼻窦/肺)...")
        apply_effect("Islands", {"Operation": "KEEP_LARGEST_ISLAND"})

        to_log("info", "[4/4] 最终反转 — 铸造实心体...")
        editorNode.SetSelectedSegmentID(skin_id)
        apply_effect("Logical operators", {"Operation": "COPY", "ModifierSegmentID": air_id})
        apply_effect("Logical operators", {"Operation": "INVERT", "ModifierSegmentID": ""})
    finally:
        editorWidget.setActiveEffectByName("")
        slicer.mrmlScene.RemoveNode(editorNode)
        editorWidget.setMRMLScene(None)
        seg.RemoveSegment(air_id)

    seg_node.CreateClosedSurfaceRepresentation()
    to_log("success", "实心化完成 — 所有内部空腔已填充, 身体为完整实心体")

    return [{"node": seg_node.GetID(), "name": seg_node.GetName(), "skin_segment": skin_id}]


def execute_seal(config):
    """二次封口: 在实心化后的 Skin 段上执行两次 MORPHOLOGICAL_CLOSING，消除鼻孔与外耳道残余空气."""
    import slicer

    d = config
    k1 = d.get("seal_kernel_1_mm", 15.0)  # 耳道大核
    k2 = d.get("seal_kernel_2_mm", 8.0)   # 鼻孔中核

    to_log("info", f"========== 二次封口: 大核{k1}mm / 中核{k2}mm ==========")

    seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if not seg_node:
        raise RuntimeError(f"未找到 {SEG['node']} 节点, 请先运行预览")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName(SEG["skin"])
    if not skin_id:
        raise RuntimeError(f"未找到 {SEG['skin']} 段")

    vol = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")[0]

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)
    editorNode.SetSelectedSegmentID(skin_id)

    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorWidget.setSourceVolumeNode(vol)

    def apply_effect(name, params: dict):
        eff = _safe_get_effect(editorWidget, name)
        for k, v in params.items():
            eff.setParameter(k, v)
        eff.self().onApply()

    try:
        # 第一次：大核封耳道（管道纵深长，需要更大核）
        to_log("info", f"[1/2] 大核封耳道 — MORPHOLOGICAL_CLOSING {k1}mm")
        apply_effect("Smoothing", {
            "SmoothingMethod": "MORPHOLOGICAL_CLOSING",
            "KernelSizeMm": str(k1),
        })

        # 第二次：中核补鼻孔（避免过大核破坏鼻尖轮廓）
        to_log("info", f"[2/2] 中核补鼻孔 — MORPHOLOGICAL_CLOSING {k2}mm")
        apply_effect("Smoothing", {
            "SmoothingMethod": "MORPHOLOGICAL_CLOSING",
            "KernelSizeMm": str(k2),
        })
    finally:
        editorWidget.setActiveEffectByName("")
        editorWidget.setMRMLScene(None)
        slicer.mrmlScene.RemoveNode(editorNode)

    seg_node.CreateClosedSurfaceRepresentation()
    to_log("success", f"二次封口完成 — 大核{k1}mm + 中核{k2}mm, 请在 Slicer 中检查鼻孔/耳道")

    return [{"node": seg_node.GetID(), "name": seg_node.GetName(), "skin_segment": skin_id}]


def execute_create_roi(config):
    import slicer

    to_log("info", "========== 创建 Markups ROI ==========")

    vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if not vols:
        raise RuntimeError("场景中无体积数据, 请先完成预览步骤")
    vol = vols[0]

    roi = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode")
    roi.SetName("BolusROI")

    bounds = [0.0]*6
    vol.GetRASBounds(bounds)
    center_ras = [(bounds[0]+bounds[1])/2, (bounds[2]+bounds[3])/2, (bounds[4]+bounds[5])/2]
    CUBE_HALF = 100.0
    roi.SetCenter(center_ras)
    roi.SetSize([CUBE_HALF*2, CUBE_HALF*2, CUBE_HALF*2])

    disp = roi.GetDisplayNode()
    if disp:
        disp.SetHandlesInteractive(True)
    slicer.app.processEvents()

    center = [0.0, 0.0, 0.0]; size = [0.0, 0.0, 0.0]
    roi.GetCenterWorld(center); roi.GetSizeWorld(size)
    to_log("success", f"ROI 已创建: {roi.GetName()} 中心({[round(c,1) for c in center]}) 大小({[round(s,1) for s in size]})")

    return [{"node": roi.GetID(), "name": roi.GetName(), "center": [round(c, 1) for c in center], "radius": [round(s / 2, 1) for s in size]}]


def execute_export(config):
    """导出选中的模型节点为 STL 文件到指定目录"""
    import slicer, vtk, os

    d = config
    out_dir = d.get("output_dir", "").strip()
    if not out_dir:
        raise RuntimeError("未设置输出目录")

    models = d.get("export_models", [])
    if not models:
        raise RuntimeError("未选择要导出的模型")

    os.makedirs(out_dir, exist_ok=True)
    exported = []

    for model_name in models:
        node = slicer.mrmlScene.GetFirstNodeByName(model_name)
        if not node or not node.IsA("vtkMRMLModelNode"):
            poly = vtk.vtkPolyData()
            # also try to find from segmentation node
            seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
            if seg_node and seg_node.IsA("vtkMRMLSegmentationNode"):
                seg = seg_node.GetSegmentation()
                seg_id = seg.GetSegmentIdBySegmentName(model_name)
                if seg_id:
                    seg_node.CreateClosedSurfaceRepresentation()
                    seg_node.GetClosedSurfaceRepresentation(seg_id, poly)
            if poly.GetNumberOfPoints() == 0:
                to_log("warning", f"  跳过 {model_name}: 未找到对应节点/段")
                continue
            node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", f"_export_{model_name}")
            node.SetAndObservePolyData(poly)

        path = os.path.join(out_dir, f"{model_name}.stl")
        slicer.util.saveNode(node, path)
        exported.append(path)
        to_log("info", f"  导出 {model_name} → {path}")

    to_log("success", f"导出完成: {len(exported)} 个文件")
    return [{"exported": exported}]


# ═══════════════════════════════════════════════
#  模具生成模块
# ═══════════════════════════════════════════════

def _get_segment_polydata(seg_node, segment_name):
    seg = seg_node.GetSegmentation()
    seg_id = seg.GetSegmentIdBySegmentName(segment_name)
    if not seg_id:
        names = [seg.GetNthSegment(i).GetName() for i in range(seg.GetNumberOfSegments())]
        raise RuntimeError(f"找不到 segment '{segment_name}'，现有: {names}")
    poly = vtk.vtkPolyData()
    seg_node.GetClosedSurfaceRepresentation(seg_id, poly)
    if poly.GetNumberOfPoints() == 0:
        seg_node.CreateClosedSurfaceRepresentation()
        seg_node.GetClosedSurfaceRepresentation(seg_id, poly)
    to_log("info", f"  [✓] {segment_name}: {poly.GetNumberOfPoints():,} pts, {poly.GetNumberOfCells():,} cells")
    return poly


def _poly_boolean(poly_a, poly_b, operation):
    def _triangulate(poly):
        tri = vtk.vtkTriangleFilter()
        tri.SetInputData(poly)
        tri.Update()
        norm = vtk.vtkPolyDataNormals()
        norm.SetInputData(tri.GetOutput())
        norm.ConsistencyOn()
        norm.Update()
        return norm.GetOutput()

    a = _triangulate(poly_a)
    b = _triangulate(poly_b)

    if operation == "difference":
        op_val = vtk.vtkBooleanOperationPolyDataFilter.VTK_DIFFERENCE
    elif operation == "union":
        op_val = vtk.vtkBooleanOperationPolyDataFilter.VTK_UNION
    elif operation == "intersection":
        op_val = vtk.vtkBooleanOperationPolyDataFilter.VTK_INTERSECTION
    else:
        raise ValueError(f"未知布尔操作: {operation}")

    boolean_filter = vtk.vtkBooleanOperationPolyDataFilter()
    boolean_filter.SetOperation(op_val)
    boolean_filter.SetInputData(0, a)
    boolean_filter.SetInputData(1, b)
    boolean_filter.ReorientDifferenceCellsOn()
    boolean_filter.Update()
    result = boolean_filter.GetOutput()
    to_log("info", f"  [{operation}] → {result.GetNumberOfPoints():,} pts")
    return result


def _apply_margin_to_segment(seg_node, segment_name, margin_mm, new_name):
    seg = seg_node.GetSegmentation()
    src_id = seg.GetSegmentIdBySegmentName(segment_name)
    new_id = seg.AddEmptySegment(new_name, new_name)
    ref_volume = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    if ref_volume is None:
        raise RuntimeError("场景中无体积数据，无法执行 Margin 膨胀。请先完成 DICOM 加载和预览分割。")
    seg_editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    seg_editor_node.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)
    seg_editor_widget = slicer.qMRMLSegmentEditorWidget()
    seg_editor_widget.setMRMLScene(slicer.mrmlScene)
    seg_editor_widget.setMRMLSegmentEditorNode(seg_editor_node)
    seg_editor_widget.setSegmentationNode(seg_node)
    seg_editor_widget.setSourceVolumeNode(ref_volume)
    seg_editor_node.SetSelectedSegmentID(new_id)
    # 确保 binary labelmap 为主表示，COPY 依赖它
    seg.CreateRepresentation(slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName())
    try:
        # 用 Logical operators COPY 复制源段（避免 seg.CopySegment 兼容性问题）
        effect = _safe_get_effect(seg_editor_widget, "Logical operators")
        effect.setParameter("Operation", "COPY")
        effect.setParameter("ModifierSegmentID", src_id)
        effect.self().onApply()
        to_log("info", f"  [复制] {segment_name} → {new_name}")

        effect = _safe_get_effect(seg_editor_widget, "Margin")
        effect.setParameter("MarginSizeMm", str(margin_mm))
        effect.self().onApply()
        to_log("info", f"  [Margin +{margin_mm}mm] 完成")
    finally:
        seg_editor_widget.setActiveEffectByName("")
        seg_editor_widget.setMRMLScene(None)
        slicer.mrmlScene.RemoveNode(seg_editor_node)
    return new_id


def _make_cylinder_poly(cx, cy, cz, radius, height, resolution=32):
    """生成沿 Z 轴的圆柱，中心位于 (cx, cy, cz)。

    vtkCylinderSource 默认沿 Y 轴。先在原点生成，再旋转为 Z 轴，最后平移到目标位置；
    顺序很关键——若先 SetCenter 再 RotateX，世界原点旋转会把圆柱甩出预期位置。
    """
    cyl = vtk.vtkCylinderSource()
    cyl.SetRadius(radius)
    cyl.SetHeight(height)
    cyl.SetResolution(resolution)
    cyl.CappingOn()
    cyl.Update()
    transform = vtk.vtkTransform()
    transform.PostMultiply()
    transform.RotateX(90)
    transform.Translate(cx, cy, cz)
    tf_filter = vtk.vtkTransformPolyDataFilter()
    tf_filter.SetInputData(cyl.GetOutput())
    tf_filter.SetTransform(transform)
    tf_filter.Update()
    return tf_filter.GetOutput()


def _add_model_to_scene(poly, name, color=(0.8, 0.5, 0.3), opacity=0.7):
    if poly.GetNumberOfPoints() == 0:
        to_log("warning", f"  [显示] {name} 跳过 — 无顶点数据")
        return None
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)
    node.SetAndObservePolyData(poly)
    disp = node.CreateDefaultDisplayNodes()
    if disp:
        disp.SetColor(*color)
        disp.SetOpacity(opacity)
    to_log("info", f"  [显示] {name} → 3D 视图")
    return node


def _make_female_mold(seg_node, bolus_name, skin_name, shell_mm):
    """阴模：bolus 外扩 shell_mm 后掏除 bolus，得到封闭空心壳。

    不减 skin：bolus 底面天然贴 skin 表面，内腔底面即为 skin 随形面；
    外壳底面深入 skin shell_mm（壳壁厚度），是浇铸模具的正常底板厚度。
    减 skin 会把底板整个挖穿，marching cubes 补出碎面，不能用。
    """
    to_log("info", "── 阴模生成 ──")
    seg = seg_node.GetSegmentation()

    _apply_margin_to_segment(seg_node, bolus_name, shell_mm, SEG["temp_bolus_expanded"])

    expanded_id = seg.GetSegmentIdBySegmentName(SEG["temp_bolus_expanded"])
    bolus_id    = seg.GetSegmentIdBySegmentName(bolus_name)

    female_name = "Mold_Female"
    female_id   = seg.AddEmptySegment(female_name, female_name)
    ref_volume  = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")

    en = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    en.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)
    ew = slicer.qMRMLSegmentEditorWidget()
    ew.setMRMLScene(slicer.mrmlScene)
    ew.setMRMLSegmentEditorNode(en)
    ew.setSegmentationNode(seg_node)
    ew.setSourceVolumeNode(ref_volume)
    en.SetSelectedSegmentID(female_id)
    seg.CreateRepresentation(slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName())

    try:
        eff = _safe_get_effect(ew, "Logical operators")
        eff.setParameter("Operation", "COPY")
        eff.setParameter("ModifierSegmentID", expanded_id)
        eff.self().onApply()
        to_log("info", f"  [复制] Bolus_Expanded → {female_name}")

        eff = _safe_get_effect(ew, "Logical operators")
        eff.setParameter("Operation", "SUBTRACT")
        eff.setParameter("ModifierSegmentID", bolus_id)
        eff.self().onApply()
        to_log("info", f"  [掏空] 减去 bolus → {shell_mm}mm 封闭壳体")
    finally:
        ew.setActiveEffectByName("")
        ew.setMRMLScene(None)
        slicer.mrmlScene.RemoveNode(en)

    female_poly = _get_segment_polydata(seg_node, female_name)

    norm = vtk.vtkPolyDataNormals()
    norm.SetInputData(female_poly)
    norm.ConsistencyOn()
    norm.SplittingOff()
    norm.Update()
    female_poly = norm.GetOutput()

    fe = vtk.vtkFeatureEdges()
    fe.SetInputData(female_poly)
    fe.BoundaryEdgesOn(); fe.NonManifoldEdgesOn()
    fe.FeatureEdgesOff(); fe.ManifoldEdgesOff()
    fe.Update()
    open_edges = fe.GetOutput().GetNumberOfCells()
    to_log("info", f"  [阴模] {female_poly.GetNumberOfPoints():,} pts，开放边: {open_edges} ({'封闭' if open_edges == 0 else '⚠ 仍有缺口'})")
    return female_poly



def _add_sprue_and_vents(female_poly, sprue_radius_mm, vent_radius_mm):
    to_log("info", "── 注料口 & 排气孔 ──")
    b = female_poly.GetBounds()
    cx = (b[0] + b[1]) / 2
    cy = (b[2] + b[3]) / 2
    cz = (b[4] + b[5]) / 2
    h_thru = (b[5] - b[4]) + 4

    # 排气孔偏移按模具 X 尺寸自适应，避免小模具上偏移过大错过本体
    x_span = b[1] - b[0]
    vent_offset = min(20.0, x_span * 0.35)
    if vent_offset < sprue_radius_mm + vent_radius_mm + 1.0:
        to_log("warning", f"  ⚠ 模具 X 跨度 {x_span:.1f}mm 过小，跳过排气孔（仅保留注料口）")
        skip_vents = True
    else:
        skip_vents = False

    sprue = _make_cylinder_poly(cx, cy, cz, sprue_radius_mm, h_thru)
    result = _poly_boolean(female_poly, sprue, "difference")
    if result.GetNumberOfPoints() == 0:
        raise RuntimeError("注料口布尔运算失败（结果为空）")

    if not skip_vents:
        vent1 = _make_cylinder_poly(cx + vent_offset, cy, cz, vent_radius_mm, h_thru)
        vent2 = _make_cylinder_poly(cx - vent_offset, cy, cz, vent_radius_mm, h_thru)
        r1 = _poly_boolean(result, vent1, "difference")
        if r1.GetNumberOfPoints() == 0:
            to_log("warning", "  ⚠ 排气孔 1 布尔失败，保留前一步结果")
        else:
            result = r1
        r2 = _poly_boolean(result, vent2, "difference")
        if r2.GetNumberOfPoints() == 0:
            to_log("warning", "  ⚠ 排气孔 2 布尔失败，保留前一步结果")
        else:
            result = r2

    to_log("info", f"  [注料口] r={sprue_radius_mm}mm | [排气孔] r={vent_radius_mm}mm 偏移±{vent_offset:.1f}mm")
    return result


def execute_mold(config):
    import slicer
    d = config
    BOLUS_THICKNESS = d.get("thickness_mm", 5.0)
    bolus_name = _bolus_name(BOLUS_THICKNESS)

    to_log("info", f"========== 模具生成: bolus={bolus_name}, 壳体={d.get('mold_shell_thickness_mm', 4.0)}mm ==========")

    seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if not seg_node or not seg_node.IsA("vtkMRMLSegmentationNode"):
        raise RuntimeError(f"未找到分割节点 '{SEG['node']}'，请先完成皮肤分割和补偿器设计")

    seg = seg_node.GetSegmentation()
    if not seg.GetSegmentIdBySegmentName(bolus_name):
        names = [seg.GetNthSegment(i).GetName() for i in range(seg.GetNumberOfSegments())]
        raise RuntimeError(f"未找到 '{bolus_name}'，现有: {names}。请先完成第6步补偿器执行。")
    if not seg.GetSegmentIdBySegmentName(SEG["skin"]):
        raise RuntimeError(f"未找到 '{SEG['skin']}' 段，请先完成预览分割")

    shell_mm = d.get("mold_shell_thickness_mm", 4.0)
    sprue_r  = d.get("mold_sprue_radius_mm", 3.0)
    vent_r   = d.get("mold_vent_radius_mm", 1.0)

    # 清理上一次生成的同名节点，避免重复生成时累积 _1/_2 后缀导致导出错乱
    for old in list(slicer.util.getNodesByClass("vtkMRMLModelNode")):
        if old.GetName().startswith("Mold_Female_Conformal"):
            slicer.mrmlScene.RemoveNode(old)

    female = _make_female_mold(seg_node, bolus_name, SEG["skin"], shell_mm)

    if d.get("mold_with_sprue", True):
        female = _add_sprue_and_vents(female, sprue_r, vent_r)
        to_log("info", f"  注料口: r={sprue_r}mm / 排气孔: r={vent_r}mm ×2")
    else:
        to_log("info", "  跳过注料口 & 排气孔")

    _add_model_to_scene(female, "Mold_Female_Conformal", color=(0.87, 0.49, 0.33), opacity=0.75)

    # 清理临时 segment
    for name in [SEG["temp_bolus_expanded"], "Mold_Female"]:
        tmp_id = seg.GetSegmentIdBySegmentName(name)
        if tmp_id:
            seg.RemoveSegment(tmp_id)

    to_log("success", "模具生成完成 — Mold_Female_Conformal（橙色）")

    return [{"node": "Mold_Female_Conformal", "type": "female", "vertices": female.GetNumberOfPoints()}]


def execute_validate(config):
    """适形度评估: 比较 bolus 与「阴模内腔」并检查模具几何健康度

    指标:
      M1 MHD       bolus ↔ 阴模内表面双向平均距离
      M2 HD95      bolus ↔ 阴模内表面双向 95% 分位距离
      M3 Dice      bolus 体素 vs 反演内腔体素
      M4 体积比    V_cavity / V_bolus
      M5 最小壳厚  外表面最近点到 bolus 距离，≥3mm 才可靠打印
      M6 非流形边  模具拓扑必须封闭流形 (3D 打印前提)
    附加信息 (不影响 PASS/FAIL):
      I1 硅胶用量  bolus 体积 × 1.1 g/cm³
      I2 模具尺寸  X/Y/Z mm，超 256mm 给出警告

    阈值随上游 CT 体素分辨率自适应，避免对超出输入精度的指标做硬要求
    """
    import slicer, vtk, numpy as np
    from vtk.util.numpy_support import vtk_to_numpy
    from scipy.ndimage import distance_transform_edt

    d = config
    BOLUS_THICKNESS = d.get("thickness_mm", 5.0)
    bolus_name = _bolus_name(BOLUS_THICKNESS)
    shell_mm = d.get("mold_shell_thickness_mm", 4.0)

    to_log("info", f"========== 适形度评估: bolus={bolus_name}, shell={shell_mm}mm ==========")

    seg_node = slicer.mrmlScene.GetFirstNodeByName(SEG["node"])
    if not seg_node or not seg_node.IsA("vtkMRMLSegmentationNode"):
        raise RuntimeError(f"未找到分割节点 '{SEG['node']}'，请先完成皮肤分割和补偿器设计")

    vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if not vols:
        raise RuntimeError("场景中无体积数据，无法读取 CT 体素分辨率")
    ct_min_spacing = max(min(vols[0].GetSpacing()), 0.1)

    # 阈值随 CT 体素分辨率自适应：labelmap 管线单次误差约 1 体素，双向约 2 体素
    mhd_thr  = max(1.0, ct_min_spacing * 2.0)
    hd95_thr = max(2.0, ct_min_spacing * 4.0)

    # ── 内部辅助 ──
    def _sample_poly(p, target_spacing):
        s = vtk.vtkPolyDataPointSampler()
        s.SetInputData(p)
        s.SetDistance(target_spacing)
        s.Update()
        return vtk_to_numpy(s.GetOutput().GetPoints().GetData())

    def _build_locator(p):
        loc = vtk.vtkCellLocator()
        loc.SetDataSet(p)
        loc.BuildLocator()
        return loc

    def _nearest_dist(pts, tgt_locator):
        c = [0., 0., 0.]
        ci = vtk.reference(0); si = vtk.reference(0); d2 = vtk.reference(0.)
        d = np.empty(len(pts))
        for i, p in enumerate(pts):
            tgt_locator.FindClosestPoint(p.tolist(), c, ci, si, d2)
            d[i] = d2 ** 0.5
        return d

    def _voxelize_3d(p, sp, origin, dims):
        """光栅化 polydata 为 3D 布尔掩码 (z, y, x)"""
        img = vtk.vtkImageData()
        img.SetOrigin(*origin); img.SetSpacing(sp, sp, sp); img.SetDimensions(*dims)
        img.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
        stk = vtk.vtkPolyDataToImageStencil()
        stk.SetInputData(p)
        stk.SetOutputOrigin(img.GetOrigin())
        stk.SetOutputSpacing(img.GetSpacing())
        stk.SetOutputWholeExtent(img.GetExtent())
        stk.Update()
        st = vtk.vtkImageStencil()
        st.SetInputData(img)
        st.SetStencilData(stk.GetOutput())
        st.SetBackgroundValue(1); st.Update()
        flat = vtk_to_numpy(st.GetOutput().GetPointData().GetScalars()).astype(bool)
        return ~flat.reshape((dims[2], dims[1], dims[0]))  # SetBackgroundValue(1) → outside=1, invert to get True=inside

    def _bad_edges(p):
        fe = vtk.vtkFeatureEdges()
        fe.SetInputData(p)
        fe.BoundaryEdgesOn(); fe.NonManifoldEdgesOn()
        fe.FeatureEdgesOff(); fe.ManifoldEdgesOff()
        fe.Update()
        return fe.GetOutput().GetNumberOfCells()

    # ── 加载几何 ──
    to_log("info", "[1/5] 加载几何数据...")
    B = _get_segment_polydata(seg_node, bolus_name)
    female_node = slicer.mrmlScene.GetFirstNodeByName("Mold_Female_Conformal")
    if not female_node:
        raise RuntimeError("未找到 Mold_Female_Conformal 节点，请先执行模具生成")
    F = female_node.GetPolyData()
    if not F or F.GetNumberOfPoints() == 0:
        raise RuntimeError("Mold_Female_Conformal 无几何数据")

    # ── 几何健康检查 ──
    to_log("info", "[2/5] 模具拓扑检查...")
    n_bad_F = _bad_edges(F)
    if n_bad_F > 0:
        to_log("warning", f"  ⚠ 模具发现 {n_bad_F} 条非流形/开放边 (3D 打印可能失败)")
    else:
        to_log("info", "  ✓ 模具为封闭流形")

    bB, bF = B.GetBounds(), F.GetBounds()
    PRINTER_LIMIT_MM = 256.0
    mold_x = bF[1] - bF[0]
    mold_y = bF[3] - bF[2]
    mold_z = bF[5] - bF[4]
    fits_printer = mold_x <= PRINTER_LIMIT_MM and mold_y <= PRINTER_LIMIT_MM and mold_z <= PRINTER_LIMIT_MM
    to_log("info", f"  模具尺寸: {mold_x:.1f} × {mold_y:.1f} × {mold_z:.1f} mm  "
                   f"({'✓ 在 256mm 限内' if fits_printer else f'⚠ 超出打印机 {PRINTER_LIMIT_MM:.0f}mm 构建体积'})")

    # ── 共享体素网格 ──
    to_log("info", "[3/5] 体素化 (共享网格 1mm)...")
    _sp = 1.0
    _pad = max(_sp * 2, shell_mm + 2.0)
    _origin = (
        min(bB[0], bF[0]) - _pad,
        min(bB[2], bF[2]) - _pad,
        min(bB[4], bF[4]) - _pad,
    )
    _dims = (
        int((max(bB[1], bF[1]) + _pad - _origin[0]) / _sp) + 1,
        int((max(bB[3], bF[3]) + _pad - _origin[1]) / _sp) + 1,
        int((max(bB[5], bF[5]) + _pad - _origin[2]) / _sp) + 1,
    )
    vB = _voxelize_3d(B, _sp, _origin, _dims)

    # dist_outside_B: EDT 距离场，bolus 内部 = 0，向外递增
    dist_outside_B = distance_transform_edt(~vB, sampling=_sp)
    vExpanded = dist_outside_B <= shell_mm

    # 阴模为空心壳（环形网格）。vtkPolyDataToImageStencil 用奇偶射线规则：
    # 射线穿过外壁再穿过内壁 → 偶数交叉 → 全部判为"外部" → vF 全空。
    # 改用 EDT 直接定义壳料体素：bolus 外表面向外 (0, shell_mm] 即壳壁材料。
    vF = (dist_outside_B > 0) & (dist_outside_B <= shell_mm)

    # vCavity = 内腔 = 外扩区域中属于 bolus 的部分（模具内表面 = bolus 表面）
    vCavity = vExpanded & ~vF  # = vB（当内表面贴合时）

    # ── 自适应密度采样 + 内表面过滤 ──
    to_log("info", "[4/5] 表面采样 (自适应密度)...")
    target_spacing = _sp * 1.5
    pB = _sample_poly(B, target_spacing)
    pF_all = _sample_poly(F, target_spacing)

    F_loc = _build_locator(F)
    B_loc = _build_locator(B)
    dF_all = _nearest_dist(pF_all, B_loc)

    # 最小壳厚：外表面采样点（距 bolus > 0.6×shell_mm）到 bolus 的最小距离
    outer_mask = dF_all > shell_mm * 0.6
    min_shell_mm = float(dF_all[outer_mask].min()) if outer_mask.any() else 0.0
    MIN_PRINT_THICKNESS_MM = 3.0
    shell_thick_ok = min_shell_mm >= MIN_PRINT_THICKNESS_MM

    inner_mask = dF_all < shell_mm * 0.4   # 收紧到 0.4 倍壁厚，避开侧壁
    pF = pF_all[inner_mask]
    dFB = dF_all[inner_mask]
    if len(pF) < 50:
        raise RuntimeError(f"阴模内表面采样点过少 ({len(pF)}/{len(pF_all)})，模具几何可能异常")
    to_log("info", f"  采样: B={len(pB)}, F全表面={len(pF_all)} → 内表面={len(pF)} (间距 {target_spacing:.1f}mm)")

    # ── 计算指标 ──
    to_log("info", "[5/5] 计算 MHD / HD95 / Dice / 体积比 / 壳厚...")
    dBF = _nearest_dist(pB, F_loc)
    MHD = max(dBF.mean(), dFB.mean())
    HD95 = max(np.percentile(dBF, 95), np.percentile(dFB, 95))

    denom = vB.sum() + vCavity.sum()
    Dice = 2 * (vB & vCavity).sum() / denom if denom > 0 else 0.0

    vox_unit = _sp ** 3
    vol_B = vB.sum() * vox_unit
    vol_cavity = vCavity.sum() * vox_unit
    Ratio = vol_cavity / vol_B if vol_B > 0 else 0.0

    silicone_cm3 = round(vol_B / 1000.0, 1)
    silicone_g   = round(silicone_cm3 * 1.1, 1)

    # ── 判定 ──
    geom_ok = (n_bad_F == 0)
    ok = all([
        MHD < mhd_thr,
        HD95 < hd95_thr,
        Dice > 0.95,
        0.95 < Ratio < 1.05,
        shell_thick_ok,
        geom_ok,
    ])

    lines = [
        f"{'指标':<14} {'值':>10}    目标",
        "─" * 52,
        f"{'MHD':<14} {MHD:>9.3f}mm   <{mhd_thr:.2f}mm     {'✓' if MHD < mhd_thr else '✗'}",
        f"{'HD95':<14} {HD95:>9.3f}mm   <{hd95_thr:.2f}mm     {'✓' if HD95 < hd95_thr else '✗'}",
        f"{'Dice':<14} {Dice:>10.4f}   >0.95          {'✓' if Dice > 0.95 else '✗'}",
        f"{'体积比':<14} {Ratio:>10.4f}   0.95~1.05      {'✓' if 0.95 < Ratio < 1.05 else '✗'}",
        f"{'最小壳厚':<14} {min_shell_mm:>9.2f}mm   ≥{MIN_PRINT_THICKNESS_MM:.0f}mm         {'✓' if shell_thick_ok else '✗ 过薄'}",
        f"{'非流形边':<14} {n_bad_F:>10d}    =0             {'✓' if geom_ok else '✗'}",
        "─" * 52,
        f"硅胶用量: {silicone_cm3:.1f} cm³ ≈ {silicone_g:.1f} g  |  "
        f"模具: {mold_x:.0f}×{mold_y:.0f}×{mold_z:.0f} mm {'✓' if fits_printer else '⚠ 超出打印机'}",
        f"(CT 体素 {ct_min_spacing:.2f}mm，MHD/HD95 阈值已自适应)",
        f"{'✓ PASS' if ok else '✗ FAIL'}",
    ]
    for line in lines:
        to_log("info", line)

    # ── 各指标说明（含不通过时的修复建议）──
    METRIC_HELP = [
        ("MHD",   MHD < mhd_thr,
         "模具内表面与 bolus 表面的平均距离，反映整体贴合精度。",
         f"当前值 {MHD:.3f}mm 超出 CT 体素精度阈值 {mhd_thr:.2f}mm。\n"
         "  → 重新执行第 6 步（模具生成）；若问题持续，检查皮肤分割是否包含噪声点。"),
        ("HD95",  HD95 < hd95_thr,
         "bolus 与模具内表面距离的 95% 分位值，反映最差 5% 区域的贴合误差。",
         f"当前值 {HD95:.3f}mm 超出阈值 {hd95_thr:.2f}mm，存在局部贴合缺陷。\n"
         "  → 检查 bolus 边缘区域（Scissors 裁切边界）是否有毛刺，重新分割后再生成模具。"),
        ("Dice",  Dice > 0.95,
         "bolus 体积与模具内腔体积的重叠度（1.0 = 完全一致）。",
         f"当前值 {Dice:.4f}，模具内腔与 bolus 体积不匹配。\n"
         "  → 确认模具是从当前 bolus 生成的；若 bolus 已重新执行，需重新生成模具。"),
        ("体积比", 0.95 < Ratio < 1.05,
         "模具内腔体积 / bolus 体积，应接近 1.0（内腔 = bolus 完整填充空间）。",
         f"当前值 {Ratio:.4f}，偏差超出 ±5%。\n"
         "  → 重新生成模具；若比值持续偏大，检查 Bolus_Expanded 段是否意外保留在场景中。"),
        ("最小壳厚", shell_thick_ok,
         f"模具最薄处壁厚，需 ≥{MIN_PRINT_THICKNESS_MM:.0f}mm 保证 3D 打印强度。",
         f"当前最薄处 {min_shell_mm:.2f}mm，CT 体素 {ct_min_spacing:.2f}mm 导致 Margin 膨胀精度不足。\n"
         f"  → 在第 6 步将壳厚设定值调高至 {shell_mm + 1.0:.0f}mm（实际膨胀后约 {min_shell_mm + 1.0:.1f}mm）。"),
        ("非流形边", geom_ok,
         "模具网格是否为封闭流形（无洞、无自交），封闭才能正确切片打印。",
         f"发现 {n_bad_F} 条非流形/开放边，模具切片可能失败。\n"
         "  → 重新生成模具；若问题持续，在 Slicer Surface Toolbox 中执行 Clean / Fill Holes。"),
    ]

    to_log("info", "── 指标说明 ──")
    for name, passed, description, fix in METRIC_HELP:
        to_log("info", f"[{name}] {description}")
        if not passed:
            for fix_line in fix.split("\n"):
                to_log("warning", f"  ✗ {fix_line.strip()}")

    result_status = "PASS" if ok else "FAIL"
    to_log("success" if ok else "error", f"适形度评估: {result_status}")

    return [{
        "status": result_status,
        "MHD_mm": round(MHD, 3),
        "HD95_mm": round(HD95, 3),
        "Dice": round(Dice, 4),
        "volume_ratio": round(Ratio, 4),
        "min_shell_thickness_mm": round(min_shell_mm, 2),
        "non_manifold_edges": int(n_bad_F),
        "silicone_cm3": silicone_cm3,
        "silicone_g": silicone_g,
        "mold_dims_mm": [round(mold_x, 1), round(mold_y, 1), round(mold_z, 1)],
        "fits_printer": fits_printer,
        "ct_voxel_min_mm": round(ct_min_spacing, 3),
        "thresholds": {
            "MHD_mm": round(mhd_thr, 3),
            "HD95_mm": round(hd95_thr, 3),
            "Dice": 0.95,
            "volume_ratio_min": 0.95,
            "volume_ratio_max": 1.05,
            "min_shell_thickness_mm": MIN_PRINT_THICKNESS_MM,
            "printer_limit_mm": PRINTER_LIMIT_MM,
        },
    }]


import qt, slicer, vtk

layoutManager = slicer.app.layoutManager()
layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)

to_log("info", "Slicer 文件桥接已启动")

last_config_mtime = 0
processed_request = None
pending_job = None


def _complete_result(result):
    with open(RESULT_FILE, "w") as f:
        json.dump({"request_id": processed_request, "status": "completed", "output_files": result}, f)
    to_log("info", f"请求 {processed_request} 完成")


def _fail_result(err_msg):
    with open(RESULT_FILE, "w") as f:
        json.dump({"request_id": processed_request, "status": "error", "detail": err_msg}, f)


def tick():
    global last_config_mtime, processed_request, pending_job

    if pending_job is not None:
        job = pending_job
        pending_job = None
        try:
            result = job()
            _complete_result(result if isinstance(result, list) else [])
        except Exception as e:
            import traceback
            to_log("error", f"请求 {processed_request} 失败: {e}\n{traceback.format_exc()}")
            _fail_result(str(e))

    update_status()

    try:
        mtime = os.path.getmtime(CONFIG_FILE)
    except OSError:
        mtime = 0

    if mtime > last_config_mtime:
        last_config_mtime = mtime
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
        except:
            return

        req_id = cfg.get("request_id")
        if req_id and req_id != processed_request:
            processed_request = req_id
            action = cfg.get("action", "execute")
            to_log("info", f"收到请求: {req_id} (action={action})")
            if action == "preview":
                pending_job = lambda c=cfg: execute_preview(c["config"])
            elif action == "activate_scissors":
                pending_job = lambda c=cfg: execute_activate_scissors(c["config"])
            elif action == "solidify":
                pending_job = lambda c=cfg: execute_solidify(c["config"])
            elif action == "seal":
                pending_job = lambda c=cfg: execute_seal(c["config"])
            elif action == "finalize_preview":
                pending_job = lambda c=cfg: execute_finalize_preview(c["config"])
            elif action == "create_roi":
                pending_job = lambda c=cfg: execute_create_roi(c["config"])
            elif action == "mold":
                pending_job = lambda c=cfg: execute_mold(c["config"])
            elif action == "export":
                pending_job = lambda c=cfg: execute_export(c["config"])
            elif action == "validate":
                pending_job = lambda c=cfg: execute_validate(c["config"])
            else:
                pending_job = lambda c=cfg: execute_pipeline(c["config"])


timer = qt.QTimer()
timer.timeout.connect(tick)
timer.start(1000)
