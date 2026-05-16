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
    # 全流程最大外扩 = bolus 厚度（EDT）+ 阴模壳厚（EDT）
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

    # HU 空气过滤：剔除 Scissors 截面侧裙和床板残留
    # cut edge 旁的"伪 bolus"落在体内组织（HU > -500），真实 bolus 落在空气（HU ≈ -1000）
    ct_arr = slicer.util.arrayFromVolume(vol)
    AIR_HU_MAX = -500
    is_air = ct_arr < AIR_HU_MAX
    n_before_air = int(bolus_arr.sum())
    bolus_arr &= is_air
    n_after_air = int(bolus_arr.sum())
    to_log("info", f"  HU 空气过滤 (HU<{AIR_HU_MAX}): {n_before_air} → {n_after_air} 体素 "
                   f"(剔除 {n_before_air - n_after_air} 个非空气位置)")

    # 应用 ROI cutter 掩膜（bbox 兜底，HU 过滤已是主防线）
    cutter_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, cutter_id, vol).astype(bool)
    seg.RemoveSegment(cutter_id)
    bolus_arr &= cutter_arr
    to_log("info", f"  ROI 裁切后体积: {bolus_arr.sum()} 体素")

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
    if d.get("dicom_dir") == "__slicer__":
        vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
        if not vols: raise RuntimeError("Slicer 中无体积数据")
        vol = vols[0]
    else:
        # 记录加载前已有的 volume ID，加载完成后从"新增"中挑选，避免误选旧病人数据
        existing_ids = {v.GetID() for v in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")}
        with DICOMUtils.TemporaryDICOMDatabase() as db:
            DICOMUtils.importDicom(d["dicom_dir"], db)
            for puid in db.patients():
                DICOMUtils.loadPatientByUID(puid)
        slicer.app.processEvents()
        new_vols = [v for v in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
                    if v.GetID() not in existing_ids]
        if not new_vols:
            raise RuntimeError("DICOM 加载未产生新体积数据，请检查目录与 DICOM 完整性")
        vol = new_vols[0]
        if len(existing_ids) > 0:
            to_log("info", f"  场景已有 {len(existing_ids)} 个体积，使用新加载的 {vol.GetName()}")
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

    try:
        slicer.modules.segmenteditor.widgetRepresentation().self().editor.setActiveEffectByName("")
    except Exception:
        pass

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

    try:
        slicer.modules.segmenteditor.widgetRepresentation().self().editor.setActiveEffectByName("")
    except Exception:
        pass

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

    # 在 try 外初始化：若早期 effect 抛错，finally 不会触发 UnboundLocalError 掩盖原始异常
    air_id = None
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
        if air_id is not None:
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


def _mask_to_polydata(mask, ref_volume, zoom_z=1, crop_offset_zyx=(0, 0, 0)):
    """numpy mask (z, y, x) → polydata in RAS。

    用于绕过 segmentation closed surface representation 的体素分辨率限制：直接在
    高分辨率 numpy 上跑 marching cubes，再用 ref_volume 的 IJK→RAS 矩阵把 mesh
    搬到 RAS 物理坐标。

    zoom_z: Z 方向上采样倍数（mask shape = (orig_z * zoom_z, y, x)）。zoom_z=1 时
    退化为常规体素。SBI 高分辨率时 zoom_z>1，vtkImageData 用 1/zoom_z 的 Z 步长，
    使 polydata 顶点直接落在原 IJK 的小数索引上，再被 IJK→RAS 矩阵转回 RAS。

    crop_offset_zyx: 若 mask 是从 ref_volume 全体素裁切出的子数组，传入裁切起点
    (z_lo, y_lo, x_lo)（低分辨率原 IJK 单位）让 polydata 落在正确 RAS 位置。
    vtk 把它作为 vtkImageData 的 origin（X/Y 对应 i/j，Z 对应 k）。
    """
    import numpy as np
    arr = np.ascontiguousarray(mask.astype(np.uint8))
    z, y, x = arr.shape
    z_off, y_off, x_off = crop_offset_zyx

    img = vtk.vtkImageImport()
    img.SetDataScalarTypeToUnsignedChar()
    img.SetNumberOfScalarComponents(1)
    img.SetWholeExtent(0, x - 1, 0, y - 1, 0, z - 1)
    img.SetDataExtent(0, x - 1, 0, y - 1, 0, z - 1)
    img.CopyImportVoidPointer(arr.tobytes(), arr.nbytes)
    img.SetDataSpacing(1.0, 1.0, 1.0 / zoom_z)
    img.SetDataOrigin(float(x_off), float(y_off), float(z_off))
    img.Update()

    mc = vtk.vtkDiscreteMarchingCubes()
    mc.SetInputConnection(img.GetOutputPort())
    mc.GenerateValues(1, 1, 1)
    mc.ComputeNormalsOff()
    mc.Update()

    ijk_to_ras = vtk.vtkMatrix4x4()
    ref_volume.GetIJKToRASMatrix(ijk_to_ras)
    transform = vtk.vtkTransform()
    transform.SetMatrix(ijk_to_ras)

    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetInputConnection(mc.GetOutputPort())
    tf.SetTransform(transform)
    tf.Update()

    # 平滑去 marching cubes 体素阶梯。passband 越小越激进；对体素直角三角形需要 ≤0.01。
    # BoundarySmoothing=off：保留开顶切口的清洁边界，不被圆化。
    # 评估的最小壳厚走 EDT 体素直接计算（不经过本 polydata），所以这里可放心激进平滑。
    smooth = vtk.vtkWindowedSincPolyDataFilter()
    smooth.SetInputConnection(tf.GetOutputPort())
    smooth.SetNumberOfIterations(60)
    smooth.SetPassBand(0.01)
    smooth.BoundarySmoothingOff()
    smooth.FeatureEdgeSmoothingOff()
    smooth.NonManifoldSmoothingOff()
    smooth.NormalizeCoordinatesOn()
    smooth.Update()
    return smooth.GetOutput()


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


def _anatomical_dir_to_axis_sign(ref_volume, label):
    """Convert anatomical label (S/I/A/P/L/R) to (numpy_axis, sign).

    Numpy labelmap axis order: (K=0, J=1, I=2). Each corresponds to IJK
    columns (2, 1, 0) of the IJK→RAS matrix.
    """
    import vtk
    ras_dirs = {
        'R': (0,  1), 'L': (0, -1),
        'A': (1,  1), 'P': (1, -1),
        'S': (2,  1), 'I': (2, -1),
    }
    ras_component, ras_polarity = ras_dirs[label.upper()]

    mat = vtk.vtkMatrix4x4()
    ref_volume.GetIJKToRASMatrix(mat)

    # numpy_axis → IJK column index
    numpy_to_ijk_col = [2, 1, 0]

    best_axis, best_sign, best_abs = 0, 1, -1.0
    for na in range(3):
        col = numpy_to_ijk_col[na]
        col_vec = [mat.GetElement(r, col) for r in range(3)]
        col_len = sum(v * v for v in col_vec) ** 0.5
        if col_len < 1e-6:
            continue
        component = col_vec[ras_component] / col_len
        if abs(component) > best_abs:
            best_abs = abs(component)
            best_axis = na
            best_sign = 1 if component * ras_polarity > 0 else -1

    return best_axis, best_sign


def _outward_direction_from_nearest_skin(bolus_coords, nearest_skin_coords, spacing_zyx):
    """Return (axis, sign, extents_mm, mean_offsets_mm) from local skin→bolus offsets.

    Axis order follows Slicer numpy labelmaps: z=0, y=1, x=2.
    """
    spacing = [float(v) for v in spacing_zyx]
    mins = [None, None, None]
    maxs = [None, None, None]
    sums = [0.0, 0.0, 0.0]
    count = 0

    for bolus_pt, skin_pt in zip(bolus_coords, nearest_skin_coords):
        count += 1
        for ax in range(3):
            b = float(bolus_pt[ax])
            s = float(skin_pt[ax])
            mins[ax] = b if mins[ax] is None else min(mins[ax], b)
            maxs[ax] = b if maxs[ax] is None else max(maxs[ax], b)
            sums[ax] += (b - s) * spacing[ax]

    if count == 0:
        raise ValueError("bolus_coords is empty")

    extents_mm = [(maxs[ax] - mins[ax] + 1.0) * spacing[ax] for ax in range(3)]
    mean_offsets_mm = [sums[ax] / count for ax in range(3)]
    axis = max(range(3), key=lambda ax: abs(mean_offsets_mm[ax]))
    sign = +1 if mean_offsets_mm[axis] >= 0 else -1
    return axis, sign, extents_mm, mean_offsets_mm


def _detect_bolus_outward_direction(bolus_arr, skin_arr, spacing_zyx):
    """Detect local outward direction for mold opening/base-plate placement."""
    import numpy as np

    bolus_coords = np.argwhere(bolus_arr)   # (N, 3) column order z, y, x
    if bolus_coords.size == 0:
        raise ValueError("bolus labelmap is empty")

    if skin_arr is not None and skin_arr.any():
        from scipy.ndimage import distance_transform_edt

        # For each bolus voxel, find its nearest skin voxel. The mean local
        # skin→bolus vector is a better outward proxy than bbox thickness:
        # thin bolus patches have their smallest bbox axis perpendicular to the
        # largest face, which can put the opening on the mold's largest side.
        _, nearest = distance_transform_edt(
            ~skin_arr, sampling=spacing_zyx, return_indices=True
        )
        bolus_index = tuple(bolus_coords[:, ax] for ax in range(3))
        nearest_skin_coords = np.column_stack([
            nearest[ax][bolus_index] for ax in range(3)
        ])
        axis, sign, extents_mm, mean_offsets_mm = _outward_direction_from_nearest_skin(
            bolus_coords, nearest_skin_coords, spacing_zyx
        )
        return axis, sign, extents_mm, mean_offsets_mm, "nearest-skin"

    extents_mm = np.array([
        (bolus_coords[:, ax].max() - bolus_coords[:, ax].min() + 1) * spacing_zyx[ax]
        for ax in range(3)
    ])
    axis = int(np.argmin(extents_mm))
    return axis, +1, extents_mm.tolist(), [0.0, 0.0, 0.0], "bbox-fallback"


def _strip_top_plate_numpy(mold_arr, bolus_arr, skin_arr, spacing_zyx, ref_volume, shell_mm, opening_dir=None):
    """纯 numpy: 沿 ref_volume 解剖方向移除模具顶板。

    输入 mold/bolus/skin 必须 same shape；spacing_zyx 与之匹配（高分辨率 SBI 时为
    上采样后的 spacing）。ref_volume 仅用于解剖方向→numpy 轴号的转换（IJK→RAS
    direction matrix），不读其 labelmap，所以高分辨率 numpy 数组也能用。

    顶板定义：mold 在该方向上全局最外侧 shell_mm 厚的体素层（按 spacing_zyx 折算
    层数）。移除该层使内腔从选定方向敞开，侧壁不受影响。

    opening_dir: 解剖方向标签 S/I/A/P/L/R（优先），None 时自动检测（bolus 最近 skin 法向）。

    执行前先 log 6 个解剖面的面积（cm²）辅助方向选择。
    返回 (mold_arr_open, dir_label)。mold/bolus 任一为空时返回 (mold_arr, None)。
    """
    import numpy as np

    if not bolus_arr.any():
        to_log("warning", "  ⚠ bolus 数组为空，跳过开顶")
        return mold_arr, None
    if not mold_arr.any():
        to_log("warning", "  ⚠ mold 数组为空，跳过开顶")
        return mold_arr, None

    spacing_zyx = np.asarray(spacing_zyx, dtype=float)
    axis_labels = ["Z", "Y", "X"]
    shape = mold_arr.shape

    # 各轴的面元面积（垂直该轴的两轴间距之积）
    face_voxel_area = [
        spacing_zyx[1] * spacing_zyx[2],  # Z 轴面: dy*dx
        spacing_zyx[0] * spacing_zyx[2],  # Y 轴面: dz*dx
        spacing_zyx[0] * spacing_zyx[1],  # X 轴面: dz*dy
    ]

    # ── 计算并 log 6 个解剖面的面积，帮助用户选方向 ──
    anat_dirs = [("S", "头顶"), ("I", "足底"), ("A", "前方"), ("P", "后方"), ("L", "左"), ("R", "右")]
    to_log("info", f"  [面积预览] 各方向顶板面积（{shell_mm}mm 厚）：")
    for ad, label in anat_dirs:
        ax, sgn = _anatomical_dir_to_axis_sign(ref_volume, ad)
        n_sl = max(1, int(np.ceil(shell_mm / spacing_zyx[ax])))
        idx_g = np.arange(shape[ax]).reshape([shape[ax] if i == ax else 1 for i in range(3)])
        if sgn > 0:
            ext = int(np.where(mold_arr, idx_g, -1).max())
            face = mold_arr & (idx_g >= ext - n_sl + 1)
        else:
            ext = int(np.where(mold_arr, idx_g, shape[ax]).min())
            face = mold_arr & (idx_g <= ext + n_sl - 1)
        area_cm2 = int(face.sum()) * face_voxel_area[ax] / 100.0
        to_log("info", f"    {label}({ad}): {area_cm2:.1f} cm²")

    # ── 确定开口方向 ──
    outward_axis, outward_sign, extents_mm, mean_offsets_mm, method = _detect_bolus_outward_direction(
        bolus_arr, skin_arr, spacing_zyx
    )

    if opening_dir and opening_dir.upper() in ("S", "I", "A", "P", "L", "R"):
        outward_axis, outward_sign = _anatomical_dir_to_axis_sign(ref_volume, opening_dir)
        method = f"anatomical-{opening_dir.upper()}"

    dir_label = f"{'+' if outward_sign > 0 else '-'}{axis_labels[outward_axis]}"
    to_log("info",
           f"  [开顶] 开口方向: {dir_label} ({method})")

    # ── 移除顶板：mold 在该方向上全局最外侧 n_slices 层 ──
    n_slices = max(1, int(np.ceil(shell_mm / spacing_zyx[outward_axis])))
    idx_range = np.arange(shape[outward_axis], dtype=np.int32)
    idx_grid = idx_range.reshape([shape[outward_axis] if i == outward_axis else 1 for i in range(3)])

    if outward_sign > 0:
        mold_extreme = int(np.where(mold_arr, idx_grid, -1).max())
        to_remove = mold_arr & (idx_grid >= mold_extreme - n_slices + 1)
    else:
        mold_extreme = int(np.where(mold_arr, idx_grid, shape[outward_axis]).min())
        to_remove = mold_arr & (idx_grid <= mold_extreme + n_slices - 1)

    mold_open = mold_arr & ~to_remove
    removed = int(to_remove.sum())
    to_log("info", f"  [开顶] 沿 {dir_label} 移除顶板 {removed} 体素（{n_slices} 层 ≈ {shell_mm}mm）")
    return mold_open, dir_label


def _make_female_mold(seg_node, bolus_name, skin_name, shell_mm, open_top=False, opening_dir=None):
    """阴模：bolus 外扩 shell_mm 后掏除 bolus，得到封闭空心壳。

    返回 (closed_poly, final_poly, open_top_direction)：
      - closed_poly：纯封闭壳体（无开口/无 sprue/无底板），供 validate 做精确体素化用
      - final_poly：在 closed_poly 基础上按 open_top 选项再处理（可能是同一对象）
      - open_top_direction：若开顶则返回方向标签，否则 None

    open_top=True 时进一步移除 bolus 上方的顶板，使内腔从 outward 方向敞开，
    便于直接灌胶和脱模（不需 sprue/vent）。

    不减 skin：bolus 底面天然贴 skin 表面，内腔底面即为 skin 随形面；
    外壳底面深入 skin shell_mm（壳壁厚度），是浇铸模具的正常底板厚度。
    """
    to_log("info", f"── 阴模生成（{'顶开式' if open_top else '封闭式'}）──")
    import numpy as np
    from scipy.ndimage import distance_transform_edt, zoom as ndi_zoom
    seg = seg_node.GetSegmentation()

    bolus_id = seg.GetSegmentIdBySegmentName(bolus_name)
    if not bolus_id:
        raise RuntimeError(f"未找到 {bolus_name} 段，无法生成模具")

    ref_volume = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    if ref_volume is None:
        raise RuntimeError("场景中无体积数据，无法计算 EDT 壳体")

    bolus_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, bolus_id, ref_volume).astype(bool)
    sx, sy, sz = ref_volume.GetSpacing()

    if not bolus_arr.any():
        raise RuntimeError(f"{bolus_name} segment 为空，无法生成模具")

    # ── 裁切到 bolus bbox + padding ──
    # 避免对全 CT 体积做 EDT/SBI（瓶颈在体素总数，非 bolus 大小）。
    # padding ≥ shell_mm 保证 EDT 在 shell 范围内看到完整邻域；+2 voxel 缓冲 SBI 插值边界。
    full_shape = bolus_arr.shape
    bolus_idx = np.argwhere(bolus_arr)
    bbox_lo = bolus_idx.min(axis=0)
    bbox_hi = bolus_idx.max(axis=0) + 1
    pad = np.array([
        int(np.ceil(shell_mm / sz)) + 2,
        int(np.ceil(shell_mm / sy)) + 2,
        int(np.ceil(shell_mm / sx)) + 2,
    ])
    crop_lo = np.maximum(bbox_lo - pad, 0)
    crop_hi = np.minimum(bbox_hi + pad, np.array(full_shape))
    crop_shape = tuple(crop_hi - crop_lo)
    saved = (1.0 - float(np.prod(crop_shape)) / float(np.prod(full_shape))) * 100.0
    to_log("info", f"  [裁切] bolus bbox+pad → {crop_shape} 体素 "
                   f"（全体积 {full_shape}，省 {saved:.1f}%）")
    bolus_arr = bolus_arr[crop_lo[0]:crop_hi[0], crop_lo[1]:crop_hi[1], crop_lo[2]:crop_hi[2]]
    crop_offset_zyx = tuple(int(v) for v in crop_lo)

    # ── SBI 上采样判定 ──
    # CT 各向异性（Z 远大于 X/Y）+ 薄壳（< 1.5×Z spacing）时启用 shape-based interpolation。
    # SDF 线性插值 → 高分辨率 bolus mask；这是医学影像分割切片间插值的标准方法
    # (Raya & Udupa 1990 IEEE TMI)。
    z_aniso = sz / max(sx, sy)
    use_sbi = z_aniso > 1.5 and shell_mm < sz * 1.5
    if use_sbi:
        # zoom_z 取两个条件的较大值：
        #   ① ceil(z_aniso) — 把 Z 拉到 ≈ X/Y 分辨率
        #   ② ceil(2×sz / shell_mm) — 保证上采样后 shell 能容纳 ≥ 2 voxel
        # 否则壳在 Z 方向只有 1 voxel 厚，最薄壳厚 = sz_hr 而非 shell_mm，评估失败
        zoom_z = max(int(np.ceil(z_aniso)),
                     int(np.ceil(2.0 * sz / shell_mm)))
        sz_hr = sz / zoom_z
        to_log("info", f"  [SBI] CT 各向异性 Z/XY={z_aniso:.2f}，shell={shell_mm}mm < 1.5×Z spacing"
                       f" → Z 方向上采样 ×{zoom_z}（{sz}mm → {sz_hr:.2f}mm，shell≈{shell_mm/sz_hr:.1f} voxel）")
        sdf_b = (distance_transform_edt(~bolus_arr, sampling=(sz, sy, sx)) -
                 distance_transform_edt(bolus_arr,  sampling=(sz, sy, sx)))
        sdf_b_hr = ndi_zoom(sdf_b, (zoom_z, 1, 1), order=1)
        bolus_hr = sdf_b_hr <= 0
        spacing_hr = (sz_hr, sy, sx)
    else:
        zoom_z = 1
        bolus_hr = bolus_arr
        spacing_hr = (sz, sy, sx)
        if shell_mm < max(sx, sy, sz) * 1.5:
            to_log("warning", f"  ⚠ 壳厚 {shell_mm}mm 小于 1.5×CT 体素 ({max(sx, sy, sz):.2f}mm)，"
                              f"且 CT 各向同性，EDT 量化可能产生壳体不连通")

    # ── 高分辨率 EDT 算壳 ──
    dist = distance_transform_edt(~bolus_hr, sampling=spacing_hr)
    mold_hr = (dist > 0) & (dist <= shell_mm)
    to_log("info", f"  [EDT 壳体] {shell_mm}mm，{int(mold_hr.sum()):,} {'高分辨率' if use_sbi else ''}体素")

    # ── 顶开式：在 numpy 高分辨率上剥顶 ──
    open_top_direction = None
    if open_top:
        skin_id = seg.GetSegmentIdBySegmentName(skin_name) if skin_name else None
        if skin_id:
            skin_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, skin_id, ref_volume).astype(bool)
            # 裁切到 bolus bbox 同一窗口（skin 在 bbox 外的部分对开口方向检测无影响）
            skin_arr = skin_arr[crop_lo[0]:crop_hi[0], crop_lo[1]:crop_hi[1], crop_lo[2]:crop_hi[2]]
            if use_sbi:
                sdf_s = (distance_transform_edt(~skin_arr, sampling=(sz, sy, sx)) -
                         distance_transform_edt(skin_arr,  sampling=(sz, sy, sx)))
                skin_hr = ndi_zoom(sdf_s, (zoom_z, 1, 1), order=1) <= 0
            else:
                skin_hr = skin_arr
        else:
            skin_hr = None
        mold_hr_open, open_top_direction = _strip_top_plate_numpy(
            mold_hr, bolus_hr, skin_hr, spacing_hr, ref_volume, shell_mm, opening_dir=opening_dir
        )
    else:
        mold_hr_open = mold_hr

    # ── 写一份下采样低分辨率 labelmap 到 segmentation（Slicer 显示和兼容用）──
    # 用 max-pool（只要任一高分辨率体素为 1，低分辨率体素就为 1），保持壳体连续性
    female_name = "Mold_Female"
    old_female = seg.GetSegmentIdBySegmentName(female_name)
    if old_female:
        seg.RemoveSegment(old_female)
    female_id = seg.AddEmptySegment(female_name, female_name)
    seg.CreateRepresentation(slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName())

    if use_sbi:
        Z_hr = mold_hr_open.shape[0]
        Z_lr = Z_hr // zoom_z
        mold_lr_crop = mold_hr_open[:Z_lr * zoom_z].reshape(Z_lr, zoom_z, *mold_hr_open.shape[1:]).max(axis=1)
    else:
        mold_lr_crop = mold_hr_open
    # 把裁切结果 paste 进全体素零数组，让 Slicer segment labelmap 几何与 ref_volume 一致
    mold_lr_full = np.zeros(full_shape, dtype=np.uint8)
    mold_lr_full[crop_lo[0]:crop_lo[0] + mold_lr_crop.shape[0],
                 crop_lo[1]:crop_lo[1] + mold_lr_crop.shape[1],
                 crop_lo[2]:crop_lo[2] + mold_lr_crop.shape[2]] = mold_lr_crop.astype(np.uint8)
    slicer.util.updateSegmentBinaryLabelmapFromArray(mold_lr_full, seg_node, female_id, ref_volume)
    to_log("info", f"  [写入] {female_name}（{'SBI 高分辨率 mesh + 下采样' if use_sbi else '原分辨率'} labelmap）")

    # ── 直接从高分辨率 numpy mask 重建 polydata，绕过 segmentation 体素分辨率限制 ──
    def _normalize(p):
        # 显式 ComputePointNormalsOn + AutoOrientNormalsOn：
        # 保证 Slicer 用 Gouraud 平滑着色（per-vertex），不会按三角面 facet 着色（即便几何已平滑也会显得阶梯）。
        n = vtk.vtkPolyDataNormals()
        n.SetInputData(p)
        n.ComputePointNormalsOn()
        n.ComputeCellNormalsOff()
        n.SetFeatureAngle(60.0)
        n.ConsistencyOn()
        n.AutoOrientNormalsOn()
        n.SplittingOff()
        n.Update()
        return n.GetOutput()

    closed_poly = _normalize(_mask_to_polydata(mold_hr,      ref_volume, zoom_z=zoom_z, crop_offset_zyx=crop_offset_zyx))
    final_poly  = closed_poly if not open_top else _normalize(
        _mask_to_polydata(mold_hr_open, ref_volume, zoom_z=zoom_z, crop_offset_zyx=crop_offset_zyx)
    )

    fe0 = vtk.vtkFeatureEdges()
    fe0.SetInputData(closed_poly)
    fe0.BoundaryEdgesOn(); fe0.NonManifoldEdgesOn()
    fe0.FeatureEdgesOff(); fe0.ManifoldEdgesOff()
    fe0.Update()
    n_open_closed = fe0.GetOutput().GetNumberOfCells()
    to_log("info", f"  [封闭壳] {closed_poly.GetNumberOfPoints():,} pts，开放边: {n_open_closed} "
                   f"({'封闭' if n_open_closed == 0 else '⚠ 有缺口（不应发生）'})")

    if open_top:
        fe1 = vtk.vtkFeatureEdges()
        fe1.SetInputData(final_poly)
        fe1.BoundaryEdgesOn(); fe1.NonManifoldEdgesOn()
        fe1.FeatureEdgesOff(); fe1.ManifoldEdgesOff()
        fe1.Update()
        n_open_final = fe1.GetOutput().GetNumberOfCells()
        to_log("info", f"  [开顶版] {final_poly.GetNumberOfPoints():,} pts，开放边: {n_open_final} "
                       f"(顶部敞开方向 {open_top_direction})")

    return closed_poly, final_poly, open_top_direction



