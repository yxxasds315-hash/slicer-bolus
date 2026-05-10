import type { PipelineConfig, ValidateStatus, ValidateResult, ValidateThresholds } from '../types';

interface ValidatePanelProps {
  config: PipelineConfig;
  onValidate: () => Promise<void>;
  validateStatus: ValidateStatus;
  validateResult: ValidateResult | null;
  validateError: string;
}

interface MetricSpec {
  key: keyof ValidateResult;
  label: string;
  unit: string;
  fmt: (v: number) => string;
  ok: (v: number, t: ValidateThresholds) => boolean;
  target: (t: ValidateThresholds) => string;
}

const METRICS: MetricSpec[] = [
  {
    key: 'MHD_mm', label: 'MHD', unit: 'mm',
    fmt: (v) => v.toFixed(3),
    ok: (v, t) => v < t.MHD_mm,
    target: (t) => `< ${t.MHD_mm.toFixed(2)}`,
  },
  {
    key: 'HD95_mm', label: 'HD95', unit: 'mm',
    fmt: (v) => v.toFixed(3),
    ok: (v, t) => v < t.HD95_mm,
    target: (t) => `< ${t.HD95_mm.toFixed(2)}`,
  },
  {
    key: 'Dice', label: 'Dice', unit: '',
    fmt: (v) => v.toFixed(4),
    ok: (v, t) => v > t.Dice,
    target: (t) => `> ${t.Dice.toFixed(2)}`,
  },
  {
    key: 'volume_ratio', label: '体积比', unit: '',
    fmt: (v) => v.toFixed(4),
    ok: (v, t) => v > t.volume_ratio_min && v < t.volume_ratio_max,
    target: (t) => `${t.volume_ratio_min.toFixed(2)}~${t.volume_ratio_max.toFixed(2)}`,
  },
  {
    key: 'mold_skin_overlap_cm3', label: 'mold∩skin', unit: 'cm³',
    fmt: (v) => v.toFixed(3),
    ok: (v, t) => v < t.overlap_cm3,
    target: (t) => `< ${t.overlap_cm3.toFixed(2)}`,
  },
  {
    key: 'non_manifold_edges', label: '非流形边', unit: '',
    fmt: (v) => String(Math.round(v)),
    ok: (v) => v === 0,
    target: () => '= 0',
  },
];

export function ValidatePanel({ config, onValidate, validateStatus, validateResult, validateError }: ValidatePanelProps) {
  const allPass = validateResult?.status === 'PASS';

  return (
    <div className="space-y-5">
      <p className="text-medical-500 text-sm">
        评估阴模（Mold_Female_Conformal）与补偿器的适形度：表面距离、体素重叠、体积比、模具与皮肤穿模检测、3D 打印拓扑健康。阈值随 CT 体素分辨率自适应。
      </p>

      <div className="bg-medical-900/50 rounded-lg p-4 border border-medical-700 space-y-3">
        <h3 className="text-xs font-medium text-medical-400 uppercase tracking-wider">评估参数</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-medical-400">Bolus 厚度</span>
            <span className="ml-2 font-mono text-accent-300">{config.thickness_mm} mm</span>
          </div>
          <div>
            <span className="text-medical-400">模具壳体</span>
            <span className="ml-2 font-mono text-accent-300">{config.mold_shell_thickness_mm} mm</span>
          </div>
        </div>
      </div>

      {validateStatus === 'idle' && (
        <button onClick={onValidate} className="w-full py-3 px-4 bg-accent-400 text-medical-900 rounded-lg text-sm font-bold hover:bg-accent-300 transition-colors">
          运行适形度评估
        </button>
      )}

      {validateStatus === 'running' && (
        <div className="flex items-center justify-center gap-3 py-4 bg-accent-400/5 border border-accent-400/20 rounded-lg">
          <div className="animate-spin w-5 h-5 border-2 border-accent-400 border-t-transparent rounded-full" />
          <span className="text-sm text-accent-300">Slicer 计算中...</span>
        </div>
      )}

      {validateStatus === 'completed' && validateResult && (
        <div className={`rounded-lg p-4 space-y-3 ${allPass ? 'bg-success/10 border border-success/30' : 'bg-danger/10 border border-danger/30'}`}>
          <div className={`text-sm font-medium flex items-center gap-2 ${allPass ? 'text-success' : 'text-danger'}`}>
            {allPass ? '✓ 适形度评估通过' : '✗ 适形度评估未通过'}
          </div>

          <div className="bg-medical-900/70 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-medical-700 text-medical-400 text-xs">
                  <th className="text-left py-2 px-3 font-medium">指标</th>
                  <th className="text-right py-2 px-3 font-medium">实测值</th>
                  <th className="text-right py-2 px-3 font-medium">目标</th>
                  <th className="text-center py-2 px-3 font-medium">判定</th>
                </tr>
              </thead>
              <tbody>
                {METRICS.map(({ key, label, unit, fmt, ok, target }) => {
                  const val = validateResult[key] as number;
                  const pass = ok(val, validateResult.thresholds);
                  return (
                    <tr key={key} className="border-b border-medical-800/50">
                      <td className="py-2 px-3 text-medical-300">{label}</td>
                      <td className={`py-2 px-3 text-right font-mono ${pass ? 'text-success' : 'text-danger'}`}>
                        {fmt(val)}{unit ? ` ${unit}` : ''}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-medical-500">{target(validateResult.thresholds)}{unit ? ` ${unit}` : ''}</td>
                      <td className="py-2 px-3 text-center">{pass ? <span className="text-success">✓</span> : <span className="text-danger">✗</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-medical-500 px-1">
            CT 最小体素 <span className="font-mono text-medical-400">{validateResult.ct_voxel_min_mm.toFixed(2)} mm</span>
            ，MHD/HD95 阈值已据此自适应
          </p>

          {validateResult.mold_skin_overlap_centroid_ras && (
            <div className="bg-danger/15 border border-danger/40 rounded-md px-3 py-2 text-xs space-y-1">
              <p className="text-danger font-medium">⚠ 穿模警告</p>
              <p className="text-danger/80">
                质心 RAS:{' '}
                <span className="font-mono">
                  ({validateResult.mold_skin_overlap_centroid_ras.map((v) => v.toFixed(1)).join(', ')})
                </span>{' '}
                mm
              </p>
              <p className="text-medical-400">
                Slicer 3D 视图已自动放置红色 Fiducial「Bolus_穿模警告」，可点击跳转该位置
              </p>
            </div>
          )}

          <button onClick={onValidate} className="w-full py-2 px-4 bg-medical-600 text-medical-300 rounded-lg text-sm hover:bg-medical-500 transition-colors">
            🔄 重新评估
          </button>
        </div>
      )}

      {validateStatus === 'error' && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg px-4 py-3">
          <p className="text-sm text-danger font-medium">评估失败</p>
          <p className="text-xs text-danger/70 mt-1">{validateError}</p>
          <button onClick={onValidate} className="mt-3 w-full py-2 px-4 bg-medical-600 text-medical-300 rounded-lg text-sm hover:bg-medical-500 transition-colors">
            🔄 重试
          </button>
        </div>
      )}
    </div>
  );
}
