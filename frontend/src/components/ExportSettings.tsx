import { useBrowseFolder } from '../hooks/useBrowseFolder';
import type { PipelineConfig } from '../types';

interface Props { config: PipelineConfig; onChange: (p: Partial<PipelineConfig>) => void; }

export function ExportSettings({ config, onChange }: Props) {
  const { browse, browsing } = useBrowseFolder();
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">设置 STL 导出参数。3D Slicer 自动将 RAS 转为 LPS 坐标系。</p>
      <div><label className="block text-sm text-medical-400 mb-1.5">输出文件夹路径</label><div className="flex gap-2"><input type="text" value={config.output_dir} onChange={(e) => onChange({ output_dir: e.target.value })} placeholder="/Users/xxx/bolus_output/" className="input-medical flex-1" /><button onClick={async () => { const p = await browse(); if (p) onChange({ output_dir: p }); }} disabled={browsing} className="btn-secondary text-sm whitespace-nowrap px-3">{browsing ? '...' : '📂 浏览'}</button></div></div>
      <div><div className="flex justify-between mb-1.5"><label className="text-sm text-medical-400">过采样倍数</label><span className="text-sm font-mono text-accent-300">{config.oversampling}x</span></div><input type="range" min={1} max={4} step={0.5} value={config.oversampling} onChange={(e) => onChange({ oversampling: Number(e.target.value) })} className="slider-medical" /><div className="flex justify-between text-xs text-medical-500 mt-1"><span>1x</span><span>推荐 2-3x</span><span>4x</span></div></div>
      <div className="bg-medical-700/50 rounded-lg p-4 border border-accent-400/20"><h3 className="text-sm font-medium text-accent-300 mb-2">🔄 坐标系说明</h3><ul className="text-xs text-medical-400 space-y-1"><li>• 内部: <span className="text-accent-200">RAS</span> (右-前-上)</li><li>• 导出: 自动转换 <span className="text-accent-200">LPS</span> (左-后-上)</li></ul></div>
    </div>
  );
}
