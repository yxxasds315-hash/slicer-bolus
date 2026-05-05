"""
Slicer 文件桥接 — 支持 Markups ROI 区域剪切 + 平滑 STL 导出
"""
import json, os, time

CONFIG_FILE = "/tmp/bolus_config.json"
RESULT_FILE = "/tmp/bolus_result.json"
STATUS_FILE = "/tmp/bolus_status.json"
LOG_FILE    = "/tmp/bolus_logs.jsonl"


def to_log(level, msg):
    entry = json.dumps({"timestamp": time.strftime("%H:%M:%S"), "level": level, "message": msg})
    try:
        with open(LOG_FILE, "a") as f: f.write(entry + "\n")
    except: pass
    print(f"[{level}] {msg}")


def update_status():
    import slicer
    s = {"volumes": [], "segmentations": [], "rois": [], "nodes_total": 0}
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

    seg_node = slicer.mrmlScene.GetFirstNodeByName("BolusSegmentation")
    if not seg_node or not seg_node.IsA("vtkMRMLSegmentationNode"):
        raise RuntimeError("未找到 BolusSegmentation 节点, 请先在步骤2中执行预览分割")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName("Skin")
    if not skin_id:
        raise RuntimeError("未找到 Skin 段, 请重新运行预览步骤")
    to_log("info", "  校验通过: Skin 段存在")

    # Step 3: 补偿器设计 (COPY→Grow→Subtract→Intersect)
    to_log("info", f"[3/5] 补偿器设计 (thickness={d['thickness_mm']}mm)...")

    BOLUS_THICKNESS = d["thickness_mm"]
    bolus_name = f"Bolus_{BOLUS_THICKNESS}mm"

    old_bolus = seg.GetSegmentIdBySegmentName(bolus_name)
    if old_bolus:
        seg.RemoveSegment(old_bolus)
    bolus_id = seg.AddEmptySegment(bolus_name, bolus_name, [0.2, 0.6, 0.9])

    roi_nodes = slicer.util.getNodesByClass("vtkMRMLMarkupsROINode")
    if not roi_nodes:
        raise RuntimeError("未找到 Markups ROI 节点, 请先在步骤3中放置 ROI 盒子")
    roi = roi_nodes[0]
    to_log("info", f"  使用 ROI: {roi.GetName()}")
    bounds = [0]*6
    roi.GetRASBounds(bounds)

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

    cutter_name = "Cutter_Mask"
    old_cutter = seg.GetSegmentIdBySegmentName(cutter_name)
    if old_cutter:
        seg.RemoveSegment(old_cutter)
    cutter_id = seg_node.AddSegmentFromClosedSurfaceRepresentation(cube.GetOutput(), cutter_name, [1, 0, 0])
    seg.CreateRepresentation(slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName())
    to_log("info", "  Cutter 掩膜已创建并光栅化")

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)
    editorNode.SetSelectedSegmentID(bolus_id)

    editorWidget.setActiveEffectByName("Logical operators")
    editorWidget.activeEffect().setParameter("Operation", "COPY")
    editorWidget.activeEffect().setParameter("ModifierSegmentID", skin_id)
    editorWidget.activeEffect().self().onApply()
    to_log("info", "  COPY skin → bolus")

    editorWidget.setActiveEffectByName("Margin")
    editorWidget.activeEffect().setParameter("MarginSizeMm", str(BOLUS_THICKNESS))
    editorWidget.activeEffect().self().onApply()
    to_log("info", f"  Margin +{BOLUS_THICKNESS}mm")

    editorWidget.setActiveEffectByName("Logical operators")
    editorWidget.activeEffect().setParameter("Operation", "SUBTRACT")
    editorWidget.activeEffect().setParameter("ModifierSegmentID", skin_id)
    editorWidget.activeEffect().self().onApply()
    to_log("info", "  SUBTRACT skin (掏空)")

    editorWidget.setActiveEffectByName("Logical operators")
    editorWidget.activeEffect().setParameter("Operation", "INTERSECT")
    editorWidget.activeEffect().setParameter("ModifierSegmentID", cutter_id)
    editorWidget.activeEffect().self().onApply()
    to_log("info", "  INTERSECT cutter (裁切)")

    editorWidget.setActiveEffectByName("Islands")
    editorWidget.activeEffect().setParameter("Operation", "KEEP_LARGEST_ISLAND")
    editorWidget.activeEffect().self().onApply()
    to_log("info", "  Islands 保留最大岛")

    editorWidget.setActiveEffectByName("Smoothing")
    editorWidget.activeEffect().setParameter("SmoothingMethod", "MEDIAN")
    editorWidget.activeEffect().setParameter("KernelSizeMm", "2.0")
    editorWidget.activeEffect().self().onApply()
    to_log("info", "  Smooth MEDIAN 2mm")

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

    old = slicer.mrmlScene.GetFirstNodeByName("BolusSegmentation")
    if old:
        slicer.mrmlScene.RemoveNode(old)

    seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    seg_node.SetName("BolusSegmentation")
    seg_node.CreateDefaultDisplayNodes()
    seg_node.SetReferenceImageGeometryParameterFromVolumeNode(vol)

    skin_id = seg_node.GetSegmentation().AddEmptySegment("Skin", "Skin", [0.2, 0.8, 0.3])
    seg = seg_node.GetSegmentation()

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorWidget.setSourceVolumeNode(vol)
    editorNode.SetSelectedSegmentID(skin_id)

    editorWidget.setActiveEffectByName("Threshold")
    effect = editorWidget.activeEffect()
    effect.setParameter("MinimumThreshold", "-300")
    effect.setParameter("MaximumThreshold", "3000")
    effect.self().onApply()
    to_log("info", "  阈值分割完成 (HU -300 ~ 3000)")

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
    to_log("success", "[2/2] 阈值初筛完成 — 请检查是否需要剪裁床板")

    return [{"node": seg_node.GetID(), "name": seg_node.GetName(), "skin_segment": skin_id}]


