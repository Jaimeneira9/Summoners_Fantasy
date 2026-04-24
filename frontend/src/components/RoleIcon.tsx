import Image from "next/image";

const ROLE_IMAGE: Record<string, string> = {
  top:     "/roles/top.png",
  jungle:  "/roles/jungla.png",
  mid:     "/roles/mid.png",
  adc:     "/roles/adc.png",
  support: "/roles/support.png",
};

export function RoleIcon({ role, className = "w-5 h-5" }: { role: string; className?: string }) {
  const src = ROLE_IMAGE[role];
  if (!src) return null;
  return <Image src={src} alt={role} width={20} height={20} className={className} />;
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
