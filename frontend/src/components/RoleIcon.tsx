// Iconos SVG personalizados por rol: top=armadura, jungle=daga, mid=bastón, adc=arco, support=escudo

export function RoleIcon({ role, className = "w-5 h-5" }: { role: string; className?: string }) {
  switch (role) {
    case "top":
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2C8 2 5 5 5 9v3l2 2h10l2-2V9c0-4-3-7-7-7z" />
          <path d="M5 12v3a2 2 0 002 2h10a2 2 0 002-2v-3" />
          <line x1="9" y1="17" x2="9" y2="20" />
          <line x1="15" y1="17" x2="15" y2="20" />
          <line x1="7" y1="20" x2="17" y2="20" />
        </svg>
      );
    case "jungle":
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.5 2l7.5 7.5-10 10L4.5 12 14.5 2z" />
          <path d="M2 22l4.5-4.5" />
          <path d="M7 17l-3.5 3.5" />
        </svg>
      );
    case "mid":
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="5" y1="21" x2="17" y2="5" />
          <circle cx="17.5" cy="4.5" r="2" />
          <path d="M5 21l-2 1 1-2" />
          <path d="M14 7l2-3 2 1.5-3 2z" fill="currentColor" opacity="0.3" />
        </svg>
      );
    case "adc":
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 12C5 7.5 8.5 4 13 4" />
          <path d="M5 12c0 4.5 3.5 8 8 8" />
          <line x1="13" y1="4" x2="19" y2="12" />
          <line x1="19" y1="12" x2="13" y2="20" />
          <line x1="3" y1="12" x2="11" y2="12" />
          <path d="M10 10l2 2-2 2" />
        </svg>
      );
    case "support":
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L4 6v6c0 5.25 3.5 9.74 8 11 4.5-1.26 8-5.75 8-11V6l-8-4z" />
          <path d="M9 12l2 2 4-4" />
        </svg>
      );
    case "coach":
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 17l3-10 4.5 6 3-8 4.5 6 3-9" />
          <line x1="2" y1="17" x2="22" y2="17" />
          <rect x="2" y="17" width="20" height="3" rx="1" />
        </svg>
      );
    default:
      return null;
  }
}

export const ROLE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  top:     { bg: "bg-red-500/20",    text: "text-red-400",    border: "border-red-500/40"    },
  jungle:  { bg: "bg-green-500/20",  text: "text-green-400",  border: "border-green-500/40"  },
  mid:     { bg: "bg-blue-500/20",   text: "text-blue-400",   border: "border-blue-500/40"   },
  adc:     { bg: "bg-yellow-500/20", text: "text-yellow-400", border: "border-yellow-500/40" },
  support: { bg: "bg-purple-500/20", text: "text-purple-400", border: "border-purple-500/40" },
  coach:   { bg: "bg-slate-500/20",  text: "text-slate-400",  border: "border-slate-500/40"  },
};

export const ROLE_LABEL: Record<string, string> = {
  top: "TOP", jungle: "JGL", mid: "MID", adc: "ADC", support: "SUP", coach: "COACH",
};
