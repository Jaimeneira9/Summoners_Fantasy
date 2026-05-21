/**
 * Ícono de rol de LoL y constantes de color y etiqueta por rol.
 *
 * RoleIcon: renderiza el ícono del rol desde /public/roles/*.png usando next/image.
 *   Retorna null si el rol no está mapeado.
 *
 * ROLE_COLORS: clases Tailwind por rol (bg, text, border) para badges y bordes.
 *   Usar en combinación con JSX className.
 *
 * ROLE_LABEL: abreviatura legible por rol (TOP, JGL, MID, ADC, SUP, COACH).
 *   Nota: existe un ROLE_COLORS paralelo en lib/roles.ts con colores hex para
 *   uso en estilos inline (border-color, background, etc.).
 */
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
