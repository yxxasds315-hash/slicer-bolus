"""
validate.py  —  粘贴进 Slicer Python Console 直接跑
比较 bolus 与「阴模内腔」的适形度，并检查模具几何健康度
阈值随上游 CT 体素分辨率自适应
"""
import slicer, vtk, numpy as np
from vtk.util.numpy_support import vtk_to_numpy
from scipy.ndimage import distance_transform_edt

# ── 改这里 ───────────────────────────────────
SEG_NODE  = "BolusSegmentation"
BOLUS_SEG = "Bolus_5.0mm"
SKIN_SEG  = "Skin"
SHELL_MM  = 4.0
# ─────────────────────────────────────────────

def poly(name):
    return slicer.mrmlScene.GetFirstNodeByName(name).GetPolyData()

def seg_poly(name):
    sn  = slicer.mrmlScene.GetFirstNodeByName(SEG_NODE)
    sid = sn.GetSegmentation().GetSegmentIdBySegmentName(name)
    p   = vtk.vtkPolyData()
    sn.GetClosedSurfaceRepresentation(sid, p)
    if not p.GetNumberOfPoints():
        sn.CreateClosedSurfaceRepresentation()
        sn.GetClosedSurfaceRepresentation(sid, p)
    return p

def sample(p, target_spacing):
    s = vtk.vtkPolyDataPointSampler()
    s.SetInputData(p); s.SetDistance(target_spacing); s.Update()
    return vtk_to_numpy(s.GetOutput().GetPoints().GetData())

def build_locator(p):
    loc = vtk.vtkCellLocator(); loc.SetDataSet(p); loc.BuildLocator()
    return loc

def nearest(pts, tgt_locator):
    c=[0.,0.,0.]; ci=vtk.reference(0); si=vtk.reference(0); d2=vtk.reference(0.)
    d = np.empty(len(pts))
    for i,p in enumerate(pts):
        tgt_locator.FindClosestPoint(p.tolist(),c,ci,si,d2); d[i]=d2**0.5
    return d

def vox3d(p, sp, origin, dims):
    img = vtk.vtkImageData()
    img.SetOrigin(*origin); img.SetSpacing(sp, sp, sp); img.SetDimensions(*dims)
    img.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    stk = vtk.vtkPolyDataToImageStencil(); stk.SetInputData(p)
    stk.SetOutputOrigin(img.GetOrigin()); stk.SetOutputSpacing(img.GetSpacing())
    stk.SetOutputWholeExtent(img.GetExtent()); stk.Update()
    st = vtk.vtkImageStencil(); st.SetInputData(img)
    st.SetStencilData(stk.GetOutput()); st.ReverseStencilOn()
    st.SetBackgroundValue(1); st.Update()
    flat = vtk_to_numpy(st.GetOutput().GetPointData().GetScalars()).astype(bool)
    return flat.reshape((dims[2], dims[1], dims[0]))

def bad_edges(p):
    fe = vtk.vtkFeatureEdges(); fe.SetInputData(p)
    fe.BoundaryEdgesOn(); fe.NonManifoldEdgesOn()
    fe.FeatureEdgesOff(); fe.ManifoldEdgesOff()
    fe.Update()
    return fe.GetOutput().GetNumberOfCells()

# ── 自适应阈值 ────────────────────────────────
vol = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")[0]
ct_min = max(min(vol.GetSpacing()), 0.1)
MHD_THR  = max(0.5, ct_min * 0.7)
HD95_THR = max(1.0, ct_min * 1.5)
OVERLAP_THR_CM3 = 0.5

# ── 加载 ─────────────────────────────────────
B = seg_poly(BOLUS_SEG)
S = seg_poly(SKIN_SEG)
F = poly("Mold_Female_Conformal")

# ── 几何健康检查 ──────────────────────────────
n_bad = bad_edges(F)

# ── 共享体素网格 ──────────────────────────────
sp = 1.0
pad = max(sp*2, SHELL_MM + 2.0)
bB, bF, bS = B.GetBounds(), F.GetBounds(), S.GetBounds()
origin = (min(bB[0], bF[0], bS[0]) - pad,
          min(bB[2], bF[2], bS[2]) - pad,
          min(bB[4], bF[4], bS[4]) - pad)
