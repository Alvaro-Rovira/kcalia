import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { draftFromProducts, itemFor, matchProduct, resolveText, round1, singleItem, tokens, type ProductMatchInfo } from './products'

// Los mismos casos que usa el servidor: los dos lados deben resolver igual.
const fixture = fileURLToPath(new URL('../../../backend/tests/fixtures/product_cases.json', import.meta.url))
const data = JSON.parse(readFileSync(fixture, 'utf8')) as {
  products: ProductMatchInfo[]
  cases: { text: string; items: Record<string, number>[]; rest: string[] }[]
}

describe('espejo del emparejado de productos del servidor', () => {
  it.each(data.cases.map((c) => [c.text, c] as const))('%s', (_text, c) => {
    const result = resolveText(c.text, data.products)
    const got = result.items.map((i) => ({ product_id: i.product_id, grams: i.grams, kcal: i.kcal, protein: i.protein, carbs: i.carbs, fat: i.fat }))
    expect(got).toEqual(c.items)
    expect(result.rest).toEqual(c.rest)
  })
})

describe('productos', () => {
  it('sin productos todo es resto', () => {
    expect(resolveText('dos yogures ligeros', [])).toEqual({ items: [], rest: ['dos yogures ligeros'] })
    expect(resolveText('  ', [])).toEqual({ items: [], rest: [] })
  })
  it('las palabras que no cuentan se ignoran', () => {
    expect([...tokens('Dos YOGURES ligeros con 200 g')].sort()).toEqual(['ligero', 'yogur'])
    expect([...tokens('un vaso de leche')]).toEqual(['leche'])
  })
  it('un nombre demasiado genérico no se empareja', () => {
    expect(matchProduct(tokens('yogur'), data.products)).toBeNull()
    expect(matchProduct(tokens('yogur natural'), data.products)).toBeNull()
    expect(matchProduct(tokens('yogur griego'), data.products)?.id).toBe(5)
  })
  it('ml y gramos valen igual; lo que no se sabe no se adivina', () => {
    const [yogur, leche, , , , barrita] = data.products
    expect(itemFor(leche, 1, 'l')?.kcal).toBe(460)
    expect(itemFor(yogur, 2, 'cda')).toBeNull()
    expect(itemFor(barrita, 2, null)).toBeNull()
    expect(itemFor(yogur, 9999, 'g')).toBeNull()
  })
  it('redondea como el servidor', () => {
    expect([0.25, 0.35, 2.45, 143.75, 1.05].map(round1)).toEqual([0.3, 0.4, 2.5, 143.8, 1.1])
  })
  it('arma el borrador de una comida de productos', () => {
    const items = resolveText('dos yogures ligeros', data.products).items
    const draft = draftFromProducts('dos yogures ligeros', items)
    expect(draft).toMatchObject({ source: 'product', kcal: 110, protein: 10.3, dish_id: null })
    expect(draft.assumptions[0]).toContain('etiqueta que guardaste')
  })
  it('un producto se añade de un toque como una unidad, o 100 g si no se sabe su peso', () => {
    const [yogur, , , , , barrita] = data.products
    expect(singleItem(yogur)).toMatchObject({ grams: 125, kcal: 55 })
    expect(singleItem(barrita)).toMatchObject({ grams: 100, kcal: 360 })
  })
})
