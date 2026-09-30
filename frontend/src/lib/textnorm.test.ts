import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { findSimilar, foodKey, normalize, parsePart, similarity, splitParts } from './textnorm'

// Los mismos casos que usa el backend: los dos lados deben normalizar igual.
const fixture = fileURLToPath(new URL('../../../backend/tests/fixtures/normalize_cases.json', import.meta.url))
const cases = JSON.parse(readFileSync(fixture, 'utf8')) as {
  normalize: [string, string][]
  food_key: [string, string][]
  parse_part: [string, [number, string | null, string]][]
  split_parts: [string, string[]][]
  similar: [string, string, boolean][]
}

describe('espejo de la normalización del backend', () => {
  it.each(cases.normalize)('normalize(%j) -> %j', (text, expected) => {
    expect(normalize(text)).toBe(expected)
  })
  it.each(cases.food_key)('foodKey(%j) -> %j', (text, expected) => {
    expect(foodKey(text)).toBe(expected)
  })
  it.each(cases.parse_part)('parsePart(%j)', (text, expected) => {
    expect(parsePart(text)).toEqual(expected)
  })
  it.each(cases.split_parts)('splitParts(%j)', (text, expected) => {
    expect(splitParts(text)).toEqual(expected)
  })
  it.each(cases.similar)('%j ~ %j -> %j', (a, b, match) => {
    expect(findSimilar(normalize(a), [[1, normalize(b)]]).length > 0).toBe(match)
  })
})

describe('similitud', () => {
  it('está acotada entre 0 y 1', () => {
    expect(similarity('', 'algo')).toBe(0)
    expect(similarity('cafe con leche', 'cafe con leche')).toBe(1)
    expect(similarity('cafe con leche', 'cafe solo')).toBeLessThan(0.85)
  })
  it('ordena de mayor a menor y excluye la coincidencia exacta', () => {
    const found = findSimilar('tostada tomate aceit', [
      [1, 'tostada tomate aceite'],
      [2, 'tostadas tomate aceite'],
      [3, 'paella'],
    ])
    expect(found.map(([id]) => id)).toEqual([1, 2])
    expect(findSimilar('cafe con leche', [[1, 'cafe con leche']])).toEqual([])
  })
})
