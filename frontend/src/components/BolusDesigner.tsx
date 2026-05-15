import type { PipelineConfig } from '../types';

interface BolusDesignerProps { config: PipelineConfig; onChange: (patch: Partial<PipelineConfig>) => void; }

export function BolusDesigner({ config, onChange }: BolusDesignerProps) {
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">补偿器厚度 = 等效组织建造深度。常规放疗 5mm，可调 1-15mm。</p>
      <div className="bg-medical-900/50 border border-medical-700 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-accent-200">EDT 偏移与相减法</span>
        </div>
        <p className="text-xs text-medical-500">在 skin 表面外侧用 scipy.ndimage.distance_transform_edt 生成精确等距壳体（dist ≤ thickness）→ HU 空气过滤 → ROI 裁切。</p>
      </div>
      <div>
        <div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">补偿器厚度</label><span className="text-sm font-mono text-accent-300">{config.thickness_mm} mm</span></div>
        <input type="range" min={1} max={15} step={0.5} value={config.thickness_mm} onChange={(e) => onChange({ thickness_mm: Number(e.target.value) })} className="slider-medical" />
        <div className="flex justify-between text-xs text-medical-500 mt-1"><span>1mm</span><span>常用 3-5mm</span><span>15mm</span></div>
      </div>
    </div>
  );
}
