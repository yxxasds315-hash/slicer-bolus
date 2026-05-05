import type { PipelineConfig, LogEntry, PipelineStatus, SlicerState } from '../types';

interface StepIndicatorProps { steps: { id: number; label: string; icon: string }[]; currentStep: number; onStepClick: (step: number) => void; status: PipelineStatus; }

export function StepIndicator({ steps, currentStep, onStepClick }: StepIndicatorProps) {
  return (<div className="flex items-center justify-center gap-0 mb-8">{steps.map((step, i) => (<div key={step.id} className="flex items-center"><button onClick={() => onStepClick(step.id)} className="flex items-center gap-2 group"><div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${currentStep === step.id ? 'bg-accent-400 text-medical-900 scale-110 shadow-lg shadow-accent-400/20' : currentStep > step.id ? 'bg-success text-white' : 'bg-medical-700 text-medical-500'}`}>{currentStep > step.id ? '✓' : step.icon}</div><span className={`hidden lg:inline text-sm whitespace-nowrap ${currentStep === step.id ? 'text-accent-200' : 'text-medical-500'}`}>{step.label}</span></button>{i < steps.length - 1 && <div className={`w-8 lg:w-16 h-0.5 mx-2 ${currentStep > step.id ? 'bg-success' : 'bg-medical-700'}`} />}</div>))}</div>);
}

interface WizardLayoutProps { children: React.ReactNode; currentStep: number; totalSteps?: number; onNext: () => void; onPrev: () => void; canNext: boolean; isLast: boolean; status: PipelineStatus; logs?: LogEntry[]; slicer?: SlicerState; slicerOnline?: boolean; onReconnect?: () => void; connecting?: boolean; }

export function WizardLayout({ children, currentStep, totalSteps: _ts, onNext, onPrev, canNext, isLast, status, logs, slicer, slicerOnline, onReconnect, connecting }: WizardLayoutProps) {
  const steps = [{ id: 1, label: 'DICOM 加载', icon: '📁' },{ id: 2, label: '皮肤分割', icon: '🔪' },{ id: 3, label: 'ROI 选择', icon: '🎯' },{ id: 4, label: '补偿器设计', icon: '🔧' },{ id: 5, label: '导出设置', icon: '📤' },{ id: 6, label: '执行', icon: '▶' }];
  const totalSteps = _ts || steps.length;
  return (
    <div className="min-h-screen flex flex-col items-center py-8 px-4">
      <div className="mb-6 text-center"><h1 className="text-2xl font-bold text-accent-200 tracking-tight">Bolus Designer</h1><p className="text-medical-500 text-sm">放疗个性化补偿器数字化设计平台</p></div>
      {slicer && slicerOnline !== false && <SlicerBar state={slicer} />}
      {slicerOnline === false && onReconnect && (<div className="w-full max-w-xl mb-4 bg-warning/10 border border-warning/30 rounded-lg px-4 py-3 flex items-center justify-between"><div className="flex items-center gap-2 text-sm"><span className="w-2 h-2 rounded-full bg-warning animate-pulse" /><span className="text-warning font-medium">3D Slicer 未连接</span><span className="text-medical-500">— 流水线需要 Slicer 运行才能执行</span></div><button onClick={onReconnect} disabled={connecting} className="px-4 py-1.5 bg-accent-400 text-medical-900 rounded-md text-sm font-medium hover:bg-accent-300 disabled:opacity-50 transition-colors">{connecting ? '启动中...' : '重新连接'}</button></div>)}
      <StepIndicator steps={steps} currentStep={currentStep} onStepClick={() => {}} status={status} />
      <div className="wizard-card w-full max-w-xl p-6">
        <h2 className="text-lg font-semibold text-accent-200 mb-4">{steps[currentStep - 1].icon} 第 {currentStep} 步：{steps[currentStep - 1].label}</h2>
        <div className="min-h-[280px]">{children}</div>
        <div className="flex justify-between mt-6 pt-4 border-t border-medical-700"><button onClick={onPrev} disabled={currentStep === 1} className="btn-secondary text-sm disabled:opacity-30 disabled:cursor-not-allowed">← 上一步</button><div className="text-medical-500 text-sm self-center">{currentStep} / {totalSteps}</div><button onClick={onNext} disabled={!canNext || status === 'running'} className="btn-primary text-sm">{isLast ? (status === 'running' ? '运行中...' : '▶ 执行') : '下一步 →'}</button></div>
      </div>
      {status === 'running' && logs && (<div className="w-full max-w-xl mt-4"><LogStream entries={logs} /></div>)}
    </div>
  );
}

function SlicerBar({ state }: { state: SlicerState }) {
  return (<div className="w-full max-w-xl mb-4"><div className="bg-medical-700/40 border border-medical-600 rounded-lg px-4 py-2 flex flex-wrap items-center gap-3 text-xs"><span className="text-medical-400">🔗 Slicer</span><span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" /><span className="text-success font-medium">已连接</span><span className="text-medical-500">|</span><span className="text-medical-300">📦 {state.volumes?.length > 0 ? `${state.volumes.length} 体积 (${state.volumes.map(v => v.name).join(', ')})` : '无已加载体积'}</span>{state.segmentations?.length > 0 && (<><span className="text-medical-500">|</span><span className="text-medical-300">🔪 {state.segmentations.length} 分割</span></>)}</div></div>);
}

function LogStream({ entries }: { entries: LogEntry[] }) {
  return (<div className="log-stream" ref={(el) => { if (el) el.scrollTop = el.scrollHeight; }}>{entries.map((entry, i) => (<div key={i} className="flex gap-2"><span className="text-medical-500 shrink-0">{entry.timestamp}</span><span className={entry.level === 'error' ? 'text-danger' : entry.level === 'success' ? 'text-success' : entry.level === 'warning' ? 'text-warning' : 'text-medical-500'}>{entry.level === 'error' ? '✗' : entry.level === 'success' ? '✓' : entry.level === 'warning' ? '⚠' : '●'}</span><span className="text-gray-300">{entry.message}</span></div>))}</div>);
}
