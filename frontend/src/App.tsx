import { useState, useCallback, useEffect } from 'react';
import type { PipelineConfig, LogEntry, PipelineStatus, SlicerState, MoldStatus } from './types';
import { WizardLayout } from './components/WizardLayout';
import { DicomSelector } from './components/DicomSelector';
import { SegmentationPanel, type PreviewStatus } from './components/SegmentationPanel';
import { BolusDesigner } from './components/BolusDesigner';
import { RoiSelector } from './components/RoiSelector';
import { ExportSettings } from './components/ExportSettings';
import { ExecutionPanel } from './components/ExecutionPanel';
import { SlicerMonitor } from './components/SlicerMonitor';
import { MoldGenerator } from './components/MoldGenerator';
import { useSSELog } from './hooks/useSSELog';

const defaultConfig: PipelineConfig = {
  dicom_dir: '', output_dir: '',
  thickness_mm: 5.0, hu_threshold: -200, oversampling: 3.0,
  smoothing_method: 'MEDIAN', smoothing_kernel_mm: 3.0,
  design_method: 'offset_subtract',
  roi_mode: 'full_skin', roi_segment_id: '',
  seal_kernel_1_mm: 15.0,
  seal_kernel_2_mm: 8.0,
  mold_shell_thickness_mm: 4.0,
  mold_base_thickness_mm: 2.5,
  mold_skin_padding_mm: 6.0,
  mold_pin_radius_mm: 2.0,
  mold_pin_height_mm: 8.0,
  mold_pin_clearance_mm: 0.20,
  mold_sprue_radius_mm: 3.0,
  mold_vent_radius_mm: 1.0,
};

type ConnStatus = 'checking' | 'online' | 'offline' | 'launching';