def _add_sprue_and_vents(female_poly, sprue_radius_mm, vent_radius_mm, shell_mm, thickness_mm):
    """返回 (polydata, vent_ok)。vent_ok=True 表示两个排气孔均打通；False 表示至少一个缺失。

    几何保证：
      - 圆柱深度 h = shell_mm + thickness_mm/2 + 2：圆柱底落在理论内腔中点
        EDT 生成的壳厚 ≈ 设定值，无量化误差；+2mm 顶部余量保证打穿外表面，
        距底板 ≥ thickness/2 ≥ 2mm，决不贯穿 bolus 内腔底面。
      - sprue 与 vent 统一以顶面点云重心 (top_cx, top_cy) 为参考，避免对不对称 bolus 用
        bounding box 中心导致圆柱不落在顶面上。
      - 落点验证：与最近顶面点距离 > 半径+2mm 则视为落在空洞中（如 U 形 bolus），拒绝处理。
      - vent 偏移上限 = 内腔半跨度 − vent_radius − 1mm，保证整个孔在 bolus 区域内。
    """
    import numpy as np
    from vtk.util.numpy_support import vtk_to_numpy

    to_log("info", "── 注料口 & 排气孔 ──")
    b = female_poly.GetBounds()

    # ── 从顶面点云中选落点 ──
    pts = vtk_to_numpy(female_poly.GetPoints().GetData())
    top_mask = pts[:, 2] > b[5] - (shell_mm + 2.0)
    top_pts = pts[top_mask]
    if len(top_pts) < 10:
        to_log("warning", "  ⚠ 顶面点过少，落点回退到全 mesh 中心")
        top_pts = pts

    top_cx = float(top_pts[:, 0].mean())
    top_cy = float(top_pts[:, 1].mean())
    top_x_span = float(top_pts[:, 0].max() - top_pts[:, 0].min())
    top_y_span = float(top_pts[:, 1].max() - top_pts[:, 1].min())

    # 内腔跨度 ≈ 外顶面跨度 - 2×shell（EDT 在两侧各膨胀 shell_mm）
    inner_x_span = max(top_x_span - 2.0 * shell_mm, 0.0)
    inner_y_span = max(top_y_span - 2.0 * shell_mm, 0.0)
    if inner_x_span >= inner_y_span:
        long_span, vent_dx, vent_dy, axis_name = inner_x_span, 1, 0, "X"
    else:
        long_span, vent_dx, vent_dy, axis_name = inner_y_span, 0, 1, "Y"

    # 圆柱深度：从外顶面上方 2mm 落到理论内腔中点
    # cylinder_bottom = b[5] + 2 - h = z_skin + thickness/2
    # EDT 生成壳厚 = shell_mm（精确），距底板 ≥ thickness/2，绝不贯穿
    h_cyl = shell_mm + thickness_mm / 2.0 + 2.0
    cz = b[5] + 2.0 - h_cyl / 2.0

    # ── sprue 落点验证 ──
    sprue_min_d = float(np.sqrt(
        (top_pts[:, 0] - top_cx) ** 2 + (top_pts[:, 1] - top_cy) ** 2
    ).min())
    if sprue_min_d > sprue_radius_mm + 2.0:
        raise RuntimeError(
            f"注料口落点 ({top_cx:.1f}, {top_cy:.1f}) 距最近顶面点 {sprue_min_d:.1f}mm，"
            "推测 bolus 为 U 形或多分量。请检查皮肤分割与 ROI 设置。"
        )

    sprue = _make_cylinder_poly(top_cx, top_cy, cz, sprue_radius_mm, h_cyl)
    result = _poly_boolean(female_poly, sprue, "difference")
    if result.GetNumberOfPoints() == 0:
        raise RuntimeError("注料口布尔运算失败（结果为空）")

    # ── 排气孔偏移范围 ──
    min_offset = sprue_radius_mm + vent_radius_mm + 1.0      # 与 sprue 不重叠
    max_offset = long_span / 2.0 - vent_radius_mm - 1.0       # 距内腔边 ≥ 1mm
    vent_offset = min(20.0, long_span * 0.35, max_offset)

    if vent_offset < min_offset:
        required = (min_offset + vent_radius_mm + 1.0) * 2.0
        to_log("warning", f"  ⚠ 内腔最长轴 {long_span:.1f}mm 过小（需 ≥{required:.1f}mm），跳过排气孔")
        skip_vents = True
    else:
        skip_vents = False

    vent_ok = not skip_vents
    if not skip_vents:
        v_positions = [
            (top_cx + vent_offset * vent_dx, top_cy + vent_offset * vent_dy, 1),
            (top_cx - vent_offset * vent_dx, top_cy - vent_offset * vent_dy, 2),
        ]
        for vx, vy, idx in v_positions:
            d_min = float(np.sqrt(
                (top_pts[:, 0] - vx) ** 2 + (top_pts[:, 1] - vy) ** 2
            ).min())
            if d_min > vent_radius_mm + 2.0:
                to_log("warning", f"  ⚠ 排气孔 {idx} 落点距顶面 {d_min:.1f}mm，超出 bolus 区域，跳过")
                vent_ok = False
                continue
            vent = _make_cylinder_poly(vx, vy, cz, vent_radius_mm, h_cyl)
            r = _poly_boolean(result, vent, "difference")
            if r.GetNumberOfPoints() == 0:
                to_log("warning", f"  ⚠ 排气孔 {idx} 布尔失败，保留前一步结果")
                vent_ok = False
            else:
                result = r

    to_log("info",
           f"  [注料口] r={sprue_radius_mm}mm h={h_cyl:.1f}mm（圆柱底位于内腔中点）| "
           f"[排气孔] r={vent_radius_mm}mm 沿内腔{axis_name}轴偏移±{vent_offset:.1f}mm")
    return result, vent_ok


