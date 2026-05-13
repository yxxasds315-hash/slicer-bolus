import type { PipelineConfig, MoldStatus } from '../types';

interface MoldGeneratorProps {
  config: PipelineConfig;
  onChange: (patch: Partial<PipelineConfig>) => void;
  onGenerate: () => Promise<void>;
  moldStatus: MoldStatus;
  moldError: string;
  ventWarning?: boolean;
  openTopDirection?: string | null;
}

export function MoldGenerator({ config, onChange, onGenerate, moldStatus, moldError, ventWarning, openTopDirection }: MoldGeneratorProps) {
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">
        基于已生成的补偿器，生成适形薄壳阴模，内腔匹配 bolus 外表面。封闭式带注料口+排气孔；顶开式无需注料口，直接灌胶+脱模。
      </p>

      <div className="bg-medical-900/50 rounded-lg p-4 border border-medical-700 space-y-4">
        <h3 className="text-xs font-medium text-medical-400 uppercase tracking-wider">模具参数</h3>

        <div>
          <div className="text-xs text-medical-400 mb-2">模具类型</div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => onChange({ mold_type: 'closed' })}
              className={`py-2 px-3 rounded-md text-xs transition-colors ${config.mold_type === 'closed' ? 'bg-accent-400 text-medical-900 font-medium' : 'bg-medical-700 text-medical-300 hover:bg-medical-600'}`}
            >
              封闭式（带注料口）
            </button>
            <button
              onClick={() => onChange({ mold_type: 'open_top' })}
              className={`py-2 px-3 rounded-md text-xs transition-colors ${config.mold_type === 'open_top' ? 'bg-accent-400 text-medical-900 font-medium' : 'bg-medical-700 text-medical-300 hover:bg-medical-600'}`}
            >
              顶开式（直接灌胶）
            </button>
          </div>
          <p className="text-xs text-medical-500 mt-1.5">
            {config.mold_type === 'closed'
              ? '硬质打印 + 注料口灌胶，需要 TPU 撕开或切开取出 bolus'
              : '自动检测 bolus 的 outward 方向开口，适配头顶/胸壁/侧脸等任意临床位置。直接倒入硅胶，固化后顺势拔出'}
          </p>
        </div>

        <div className="border-t border-medical-700 pt-4">
          <div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">壳体壁厚</label><span className="text-sm font-mono text-accent-300">{config.mold_shell_thickness_mm} mm</span></div>
          <input type="range" min={4} max={10} step={0.5} value={config.mold_shell_thickness_mm} onChange={(e) => onChange({ mold_shell_thickness_mm: Number(e.target.value) })} className="slider-medical" />
          <p className="text-xs text-medical-500 mt-0.5">最小 4mm（Z 向 ≥ 1 体素）</p>
        </div>

        {config.mold_type === 'closed' && (
          <div className="border-t border-medical-700 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-medium text-medical-400">注料口 & 排气孔</h4>
              <button
                onClick={() => onChange({ mold_with_sprue: !config.mold_with_sprue })}
                className={`relative w-10 h-5 rounded-full transition-colors ${config.mold_with_sprue ? 'bg-accent-400' : 'bg-medical-600'}`}
              >
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${config.mold_with_sprue ? 'left-5' : 'left-0.5'}`} />
              </button>
            </div>
            {config.mold_with_sprue && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="flex justify-between mb-1"><label className="text-xs text-medical-400">注料口半径</label><span className="text-xs font-mono text-accent-300">{config.mold_sprue_radius_mm}</span></div>
                    <input type="range" min={1.5} max={6} step={0.5} value={config.mold_sprue_radius_mm} onChange={(e) => onChange({ mold_sprue_radius_mm: Number(e.target.value) })} className="slider-medical" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1"><label className="text-xs text-medical-400">排气孔半径</label><span className="text-xs font-mono text-accent-300">{config.mold_vent_radius_mm}</span></div>
                    <input type="range" min={0.5} max={2.5} step={0.1} value={config.mold_vent_radius_mm} onChange={(e) => onChange({ mold_vent_radius_mm: Number(e.target.value) })} className="slider-medical" />
                  </div>
                </div>
                <p className="text-xs text-medical-500 mt-1">注料口居中，排气孔沿模具最长轴各 1 个</p>
              </>
            )}
          </div>
        )}
      </div>

      {moldStatus === 'idle' && (
        <button onClick={onGenerate} className="w-full py-3 px-4 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors">
          生成模具
        </button>
      )}

      {moldStatus === 'running' && (
        <div className="flex items-center justify-center gap-3 py-4 bg-accent-400/5 border border-accent-400/20 rounded-lg">
          <div className="animate-spin w-5 h-5 border-2 border-accent-400 border-t-transparent rounded-full" /><span className="text-sm text-accent-300">Slicer 处理中...</span>
        </div>
      )}

      {moldStatus === 'completed' && (
        <div className="bg-success/10 border border-success/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm text-success font-medium">
            模具生成完成 — Mold_Female_Conformal（{config.mold_type === 'open_top' ? '顶开式' : '封闭式'}，橙色）
          </div>
          {config.mold_type === 'open_top' && openTopDirection && (
            <div className="bg-accent-400/10 border border-accent-400/30 rounded-md px-3 py-2 text-xs text-accent-300">
              开口方向自动检测为 <span className="font-mono font-bold">{openTopDirection}</span>。
              灌胶时将该方向朝上放置（曲面底面用沙袋/橡皮泥支撑），慢倒细流，必要时倾斜释放气泡。
            </div>
          )}
          {ventWarning && config.mold_type === 'closed' && (
            <div className="bg-yellow-500/10 border border-yellow-500/40 rounded-md px-3 py-2 text-xs text-yellow-400">
              排气孔未完整生成，灌胶时可能有气泡残留。建议重新生成或关闭排气孔选项后再次生成。
            </div>
          )}
          <button onClick={onGenerate} className="w-full py-2 px-4 bg-medical-600 text-medical-300 rounded-lg text-sm hover:bg-medical-500 transition-colors">🔄 重新生成</button>
        </div>
      )}

      {moldStatus === 'error' && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg px-4 py-3">
          <p className="text-sm text-danger font-medium">模具生成失败</p>
          <p className="text-xs text-danger/70 mt-1">{moldError}</p>
        </div>
      )}
    </div>
  );
}
