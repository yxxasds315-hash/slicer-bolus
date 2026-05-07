# Bolus Designer

放疗个性化补偿器数字化设计平台 — 基于 3D Slicer 的补偿器自动建模工具。

## 项目概述

在放射治疗中，**补偿器（Bolus）** 是覆盖在患者皮肤表面的组织等效材料，用于修正剂量分布。传统补偿器制作依赖手工翻模，精度低、耗时长。

Bolus Designer 从 CT DICOM 数据出发，自动完成皮肤分割、ROI 定位和补偿器 3D 建模，最终导出 STL 文件供 3D 打印或 CNC 加工。

### 核心流程

```
DICOM 加载 → 皮肤分割 → ROI 定位 → 补偿器建模 → STL 导出
            (阈值+平滑)   (Markups)   (偏移相减)   (3D 打印就绪)
```

## 架构

```
┌──────────────────┐     HTTP/SSE     ┌──────────────────┐   文件轮询 (/tmp)   ┌──────────────────┐
│   React 前端      │ ◄──────────────► │   Flask 后端      │ ◄─────────────────► │  3D Slicer 进程   │
│   Vite :5173      │   proxy → :8765  │   Waitress :8765  │  config →  poll    │  slicer_watcher   │
└──────────────────┘                   └──────────────────┘   ← result           └──────────────────┘
```

- **前端**：React 19 + TypeScript 6 + TailwindCSS 4，6 步向导式界面
- **后端**：Flask + Waitress（生产模式），通过临时文件与 Slicer 通信
- **Slicer 桥接**：3D Slicer 内部 Python 脚本，QTimer 每秒轮询配置文件

### 为什么用文件桥接

3D Slicer 作为宿主进程运行 Python 脚本，无法长期监听 socket。文件桥接避免了将 Flask 嵌入 Slicer 的复杂性和依赖冲突。文件全部位于 `/tmp/`，系统重启后自动清理。

## 目录结构

```
slicer-bolus/
├── .gitignore                  # 根级忽略规则
├── README.md
├── launch_slicer.sh            # 一键启动脚本（后端+前端+Slicer）
│
├── backend/
│   ├── .gitignore              # 忽略日志、缓存、备份
│   ├── requirements.txt        # Python 依赖
│   ├── server.py               # Flask API 服务（8 线程，8765 端口）
│   └── slicer_watcher.py       # Slicer 内运行的桥接脚本
│
└── frontend/
    ├── .gitignore
    ├── package.json            # React + Vite + TailwindCSS
    ├── vite.config.ts          # Vite 配置（含自定义中间件）
    ├── tsconfig*.json
    ├── index.html
    └── src/
        ├── main.tsx            # 入口
        ├── App.tsx             # 状态中枢 + 6 步向导
        ├── index.css           # Tailwind + 医疗主题样式
        ├── types/index.ts      # TypeScript 类型定义
        ├── hooks/
        │   ├── useSSELog.ts    # SSE 日志流 hook
        │   └── useBrowseFolder.ts
        └── components/
            ├── WizardLayout.tsx      # 步骤导航 + Slicer 状态栏
            ├── DicomSelector.tsx     # 第 1 步：DICOM 目录选择
            ├── SegmentationPanel.tsx # 第 2 步：皮肤分割（阈值/剪裁/实心化/封口/平滑）
            ├── RoiSelector.tsx       # 第 3 步：ROI 盒子定位
            ├── BolusDesigner.tsx     # 第 4 步：补偿器设计参数
            ├── ExportSettings.tsx    # 第 5 步：导出设置
            ├── ExecutionPanel.tsx    # 第 6 步：执行 + 日志
            └── SlicerMonitor.tsx     # 可折叠底部状态监视窗
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | React 19 + TypeScript 6 |
| 样式 | TailwindCSS 4（医疗深色主题） |
| 构建 | Vite 8（含自定义中间件处理 `/api/launch`、`/api/browse-folder`） |
| 后端 | Flask + Waitress（`BOLUS_PROD=1` 切换生产模式） |
| 医学影像 | 3D Slicer Python API（DICOMLib, SegmentEditor, VTK） |
| 进程通信 | REST API + 临时文件桥接 + SSE 日志流 |
| 平台 | macOS（AppleScript 文件选择器，Slicer.app 路径） |

## 环境要求

- **macOS**（当前仅支持 macOS）
- **Python 3.10+**：`pip install flask waitress`
- **Node.js 20+**：`npm install`
- **3D Slicer 5.6+**：安装于 `/Applications/Slicer.app`

## 快速启动

### 一键启动

```bash
./launch_slicer.sh
```

此脚本依次启动 Flask 后端（8765）、Vite 开发服务器（5173）和 3D Slicer。浏览器自动打开 `http://localhost:5173`。

