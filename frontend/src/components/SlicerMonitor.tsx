import { useState, useRef, useEffect } from 'react';
import type { LogEntry, SlicerState, PipelineStatus } from '../types';

interface SlicerMonitorProps {
  slicer: SlicerState;
  slicerOnline: boolean;
  logs: LogEntry[];
  pipeStatus: PipelineStatus;
}

function StatusCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="bg-medical-700/40 rounded-md px-3 py-2 border border-medical-600/50">
      <div className="text-[10px] text-medical-500 uppercase tracking-wider">{label}</div>
      <div className="text-sm font-medium text-medical-200">{value}</div>
      {detail && <div className="text-[10px] text-medical-500 truncate mt-0.5">{detail}</div>}
    </div>
  );
}

export function SlicerMonitor({ slicer, slicerOnline, logs, pipeStatus }: SlicerMonitorProps) {
  const [expanded, setExpanded] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, expanded]);

  const latestLog = logs[logs.length - 1];

  const statusLabel = pipeStatus === 'running'
    ? '执行中'
    : pipeStatus === 'completed'
    ? '已完成'
    : pipeStatus === 'error'
    ? '出错'
    : slicerOnline
    ? '就绪'
    : '离线';

  const statusColor = pipeStatus === 'running'
    ? 'bg-accent-400 animate-pulse'
    : pipeStatus === 'completed'
    ? 'bg-success'
    : pipeStatus === 'error'
    ? 'bg-danger'
    : slicerOnline
    ? 'bg-success animate-pulse'
    : 'bg-danger';

  return (
    <div className={`slicer-monitor ${expanded ? 'slicer-monitor-expanded' : ''}`}>
      <button
        className="monitor-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${statusColor}`} />
          <span className="text-xs font-medium text-medical-300">Slicer</span>
          <span className="text-xs text-medical-500">{statusLabel}</span>
          {slicer.volumes.length > 0 && (
            <>
              <span className="text-medical-600">|</span>
              <span className="text-xs text-medical-500 truncate">{slicer.volumes.map(v => v.name).join(', ')}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3 min-w-0">
          {!expanded && latestLog && (
            <span className="text-[11px] text-medical-500 truncate max-w-[280px] hidden sm:block">
              {latestLog.level === 'error' ? '✗' : latestLog.level === 'success' ? '✓' : '●'} {latestLog.message}
            </span>
          )}
          <span className="text-[10px] text-medical-500 shrink-0">
            {expanded ? '▼ 折叠' : '▲ 展开'} {logs.length > 0 && `(${logs.length})`}
          </span>
        </div>
      </button>

      {expanded && (
        <div className="monitor-body">
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mb-3">
            <StatusCard label="连接状态" value={slicerOnline ? '已连接' : '未连接'} />
            <StatusCard label="体积" value={`${slicer.volumes.length} 个`} detail={slicer.volumes.map(v => v.name).join(', ')} />
            <StatusCard label="分割" value={`${slicer.segmentations.length} 个`} detail={slicer.segmentations.flatMap(s => s.segments).join(', ')} />
            <StatusCard label="ROI" value={`${slicer.rois?.length ?? 0} 个`} detail={slicer.rois?.map(r => r.name).join(', ')} />
            <StatusCard label="节点总数" value={`${slicer.nodes_total}`} />
          </div>
          {logs.length === 0 ? (
            <div className="text-center py-6 text-medical-500 text-xs">暂无日志 — 执行操作后将在此显示实时日志</div>
          ) : (
            <div className="log-stream">
              {logs.map((entry, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-medical-500 shrink-0">{entry.timestamp}</span>
                  <span className={
                    entry.level === 'error' ? 'text-danger' :
                    entry.level === 'success' ? 'text-success' :
                    entry.level === 'warning' ? 'text-warning' :
                    'text-medical-500'
                  }>{
                    entry.level === 'error' ? '✗' :
                    entry.level === 'success' ? '✓' :
                    entry.level === 'warning' ? '⚠' : '●'
                  }</span>
                  <span className="text-gray-300">{entry.message}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
