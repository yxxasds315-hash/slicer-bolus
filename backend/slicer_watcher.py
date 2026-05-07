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
    """由厚度推导补偿器 segment 名称，全流程统一。"""
    return f"Bolus_{thickness_mm}mm"


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

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorWidget.setSourceVolumeNode(vol)
    editorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)
    editorNode.SetSelectedSegmentID(bolus_id)

    try:
        # Step A: COPY skin → bolus
        effect = _safe_get_effect(editorWidget, "Logical operators")
        effect.setParameter("Operation", "COPY")
        effect.setParameter("ModifierSegmentID", skin_id)
        effect.self().onApply()
        to_log("info", "  COPY skin → bolus")

        # Step B: 向外膨胀
        effect = _safe_get_effect(editorWidget, "Margin")
        effect.setParameter("MarginSizeMm", str(BOLUS_THICKNESS))
        effect.self().onApply()
        to_log("info", f"  Margin +{BOLUS_THICKNESS}mm")

        # Step C: 掏空内部
        if design_method == "hollow":
            effect = _safe_get_effect(editorWidget, "Hollow")
            effect.setParameter("ShellMode", "INSIDE_SURFACE")
            effect.setParameter("ShellThicknessMm", str(BOLUS_THICKNESS))
            effect.self().onApply()
            to_log("info", f"  Hollow INSIDE_SURFACE {BOLUS_THICKNESS}mm")
        else:
            effect = _safe_get_effect(editorWidget, "Logical operators")
            effect.setParameter("Operation", "SUBTRACT")
            effect.setParameter("ModifierSegmentID", skin_id)
            effect.self().onApply()
            to_log("info", "  SUBTRACT skin (掏空)")

        # 后处理
        effect = _safe_get_effect(editorWidget, "Logical operators")
        effect.setParameter("Operation", "INTERSECT")
        effect.setParameter("ModifierSegmentID", cutter_id)
        effect.self().onApply()
        to_log("info", "  INTERSECT cutter (裁切)")

        effect = _safe_get_effect(editorWidget, "Islands")
        effect.setParameter("Operation", "KEEP_LARGEST_ISLAND")
        effect.self().onApply()
        to_log("info", "  Islands 保留最大岛")

        effect = _safe_get_effect(editorWidget, "Smoothing")
        effect.setParameter("SmoothingMethod", "MEDIAN")
        effect.setParameter("KernelSizeMm", "2.0")
        effect.self().onApply()
        to_log("info", "  Smooth MEDIAN 2mm")
    finally:
        editorWidget.setActiveEffectByName("")
        editorWidget.setMRMLScene(None)
        slicer.mrmlScene.RemoveNode(editorNode)

    seg.RemoveSegment(cutter_id)
    seg_node.CreateClosedSurfaceRepresentation()

    polyData = vtk.vtkPolyData()
    seg_node.GetClosedSurfaceRepresentation(bolus_id, polyData)
    pts = polyData.GetNumberOfPoints()
    if pts == 0:
        raise RuntimeError("Bolus 生成失败: 网格顶点为 0, ROI 可能偏离皮肤表面")
    to_log("success", f"Bolus 已生成: {bolus_name} ({pts} 顶点), 请在 Slicer 中检查")

    return [{"node": seg_node.GetID(), "bolus": bolus_name, "vertices": pts}]


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
        norm.AutoOrientNormalsOn()
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
    cyl = vtk.vtkCylinderSource()
    cyl.SetCenter(cx, cy, cz)
    cyl.SetRadius(radius)
    cyl.SetHeight(height)
    cyl.SetResolution(resolution)
    cyl.CappingOn()
    cyl.Update()
    transform = vtk.vtkTransform()
    transform.RotateX(90)
    tf_filter = vtk.vtkTransformPolyDataFilter()
    tf_filter.SetInputData(cyl.GetOutput())
    tf_filter.SetTransform(transform)
    tf_filter.Update()
    return tf_filter.GetOutput()


