import type { PipelineConfig } from '../types';

interface BolusDesignerProps { config: PipelineConfig; onChange: (patch: Partial<PipelineConfig>) => void; }

export function BolusDesigner({ config, onChange }: BolusDesignerProps) {
  const methods = [
    { id: 'offset_subtract' as const, title: '偏移与相减法', desc: '复制皮肤 → 向外扩张 → 减去原皮肤 → 得到完美贴合的补偿器外壳。', pros: '可精确控制覆盖区域' },
    { id: 'hollow' as const, title: 'Hollow 抽壳法', desc: '直接在皮肤表面向外生成均匀厚度壳体。', pros: '操作简便，一键生成' },
  ];
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">选择合适的补偿器设计方法，设定厚度参数。</p>
      <div><label className="block text-sm text-medical-400 mb-2">设计方法</label><div className="space-y-3">{methods.map((m) => (<button key={m.id} onClick={() => onChange({ design_method: m.id })} className={`w-full text-left p-4 rounded-lg border transition-all ${config.design_method === m.id ? 'border-accent-400 bg-accent-400/10' : 'border-medical-600 hover:border-medical-500'}`}><div className="flex items-center gap-2 mb-1"><span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${config.design_method === m.id ? 'border-accent-400' : 'border-medical-500'}`}>{config.design_method === m.id && <span className="w-2 h-2 rounded-full bg-accent-400" />}</span><span className={`text-sm font-medium ${config.design_method === m.id ? 'text-accent-200' : 'text-medical-300'}`}>{m.title}</span><span className="text-xs text-medical-500 ml-auto">{m.pros}</span></div><p className="text-xs text-medical-500 ml-6">{m.desc}</p></button>))}</div></div>
      <div><div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">补偿器厚度</label><span className="text-sm font-mono text-accent-300">{config.thickness_mm} mm</span></div><input type="range" min={1} max={15} step={0.5} value={config.thickness_mm} onChange={(e) => onChange({ thickness_mm: Number(e.target.value) })} className="slider-medical" /><div className="flex justify-between text-xs text-medical-500 mt-1"><span>1mm</span><span>常用 3-5mm</span><span>15mm</span></div></div>
    </div>
  );
}
