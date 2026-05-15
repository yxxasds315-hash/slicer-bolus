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
- **壳厚下限**：前端 slider 最小值 3mm（EDT 精确生成，无 Margin 量化损失）

### 模具生成（2026-05-15 重构）
- **Bolus_Expanded 改 EDT**：原 Slicer Margin effect 量化误差导致实际壳厚 = 设定值 × 50-80%；改用 `scipy.ndimage.distance_transform_edt` 直接在 numpy 层计算精确壳体 `(0 < dist ≤ shell_mm)`，跳过 Bolus_Expanded 中间段和 Editor Widget，一次写入 Mold_Female labelmap。实际壳厚 ≈ 设定值，无量化损失。
- **顶板开口修复**：原 per-column bolus 极值切割导致曲面 bolus 侧壁被削；改为沿选定轴取 mold 全局最外侧 `⌈shell_mm/spacing⌉` 层体素移除，侧壁保持完整。执行前 log 6 个解剖方向（S/I/A/P/L/R）顶板面积供选择参考。

### 适形度验证（2026-05-12）
- **Dice/体积比移除**：空心薄壁网格（EDT 生成 2-voxel 厚）无法被 `vtkPolyDataToImageStencil`（奇偶失效）或 `vtkSelectEnclosedPoints`（返回整个内腔）可靠体素化；移除 Dice 和体积比，不参与 PASS/FAIL。
- **现行 PASS/FAIL 指标（4 项）**：MHD（内表面贴合距离）、HD95（95% 分位贴合）、最小壳厚（≥3mm）、非流形边（=0）。MHD/HD95 同时承担"模具是否匹配当前 bolus"的检测职责。
- **最小壳厚滤波器修复**：原 `0.6×shell_mm` 相对阈值在壳设定较大时会把真实薄点误判为内表面剔除；改为绝对阈值 1.5mm，真实最小值可正常暴露。
- **fix_hints**：后端验证结果新增 `fix_hints` dict，失败指标的修改建议随 JSON 返回前端，在 ValidatePanel 展示"修改建议"区块。
- **mold∩skin 删除**：bolus 贴皮肤界面必然有重叠，该指标永远误报且信息冗余（MHD/HD95 已验证贴合），已移除。
- **新增指标**：最小壳厚（外表面采样点到 bolus 最小距离，≥3mm 才可打印）；硅胶用量（bolus 体积 × 1.1 g/cm³，仅报告）；模具尺寸（超 256mm 给出警告）。
- **去除测试模式**：删除 `?dev` URL 参数及所有关联逻辑（连接检查绕过、步骤自由跳转、DEV MODE 横幅）。
- **删除长方体测试体模**：移除 `execute_load_box_phantom`、`/api/test/box_phantom` 路由、`test_phantom.py` 及前端两处测试按钮。

### 前端
- 三态连接检测：online / no_watcher / offline
- QuickJump 横幅：检测已完成步骤，一键跳转
- Vite 中间件 pkill + 重启 Slicer
- SVG 矢量图标替换 emoji
- ValidatePanel：Dice/体积比列移除，新增最小壳厚列和修改建议区块；硅胶用量/模具尺寸展示

### 其他
- `_safe_get_effect()` 空指针保护
- `.self().onApply()` API 兼容（非 `.onApply()`）
- `AddEmptySegment` 双参数，`Logical operators COPY` 替代 `CopySegment`
- `slicer_process_running` 字段（pgrep 检测）
- roi_mode `slicer_roi` 后端验证

## 当前待验证

- **EDT 壳体端到端**：重新生成模具后适形度评估是否全 PASS（MHD/HD95/最小壳厚/非流形边）
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

### 模具生成（遗留风险）
- **单片封闭模具无脱模设计**：模具仅一个 sprue 孔，硅胶硬化后取不出 bolus。当前用法假设：① 柔性 TPU 打印后撕开，② 一次性切开。若临床要重复使用，需要加分模面或两瓣式设计。
- **底板与皮肤段重叠**：底板深入 skin 体素空间 shell_mm 深度。浇铸场景无影响（mold 离体使用）；若 mold 直接戴在患者身上治疗，底板会和皮肤冲突。需明确临床流程。
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