export default function App() {
  const [config, setConfig] = useState<PipelineConfig>(defaultConfig);
  const [step, setStep] = useState(1);
  const [pipeStatus, setPipeStatus] = useState<PipelineStatus>('idle');
  const [localLogs, setLocalLogs] = useState<LogEntry[]>([]);
  const [conn, setConn] = useState<ConnStatus>('checking');
  const [slicerOnline, setSlicerOnline] = useState(false);
  const [launchLog, setLaunchLog] = useState('');
  const [slicer, setSlicer] = useState<SlicerState>({ volumes: [], segmentations: [], nodes_total: 0, scene_modified: false });
  const [previewStatus, setPreviewStatus] = useState<PreviewStatus>('idle');
  const [previewError, setPreviewError] = useState('');
  const [moldStatus, setMoldStatus] = useState<MoldStatus>('idle');
  const [moldError, setMoldError] = useState('');

  const { logs: wsLogs, clearLogs } = useSSELog(pipeStatus);
  const logs = wsLogs.length > 0 ? wsLogs : localLogs;

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const r = await fetch('/api/health');
        const d = await r.json();
        if (cancelled) return;
        if (d.status === 'ok') { setConn('online'); setSlicerOnline(d.slicer_running === true); try { const sr = await fetch('/api/slicer/status'); const sd = await sr.json(); if (!cancelled && sd && typeof sd === 'object') setSlicer(prev => ({ ...prev, ...sd })); } catch { } }
        else { setConn('offline'); setSlicerOnline(false); }
      } catch { if (!cancelled) { setConn('offline'); setSlicerOnline(false); } }
    };
    check();
    const timer = setInterval(check, 3000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  const launchSlicer = async () => { setConn('launching'); setLaunchLog('Starting Slicer...\n'); fetch('/api/launch', { method: 'POST' }).then(r => r.text()).then(txt => setLaunchLog(p => p + txt)).catch(err => setLaunchLog(p => p + `\nFailed: ${err.message}`)).finally(() => setConn('offline')); };
  const updateConfig = useCallback((p: Partial<PipelineConfig>) => setConfig((prev) => ({ ...prev, ...p })), []);

  const canNext = () => {
    switch (step) {
      case 1: return config.dicom_dir.trim().length > 0 || slicer.volumes.length > 0;
      case 2: return previewStatus === 'done';
      case 3: return true; case 4: return config.thickness_mm > 0;
      case 5: return config.output_dir.trim().length > 0;
      case 6: return pipeStatus !== 'running';
      case 7: return true;
      default: return false;
    }
  };

  const handlePreview = async () => { setPreviewStatus('running'); setPreviewError(''); try { const r = await fetch('/api/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }); if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '预览失败'); } setPreviewStatus('threshold_done'); } catch (err: any) { setPreviewStatus('error'); setPreviewError(err.message); } };
  const handleScissors = async () => { setPreviewStatus('scissors_active'); try { await fetch('/api/scissors/activate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); } catch { setPreviewStatus('error'); setPreviewError('Scissors 激活失败，请检查 Slicer 连接'); } };
  const handleSolidify = async () => { setPreviewStatus('running'); setPreviewError(''); try { const r = await fetch('/api/solidify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }); if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '实心化失败'); } setPreviewStatus('solidified'); } catch (err: any) { setPreviewStatus('error'); setPreviewError(err.message); } };
  const handleSeal = async () => { setPreviewStatus('running'); setPreviewError(''); try { const r = await fetch('/api/seal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }); if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '二次封口失败'); } setPreviewStatus('sealed'); } catch (err: any) { setPreviewStatus('error'); setPreviewError(err.message); } };
  const handleFinalize = async () => { setPreviewStatus('running'); setPreviewError(''); try { const r = await fetch('/api/preview/finalize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }); if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '后处理失败'); } setPreviewStatus('done'); } catch (err: any) { setPreviewStatus('error'); setPreviewError(err.message); } };
  const handleMold = async () => { setMoldStatus('running'); setMoldError(''); try { const r = await fetch('/api/mold/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }); if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '模具生成失败'); } setMoldStatus('completed'); } catch (err: any) { setMoldStatus('error'); setMoldError(err.message); } };

  const handleNext = () => { if (step === 6 && pipeStatus !== 'completed') { executePipeline(); return; } setStep((s) => Math.min(s + 1, 7)); };
  const addLocalLog = (level: LogEntry['level'], msg: string) => setLocalLogs((p) => [...p, { timestamp: new Date().toLocaleTimeString(), level, message: msg }]);

  const executePipeline = async () => { setPipeStatus('running'); setLocalLogs([]); clearLogs(); addLocalLog('info', 'Starting pipeline...'); try { const r = await fetch('/api/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...config, use_existing_volumes: config.dicom_dir === '__slicer__' }) }); if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Failed'); } const d = await r.json(); addLocalLog('success', `Done! ${d.output_files?.join(', ') || ''}`); setPipeStatus('completed'); } catch (err: any) { addLocalLog('error', err.message); setPipeStatus('error'); } };

  const renderStep = () => {
    switch (step) {
      case 1: return <DicomSelector config={config} onChange={updateConfig} slicer={slicer} />;
      case 2: return <SegmentationPanel config={config} onChange={updateConfig} onPreview={handlePreview} onScissors={handleScissors} onSolidify={handleSolidify} onSeal={handleSeal} onFinalize={handleFinalize} previewStatus={previewStatus} previewError={previewError} />;
      case 3: return <RoiSelector config={config} onChange={updateConfig} slicer={slicer} />;
      case 4: return <BolusDesigner config={config} onChange={updateConfig} />;
      case 5: return <ExportSettings config={config} onChange={updateConfig} />;
      case 6: return <ExecutionPanel config={config} status={pipeStatus} logs={logs} onExecute={executePipeline} slicer={slicer} />;
      case 7: return <MoldGenerator config={config} onChange={updateConfig} onGenerate={handleMold} moldStatus={moldStatus} moldError={moldError} />;
    }
  };

  if (conn !== 'online') return (<><div className="min-h-screen flex items-center justify-center bg-medical-900 pb-12"><div className="wizard-card w-full max-w-md p-8 text-center"><h1 className="text-2xl font-bold text-accent-200 mb-2">Bolus Designer</h1><p className="text-medical-500 text-sm mb-8">放疗个性化补偿器数字化设计平台</p><div className="mb-6">{conn === 'checking' ? <div className="animate-spin inline-block w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full" /> : conn === 'launching' ? <><div className="animate-spin inline-block w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full mb-3" /><p className="text-accent-300 text-sm">Starting...</p></> : <div className="text-5xl mb-3">🔬</div>}<p className="text-medical-400 text-sm mt-3">{conn === 'checking' ? '检测中...' : conn === 'launching' ? '启动中...' : 'Slicer 未连接'}</p></div><button onClick={launchSlicer} disabled={conn === 'launching' || conn === 'checking'} className="btn-primary w-full mb-3 text-base">{conn === 'launching' ? '启动中...' : '🚀 启动 3D Slicer'}</button>{launchLog && <div className="log-stream mt-4 text-left"><pre className="text-xs text-gray-300 whitespace-pre-wrap">{launchLog}</pre></div>}</div></div><SlicerMonitor slicer={slicer} slicerOnline={slicerOnline} logs={logs} pipeStatus={pipeStatus} /></>);

  return (<><WizardLayout currentStep={step} totalSteps={7} onNext={handleNext} onPrev={() => { const prev = Math.max(step - 1, 1); setStep(prev); if (step >= 6) setPipeStatus('idle'); if (step === 7) setMoldStatus('idle'); }} canNext={canNext()} isLast={step === 7} status={pipeStatus} slicer={slicer} slicerOnline={slicerOnline} onReconnect={launchSlicer} connecting={conn === 'launching'}>{renderStep()}</WizardLayout><SlicerMonitor slicer={slicer} slicerOnline={slicerOnline} logs={logs} pipeStatus={pipeStatus} /></>);
}
