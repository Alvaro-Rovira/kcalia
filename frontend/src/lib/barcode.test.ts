import { describe, expect, it } from 'vitest'
import { normalizeBarcode } from './barcode'

describe('normalizeBarcode (mismos casos que el servidor)', () => {
  it('acepta EAN-13 válidos y limpia espacios', () => expect(normalizeBarcode(' 8410000123456 ')).toBe('8410000123456'))
  it('rechaza un dígito de control incorrecto', () => expect(normalizeBarcode('8410000123457')).toBeNull())
  it('pasa UPC-A a EAN-13', () => expect(normalizeBarcode('036000291452')).toBe('0036000291452'))
  it('acepta EAN-8 y rechaza longitudes raras', () => {
    expect(normalizeBarcode('96385074')).toBe('96385074')
    expect(normalizeBarcode('12345')).toBeNull()
    expect(normalizeBarcode('abc')).toBeNull()
  })
})
