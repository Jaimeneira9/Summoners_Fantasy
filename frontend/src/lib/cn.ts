/**
 * Utility para concatenar clases CSS de forma segura.
 * Descarta valores falsy (undefined, false, null) antes de unir.
 * Alternativa liviana a clsx para este proyecto.
 */
export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(' ')
}
