import type { PipelineConfig } from '../types';

export type PreviewStatus = 'idle' | 'running' | 'threshold_done' | 'scissors_active' | 'solidified' | 'sealed' | 'done' | 'error';

interface SegmentationPanelProps {
  config: PipelineConfig;
  onChange: (patch: Partial<PipelineConfig>) => void;
  onPreview: () => Promise<void>;
  onScissors: () => Promise<void>;
  onSolidify: () => Promise<void>;
  onSeal: () => Promise<void>;
  onFinalize: () => Promise<void>;
  previewStatus: PreviewStatus;
  previewError: string;
}

export function SegmentationPanel({ config, onChange, onPreview, onScissors, onSolidify, onSeal, onFinalize, previewStatus, previewError }: SegmentationPanelProps) {
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">
        阈值初筛全身组织，手动剪裁去除床板粘连，实心化填充内部空腔，可选二次封口消除鼻孔/耳道残余空气，最后平滑。
      </p>
      <p className="text-medical-600 text-xs">步骤: 阈值 -300~3000 HU → 检查/剪裁床板 → 实心化 → 二次封口(可选) → 保留最大岛 → 平滑</p>

      {(previewStatus === 'idle' || previewStatus === 'error') && (
        <button onClick={onPreview} className="w-full py-3 px-4 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors">执行分割 (阈值初筛)</button>
      )}

      {previewStatus === 'running' && (
        <div className="flex items-center justify-center gap-3 py-4 bg-accent-400/5 border border-accent-400/20 rounded-lg">
          <div className="animate-spin w-5 h-5 border-2 border-accent-400 border-t-transparent rounded-full" /><span className="text-sm text-accent-300">Slicer 处理中...</span>
        </div>
      )}

      {previewStatus === 'threshold_done' && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2"><span className="text-lg">⚠️</span><span className="text-sm text-warning font-medium">检查是否需要剪切床板</span></div>
          <p className="text-xs text-medical-400">阈值可能包含治疗床/头枕，请在 Slicer 2D 视图检查。</p>
          <div className="flex gap-3">
            <button onClick={onScissors} className="flex-1 py-2 px-4 bg-warning/20 border border-warning/50 text-warning rounded-lg text-sm font-medium hover:bg-warning/30 transition-colors">✂️ 剪裁</button>
            <button onClick={onSolidify} className="flex-1 py-2 px-4 bg-medical-600 text-medical-300 rounded-lg text-sm hover:bg-medical-500 transition-colors">跳过剪裁，直接实心化 →</button>
          </div>
        </div>
      )}

      {previewStatus === 'scissors_active' && (
        <div className="bg-accent-400/10 border border-accent-400/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-accent-400 animate-pulse" /><span className="text-sm text-accent-300 font-medium">Scissors 已激活</span></div>
          <p className="text-xs text-medical-400">请在 Slicer <strong className="text-white">2D 切片视图</strong>中切断身体与床板的粘连，完成后点下方按钮。</p>
          <button onClick={onSolidify} className="w-full py-2.5 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors">完成剪裁，执行实心化</button>
        </div>
      )}

      {/* 实心化完成 → 二次封口（可选）*/}
      {previewStatus === 'solidified' && (
        <div className="bg-accent-400/10 border border-accent-400/30 rounded-lg p-4 space-y-4">
          <div className="flex items-center gap-2"><span className="text-lg">🧱</span><span className="text-sm text-accent-300 font-medium">实心化完成</span></div>
          <p className="text-xs text-medical-400">
            所有内部空腔（气管/鼻窦/肺）已填充。请在 Slicer 3D 视图中检查<strong className="text-warning">鼻孔和外耳道</strong>是否仍有残余空气。
          </p>

          {/* 封口参数 */}
          <div className="bg-medical-900/50 rounded-lg p-3 space-y-3 border border-medical-700">
            <p className="text-xs text-medical-400 font-medium">🔧 二次封口参数（可调）</p>
            <div>
              <div className="flex justify-between mb-1"><label className="text-xs text-medical-400">耳道大核</label><span className="text-xs font-mono text-accent-300">{config.seal_kernel_1_mm} mm</span></div>
              <input type="range" min={8} max={20} step={0.5} value={config.seal_kernel_1_mm} onChange={(e) => onChange({ seal_kernel_1_mm: Number(e.target.value) })} className="slider-medical" />
              <p className="text-xs text-medical-500 mt-0.5">外耳道纵深长，需较大核（默认 15mm）</p>
            </div>
            <div>
              <div className="flex justify-between mb-1"><label className="text-xs text-medical-400">鼻孔中核</label><span className="text-xs font-mono text-accent-300">{config.seal_kernel_2_mm} mm</span></div>
              <input type="range" min={4} max={12} step={0.5} value={config.seal_kernel_2_mm} onChange={(e) => onChange({ seal_kernel_2_mm: Number(e.target.value) })} className="slider-medical" />
              <p className="text-xs text-medical-500 mt-0.5">鼻孔直径 ~8-10mm，避免过大核破坏鼻尖（默认 8mm）</p>
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={onSeal} className="flex-1 py-2.5 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors">👂 执行二次封口</button>
            <button onClick={onFinalize} className="flex-1 py-2 px-4 bg-medical-600 text-medical-300 rounded-lg text-sm hover:bg-medical-500 transition-colors">跳过封口 →</button>
          </div>
        </div>
      )}

      {/* 二次封口完成 */}
      {previewStatus === 'sealed' && (
        <div className="bg-accent-400/10 border border-accent-400/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2"><span className="text-lg">👂</span><span className="text-sm text-accent-300 font-medium">二次封口完成</span></div>
          <p className="text-xs text-medical-400">
            大核 {config.seal_kernel_1_mm}mm 封耳道 + 中核 {config.seal_kernel_2_mm}mm 补鼻孔已完成。请在 Slicer 中检查效果，不满意可调整参数后再次执行。
          </p>
          <div className="flex gap-3">
            <button onClick={onFinalize} className="flex-1 py-2.5 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors">完成平滑，继续</button>
            <button onClick={onSeal} className="flex-1 py-2 px-4 bg-medical-600 text-medical-300 rounded-lg text-sm hover:bg-medical-500 transition-colors">🔄 再次封口</button>
          </div>
        </div>
      )}

      {previewStatus === 'done' && (
        <div className="bg-success/10 border border-success/30 rounded-lg px-4 py-3 text-sm text-success font-medium">分割完成 — 3D 皮肤已显示在 Slicer 中, 请确认后点下一步</div>
      )}

      {previewStatus === 'error' && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg px-4 py-3"><p className="text-sm text-danger font-medium">分割失败</p><p className="text-xs text-danger/70 mt-1">{previewError}</p></div>
      )}

      <div className="border-t border-medical-700" />
      <div>
        <label className="block text-sm text-medical-400 mb-1.5">平滑方法</label>
        <div className="grid grid-cols-2 gap-2">
          {(['MEDIAN', 'GAUSSIAN', 'MORPHOLOGICAL_OPENING', 'JOINT_TAUBIN'] as const).map((m) => (
            <button key={m} onClick={() => onChange({ smoothing_method: m })} className={`text-xs py-2 px-3 rounded-lg border transition-all ${config.smoothing_method === m ? 'border-accent-400 bg-accent-400/10 text-accent-200' : 'border-medical-600 text-medical-400 hover:border-medical-500'}`}>{m === 'MEDIAN' ? '中值平滑' : m === 'GAUSSIAN' ? '高斯平滑' : m === 'MORPHOLOGICAL_OPENING' ? '形态学开运算' : '联合 Taubin'}</button>
          ))}
        </div>
      </div>
      <div>
        <div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">平滑核大小</label><span className="text-sm font-mono text-accent-300">{config.smoothing_kernel_mm} mm</span></div>
        <input type="range" min={1} max={10} step={0.5} value={config.smoothing_kernel_mm} onChange={(e) => onChange({ smoothing_kernel_mm: Number(e.target.value) })} className="slider-medical" />
      </div>
    </div>
  );
}
