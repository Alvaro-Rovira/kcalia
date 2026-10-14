import { describe, expect, it } from 'vitest'
import { officialShare, sourceOf } from './source'
import type { Item } from './types'

const item = (over: Partial<Item>): Item => ({ name: 'x', qty: 1, unit: 'g', grams: 100, kcal: 100, protein: 1, carbs: 1, fat: 1, ...over })

describe('origen de los valores', () => {
  it('reconoce cada origen y trata lo antiguo sin origen como estimado', () => {
    expect(sourceOf(item({ source: 'tabla' }))).toBe('tabla')
    expect(sourceOf(item({ product_id: 3 }))).toBe('etiqueta')
    expect(sourceOf(item({ manual: true }))).toBe('manual')
    expect(sourceOf(item({ source: 'usuario' }))).toBe('manual')
    expect(sourceOf(item({}))).toBe('ia')
  })

  it('calcula la parte de las kcal con valores oficiales, como el servidor', () => {
    expect(officialShare([item({ kcal: 300, source: 'tabla' }), item({ kcal: 100, source: 'ia' })])).toBe(0.75)
    expect(officialShare([item({ kcal: 50 })])).toBe(0)
    expect(officialShare([])).toBe(0)
    expect(officialShare([item({ kcal: 90, product_id: 1 }), item({ kcal: 10, manual: true })])).toBe(1)
  })
})
