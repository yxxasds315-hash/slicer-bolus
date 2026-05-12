import { useState } from 'react';
import { useBrowseFolder } from '../hooks/useBrowseFolder';
import type { PipelineConfig, SlicerState } from '../types';

interface Props {
  config: PipelineConfig;
  onChange: (p: Partial<PipelineConfig>) => void;
  slicer?: SlicerState;
  onJumpToStep?: (target: number) => void;
}

export function DicomSelector({ config, onChange, slicer, onJumpToStep }: Props) {
  const { browse, browsing } = useBrowseFolder();
  const [phantomStatus, setPhantomStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [phantomError, setPhantomError] = useState('');

  const loadBoxPhantom = async () => {
    setPhantomStatus('running'); setPhantomError('');
    try {
      const r = await fetch('/api/test/box_phantom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thickness_mm: config.thickness_mm || 5.0 }),
      });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '测试体模载入失败'); }
      setPhantomStatus('done');
      // 等 slicer 状态轮询刷新（1s/次），再尝试跳到第 6 步
      if (onJumpToStep) {
        setTimeout(() => onJumpToStep(6), 1500);
      }
    } catch (err: any) {
      setPhantomStatus('error'); setPhantomError(err.message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-amber-900/20 border border-amber-700/40 rounded-lg p-3 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1">
            <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wider">🧪 测试模式（跳过 DICOM）</h4>
            <p className="text-xs text-amber-200/70 mt-0.5">载入 20×20×{config.thickness_mm || 5}mm 长方体 + 平面皮肤，用于验证模具/评估逻辑。载入成功后自动跳到第 6 步。</p>
          </div>
          <button
            onClick={loadBoxPhantom}
            disabled={phantomStatus === 'running'}
            className="px-3 py-1.5 bg-amber-600 text-medical-900 rounded text-xs font-bold hover:bg-amber-500 disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {phantomStatus === 'running' ? '载入中…' : phantomStatus === 'done' ? '✓ 已载入' : '载入长方体'}
          </button>
        </div>
        {phantomStatus === 'error' && (
          <p className="text-xs text-danger">{phantomError}</p>
        )}
        {phantomStatus === 'done' && (
          <p className="text-xs text-amber-200/80">✓ BoxPhantomVolume + Skin + Bolus_{config.thickness_mm || 5}mm 已就绪</p>
        )}
      </div>

      {slicer && slicer.volumes.length > 0 && (
        <div className="bg-success/10 border border-success/30 rounded-lg p-4">
          <h3 className="text-sm font-medium text-success mb-2">✅ Slicer 中已有患者数据</h3>
          <div className="space-y-1 mb-3">{slicer.volumes.map((v) => (<div key={v.id} className="flex justify-between text-xs text-medical-300"><span>{v.name}</span><span className="text-medical-500">{v.dimensions.join(' × ')} | {v.spacing_mm[0]}mm 层厚</span></div>))}</div>
          <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={config.dicom_dir === '__slicer__'} onChange={(e) => onChange({ dicom_dir: e.target.checked ? '__slicer__' : '' })} className="accent-accent-400" /><span className="text-xs text-success">直接使用已加载数据（跳过 DICOM 导入步骤）</span></label>
        </div>
      )}
      <p className="text-medical-500 text-sm">选择患者 CT DICOM 数据文件夹，或使用 Slicer 中已加载的数据。建议层厚 0.8mm - 2.5mm。</p>
      <div><label className="block text-sm text-medical-400 mb-1.5">DICOM 文件夹路径</label>
        <div className="flex gap-2"><input type="text" value={config.dicom_dir === '__slicer__' ? '' : config.dicom_dir} onChange={(e) => onChange({ dicom_dir: e.target.value })} placeholder="/Users/xxx/patient_dicom/" className="input-medical flex-1" disabled={config.dicom_dir === '__slicer__'} /><button onClick={async () => { const p = await browse(); if (p) onChange({ dicom_dir: p }); }} disabled={browsing || config.dicom_dir === '__slicer__'} className="btn-secondary text-sm whitespace-nowrap px-3">{browsing ? '...' : '📂 浏览'}</button></div>
        <p className="text-xs text-medical-500 mt-1">💡 Finder 中按 ⌥⌘C 复制路径后粘贴</p></div>
      <div className="bg-medical-700/50 rounded-lg p-4 border border-medical-600/50"><h3 className="text-sm font-medium text-accent-300 mb-2">📋 DICOM 要求</h3><ul className="text-xs text-medical-400 space-y-1"><li>• 支持标准 DICOM 3.0 格式 | 推荐层厚 ≤ 2.5mm</li><li>• 建议安装 SlicerRT 扩展以解析 RT Structure Set</li></ul></div>
    </div>
  );
}
