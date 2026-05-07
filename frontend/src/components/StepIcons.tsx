type IconProps = { className?: string };

const S = 'w-5 h-5 shrink-0';

function DicomIcon({ className = S }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="13" x2="21" y2="13" />
      <line x1="12" y1="13" x2="12" y2="19" />
    </svg>
  );
}

function SkinIcon({ className = S }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="10.5" r="3" />
      <path d="M5 19c0-3.3 3.6-6 7-6s7 2.7 7 6" />
      <path d="M12 13.5v-3" />
    </svg>
  );
}

function RoiIcon({ className = S }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="5" width="14" height="14" rx="1" strokeDasharray="3 2" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
      <line x1="12" y1="3" x2="12" y2="7" />
      <line x1="12" y1="17" x2="12" y2="21" />
      <line x1="3" y1="12" x2="7" y2="12" />
      <line x1="17" y1="12" x2="21" y2="12" />
    </svg>
  );
}

function BolusIcon({ className = S }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 18c2-6 6-9 8-9s6 3 8 9" />
      <path d="M4 18c2-4 6-7 8-7s6 3 8 7" strokeWidth="1" opacity="0.4" />
      <line x1="12" y1="9" x2="12" y2="21" />
      <line x1="7" y1="21" x2="17" y2="21" />
    </svg>
  );
}

function ExecuteIcon({ className = S }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <polygon points="10,8 16,12 10,16" fill="currentColor" stroke="none" />
    </svg>
  );
}

function MoldIcon({ className = S }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="5" width="16" height="15" rx="1.5" />
      <path d="M7 5V3h10v2" />
      <path d="M8 10c2 1.5 6 1.5 8 0" />
      <path d="M8 14c2 1 4 1 6 0" />
    </svg>
  );
}

function ExportIcon({ className = S }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 20h12" />
      <path d="M12 4v12" />
      <polyline points="8,10 12,14 16,10" />
      <rect x="4" y="16" width="16" height="5" rx="1" />
    </svg>
  );
}

export const STEP_ICONS: Record<number, (p: IconProps) => JSX.Element> = {
  1: DicomIcon, 2: SkinIcon, 3: RoiIcon, 4: BolusIcon,
  5: ExecuteIcon, 6: MoldIcon, 7: ExportIcon,
};
