import { describe, expect, it } from 'vitest'
import { readShortcut, voiceShortcutUrl, withoutShortcut } from './shortcuts'

const read = (query: string) => readShortcut(new URLSearchParams(query))

describe('atajos por URL', () => {
  it('sin parámetros de atajo no hace nada', () => {
    expect(read('')).toBeNull()
    expect(read('fecha=2026-10-01')).toBeNull()
  })

  it('abre la hoja de añadir con el texto dictado, limpio y acotado', () => {
    expect(read('nueva=1')).toEqual({ add: true, text: '', waterMl: null })
    expect(read('nueva=1&texto=dos%20huevos%0Acon%20%20tostada%20')).toEqual({ add: true, text: 'dos huevos con tostada', waterMl: null })
    expect(read(`nueva=1&texto=${'a'.repeat(900)}`)!.text).toHaveLength(600)
  })

  it('el texto solo cuenta si se abre la hoja', () => {
    expect(read('texto=hola')).toEqual({ add: false, text: '', waterMl: null })
  })

  it('agua: solo cantidades enteras razonables', () => {
    expect(read('agua=250')!.waterMl).toBe(250)
    for (const bad of ['agua=0', 'agua=10', 'agua=5000', 'agua=abc', 'agua=250.5', 'agua=']) expect(read(bad)!.waterMl).toBeNull()
  })

  it('quita solo los parámetros de atajo', () => {
    expect(withoutShortcut(new URLSearchParams('fecha=2026-10-01&nueva=1&texto=x&agua=250')).toString()).toBe('fecha=2026-10-01')
  })

  it('dirección del atajo de voz', () => {
    expect(voiceShortcutUrl('https://kcalia.example.com/')).toBe('https://kcalia.example.com/?nueva=1&texto=')
  })
})