dims = (int((max(bB[1], bF[1], bS[1]) + pad - origin[0]) / sp) + 1,
        int((max(bB[3], bF[3], bS[3]) + pad - origin[1]) / sp) + 1,
        int((max(bB[5], bF[5], bS[5]) + pad - origin[2]) / sp) + 1)
vB = vox3d(B, sp, origin, dims)
vF = vox3d(F, sp, origin, dims)
vSkin = vox3d(S, sp, origin, dims)

# 反演阴模内腔（& ~vSkin 让公式对穿模/不穿模两种 mold 都鲁棒）
dist_outside_B = distance_transform_edt(~vB, sampling=sp)
vExpanded = dist_outside_B <= SHELL_MM
vCavity = vExpanded & ~vF & ~vSkin

# ── 自适应密度采样 + 内表面过滤 ────────────────
target_spacing = sp * 1.5
pB = sample(B, target_spacing)
pF_all = sample(F, target_spacing)
F_loc = build_locator(F)
B_loc = build_locator(B)
dF_all = nearest(pF_all, B_loc)
inner_mask = dF_all < SHELL_MM * 0.4
pF, dFB = pF_all[inner_mask], dF_all[inner_mask]
assert len(pF) >= 50, f"阴模内表面采样点过少 ({len(pF)}/{len(pF_all)})"

# ── 指标 ─────────────────────────────────────
dBF = nearest(pB, F_loc)
MHD  = max(dBF.mean(), dFB.mean())
HD95 = max(np.percentile(dBF, 95), np.percentile(dFB, 95))

denom = vB.sum() + vCavity.sum()
Dice = 2 * (vB & vCavity).sum() / denom if denom > 0 else 0.0

vox_unit = sp ** 3
vol_B = vB.sum() * vox_unit
vol_cavity = vCavity.sum() * vox_unit
Ratio = vol_cavity / vol_B if vol_B > 0 else 0.0

overlap_voxels = vF & vSkin
overlap_cm3 = overlap_voxels.sum() * vox_unit / 1000.0
centroid_ras = None
if overlap_voxels.any():
    cz, cy, cx = np.argwhere(overlap_voxels).mean(axis=0)
    centroid_ras = (origin[0] + cx*sp, origin[1] + cy*sp, origin[2] + cz*sp)

# ── 输出 ─────────────────────────────────────
print(f"\n{'指标':<14} {'值':>10}    目标")
print("─"*52)
print(f"{'MHD':<14} {MHD:>9.3f}mm   <{MHD_THR:.2f}mm     {'✓' if MHD < MHD_THR else '✗'}")
print(f"{'HD95':<14} {HD95:>9.3f}mm   <{HD95_THR:.2f}mm     {'✓' if HD95 < HD95_THR else '✗'}")
print(f"{'Dice':<14} {Dice:>10.4f}   >0.95          {'✓' if Dice > 0.95 else '✗'}")
print(f"{'体积比':<14} {Ratio:>10.4f}   0.95~1.05      {'✓' if 0.95 < Ratio < 1.05 else '✗'}")
print(f"{'mold∩skin':<14} {overlap_cm3:>9.3f}cm³  <{OVERLAP_THR_CM3:.2f}cm³    {'✓' if overlap_cm3 < OVERLAP_THR_CM3 else '✗ 穿模'}")
print(f"{'非流形边':<14} {n_bad:>10d}    =0             {'✓' if n_bad == 0 else '✗'}")
print("─"*52)
print(f"(CT 体素 {ct_min:.2f}mm，MHD/HD95 阈值已自适应)")
if centroid_ras:
    print(f"穿模质心 RAS≈({centroid_ras[0]:.1f}, {centroid_ras[1]:.1f}, {centroid_ras[2]:.1f}) mm")
ok = all([MHD < MHD_THR, HD95 < HD95_THR, Dice > 0.95,
          0.95 < Ratio < 1.05, overlap_cm3 < OVERLAP_THR_CM3, n_bad == 0])
print(f"{'✓ PASS' if ok else '✗ FAIL'}\n")