def _add_base_plate(female_poly, opening_dir, plate_mm=3.0, border_mm=5.0):
    """在 opening_dir 反方向添加 plate_mm 厚底板（顶开式专用）。

    设计：
      - 方向：opening_dir（如 "+Z" 或 "+Z(S)"）取反，不重新探测
      - 形状：mold bbox + border_mm 外扩（提供站立稳定性的裙边）
      - 厚度：plate_mm（默认 3mm，约 7-8 层 0.4mm 墙）
      - 嵌入：底板深入 mold 内部 2mm，保证切片软件 flood fill 识别为一体
      - 合并：vtkAppendPolyData（避免 vtkBooleanOperationPolyDataFilter 对薄壳易失败的问题；
        STL 是无对象概念的三角形列表，重叠 ≥0 切片软件均识别为一个固体）
    """
    if not opening_dir or len(opening_dir) < 2:
        to_log("warning", "  [底板] 未传入有效 opening_dir，跳过")
        return female_poly

    sign_char = opening_dir[0]
    axis_char = opening_dir[1]
    if sign_char not in ('+', '-') or axis_char not in ('X', 'Y', 'Z'):
        to_log("warning", f"  [底板] opening_dir '{opening_dir}' 格式不识别（期望 +X/-X/+Y/-Y/+Z/-Z 开头），跳过")
        return female_poly

    # opening 在 +Z → 底板在 -Z 端；反之亦然
    plate_sign = -1 if sign_char == '+' else +1
    axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[axis_char]   # vtk bounds 顺序

    overlap_mm = 2.0  # 底板嵌入 mold 的深度，切片软件 flood fill 识别为一体
    b = list(female_poly.GetBounds())  # [xmin, xmax, ymin, ymax, zmin, zmax]
    bound_lo = b[axis_idx * 2]
    bound_hi = b[axis_idx * 2 + 1]
    if plate_sign > 0:
        plate_near = bound_hi - overlap_mm
        plate_far  = bound_hi + plate_mm
    else:
        plate_near = bound_lo - plate_mm
        plate_far  = bound_lo + overlap_mm

    # 裙边：除底板厚度方向外，所有方向外扩 border_mm
    cube_bounds = list(b)
    for i in range(3):
        if i == axis_idx:
            cube_bounds[i*2]     = plate_near
            cube_bounds[i*2 + 1] = plate_far
        else:
            cube_bounds[i*2]     -= border_mm
            cube_bounds[i*2 + 1] += border_mm

    cube = vtk.vtkCubeSource()
    cube.SetBounds(*cube_bounds)
    cube.Update()

    appender = vtk.vtkAppendPolyData()
    appender.AddInputData(female_poly)
    appender.AddInputData(cube.GetOutput())
    appender.Update()

    tri = vtk.vtkTriangleFilter()
    tri.SetInputConnection(appender.GetOutputPort())
    tri.Update()

    norm = vtk.vtkPolyDataNormals()
    norm.SetInputData(tri.GetOutput())
    norm.ConsistencyOn(); norm.AutoOrientNormalsOn(); norm.SplittingOff()
    norm.Update()

    to_log("info", f"  [底板] {plate_mm}mm 厚 + bbox 外扩 {border_mm}mm 裙边，"
                   f"位于 opening_dir {opening_dir} 反方向（plate_sign={'+' if plate_sign>0 else '-'}{axis_char}），"
                   f"嵌入 mold {overlap_mm}mm，vtkAppendPolyData 合并")
    return norm.GetOutput()


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
    mold_type = d.get("mold_type", "closed")   # "closed" | "open_top"
    opening_dir = d.get("opening_dir", None)   # S/I/A/P/L/R 或 None（自动）

    # 清理上一次生成的同名节点（含 Mold_Female_Closed 和 Mold_Female_Conformal），
    # 避免重复生成时累积 _1/_2 后缀导致导出/validate 错乱
    for old in list(slicer.util.getNodesByClass("vtkMRMLModelNode")):
        if old.GetName().startswith("Mold_Female"):
            slicer.mrmlScene.RemoveNode(old)

    try:
        closed, female, open_top_direction = _make_female_mold(
            seg_node, bolus_name, SEG["skin"], shell_mm,
            open_top=(mold_type == "open_top"),
            opening_dir=opening_dir,
        )

        # 纯封闭壳作为 validate 的体素化基准（隐藏，避免干扰用户视图）
        closed_node = _add_model_to_scene(closed, "Mold_Female_Closed", color=(0.5, 0.5, 0.5), opacity=0.0)
        if closed_node and closed_node.GetDisplayNode():
            closed_node.GetDisplayNode().SetVisibility(False)

        if mold_type == "open_top":
            vent_ok = None
            to_log("info", f"  顶开模具：内腔沿 {open_top_direction} 方向敞开，"
                           "直接灌胶+脱模，无需注料口/排气孔")
        elif d.get("mold_with_sprue", True):
            female, vent_ok = _add_sprue_and_vents(female, sprue_r, vent_r, shell_mm, BOLUS_THICKNESS)
            if not vent_ok:
                to_log("warning", "  ⚠ 排气孔未完整生成，灌胶时可能有气泡残留，建议重新生成")
            to_log("info", f"  注料口: r={sprue_r}mm / 排气孔: r={vent_r}mm ×2")
        else:
            vent_ok = None
            to_log("info", "  跳过注料口 & 排气孔")

        if d.get("mold_base_plate", False):
            if mold_type != "open_top" or not open_top_direction:
                to_log("warning", "  [底板] 仅顶开式 + 已确定开口方向时启用，本次跳过")
            else:
                plate_mm = float(d.get("mold_base_plate_mm", 3.0))
                female = _add_base_plate(female, open_top_direction, plate_mm=plate_mm)

        _add_model_to_scene(female, "Mold_Female_Conformal", color=(0.87, 0.49, 0.33), opacity=0.75)

        to_log("success", f"模具生成完成 — Mold_Female_Conformal（{'顶开式' if mold_type == 'open_top' else '封闭式'}，橙色）")

        return [{
            "node": "Mold_Female_Conformal",
            "type": "female",
            "subtype": mold_type,
            "open_top_direction": open_top_direction,
            "vertices": female.GetNumberOfPoints(),
            "vent_ok": vent_ok,
        }]
    finally:
        # 无论成功/失败都清理临时 segment，避免污染下次生成（旧 Bolus_Expanded 被错误复用）
        for name in [SEG["temp_bolus_expanded"], "Mold_Female"]:
            tmp_id = seg.GetSegmentIdBySegmentName(name)
            if tmp_id:
                seg.RemoveSegment(tmp_id)


