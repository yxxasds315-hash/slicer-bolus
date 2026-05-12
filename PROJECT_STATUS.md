# Bolus Designer 项目状态

## 概述

放疗个性化补偿器（Bolus）数字化设计平台。React 19 + TypeScript + TailwindCSS 4 前端，Python Flask 后端，通过文件桥接与 3D Slicer 通信。

## 架构

```
前端 (Vite :5173) → Flask 后端 (:8765) → /tmp/bolus_config.json
                                              ↓
                                     Slicer watcher (1s 轮询)
                                              ↓
                                    /tmp/bolus_result.json
                                    /tmp/bolus_status.json
                                    /tmp/bolus_logs.jsonl
```

## 7 步向导

1. **DICOM 加载** — 选择文件夹或使用 Slicer 中已有数据
2. **皮肤分割** — HU 阈值分割 → Scissors 裁切 → 实心化 → 二次封口 → 完成
3. **ROI 选择** — 全皮肤 / Slicer Markups ROI 裁切
4. **补偿器设计** — Hollow 抽壳法 / 偏移与相减法，设定 5mm 厚度
5. **执行** — 生成 Bolus_Nmm 壳体
6. **模具设计** — 阴模 (Mold_Female) + 阳模 (Mold_Male)，销钉/注料口可选
7. **导出 STL** — 勾选场景中 bolus/mold 模型导出为 STL（RAS→LPS 自动转换）

## 核心修复记录

### Bolus 生成
- **孔洞根因**：cutter 边界 = 皮肤 bbox，未为膨胀量预留空间 → 6 面各外扩 2×厚度
- **Hollow OUTSIDE_SURFACE 不生效**：pipeline 缺少 `setSourceVolumeNode(vol)`，Margin/Hollow 需要参考体积
- **CLOSING 大核破坏标记图**：膨胀前做 5mm CLOSING 导致边界偏移 → 移除

### 模具生成
- **VTK 布尔崩溃**：`expanded - bolus = 0 pts`（重合面），`skin ∪ base = 0 pts`（无交集）
- **修复**：阴模用 Segment Editor 标记图 COPY+SUBTRACT；阳模用 vtkAppendPolyData
- **壳厚下限**：CT Z=3mm 间距，最小壳厚 ≥4mm（前端限到 4-10mm）

### 适形度验证（2026-05-12）
- **Dice/体积比误判根因**：`vtkPolyDataToImageStencil` 对空心壳网格用奇偶射线规则，射线穿外壁再穿内壁 = 偶数交叉 = "外部"，导致 `vF` 全空 → `vCavity = vExpanded`（实为 bolus + 壳料体积）→ 体积比 3.14、Dice 0.48
- **修复**：用 EDT 距离场直接定义壳料体素（`dist_outside_B ∈ (0, shell_mm]`），绕开空心网格体素化问题；`vCavity = vB`，体积比/Dice → 1.0
- **mold∩skin 删除**：bolus 贴皮肤界面必然有重叠，该指标永远误报且信息冗余（MHD/HD95 已验证贴合），已移除
- **新增指标**：最小壳厚（外表面采样点到 bolus 最小距离，≥3mm 才可打印）；硅胶用量（bolus 体积 × 1.1 g/cm³，仅报告）；模具尺寸（超 256mm 给出警告）
- **指标说明**：每次验证结束输出各指标含义；不通过时给出具体原因和修复建议
- **去除测试模式**：删除 `?dev` URL 参数及所有关联逻辑（连接检查绕过、步骤自由跳转、DEV MODE 横幅）

### 前端
- 三态连接检测：online / no_watcher / offline
- QuickJump 横幅：检测已完成步骤，一键跳转
- Vite 中间件 pkill + 重启 Slicer
- SVG 矢量图标替换 emoji

### 其他
- `_safe_get_effect()` 空指针保护
- `.self().onApply()` API 兼容（非 `.onApply()`）
- `AddEmptySegment` 双参数，`Logical operators COPY` 替代 `CopySegment`
- `slicer_process_running` 字段（pgrep 检测）
- roi_mode `slicer_roi` 后端验证

## 当前待验证

- **4mm 壳厚模具**：体素连续性（Z 向 1.3 体素，勉强）
- **实际打印**：Bambu Studio 墙层数 ≥5，防硅胶泄漏
- **Hollow 抽壳法 vs 偏移相减法**：实际效果对比

## 启动方式

```bash
# 后端
cd backend && python3 server.py

# 前端
cd frontend && npx vite --host 0.0.0.0

# Slicer
/Applications/Slicer.app/Contents/MacOS/Slicer --python-script backend/slicer_watcher.py
```

或前端点击"启动 3D Slicer"按钮自动拉起。

## 已知缺陷（待处理）

### 功能
- **`hollow` 方法未验证**：代码存在于 `execute_pipeline`，但从未端到端运行过。UI 上可选，实际效果不明。需在 Slicer 中手动验证后更新 README。

### 模具生成（2026-05-12 深审遗留风险）
- **Margin 体素化精度损失**：Slicer Margin 效果按体素膨胀，4mm shell 在 3mm CT 体素上只膨胀 1 体素 ≈ 3mm，实际壳厚比设定值少 ~25%。需在 Slicer 中实测后决定是否补偿（如设 5mm 输入换 4mm 实际厚度）。
- **单片封闭模具无脱模设计**：模具仅一个 sprue 孔，硅胶硬化后取不出 bolus。当前用法假设：① 柔性 TPU 打印后撕开，② 一次性切开。若临床要重复使用，需要加分模面或两瓣式设计。
- **底板与皮肤段重叠**：`expanded - bolus` 让模具底板深入 skin 体素空间 shell_mm 深度。浇铸场景无影响（mold 离体使用）；若要把 mold 直接戴在患者身上做治疗，底板会和皮肤冲突。需明确临床流程。
- **方向假设 Z 朝上**：sprue 与 vent 默认沿 Z 轴穿透模具中心。头顶 bolus 正确；侧脸/腹部 bolus 方向错误，sprue 不在重力上方，硅胶会从错误位置溢出。需根据 bolus 法线方向自适应或加用户朝向控制。

### 工程质量
- **无自动化测试**：`test_http.py` 无断言，`test_phantom.py` 需手动粘贴到 Slicer Console。无法做回归保护。
- **`test_http.py` 仅打印不断言**：`test_health()` / `test_status()` 缺少 assert，不能用于 CI。

### 架构
- **生产构建后 `/api/launch` 和 `/api/browse-folder` 失效**：这两个端点在 Vite 中间件（`vite.config.ts`）实现，`vite build` 后不可用。目前仅开发模式使用，如需打包分发须迁移到 Flask。
- **macOS 硬绑定**：`/Applications/Slicer.app`、AppleScript 写死，无法在 Windows 工作站运行。

## Git

- 主分支: main
- 远程: github.com:yxxasds315-hash/slicer-bolus.git
- 本地与远程同步（已推送）