def execute_activate_scissors(config):
    import slicer

    to_log("info", "========== 激活 Scissors 剪裁工具 ==========")

    seg_node = slicer.mrmlScene.GetFirstNodeByName("BolusSegmentation")
    if not seg_node:
        raise RuntimeError("未找到分割节点, 请先运行预览")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName("Skin")
    if not skin_id:
        raise RuntimeError("未找到 Skin 段")

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

    seg_node = slicer.mrmlScene.GetFirstNodeByName("BolusSegmentation")
    if not seg_node:
        raise RuntimeError("未找到分割节点")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName("Skin")
    if not skin_id:
        raise RuntimeError("未找到 Skin 段")

    editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editorWidget = slicer.qMRMLSegmentEditorWidget()
    editorWidget.setMRMLScene(slicer.mrmlScene)
    editorWidget.setMRMLSegmentEditorNode(editorNode)
    editorWidget.setSegmentationNode(seg_node)
    editorNode.SetSelectedSegmentID(skin_id)

    editorWidget.setActiveEffectByName("Islands")
    effect = editorWidget.activeEffect()
    effect.setParameter("Operation", "KEEP_LARGEST_ISLAND")
    effect.self().onApply()
    to_log("info", "  去杂讯完成 (保留最大岛)")

    editorWidget.setActiveEffectByName("Smoothing")
    effect = editorWidget.activeEffect()
    effect.setParameter("SmoothingMethod", d.get("smoothing_method", "MEDIAN"))
    effect.setParameter("KernelSizeMm", str(d.get("smoothing_kernel_mm", 3.0)))
    effect.self().onApply()
    seg_node.CreateClosedSurfaceRepresentation()
    to_log("info", f"  平滑完成")

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

    seg_node = slicer.mrmlScene.GetFirstNodeByName("BolusSegmentation")
    if not seg_node:
        raise RuntimeError("未找到 BolusSegmentation 节点, 请先运行预览")
    seg = seg_node.GetSegmentation()
    skin_id = seg.GetSegmentIdBySegmentName("Skin")
    if not skin_id:
        raise RuntimeError("未找到 Skin 段")

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
        editorWidget.setActiveEffectByName(name)
        eff = editorWidget.activeEffect()
        for k, v in params.items():
            eff.setParameter(k, v)
        eff.self().onApply()

    to_log("info", "[1/4] 形态学闭合 — 密封气道开口...")
    apply_effect("Smoothing", {
        "SmoothingMethod": "MORPHOLOGICAL_CLOSING",
        "KernelSizeMm": "6.0",
    })

    to_log("info", "[2/4] 构建外部空气掩膜...")
    AIR_NAME = "__Temp_Outside_Air__"
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

    editorWidget.setActiveEffectByName("")
    slicer.mrmlScene.RemoveNode(editorNode)
    editorWidget.setMRMLScene(None)
    seg.RemoveSegment(air_id)

    seg_node.CreateClosedSurfaceRepresentation()
    to_log("success", "实心化完成 — 所有内部空腔已填充, 身体为完整实心体")

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


import qt, slicer

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
            elif action == "finalize_preview":
                pending_job = lambda c=cfg: execute_finalize_preview(c["config"])
            elif action == "create_roi":
                pending_job = lambda c=cfg: execute_create_roi(c["config"])
            else:
                pending_job = lambda c=cfg: execute_pipeline(c["config"])


timer = qt.QTimer()
timer.timeout.connect(tick)
timer.start(1000)
