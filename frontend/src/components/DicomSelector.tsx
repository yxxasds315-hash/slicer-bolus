import { useBrowseFolder } from '../hooks/useBrowseFolder';
import type { PipelineConfig, SlicerState } from '../types';

interface Props {
  config: PipelineConfig;
  onChange: (p: Partial<PipelineConfig>) => void;
  slicer?: SlicerState;
}

export function DicomSelector({ config, onChange, slicer }: Props) {
  const { browse, browsing } = useBrowseFolder();

  return (
    <div className="space-y-4">
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
