# Bolus Designer

放疗个性化补偿器数字化设计平台 — 基于 3D Slicer 的补偿器自动建模工具。

## 项目概述

在放射治疗中，**补偿器（Bolus）** 是覆盖在患者皮肤表面的组织等效材料，用于修正剂量分布。传统补偿器制作依赖手工翻模，精度低、耗时长。

Bolus Designer 从 CT DICOM 数据出发，自动完成皮肤分割、ROI 定位、补偿器 3D 建模和阴模生成，最终导出 STL 文件供 3D 打印。

### 核心流程

```
DICOM 加载 → 皮肤分割 → ROI 定位 → 补偿器建模 → 模具生成 → 适形度评估 → STL 导出
            (阈值+平滑)   (Markups)   (EDT 偏移)   (阴模封闭/顶开)  (MHD/HD95)
```

## 架构

```
┌──────────────────┐     HTTP/SSE     ┌──────────────────┐   文件轮询 (/tmp)   ┌──────────────────┐
│   React 前端      │ ◄──────────────► │   Flask 后端      │ ◄─────────────────► │  3D Slicer 进程   │
│   Vite :5173      │   proxy → :8765  │   Waitress :8765  │  config →  poll    │  slicer_watcher   │
└──────────────────┘                   └──────────────────┘   ← result           └──────────────────┘
```

- **前端**：React 19 + TypeScript 6 + TailwindCSS 4，8 步向导式界面
- **后端**：Flask + Waitress（生产模式），通过临时文件与 Slicer 通信
- **Slicer 桥接**：3D Slicer 内部 Python 脚本，QTimer 每秒轮询配置文件

### 为什么用文件桥接

3D Slicer 作为宿主进程运行 Python 脚本，无法长期监听 socket。文件桥接避免了将 Flask 嵌入 Slicer 的复杂性和依赖冲突。文件全部位于 `/tmp/`，系统重启后自动清理。

## 目录结构

```
slicer-bolus/
├── README.md
├── PROJECT_STATUS.md               # 当前状态、待验证项、已知缺陷
├── 启动 Bolus Designer.command     # 双击一键启动
├── scripts/
│   └── launch_slicer.sh            # 一键启动脚本（后端+前端+Slicer）
├── dist/
│   └── BolusDesigner.app           # macOS 应用图标（调用 launch_slicer.sh）
├── docs/                           # 设计文档与 Slicer API 参考
├── backend/
│   ├── requirements.txt
│   ├── server.py                   # Flask API 服务（8765 端口）
│   ├── slicer_watcher.py           # Slicer 内运行的桥接脚本（核心计算逻辑）
│   └── tests/
│       ├── test_http.py            # HTTP 集成测试
│       └── test_mold_outward.py    # 开口方向单元测试
└── frontend/
    ├── package.json
    ├── vite.config.ts              # Vite 配置（含 /api/launch、/api/browse-folder 中间件）
    └── src/
        ├── App.tsx                 # 状态中枢 + 8 步向导
        ├── types/index.ts          # TypeScript 类型定义
        ├── hooks/
        │   ├── useSSELog.ts        # SSE 日志流
        │   └── useBrowseFolder.ts
        └── components/
            ├── WizardLayout.tsx        # 步骤导航 + Slicer 状态栏
            ├── DicomSelector.tsx       # 第 1 步：DICOM 目录选择
            ├── SegmentationPanel.tsx   # 第 2 步：皮肤分割
            ├── RoiSelector.tsx         # 第 3 步：ROI 选择
            ├── BolusDesigner.tsx       # 第 4 步：补偿器参数
            ├── ExecutionPanel.tsx      # 第 5 步：执行 + 日志
            ├── MoldGenerator.tsx       # 第 6 步：模具设计
            ├── ValidatePanel.tsx       # 第 7 步：适形度评估
            ├── ExportPanel.tsx         # 第 8 步：STL 导出
            └── SlicerMonitor.tsx       # 底部状态监视窗
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | React 19 + TypeScript 6 |
| 样式 | TailwindCSS 4（医疗深色主题） |
| 构建 | Vite 8（含自定义中间件） |
| 后端 | Flask + Waitress（`BOLUS_PROD=1` 切换生产模式） |
| 补偿器算法 | scipy `distance_transform_edt`（EDT 精确等距壳体） |
| 薄壳重建 | Shape-Based Interpolation（SBI，Raya & Udupa 1990） |
| 医学影像 | 3D Slicer Python API（DICOMLib, SegmentEditor, VTK） |
| 进程通信 | REST API + 临时文件桥接 + SSE 日志流 |
| 平台 | macOS（AppleScript 文件选择器，Slicer.app 路径） |

## 环境要求

- **macOS**（当前仅支持 macOS）
- **Python 3.10+**：`pip install flask waitress scipy`
- **Node.js 20+**：`npm install`（在 `frontend/` 目录下）
- **3D Slicer 5.6+**：安装于 `/Applications/Slicer.app`

## 快速启动

### 图标启动（推荐）

双击 `dist/BolusDesigner.app` 或 `启动 Bolus Designer.command`，自动启动 Flask 后端、Vite 前端和 3D Slicer，并打开浏览器。

### 命令行启动

```bash
bash scripts/launch_slicer.sh
```

### 分步启动

```bash
# 后端
cd backend && python server.py

# 前端（新终端）
cd frontend && npm run dev

# Slicer（新终端）
/Applications/Slicer.app/Contents/MacOS/Slicer \
  --python-script backend/slicer_watcher.py
