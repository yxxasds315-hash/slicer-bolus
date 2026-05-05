import type { PipelineConfig } from '../types';

export type PreviewStatus = 'idle' | 'running' | 'threshold_done' | 'scissors_active' | 'solidified' | 'done' | 'error';

interface SegmentationPanelProps {
  config: PipelineConfig;
  onChange: (patch: Partial<PipelineConfig>) => void;
  onPreview: () => Promise<void>;
  onScissors: () => Promise<void>;
  onSolidify: () => Promise<void>;
  onFinalize: () => Promise<void>;
  previewStatus: PreviewStatus;
  previewError: string;
}

export function SegmentationPanel({ config, onChange, onPreview, onScissors, onSolidify, onFinalize, previewStatus, previewError }: SegmentationPanelProps) {
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">阈值初筛全身组织，手动剪裁去除床板粘连，实心化填充内部空腔，最后平滑。</p>
      <p className="text-medical-600 text-xs">步骤: 阈值 -300~3000 HU → 检查/剪裁床板 → 实心化 → 保留最大岛 → 平滑</p>

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

      {previewStatus === 'solidified' && (
        <div className="bg-accent-400/10 border border-accent-400/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2"><span className="text-lg">🧱</span><span className="text-sm text-accent-300 font-medium">实心化完成</span></div>
          <p className="text-xs text-medical-400">所有内部空腔（气管/鼻窦/肺）已填充，身体为完整实心体。点击下方完成最终平滑处理。</p>
          <button onClick={onFinalize} className="w-full py-2.5 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors">完成平滑，继续</button>
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
