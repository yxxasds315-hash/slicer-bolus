import type { PipelineConfig, PipelineStatus, LogEntry, SlicerState, BolusInfo } from '../types';

interface ExecutionPanelProps { config: PipelineConfig; status: PipelineStatus; logs: LogEntry[]; onExecute: () => void; slicer?: SlicerState; bolusInfo?: BolusInfo | null; }

export function ExecutionPanel({ config, status, logs, bolusInfo }: ExecutionPanelProps) {
  const renderStatus = () => {
    switch (status) {
      case 'idle': return (<div className="text-center py-8"><div className="text-4xl mb-3">🚀</div><p className="text-medical-400 text-sm">所有参数已就绪，点击下方按钮启动处理</p></div>);
      case 'running': return (<div className="text-center py-4"><div className="animate-spin inline-block w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full mb-3" /><p className="text-accent-300 text-sm">处理中，请稍候...</p></div>);
      case 'completed': return (
        <div className="space-y-3">
          <div className="text-center py-4">
            <div className="text-4xl mb-2">✅</div>
            <p className="text-success text-sm font-medium">补偿器设计完成</p>
          </div>
          {bolusInfo && (
            <div className="bg-medical-900/60 border border-accent-400/30 rounded-lg p-4 space-y-2">
              <p className="text-xs font-medium text-accent-300 uppercase tracking-wider">{bolusInfo.bolus}</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <span className="text-medical-400">空间尺寸</span>
                <span className="font-mono text-medical-200">
                  {bolusInfo.bounds_mm[0]} × {bolusInfo.bounds_mm[1]} × {bolusInfo.bounds_mm[2]} mm
                </span>
                <span className="text-medical-400">实际体积</span>
                <span className="font-mono text-medical-200">
                  {bolusInfo.volume_cm3} cm³
                  <span className="text-medical-500 text-xs ml-1">(≈ {bolusInfo.volume_cm3} mL)</span>
                </span>
              </div>
            </div>
          )}
        </div>
      );
      case 'error': return (<div className="text-center py-8"><div className="text-4xl mb-3">❌</div><p className="text-danger text-sm">处理出错，请查看日志了解详情。</p></div>);
    }
  };
  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">确认所有参数后，执行补偿器设计流水线。</p>
      <div className="bg-medical-900/50 rounded-lg p-4 border border-medical-700">
        <h3 className="text-xs font-medium text-medical-400 mb-3 uppercase tracking-wider">参数摘要</h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <ConfigRow label="DICOM" value={config.dicom_dir || '(未设置)'} />
          <ConfigRow label="设计方法" value="EDT 偏移与相减" /><ConfigRow label="厚度" value={`${config.thickness_mm} mm`} />
          <ConfigRow label="平滑" value={`${config.smoothing_method} / ${config.smoothing_kernel_mm}mm`} />
          <ConfigRow label="输出" value={config.output_dir || '(未设置)'} />
        </div>
      </div>
      {renderStatus()}
      {(status === 'running' || status === 'error') && logs.length > 0 && (<div className="log-stream">{logs.map((entry, i) => (<div key={i} className="flex gap-2"><span className="text-medical-500 shrink-0">{entry.timestamp}</span><span className={entry.level === 'error' ? 'text-danger' : entry.level === 'success' ? 'text-success' : entry.level === 'warning' ? 'text-warning' : 'text-medical-500'}>{entry.level === 'error' ? '✗' : entry.level === 'success' ? '✓' : entry.level === 'warning' ? '⚠' : '●'}</span><span className="text-gray-300">{entry.message}</span></div>))}</div>)}
    </div>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (<div className="flex justify-between py-1 border-b border-medical-700/50"><span className="text-medical-500">{label}</span><span className="text-medical-300 truncate ml-2 max-w-[140px]" title={value}>{value}</span></div>);
}
