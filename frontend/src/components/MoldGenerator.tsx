import type { PipelineConfig, MoldStatus } from '../types';

interface MoldGeneratorProps {
  config: PipelineConfig;
  onChange: (patch: Partial<PipelineConfig>) => void;
  onGenerate: () => Promise<void>;
  moldStatus: MoldStatus;
  moldError: string;
  ventWarning?: boolean;
  openTopDirection?: string | null;
  moldHasBasePlate?: boolean;
  onRemoveBasePlate?: () => void;
}

export function MoldGenerator({ config, onChange, onGenerate, moldStatus, moldError, ventWarning, openTopDirection, moldHasBasePlate, onRemoveBasePlate }: MoldGeneratorProps) {
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
              : '指定解剖方向开口，直接倒入硅胶，固化后顺势拔出'}
          </p>
        </div>

        {config.mold_type === 'open_top' && (
          <div className="border-t border-medical-700 pt-4">
            <div className="text-xs text-medical-400 mb-2">开口方向</div>
            <div className="grid grid-cols-4 gap-1.5">
              {(['S', 'I', 'A', 'P', 'L', 'R', 'auto'] as const).map((dir) => (
                <button
                  key={dir}
                  onClick={() => onChange({ opening_dir: dir })}
                  className={`py-1.5 rounded text-xs font-mono transition-colors ${config.opening_dir === dir ? 'bg-accent-400 text-medical-900 font-semibold' : 'bg-medical-700 text-medical-300 hover:bg-medical-600'}`}
                >
                  {dir === 'auto' ? '自动' : dir}
                </button>
              ))}
            </div>
            <p className="text-xs text-medical-500 mt-1.5">
              S=头顶 I=足底 A=前 P=后 L=左 R=右 · 自动=几何推断
            </p>
          </div>
        )}

        <div className="border-t border-medical-700 pt-4">
          <div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">壳体壁厚</label><span className="text-sm font-mono text-accent-300">{config.mold_shell_thickness_mm} mm</span></div>
          <input type="range" min={1.2} max={10} step={0.4} value={config.mold_shell_thickness_mm} onChange={(e) => onChange({ mold_shell_thickness_mm: Number(e.target.value) })} className="slider-medical" />
          <p className="text-xs text-medical-500 mt-0.5">0.4mm 喷嘴 · 3 层墙=1.2mm｜4 层=1.6mm｜5 层=2.0mm（越薄越易脱模，但需 CT voxel ≤ 1.0mm 才稳定）</p>
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

        <div className="border-t border-medical-700 pt-4">
          {config.mold_type === 'open_top' ? (
            <>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h4 className="text-xs font-medium text-medical-400">底板（开口反方向，3D 打印站立稳定性）</h4>
                  <p className="text-xs text-medical-500 mt-0.5">嵌入模具 2mm + 外扩 5mm 裙边，与模具一体打印</p>
                </div>
                <button
                  onClick={() => onChange({ mold_base_plate: !config.mold_base_plate })}
                  className={`relative w-10 h-5 rounded-full transition-colors ${config.mold_base_plate ? 'bg-accent-400' : 'bg-medical-600'}`}
                >
                  <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${config.mold_base_plate ? 'left-5' : 'left-0.5'}`} />
                </button>
              </div>
              {config.mold_base_plate && (
                <div className="mt-3">
                  <div className="flex justify-between mb-1.5"><label className="text-xs text-medical-400">底板厚度</label><span className="text-xs font-mono text-accent-300">{config.mold_base_plate_mm} mm</span></div>
                  <input type="range" min={2} max={5} step={1} value={config.mold_base_plate_mm} onChange={(e) => onChange({ mold_base_plate_mm: Number(e.target.value) })} className="slider-medical" />
                  <p className="text-xs text-medical-500 mt-0.5">2mm（5 层墙，轻量）｜3mm（推荐）｜5mm（重型）</p>
                </div>
              )}
            </>
          ) : (
            <div className="bg-medical-900/40 border border-medical-700 rounded-md px-3 py-2.5">
              <p className="text-xs text-medical-500">封闭式暂不支持底板（无明确"底面"方向）。如需底板，请切换为「顶开式」。</p>
            </div>
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
          {moldHasBasePlate && onRemoveBasePlate && (
            <button onClick={onRemoveBasePlate} className="w-full py-2 px-4 bg-medical-700 text-medical-400 rounded-lg text-xs hover:bg-medical-600 transition-colors">撤销底板</button>
          )}
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
