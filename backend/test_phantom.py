"""
test_phantom.py  --  独立测试模块
在 Slicer Python Console 中粘贴运行，或作为 --python-script 加载

生成合成椭球体模 + 皮肤分割，覆盖全流程测试：
  DICOM → 分割 → ROI → 补偿器 → 执行 → 模具 → 评估 → 导出
"""
import slicer, vtk, numpy as np
from vtk.util.numpy_support import vtk_to_numpy

# ═══════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════
PHANTOM_RX = 40.0   # 左右半径 mm
PHANTOM_RY = 30.0   # 前后半径 mm
PHANTOM_RZ = 45.0   # 上下半径 mm
SPACING    = 1.0    # 体素 mm
SEG_NODE   = "BolusSegmentation"
SKIN_NAME  = "Skin"

print("=" * 60)
print(f" 测试体模: 椭球 rx={PHANTOM_RX} ry={PHANTOM_RY} rz={PHANTOM_RZ}mm")
print("=" * 60)

# ── 清理旧数据 ─────────────────────────────────
for name in [SEG_NODE, "Phantom"]:
    old = slicer.mrmlScene.GetFirstNodeByName(name)
    if old:
        slicer.mrmlScene.RemoveNode(old)
        print(f"  [清理] 移除 {name}")

# ── Step 1: 构建椭球体模体积 ──────────────────
# 体积 padding 需覆盖全流程最大外轮廓:
#   skin + BOLUS_THICKNESS(Margin) + max(shell_mm, skin_pad_mm) + 安全余量
BOLUS_MM   = 5.0   # bolus 厚度 (Margin 膨胀量)
SHELL_MM   = 4.0   # 阴模壳体壁厚
SKIN_PAD   = 6.0   # 阳模皮肤裁切外扩
SAFETY_MM  = 4.0   # labelmap 光栅化安全余量
PAD_PER_SIDE = int(BOLUS_MM + max(SHELL_MM, SKIN_PAD) + SAFETY_MM)  # = 5+6+4 = 15mm/side
PAD_TOTAL    = PAD_PER_SIDE * 2  # 30 voxels

# padding 每侧 15mm，确保阴模 Margin(+4mm) 和阳模 clip_box(+6mm) 均不触及 volume 边界
dims = [int(2 * r / SPACING) + PAD_TOTAL for r in [PHANTOM_RX, PHANTOM_RY, PHANTOM_RZ]]
print(f"  padding: {PAD_PER_SIDE}mm/side, volume 边界距 skin 最外缘 {PAD_PER_SIDE}mm")

image = vtk.vtkImageData()
image.SetDimensions(dims)
image.SetSpacing(SPACING, SPACING, SPACING)
image.SetOrigin(-(dims[0]*SPACING)/2, -(dims[1]*SPACING)/2, -(dims[2]*SPACING)/2)
image.AllocateScalars(vtk.VTK_SHORT, 1)

arr = vtk_to_numpy(image.GetPointData().GetScalars())
arr.fill(-1000)  # 空气背景

zz, yy, xx = np.mgrid[0:dims[2], 0:dims[1], 0:dims[0]]
cx, cy, cz = dims[0]/2, dims[1]/2, dims[2]/2
inside = ((xx-cx)**2 / (PHANTOM_RX/SPACING)**2
        + (yy-cy)**2 / (PHANTOM_RY/SPACING)**2
        + (zz-cz)**2 / (PHANTOM_RZ/SPACING)**2) <= 1.0
arr[inside.ravel()] = 0  # 软组织 ~0 HU

vol_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
vol_node.SetName("Phantom")
vol_node.SetAndObserveImageData(image)
vol_node.CreateDefaultDisplayNodes()
disp = vol_node.GetDisplayNode()
if disp:
    disp.SetWindowLevel(400, 40)

print(f"  [体积] Phantom: {dims[0]}×{dims[1]}×{dims[2]} @ {SPACING}mm")

# ── Step 2: 皮肤阈值分割 ──────────────────────
seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
seg_node.SetName(SEG_NODE)
seg_node.CreateDefaultDisplayNodes()
seg_node.SetReferenceImageGeometryParameterFromVolumeNode(vol_node)

skin_id = seg_node.GetSegmentation().AddEmptySegment(SKIN_NAME, SKIN_NAME, (0.2, 0.8, 0.3))

editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
editorWidget = slicer.qMRMLSegmentEditorWidget()
editorWidget.setMRMLScene(slicer.mrmlScene)
editorWidget.setMRMLSegmentEditorNode(editorNode)
editorWidget.setSegmentationNode(seg_node)
editorWidget.setSourceVolumeNode(vol_node)
editorNode.SetSelectedSegmentID(skin_id)

# 安全获取效果
def _safe_effect(widget, name):
    widget.setActiveEffectByName(name)
    e = widget.activeEffect()
    if not e:
        raise RuntimeError(f"'{name}' 效果不可用")
    return e

try:
    eff = _safe_effect(editorWidget, "Threshold")
    eff.setParameter("MinimumThreshold", "-300")
    eff.setParameter("MaximumThreshold", "3000")
    eff.self().onApply()
    print("  [分割] 阈值 HU -300 ~ 3000 → Skin")
finally:
    editorWidget.setActiveEffectByName("")
    editorWidget.setMRMLScene(None)
    slicer.mrmlScene.RemoveNode(editorNode)

seg_node.CreateClosedSurfaceRepresentation()
seg_disp = seg_node.GetDisplayNode()
if seg_disp:
    seg_disp.SetVisibility3D(True)
    seg_disp.SetOpacity3D(0.5)

# 重置相机
lm = slicer.app.layoutManager()
for dv in range(lm.threeDViewCount):
    lm.threeDWidget(dv).threeDView().resetFocalPoint()

print()
print("=" * 60)
print(" 体模就绪 -- 可开始全流程测试")
print()
print("  方式 1: 在 Slicer 中手动执行剩余步骤")
print("    步骤3: 在 ROI 模块创建 Markups ROI")
print("    步骤4-5: 通过 Bolus Designer 前端执行补偿器设计")
print("    步骤6: 模具生成")
print("    步骤7: 适形度评估")
print("    步骤8: 导出 STL")
print()
print("  方式 2: 在前端将 DICOM 目录设为 __slicer__")
print("    跳过步骤1(已加载Phantom), 从步骤2继续")
print("=" * 60)
