import { useState } from 'react';
import type { PipelineConfig, SlicerState } from '../types';
import { useBrowseFolder } from '../hooks/useBrowseFolder';

interface Props {
  config: PipelineConfig;
  onChange: (p: Partial<PipelineConfig>) => void;
  slicer: SlicerState;
}

type ExportStatus = 'idle' | 'running' | 'completed' | 'error';

export function ExportPanel({ config, onChange, slicer }: Props) {
  const { browse, browsing } = useBrowseFolder();
  const [status, setStatus] = useState<ExportStatus>('idle');
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // 从场景状态中收集可导出的模型
  const candidates: { name: string; source: string }[] = [];
  for (const seg of slicer.segmentations) {
    for (const s of seg.segments) {
      if (s === 'Skin' || s.startsWith('__')) continue;
      candidates.push({ name: s, source: `分割 ${seg.name}` });
    }
  }
  for (const m of slicer.models || []) {
    if (m.name.startsWith('Mold_')) {
      candidates.push({ name: m.name, source: `模型 ${m.vertices} 顶点` });
    }
  }

  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name); else next.add(name);
    setSelected(next);
  };

  const handleExport = async () => {
    if (selected.size === 0) return;
    setStatus('running'); setError('');
    try {
      const r = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, export_models: [...selected] }),
      });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '导出失败'); }
      const d = await r.json();
      setStatus('completed');
      setError(`已完成: ${d.output_files?.[0]?.exported?.length || 0} 个文件`);
    } catch (err: any) {
      setStatus('error');
      setError(err.message);
    }
  };

  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">选择要导出的模型，设置输出目录后导出 STL 文件。</p>

      <div>
        <label className="block text-sm text-medical-400 mb-2">可导出项目</label>
        {candidates.length === 0 ? (
          <p className="text-xs text-medical-500">场景中暂无 bolus 或模具模型，请先完成前面的步骤。</p>
        ) : (
          <div className="space-y-2">
            {candidates.map((c) => (
              <label key={c.name} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${selected.has(c.name) ? 'border-accent-400 bg-accent-400/10' : 'border-medical-600 hover:border-medical-500'}`}>
                <input type="checkbox" checked={selected.has(c.name)} onChange={() => toggle(c.name)} className="accent-accent-400" />
                <div>
                  <span className="text-sm text-medical-200">{c.name}.stl</span>
                  <p className="text-xs text-medical-500">{c.source}</p>
                </div>
              </label>
            ))}
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm text-medical-400 mb-1.5">输出文件夹</label>
        <div className="flex gap-2">
          <input type="text" value={config.output_dir} onChange={(e) => onChange({ output_dir: e.target.value })} placeholder="/Users/xxx/bolus_output/" className="input-medical flex-1" />
          <button onClick={async () => { const p = await browse(); if (p) onChange({ output_dir: p }); }} disabled={browsing} className="btn-secondary text-sm whitespace-nowrap px-3">{browsing ? '...' : '📂 浏览'}</button>
        </div>
      </div>

      {status === 'idle' && (
        <button onClick={handleExport} disabled={selected.size === 0 || !config.output_dir} className="w-full py-3 px-4 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors disabled:opacity-40">
          导出 STL
        </button>
      )}

      {status === 'running' && (
        <div className="flex items-center justify-center gap-3 py-4 bg-accent-400/5 border border-accent-400/20 rounded-lg">
          <div className="animate-spin w-5 h-5 border-2 border-accent-400 border-t-transparent rounded-full" /><span className="text-sm text-accent-300">导出中...</span>
        </div>
      )}

      {status === 'completed' && (
        <div className="bg-success/10 border border-success/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm text-success font-medium mb-2">导出完成</div>
          <p className="text-xs text-medical-400">{error}</p>
        </div>
      )}

      <div className="bg-medical-700/50 rounded-lg p-4 border border-accent-400/20">
        <h3 className="text-sm font-medium text-accent-300 mb-2">坐标系说明</h3>
        <ul className="text-xs text-medical-400 space-y-1">
          <li>• STL 导出保持 <span className="text-accent-200">RAS</span> 坐标系 (Slicer 原生)</li>
          <li>• 导入切片软件时请确认坐标系设置</li>
        </ul>
      </div>

      {status === 'error' && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg px-4 py-3">
          <p className="text-sm text-danger font-medium">导出失败</p>
          <p className="text-xs text-danger/70 mt-1">{error}</p>
        </div>
      )}
    </div>
  );
}
