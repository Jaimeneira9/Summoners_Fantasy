/**
 * Fuente de verdad para colores de rol.
 * Valores alineados con las variables CSS en globals.css (--role-top, etc.)
 */
export const ROLE_COLORS: Record<string, string> = {
  top:     "#dc2626",
  jungle:  "#16a34a",
  mid:     "#2563eb",
  adc:     "#ca8a04",
  support: "#7c3aed",
  coach:   "#475569",
};

export function getRoleColor(role: string): string {
  return ROLE_COLORS[role?.toLowerCase()] ?? "#444444";
}