def _make_box_poly(cx, cy, cz, sx, sy, sz):
    box = vtk.vtkCubeSource()
    box.SetCenter(cx, cy, cz)
    box.SetXLength(sx)
    box.SetYLength(sy)
    box.SetZLength(sz)
    box.Update()
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(box.GetOutput())
    tri.Update()
    return tri.GetOutput()


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
    """阴模：Segment Editor 二元标记图 COPY+SUBTRACT，避免 VTK 布尔重合面问题"""
    to_log("info", "── 阴模生成 ──")
    seg = seg_node.GetSegmentation()

    _apply_margin_to_segment(seg_node, bolus_name, shell_mm, SEG["temp_bolus_expanded"])

    expanded_id = seg.GetSegmentIdBySegmentName(SEG["temp_bolus_expanded"])
    female_name = "Mold_Female"
    female_id = seg.AddEmptySegment(female_name, female_name)
    ref_volume = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")

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
        to_log("info", f"  [复制] → {female_name}")

        eff = _safe_get_effect(ew, "Logical operators")
        eff.setParameter("Operation", "SUBTRACT")
        eff.setParameter("ModifierSegmentID", seg.GetSegmentIdBySegmentName(bolus_name))
        eff.self().onApply()
        to_log("info", f"  [掏空] 减去 bolus → {shell_mm}mm 壳体")
    finally:
        ew.setActiveEffectByName("")
        ew.setMRMLScene(None)
        slicer.mrmlScene.RemoveNode(en)

    female_poly = _get_segment_polydata(seg_node, female_name)
    to_log("info", f"  [阴模] {female_poly.GetNumberOfPoints():,} pts")
    return female_poly


def _make_male_mold(seg_node, bolus_name, skin_name, skin_padding_mm, base_thickness_mm):
    to_log("info", "── 阳模生成 ──")
    bolus_poly = _get_segment_polydata(seg_node, bolus_name)
    skin_poly = _get_segment_polydata(seg_node, skin_name)
    b = bolus_poly.GetBounds()
    pad = skin_padding_mm
    bx = (b[1] - b[0]) + 2 * pad
    by = (b[3] - b[2]) + 2 * pad
    bz = 500.0
    cx = (b[0] + b[1]) / 2
    cy = (b[2] + b[3]) / 2
    cz = b[4] - bz / 2 + 10
    clip_box = _make_box_poly(cx, cy, cz, bx, by, bz)
    skin_region = _poly_boolean(skin_poly, clip_box, "intersection")
    if skin_region.GetNumberOfPoints() == 0:
        to_log("warning", "  skin_region 为空，回退到原始皮肤表面")
        skin_region = skin_poly

    sb = skin_region.GetBounds()
    z_bot = sb[4]
    base = _make_box_poly(cx, cy, z_bot - base_thickness_mm / 2, bx, by, base_thickness_mm)

    # vtkAppendPolyData 拼接，避免 VTK 布尔 UNION 在无交集网格上失败
    append_filter = vtk.vtkAppendPolyData()
    append_filter.AddInputData(skin_region)
    append_filter.AddInputData(base)
    append_filter.Update()
    male = append_filter.GetOutput()
    to_log("info", f"  [阳模] {male.GetNumberOfPoints():,} pts")
    return male


def _add_pins(female_poly, male_poly, pin_radius_mm, pin_height_mm, pin_clearance_mm):
    to_log("info", "── 对准销 ──")
    b = female_poly.GetBounds()
    cx = (b[0] + b[1]) / 2
    cy = (b[2] + b[3]) / 2
    z_pin = (b[4] + b[5]) / 2
    dx = (b[1] - b[0]) * 0.28
    dy = (b[3] - b[2]) * 0.28
    positions = [(cx + dx, cy + dy), (cx - dx, cy + dy), (cx + dx, cy - dy), (cx - dx, cy - dy)]
    r = pin_radius_mm
    h = pin_height_mm
    clr = pin_clearance_mm
    for (px, py) in positions:
        solid = _make_cylinder_poly(px, py, z_pin, r, h)
        hole = _make_cylinder_poly(px, py, z_pin, r + clr, h + 1.0)
        female_poly = _poly_boolean(female_poly, hole, "difference")
        male_poly = _poly_boolean(male_poly, solid, "union")
        to_log("info", f"  [销] ({px:.1f}, {py:.1f}, {z_pin:.1f})")
    return female_poly, male_poly