def execute_validate(config):
    """适形度评估: 比较 bolus 与「阴模内腔」并检查模具几何健康度

    PASS/FAIL 指标:
      M1 MHD      bolus ↔ 阴模内表面双向平均距离，检测模具是否匹配当前 bolus
      M2 HD95     bolus ↔ 阴模内表面双向 95% 分位距离，检测局部贴合最差区域
      M3 最小壳厚 外表面采样点到 bolus 最小距离，≥3mm 保证 3D 打印强度
      M4 非流形边 模具拓扑必须封闭流形（3D 打印前提）
    附加信息 (不影响 PASS/FAIL):
      I1 硅胶用量 bolus 体积 × 1.1 g/cm³
      I2 模具尺寸 X/Y/Z mm，超 256mm 给出警告

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
    ct_max_spacing = max(max(vols[0].GetSpacing()), 0.1)

    # 阈值与放疗 bolus 临床精度（±1-2mm 建造深度）对齐：
    # SBI 后两侧 mesh 是亚体素精度，老的 4mm/8mm（按 2× CT 体素）阈值过于宽松。
    mhd_thr  = max(0.5, ct_max_spacing * 0.5)
    hd95_thr = max(1.0, ct_max_spacing * 1.0)

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
    # Mold_Female_Closed：制造改造前的纯封闭壳，用于精确体素化和真"几何健康"判定
    closed_node = slicer.mrmlScene.GetFirstNodeByName("Mold_Female_Closed")
    closed_poly = closed_node.GetPolyData() if closed_node else None
    has_closed = bool(closed_poly and closed_poly.GetNumberOfPoints() > 0)

    # ── 几何健康检查 ──
    to_log("info", "[2/5] 模具拓扑检查...")
    n_bad_F = _bad_edges(F)
    if has_closed:
        # 用封闭壳判定真"非流形/开放边"：设计中的 sprue/vent/开顶切口会让 Conformal 必然有开放边
        n_bad_closed = _bad_edges(closed_poly)
        if n_bad_closed > 0:
            to_log("warning", f"  ⚠ 封闭壳发现 {n_bad_closed} 条非流形/开放边（应为 0，几何生成异常）")
        else:
            to_log("info", "  ✓ 封闭壳为封闭流形")
        to_log("info", f"  Conformal 开放边: {n_bad_F}（开顶/sprue/vent 的设计开口属正常）")
    else:
        # 旧场景无 Closed 节点：只能拿 Conformal 凑合判，对 open_top/sprue 模具会误报
        n_bad_closed = n_bad_F
        if n_bad_F > 0:
            to_log("warning", f"  ⚠ 模具发现 {n_bad_F} 条非流形/开放边（无 Closed 参照，开顶模具可能误报）")
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

    # ── bolus 体积：直接从 CT-分辨率 labelmap 读取，绕开薄壳网格体素化失败问题 ──
    to_log("info", "[3/5] 计算 bolus 体积...")
    _seg = seg_node.GetSegmentation()
    _bolus_seg_id = _seg.GetSegmentIdBySegmentName(bolus_name)
    _bolus_for_edt = None  # numpy mask，用于直接 EDT 计算最小壳厚（不经过 polydata smooth）
    _spacing_for_edt = None
    if _bolus_seg_id:
        _arr_b = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, _bolus_seg_id, vols[0]).astype(bool)
        _ct_sx, _ct_sy, _ct_sz = vols[0].GetSpacing()
        vol_B = float(_arr_b.sum()) * _ct_sx * _ct_sy * _ct_sz
        to_log("info", f"  bolus 体积（labelmap）: {vol_B:.0f} mm³")

        # ── 裁切 bbox + padding（SBI 和 fallback 都用，避免对全 CT 体积做 EDT）──
        if _arr_b.any():
            _bolus_idx = np.argwhere(_arr_b)
            _bbox_lo = _bolus_idx.min(axis=0)
            _bbox_hi = _bolus_idx.max(axis=0) + 1
            _pad = np.array([
                int(np.ceil(shell_mm / _ct_sz)) + 2,
                int(np.ceil(shell_mm / _ct_sy)) + 2,
                int(np.ceil(shell_mm / _ct_sx)) + 2,
            ])
            _crop_lo = np.maximum(_bbox_lo - _pad, 0)
            _crop_hi = np.minimum(_bbox_hi + _pad, np.array(_arr_b.shape))
            _arr_b_crop = _arr_b[_crop_lo[0]:_crop_hi[0], _crop_lo[1]:_crop_hi[1], _crop_lo[2]:_crop_hi[2]]
            _crop_offset = tuple(int(v) for v in _crop_lo)

            # ── SBI 评估：CT 各向异性 + 薄壳时，对 bolus mesh 也做 SBI 重建 ──
            # 否则 mold 已是高分辨率（_make_female_mold 走 SBI），bolus 仍是体素阶梯，
            # MHD/HD95 会被分辨率不匹配虚高约 Z_spacing/4。
            _z_aniso = _ct_sz / max(_ct_sx, _ct_sy)
            if _z_aniso > 1.5 and shell_mm < _ct_sz * 1.5:
                from scipy.ndimage import zoom as ndi_zoom
                # zoom_z 公式必须与 _make_female_mold 保持一致，否则两侧 mesh 分辨率错位
                _zoom_z = max(int(np.ceil(_z_aniso)),
                              int(np.ceil(2.0 * _ct_sz / shell_mm)))
                to_log("info", f"  [评估 SBI] CT Z/XY={_z_aniso:.2f}，对 bolus 也做 SBI 重建（×{_zoom_z}，裁切 {_arr_b_crop.shape}）以匹配模具 mesh 精度")
                _sdf_b = (distance_transform_edt(~_arr_b_crop, sampling=(_ct_sz, _ct_sy, _ct_sx)) -
                          distance_transform_edt(_arr_b_crop,  sampling=(_ct_sz, _ct_sy, _ct_sx)))
                _bolus_hr = ndi_zoom(_sdf_b, (_zoom_z, 1, 1), order=1) <= 0
                _B_hr = _mask_to_polydata(_bolus_hr, vols[0], zoom_z=_zoom_z, crop_offset_zyx=_crop_offset)
                _n = vtk.vtkPolyDataNormals()
                _n.SetInputData(_B_hr)
                _n.ComputePointNormalsOn(); _n.ComputeCellNormalsOff()
                _n.SetFeatureAngle(60.0)
                _n.ConsistencyOn(); _n.AutoOrientNormalsOn(); _n.SplittingOff()
                _n.Update()
                B = _n.GetOutput()
                to_log("info", f"  [评估 SBI] bolus 高分辨率 mesh: {B.GetNumberOfPoints():,} pts (低分辨率原版 已替换)")
                _bolus_for_edt = _bolus_hr
                _spacing_for_edt = (_ct_sz / _zoom_z, _ct_sy, _ct_sx)
            else:
                _bolus_for_edt = _arr_b_crop
                _spacing_for_edt = (_ct_sz, _ct_sy, _ct_sx)
    else:
        vol_B = 0.0
        to_log("warning", "  ⚠ 未找到 bolus 段，硅胶用量无法计算")

    # ── 自适应密度采样 + 内表面过滤 ──
    to_log("info", "[4/5] 表面采样 (自适应密度)...")
    target_spacing = 1.5
    pB = _sample_poly(B, target_spacing)
    pF_all = _sample_poly(F, target_spacing)

    F_loc = _build_locator(F)
    B_loc = _build_locator(B)
    dF_all = _nearest_dist(pF_all, B_loc)

    # 最小壳厚：直接从 EDT 体素计算，绕开 polydata smooth/marching cubes 的几何收缩。
    # 这是 mold 在 EDT 体素层面的真实最薄壳厚（外侧壳体素到 bolus 表面的最小距离），
    # 而非通过测量平滑后的 mesh — 后者会被 vtkWindowedSinc 拉近 0.1-0.2mm 导致虚弱化。
    if _bolus_for_edt is not None:
        _dist_edt = distance_transform_edt(~_bolus_for_edt, sampling=_spacing_for_edt)
        # 外侧壳体素：在壳范围内（dist ≤ shell_mm）且距 bolus 表面足够远（> 0.6×shell_mm）
        _outer_vox = (_dist_edt > shell_mm * 0.6) & (_dist_edt <= shell_mm)
        min_shell_mm = float(_dist_edt[_outer_vox].min()) if _outer_vox.any() else 0.0
    else:
        min_shell_mm = 0.0
    # 阈值随用户目标壳厚伸缩：允许实际壳厚损失 40%（含 EDT 量化、corner、smooth），
    # 绝不低于 0.8mm（≈2 层 0.4mm 墙的物理打印底线）
    MIN_PRINT_THICKNESS_MM = max(0.8, shell_mm * 0.6)
    shell_thick_ok = min_shell_mm >= MIN_PRINT_THICKNESS_MM

    inner_mask = dF_all < shell_mm * 0.4   # 收紧到 0.4 倍壁厚，避开侧壁
    pF = pF_all[inner_mask]
    dFB = dF_all[inner_mask]
    if len(pF) < 50:
        raise RuntimeError(f"阴模内表面采样点过少 ({len(pF)}/{len(pF_all)})，模具几何可能异常")
    to_log("info", f"  采样: B={len(pB)}, F全表面={len(pF_all)} → 内表面={len(pF)} (间距 {target_spacing:.1f}mm)")

    # ── 计算指标 ──
    to_log("info", "[5/5] 计算 MHD / HD95 / 壳厚...")
    dBF = _nearest_dist(pB, F_loc)
    MHD = max(dBF.mean(), dFB.mean())
    HD95 = max(np.percentile(dBF, 95), np.percentile(dFB, 95))

    silicone_cm3 = round(vol_B / 1000.0, 1)
    silicone_g   = round(silicone_cm3 * 1.1, 1)

    # ── 判定 ──
    # geom_ok 用封闭壳的非流形/开放边数：Conformal 上的 sprue/vent/开顶切口是设计意图，不应判 FAIL
    geom_ok = (n_bad_closed == 0)
    ok = all([
        MHD < mhd_thr,
        HD95 < hd95_thr,
        shell_thick_ok,
        geom_ok,
    ])

    lines = [
        f"{'指标':<14} {'值':>10}    目标",
        "─" * 52,
        f"{'MHD':<14} {MHD:>9.3f}mm   <{mhd_thr:.2f}mm     {'✓' if MHD < mhd_thr else '✗'}",
        f"{'HD95':<14} {HD95:>9.3f}mm   <{hd95_thr:.2f}mm     {'✓' if HD95 < hd95_thr else '✗'}",
        f"{'最小壳厚':<14} {min_shell_mm:>9.2f}mm   ≥{MIN_PRINT_THICKNESS_MM:.2f}mm      {'✓' if shell_thick_ok else '✗ 过薄'}",
        f"{'非流形边':<14} {n_bad_closed:>10d}    =0             {'✓' if geom_ok else '✗'}",
        "─" * 52,
        f"硅胶用量: {silicone_cm3:.1f} cm³ ≈ {silicone_g:.1f} g  |  "
        f"模具: {mold_x:.0f}×{mold_y:.0f}×{mold_z:.0f} mm {'✓' if fits_printer else '⚠ 超出打印机'}",
        f"(CT 体素 {ct_max_spacing:.2f}mm，MHD/HD95 阈值已自适应)",
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
        ("最小壳厚", shell_thick_ok,
         f"模具最薄处壁厚（直接从 EDT 体素测量），需 ≥{MIN_PRINT_THICKNESS_MM:.2f}mm（目标壳厚 {shell_mm}mm 的 60%）。",
         f"当前最薄处 {min_shell_mm:.2f}mm，低于目标壳厚的 60%。\n"
         f"  → CT 体素 {ct_max_spacing:.2f}mm，体素量化在 corner 处理论极限 ≈ {ct_max_spacing:.1f}mm；"
         f"建议将壳厚设定 ≥ {max(ct_max_spacing * 1.5, shell_mm + 0.4):.1f}mm 后重新生成模具。"),
        ("非流形边", geom_ok,
         "封闭壳网格是否为封闭流形（设计中的 sprue/vent/开顶切口已用 Closed 排除）。",
         f"封闭壳发现 {n_bad_closed} 条非流形/开放边，几何生成阶段已出现破坏。\n"
         "  → 重新生成模具；若问题持续，在 Slicer Surface Toolbox 中执行 Clean / Fill Holes。"),
    ]

    _key_map = {
        "MHD": "MHD_mm", "HD95": "HD95_mm",
        "最小壳厚": "min_shell_thickness_mm", "非流形边": "non_manifold_edges",
    }
    fix_hints = {}
    to_log("info", "── 指标说明 ──")
    for name, passed, description, fix in METRIC_HELP:
        to_log("info", f"[{name}] {description}")
        if not passed:
            for fix_line in fix.split("\n"):
                to_log("warning", f"  ✗ {fix_line.strip()}")
            fix_hints[_key_map.get(name, name)] = " ".join(l.strip() for l in fix.split("\n") if l.strip())

    result_status = "PASS" if ok else "FAIL"
    to_log("success" if ok else "error", f"适形度评估: {result_status}")

    return [{
        "status": result_status,
        "MHD_mm": round(MHD, 3),
        "HD95_mm": round(HD95, 3),
        "min_shell_thickness_mm": round(min_shell_mm, 2),
        "non_manifold_edges": int(n_bad_closed),
        "silicone_cm3": silicone_cm3,
        "silicone_g": silicone_g,
        "mold_dims_mm": [round(mold_x, 1), round(mold_y, 1), round(mold_z, 1)],
        "fits_printer": fits_printer,
        "ct_voxel_max_mm": round(ct_max_spacing, 3),
        "thresholds": {
            "MHD_mm": round(mhd_thr, 3),
            "HD95_mm": round(hd95_thr, 3),
            "min_shell_thickness_mm": MIN_PRINT_THICKNESS_MM,
            "printer_limit_mm": PRINTER_LIMIT_MM,
        },
        "fix_hints": fix_hints,
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
        # 仅在 JSON 成功解析后才更新 last_config_mtime；若读到 Flask 未写完的文件
        # （json.JSONDecodeError 或 OSError），保留旧 mtime 让下次 tick 重试，避免丢请求
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        last_config_mtime = mtime

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