### 分步启动

```bash
# 1. 后端
cd backend && python server.py

# 2. 前端（新终端）
cd frontend && npm run dev

# 3. Slicer（新终端）
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
| 2. 皮肤分割 | 阈值初筛 → 手动剪裁床板 → 实心化填充 → 二次封口(可选) → 平滑 | Threshold(-300~3000HU) → Scissors → Morphological Closing + Invert → Islands + Smooth |
| 3. ROI 选择 | 在 Slicer 中放置 Markups ROI 盒子 | 自动创建 200mm 立方体 ROI |
| 4. 补偿器设计 | 选择方法 + 设置厚度(1-15mm) | — |
| 5. 导出设置 | 选择输出目录和格式参数 | — |
| 6. 执行 | 确认参数并启动 | COPY Skin→Margin→Subtract→Intersect Cutter→Islands→Smooth→导出 STL |

### 二次封口

实心化后，鼻孔和外耳道可能残留小孔洞。提供两级形态学闭合：
- **大核**（默认 15mm）：密封纵深管道（外耳道）
- **中核**（默认 8mm）：补充浅层凹陷（鼻孔）

## API 参考

所有 API 通过文件 `/tmp/bolus_config.json` → `/tmp/bolus_result.json` 与 Slicer 异步通信。

| 端点 | 方法 | 说明 | 超时 |
|------|------|------|------|
| `/api/health` | GET | 健康检查 + Slicer 存活（status 文件 mtime < 10s） | — |
| `/api/slicer/status` | GET | Slicer 场景状态（体积、分割、ROI、节点数） | — |
| `/api/preview` | POST | 加载 DICOM + 阈值分割 Skin | 120s |
| `/api/scissors/activate` | POST | 激活 SegmentEditor Scissors 工具 | 120s |
| `/api/solidify` | POST | 实心化：形态学闭合 → 反转填充内部空腔 | 120s |
| `/api/seal` | POST | 二次封口：大核+中核形态学闭合 | 120s |
| `/api/preview/finalize` | POST | 去杂讯（保留最大岛）+ 平滑 | 120s |
| `/api/roi/create` | POST | 创建 200mm Markups ROI | 120s |
| `/api/execute` | POST | 完整补偿器建模流水线 | 300s |
| `/api/logs/stream` | GET | SSE 实时日志流 | — |

## 临时文件

| 文件 | 用途 |
|------|------|
| `/tmp/bolus_config.json` | Flask → Slicer 请求（request_id, action, config） |
| `/tmp/bolus_result.json` | Slicer → Flask 响应（request_id, status, output_files） |
| `/tmp/bolus_status.json` | Slicer → Flask 场景状态（每秒更新） |
| `/tmp/bolus_logs.jsonl` | 日志持久化（JSONL 格式） |

## 设计决策

- **串行化请求**：Flask 端使用 `threading.Lock` 确保一次仅一个请求进入 Slicer。Slicer 端的 `pending_job` 也是单任务模型，与锁机制一致。
- **SSE 而非 WebSocket**：日志流仅需单向推送，SSE 足够且实现简单。
- **Waitress 生产服务器**：在 debug 模式下使用 Flask 内置服务器（支持热重载），生产模式切换 Waitress 8 线程。
- **DICOM 双模式**：支持通过 `dicom_dir` 指定目录加载，也支持使用 Slicer 已打开的数据（`__slicer__` 模式）。

## 局限

- 仅支持 macOS（AppleScript 文件选择、Slicer.app 路径硬编码）
- 无用户认证（本地单用户场景）
- 无数据持久化（所有状态存于 `/tmp/`）
- 补偿器设计仅实现了 offset_subtract 方法，hollow 方法待实现
