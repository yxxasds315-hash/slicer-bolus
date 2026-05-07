import type { PipelineConfig, MoldStatus } from '../types';

interface MoldGeneratorProps {
  config: PipelineConfig;
  onChange: (patch: Partial<PipelineConfig>) => void;
  onGenerate: () => Promise<void>;
  moldStatus: MoldStatus;
  moldError: string;
}

export function MoldGenerator({ config, onChange, onGenerate, moldStatus, moldError }: MoldGeneratorProps) {
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">
        基于已生成的补偿器，生成适形薄壳模具（阴模+阳模），可选择是否添加对准销和注料/排气结构。
      </p>

      <div className="bg-medical-900/50 rounded-lg p-4 border border-medical-700 space-y-4">
        <h3 className="text-xs font-medium text-medical-400 uppercase tracking-wider">模具参数</h3>

        <div>
          <div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">壳体壁厚</label><span className="text-sm font-mono text-accent-300">{config.mold_shell_thickness_mm} mm</span></div>
          <input type="range" min={2} max={8} step={0.5} value={config.mold_shell_thickness_mm} onChange={(e) => onChange({ mold_shell_thickness_mm: Number(e.target.value) })} className="slider-medical" />
          <p className="text-xs text-medical-500 mt-0.5">阴模壳体厚度 & 法兰宽度</p>
        </div>

        <div>
          <div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">底板厚度</label><span className="text-sm font-mono text-accent-300">{config.mold_base_thickness_mm} mm</span></div>
          <input type="range" min={1} max={5} step={0.5} value={config.mold_base_thickness_mm} onChange={(e) => onChange({ mold_base_thickness_mm: Number(e.target.value) })} className="slider-medical" />
          <p className="text-xs text-medical-500 mt-0.5">阳模底板厚度</p>
        </div>

        <div>
          <div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">皮肤裁切外扩</label><span className="text-sm font-mono text-accent-300">{config.mold_skin_padding_mm} mm</span></div>
          <input type="range" min={3} max={15} step={0.5} value={config.mold_skin_padding_mm} onChange={(e) => onChange({ mold_skin_padding_mm: Number(e.target.value) })} className="slider-medical" />
          <p className="text-xs text-medical-500 mt-0.5">皮肤区域 XY 外扩量，确保覆盖 bolus 投影</p>
        </div>

        <div className="border-t border-medical-700 pt-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-medium text-medical-400">对准销</h4>
            <button
              onClick={() => onChange({ mold_with_pins: !config.mold_with_pins })}
              className={`relative w-10 h-5 rounded-full transition-colors ${config.mold_with_pins ? 'bg-accent-400' : 'bg-medical-600'}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${config.mold_with_pins ? 'left-5' : 'left-0.5'}`} />
            </button>
          </div>
          {config.mold_with_pins && (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <div className="flex justify-between mb-1"><label className="text-xs text-medical-400">半径</label><span className="text-xs font-mono text-accent-300">{config.mold_pin_radius_mm}</span></div>
                  <input type="range" min={1} max={4} step={0.1} value={config.mold_pin_radius_mm} onChange={(e) => onChange({ mold_pin_radius_mm: Number(e.target.value) })} className="slider-medical" />
                </div>
                <div>
                  <div className="flex justify-between mb-1"><label className="text-xs text-medical-400">高度</label><span className="text-xs font-mono text-accent-300">{config.mold_pin_height_mm}</span></div>
                  <input type="range" min={4} max={15} step={0.5} value={config.mold_pin_height_mm} onChange={(e) => onChange({ mold_pin_height_mm: Number(e.target.value) })} className="slider-medical" />
                </div>
                <div>
                  <div className="flex justify-between mb-1"><label className="text-xs text-medical-400">间隙</label><span className="text-xs font-mono text-accent-300">{config.mold_pin_clearance_mm}</span></div>
                  <input type="range" min={0.05} max={0.5} step={0.05} value={config.mold_pin_clearance_mm} onChange={(e) => onChange({ mold_pin_clearance_mm: Number(e.target.value) })} className="slider-medical" />
                </div>
              </div>
              <p className="text-xs text-medical-500 mt-1">4 个对准销，四角分布，内缩 28%</p>
            </>
          )}
        </div>

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
              <p className="text-xs text-medical-500 mt-1">注料口居中，排气孔左右各 1 个</p>
            </>
          )}
        </div>
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
          <div className="flex items-center gap-2 text-sm text-success font-medium">模具生成完成 — Mold_Female_Conformal（橙色）+ Mold_Male_Base（蓝色）</div>
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
