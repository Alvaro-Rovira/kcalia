/** Códigos de barras de producto (EAN-13, EAN-8, UPC-A). Espejo de backend/app/barcode.py:normalize_code. */

export function gtinCheck(code: string): boolean {
  const digits = [...code].map(Number)
  const check = digits.pop()
  const total = digits.reverse().reduce((sum, d, i) => sum + d * (i % 2 === 0 ? 3 : 1), 0)
  return (10 - (total % 10)) % 10 === check
}

/** Solo dígitos; UPC-A (12) pasa a EAN-13. null si no es un código de producto válido. */
export function normalizeBarcode(raw: string): string | null {
  let code = raw.replace(/\D/g, '')
  if (code.length === 12) code = `0${code}`
  if (![8, 13, 14].includes(code.length)) return null
  if (code.length === 8) return code
  return gtinCheck(code) ? code : null
}
