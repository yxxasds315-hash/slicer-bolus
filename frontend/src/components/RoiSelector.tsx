import { useState } from 'react';
import type { PipelineConfig, SlicerState } from '../types';

interface Props { config: PipelineConfig; onChange: (p: Partial<PipelineConfig>) => void; slicer?: SlicerState; }

export function RoiSelector({ config, onChange, slicer }: Props) {
  const hasRoi = (slicer?.rois?.length || 0) > 0;
  const [creating, setCreating] = useState(false);
  const createRoi = async () => { setCreating(true); try { await fetch('/api/roi/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); } catch { } setCreating(false); };
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">选择 bolus 生成区域。</p>
      <button onClick={() => onChange({ roi_mode: 'full_skin' })} className={`w-full text-left p-4 rounded-lg border transition-all ${config.roi_mode === 'full_skin' ? 'border-accent-400 bg-accent-400/10' : 'border-medical-600 hover:border-medical-500'}`}><div className="flex items-center gap-2"><span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${config.roi_mode === 'full_skin' ? 'border-accent-400' : 'border-medical-500'}`}>{config.roi_mode === 'full_skin' && <span className="w-2 h-2 rounded-full bg-accent-400" />}</span><span className={`text-sm font-medium ${config.roi_mode === 'full_skin' ? 'text-accent-200' : 'text-medical-300'}`}>全部皮肤</span></div><p className="text-xs text-medical-500 ml-6">在整个皮肤表面生成 bolus</p></button>
      <button onClick={() => onChange({ roi_mode: 'slicer_roi' })} className={`w-full text-left p-4 rounded-lg border transition-all ${config.roi_mode === 'slicer_roi' ? 'border-accent-400 bg-accent-400/10' : 'border-medical-600 hover:border-medical-500'}`}><div className="flex items-center gap-2"><span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${config.roi_mode === 'slicer_roi' ? 'border-accent-400' : 'border-medical-500'}`}>{config.roi_mode === 'slicer_roi' && <span className="w-2 h-2 rounded-full bg-accent-400" />}</span><span className={`text-sm font-medium ${config.roi_mode === 'slicer_roi' ? 'text-accent-200' : 'text-medical-300'}`}>Markups ROI 框选</span>{hasRoi && <span className="text-xs text-success ml-auto">✅ 已检测到</span>}</div><p className="text-xs text-medical-500 ml-6">在 Slicer 中创建 Markups ROI 框选治疗区域</p></button>
      {config.roi_mode === 'slicer_roi' && (<div className="bg-medical-700/50 rounded-lg p-4 border border-accent-400/20"><h3 className="text-sm font-medium text-accent-300 mb-3">📌 ROI 框选</h3>{!hasRoi && <button onClick={createRoi} disabled={creating} className="w-full py-2.5 px-4 bg-accent-400 text-medical-900 rounded-lg text-sm font-medium hover:bg-accent-300 disabled:opacity-50 transition-colors mb-3">{creating ? '创建中...' : '在 Slicer 中创建 ROI 框'}</button>}<p className="text-xs text-medical-400 mb-2">创建 ROI 后在 3D 视图中拖动控制点调整位置和大小。</p>{hasRoi && slicer?.rois && (<div className="flex flex-col gap-1">{slicer.rois.map((r, i) => (<div key={i} className="text-xs text-success">✅ {r.name}: 中心({r.center?.join(', ')}) 范围({r.radius?.join(', ')})mm</div>))}</div>)}{!hasRoi && !creating && <p className="text-xs text-warning">⏳ 点击上方按钮在 Slicer 中创建 ROI...</p>}</div>)}
    </div>
  );
}