```

### 生产模式

```bash
BOLUS_PROD=1 python backend/server.py
# Waitress 8 线程，无热重载
```

## 使用流程

| 步骤 | 操作 | Slicer 端处理 |
|------|------|--------------|
| 1. DICOM 加载 | 选择 CT 目录或使用 Slicer 已加载数据 | — |
| 2. 皮肤分割 | 阈值初筛 → 手动剪裁床板 → 实心化 → 二次封口（可选）→ 平滑 | Threshold(-300~3000HU) → Scissors → Morphological Closing+Invert → Islands+Smooth |
| 3. ROI 选择 | 全皮肤 或 在 Slicer 中调整 Markups ROI 盒子 | 自动创建 200×200×200mm ROI，可拖拽调整 |
| 4. 补偿器参数 | 设置厚度（1-15mm，常用 3-5mm） | — |
| 5. 执行 | 确认参数并启动 | EDT 偏移相减 → HU 空气过滤 → ROI 裁切 → 保留最大连通体 |
| 6. 模具设计 | 选择封闭/顶开式，设置壳厚、注料口、底板 | EDT 精确壳体 + SBI 上采样（CT 各向异性时） |
| 7. 适形度评估 | 运行评估 | MHD / HD95 / 最小壳厚 / 非流形边 四项 PASS/FAIL |
| 8. 导出 STL | 选择目标目录，勾选模型导出 | vtkSTLWriter |

### 皮肤分割说明

```
阈值初筛 → [检查是否需要剪裁床板]
              ↓ 需要              ↓ 不需要
           Scissors 剪裁      跳过剪裁
              ↓
           实心化（头/胸）或跳过（四肢/后背）
              ↓
           二次封口（可选）：大核封耳道 + 中核补鼻孔
              ↓
           平滑完成
```

**二次封口参数**（可在完成后调参重做）：
- 大核（默认 10mm）：密封纵深管道（外耳道）
- 中核（默认 5mm）：补充浅层凹陷（鼻孔）

### 模具类型

| 类型 | 说明 | 适用场景 |
|------|------|---------|
| 封闭式 | 带注料口 + 排气孔，TPU 打印后撕开取模 | 需要重复使用的模具 |
| 顶开式 | 指定解剖方向开口，直接灌胶脱模 | 单次使用，操作简便 |

### 适形度评估指标

| 指标 | 含义 | 通过条件 |
|------|------|---------|
| MHD | 模具内腔与 bolus 平均表面距离 | < 0.5×CT体素mm |
| HD95 | 95% 分位表面距离（最差区域） | < 1.0×CT体素mm |
| 最小壳厚 | 模具最薄处（EDT 体素直接测量） | ≥ 壳厚设定值×60% |
| 非流形边 | 封闭壳网格拓扑健康度 | = 0 |

## API 参考

| 端点 | 方法 | 说明 | 超时 |
|------|------|------|------|
| `/api/health` | GET | 健康检查 + Slicer 存活检测 | — |
| `/api/slicer/status` | GET | Slicer 场景状态（体积、分割、ROI、模型） | — |
| `/api/preview` | POST | 加载 DICOM + 阈值分割皮肤 | 120s |
| `/api/scissors/activate` | POST | 激活 SegmentEditor Scissors 工具 | 120s |
| `/api/solidify` | POST | 实心化：形态学闭合 → 反转填充内部空腔 | 120s |
| `/api/seal` | POST | 二次封口：大核+中核形态学闭合 | 120s |
| `/api/preview/finalize` | POST | 去杂讯（保留最大岛）+ 平滑 | 120s |
| `/api/roi/create` | POST | 创建 200mm Markups ROI | 120s |
| `/api/execute` | POST | 补偿器建模（EDT 偏移相减） | 300s |
| `/api/mold/generate` | POST | 模具生成（封闭/顶开，含 SBI） | 300s |
| `/api/validate` | POST | 适形度评估（MHD/HD95/壳厚/非流形边） | 120s |
| `/api/export` | POST | 导出选中模型为 STL | 120s |
| `/api/logs/stream` | GET | SSE 实时日志流 | — |

## 临时文件

| 文件 | 用途 |
|------|------|
| `/tmp/bolus_config.json` | Flask → Slicer 请求（request_id, action, config） |
| `/tmp/bolus_result.json` | Slicer → Flask 响应（request_id, status, output_files） |
| `/tmp/bolus_status.json` | Slicer 场景状态（每秒更新） |
| `/tmp/bolus_logs.jsonl` | 日志持久化（JSONL 格式） |

## 设计决策

- **串行化请求**：Flask 端使用 `threading.Lock` 确保一次仅一个请求进入 Slicer。
- **EDT 精确壳体**：模具壳体通过 `scipy.ndimage.distance_transform_edt` 在 numpy 层直接计算，实际壳厚 ≈ 设定值，无 SegmentEditor Margin 的量化误差。
- **SBI 上采样**：CT Z 方向各向异性（Z/XY > 1.5）且薄壳时，对 bolus/mold 均做 Shape-Based Interpolation 再跑 marching cubes，避免 Z 方向只有 1 voxel 厚的壳体破碎。
- **SSE 而非 WebSocket**：日志流仅需单向推送，SSE 足够且实现简单。
- **DICOM 双模式**：支持指定目录加载，也支持使用 Slicer 已打开的数据（`__slicer__` 模式）。

## 局限

- 仅支持 macOS（AppleScript 文件选择、Slicer.app 路径硬编码）
- 无用户认证（本地单用户场景）
- 无数据持久化（所有状态存于 `/tmp/`）
- 封闭式模具无脱模设计（假设 TPU 材质撕开或一次性使用）
