import type { PipelineStatus, SlicerState } from '../types';
import { STEP_ICONS } from './StepIcons';

interface StepInfo { id: number; label: string; Icon: (p: { className?: string }) => JSX.Element; }

interface StepIndicatorProps { steps: StepInfo[]; currentStep: number; onStepClick: (step: number) => void; status: PipelineStatus; }

export function StepIndicator({ steps, currentStep, onStepClick }: StepIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-0 mb-8">
      {steps.map((step, i) => (
        <div key={step.id} className="flex items-center">
          <button onClick={() => onStepClick(step.id)} className="flex items-center gap-2 group">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 ${
              currentStep === step.id
                ? 'bg-accent-400 text-medical-900 scale-110 shadow-lg shadow-accent-400/20'
                : currentStep > step.id
                ? 'bg-success text-white'
                : 'bg-medical-700 text-medical-500'
            }`}>
              {currentStep > step.id ? (
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="5,13 10,18 19,6" />
                </svg>
              ) : (
                <step.Icon className="w-5 h-5" />
              )}
            </div>
            <span className={`hidden lg:inline text-sm whitespace-nowrap ${
              currentStep === step.id ? 'text-accent-200' : 'text-medical-500'
            }`}>{step.label}</span>
          </button>
          {i < steps.length - 1 && (
            <div className={`w-8 lg:w-16 h-0.5 mx-2 ${
              currentStep > step.id ? 'bg-success' : 'bg-medical-700'
            }`} />
          )}
        </div>
      ))}
    </div>
  );
}

interface WizardLayoutProps { children: React.ReactNode; currentStep: number; totalSteps?: number; onNext: () => void; onPrev: () => void; canNext: boolean; isLast: boolean; status: PipelineStatus; slicer?: SlicerState; slicerOnline?: boolean; onReconnect?: () => void; connecting?: boolean; onJumpToStep?: (step: number) => void; devMode?: boolean; }

function detectCompletedSteps(slicer?: SlicerState): Set<number> {
  const done = new Set<number>();
  if (!slicer) return done;
  if (slicer.volumes.length > 0) done.add(1);
  const allSegs = slicer.segmentations.flatMap(s => s.segments);
  if (allSegs.includes('Skin')) done.add(2);
  if (allSegs.some(s => /^Bolus_\d+mm$/.test(s))) done.add(5);
  if (slicer.models?.some(m => m.name === 'Mold_Female_Conformal')) done.add(6);
  return done;
}

function getJumpTarget(done: Set<number>, current: number): { step: number; label: string } | null {
  const milestones: [number, string][] = [[6, '模具已生成'], [5, '补偿器已生成'], [2, '皮肤分割已完成'], [1, 'DICOM 已加载']];
  for (const [step, label] of milestones) {
    if (done.has(step) && step > current) return { step, label };
  }
  return null;
}

const steps: StepInfo[] = [
  { id: 1, label: 'DICOM 加载', Icon: STEP_ICONS[1] },
  { id: 2, label: '皮肤分割', Icon: STEP_ICONS[2] },
  { id: 3, label: 'ROI 选择',   Icon: STEP_ICONS[3] },
  { id: 4, label: '补偿器设计', Icon: STEP_ICONS[4] },
  { id: 5, label: '执行',       Icon: STEP_ICONS[5] },
  { id: 6, label: '模具设计',   Icon: STEP_ICONS[6] },
  { id: 7, label: '适形度评估', Icon: STEP_ICONS[7] },
  { id: 8, label: '导出 STL',   Icon: STEP_ICONS[8] },
];

export function WizardLayout({ children, currentStep, totalSteps: _ts, onNext, onPrev, canNext, isLast, status, slicer, slicerOnline, onReconnect, connecting, onJumpToStep, devMode }: WizardLayoutProps) {
  const totalSteps = _ts || steps.length;
  const CurrentIcon = STEP_ICONS[currentStep] || STEP_ICONS[1];
  return (
    <div className="min-h-screen flex flex-col items-center py-8 px-4 pb-16">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-accent-200 tracking-tight">Bolus Designer</h1>
        <p className="text-medical-500 text-sm">放疗个性化补偿器数字化设计平台</p>
      </div>
      {slicer && slicerOnline !== false && <SlicerBar state={slicer} />}
      {slicerOnline === false && onReconnect && (
        <div className="w-full max-w-xl mb-4 bg-warning/10 border border-warning/30 rounded-lg px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-warning animate-pulse" />
            <span className="text-warning font-medium">3D Slicer 未连接</span>
            <span className="text-medical-500">— 流水线需要 Slicer 运行才能执行</span>
          </div>
          <button onClick={onReconnect} disabled={connecting} className="px-4 py-1.5 bg-accent-400 text-medical-900 rounded-md text-sm font-medium hover:bg-accent-300 disabled:opacity-50 transition-colors">
            {connecting ? '启动中...' : '重新连接'}
          </button>
        </div>
      )}
      {devMode && (
        <div className="w-full max-w-xl mb-2 text-center">
          <span className="inline-block px-3 py-0.5 bg-warning/20 border border-warning/30 rounded-full text-xs text-warning font-mono">DEV MODE — 自由跳转</span>
        </div>
      )}
      <StepIndicator steps={steps} currentStep={currentStep} onStepClick={(id) => devMode && onJumpToStep?.(id)} status={status} />
      <div className="wizard-card w-full max-w-xl p-6">
        <h2 className="text-lg font-semibold text-accent-200 mb-4 flex items-center gap-2.5">
          <CurrentIcon className="w-6 h-6 text-accent-400" />
          <span>第 {currentStep} 步：{steps[currentStep - 1].label}</span>
        </h2>
        {onJumpToStep && (() => {
          const done = detectCompletedSteps(slicer);
          const target = getJumpTarget(done, currentStep);
          if (!target) return null;
          return (
            <div className="mb-4 px-4 py-3 bg-accent-400/10 border border-accent-400/30 rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-accent-300">✅</span>
                <span className="text-medical-300">检测到 {target.label}</span>
              </div>
              <button onClick={() => onJumpToStep(target.step)} className="px-3 py-1.5 bg-accent-400 text-medical-900 rounded-md text-xs font-bold hover:bg-accent-300 transition-colors">
                跳转至步骤 {target.step} →
              </button>
            </div>
          );
        })()}
        <div className="min-h-[280px]">{children}</div>
        <div className="flex justify-between mt-6 pt-4 border-t border-medical-700">
          <button onClick={onPrev} disabled={currentStep === 1} className="btn-secondary text-sm disabled:opacity-30 disabled:cursor-not-allowed">← 上一步</button>
          <div className="text-medical-500 text-sm self-center">{currentStep} / {totalSteps}</div>
          {isLast ? (
            <div className="w-[80px]" />
          ) : (
            <button onClick={onNext} disabled={!canNext || status === 'running'} className="btn-primary text-sm">
              {status === 'running' && currentStep === 5 ? '运行中...' : '下一步 →'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SlicerBar({ state }: { state: SlicerState }) {
  return (
    <div className="w-full max-w-xl mb-4">
      <div className="bg-medical-700/40 border border-medical-600 rounded-lg px-4 py-2 flex flex-wrap items-center gap-3 text-xs">
        <span className="text-medical-400">🔗 Slicer</span>
        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
        <span className="text-success font-medium">已连接</span>
        <span className="text-medical-500">|</span>
        <span className="text-medical-300">
          📦 {state.volumes?.length > 0 ? `${state.volumes.length} 体积 (${state.volumes.map(v => v.name).join(', ')})` : '无已加载体积'}
        </span>
        {state.segmentations?.length > 0 && (
          <>
            <span className="text-medical-500">|</span>
            <span className="text-medical-300">🔪 {state.segmentations.length} 分割</span>
          </>
        )}
      </div>
    </div>
  );
}