def _add_sprue_and_vents(female_poly, sprue_radius_mm, vent_radius_mm):
    to_log("info", "── 注料口 & 排气孔 ──")
    b = female_poly.GetBounds()
    cx = (b[0] + b[1]) / 2
    cy = (b[2] + b[3]) / 2
    cz = (b[4] + b[5]) / 2
    h_thru = (b[5] - b[4]) + 4
    sprue = _make_cylinder_poly(cx, cy, cz, sprue_radius_mm, h_thru)
    vent1 = _make_cylinder_poly(cx + 20, cy, cz, vent_radius_mm, h_thru)
    vent2 = _make_cylinder_poly(cx - 20, cy, cz, vent_radius_mm, h_thru)
    result = _poly_boolean(female_poly, sprue, "difference")
    result = _poly_boolean(result, vent1, "difference")
    result = _poly_boolean(result, vent2, "difference")
    to_log("info", f"  [注料口] r={sprue_radius_mm}mm | [排气孔] r={vent_radius_mm}mm ×2")
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
    base_mm = d.get("mold_base_thickness_mm", 2.5)
    skin_pad_mm = d.get("mold_skin_padding_mm", 6.0)
    pin_r = d.get("mold_pin_radius_mm", 2.0)
    pin_h = d.get("mold_pin_height_mm", 8.0)
    pin_clr = d.get("mold_pin_clearance_mm", 0.20)
    sprue_r = d.get("mold_sprue_radius_mm", 3.0)
    vent_r = d.get("mold_vent_radius_mm", 1.0)

    female = _make_female_mold(seg_node, bolus_name, SEG["skin"], shell_mm)
    male = _make_male_mold(seg_node, bolus_name, SEG["skin"], skin_pad_mm, base_mm)
    if d.get("mold_with_pins", True):
        female, male = _add_pins(female, male, pin_r, pin_h, pin_clr)
        to_log("info", f"  对准销: r={pin_r}mm x4")
    else:
        to_log("info", "  跳过对准销")
    if d.get("mold_with_sprue", True):
        female = _add_sprue_and_vents(female, sprue_r, vent_r)
        to_log("info", f"  注料口: r={sprue_r}mm / 排气孔: r={vent_r}mm x2")
    else:
        to_log("info", "  跳过注料口 & 排气孔")

    _add_model_to_scene(female, "Mold_Female_Conformal", color=(0.87, 0.49, 0.33), opacity=0.75)
    _add_model_to_scene(male, "Mold_Male_Base", color=(0.36, 0.55, 0.93), opacity=0.75)

    # 清理临时 segment
    for name in [SEG["temp_bolus_expanded"], "Mold_Female"]:
        tmp_id = seg.GetSegmentIdBySegmentName(name)
        if tmp_id:
            seg.RemoveSegment(tmp_id)

    to_log("success", "模具生成完成 — Mold_Female_Conformal（橙色）+ Mold_Male_Base（蓝色）")

    return [
        {"node": "Mold_Female_Conformal", "type": "female", "vertices": female.GetNumberOfPoints()},
        {"node": "Mold_Male_Base", "type": "male", "vertices": male.GetNumberOfPoints()},
    ]


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
            else:
                pending_job = lambda c=cfg: execute_pipeline(c["config"])


timer = qt.QTimer()
timer.timeout.connect(tick)
timer.start(1000)
