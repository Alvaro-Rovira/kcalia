import { describe, expect, it } from 'vitest'
import { addDays, diffDays, fmtRange, isValidISO, parseISO, toISO, weekStart, weekdayInitial } from './dates'
import { fmt, fmtSigned, fmtSmart, kgTo, parseNumber, plural, toKg } from './format'
import { slotForTime } from './slots'

const at = (h: number, m = 0) => new Date(2026, 8, 30, h, m)

describe('números en es-ES', () => {
  it('usa coma decimal y punto de millares', () => {
    expect(fmt(1234.5, 1)).toBe('1.234,5')
    expect(fmt(2220)).toBe('2.220')
    expect(fmt(1000)).toBe('1.000')
  })
  it('no muestra -0', () => {
    expect(fmt(-0.2)).toBe('0')
    expect(fmtSigned(-0.2)).toBe('0')
  })
  it('fmtSmart solo enseña los decimales que aportan', () => {
    expect(fmtSmart(80)).toBe('80')
    expect(fmtSmart(80.4)).toBe('80,4')
    expect(fmtSmart(1.5, 2)).toBe('1,5')
    expect(fmtSmart(1.25, 2)).toBe('1,25')
    expect(fmtSmart(2, 2)).toBe('2')
  })
  it('fmtSigned usa el signo menos tipográfico', () => {
    expect(fmtSigned(-633)).toBe('−633')
    expect(fmtSigned(275)).toBe('+275')
    expect(fmtSigned(0)).toBe('0')
  })
  it('lee coma y punto decimal', () => {
    expect(parseNumber('72,5')).toBe(72.5)
    expect(parseNumber('72.5')).toBe(72.5)
    expect(parseNumber(' 80 ')).toBe(80)
    expect(parseNumber('')).toBeNaN()
    expect(parseNumber('abc')).toBeNaN()
  })
  it('convierte kg y lb sin perder precisión visible', () => {
    expect(kgTo('kg', 80)).toBe(80)
    expect(kgTo('lb', 80)).toBeCloseTo(176.37, 2)
    expect(toKg('lb', kgTo('lb', 80))).toBeCloseTo(80, 6)
  })
  it('pluraliza', () => {
    expect(plural(1, 'día', 'días')).toBe('día')
    expect(plural(0, 'día', 'días')).toBe('días')
    expect(plural(-1, 'día', 'días')).toBe('día')
  })
})

describe('fechas', () => {
  it('la semana empieza en lunes', () => {
    expect(weekStart('2026-09-27')).toBe('2026-09-21') // domingo
    expect(weekStart('2026-09-21')).toBe('2026-09-21') // lunes
    expect(weekStart('2026-09-28')).toBe('2026-09-28')
  })
  it('suma días cruzando meses y cambios de hora', () => {
    expect(addDays('2026-09-30', 1)).toBe('2026-10-01')
    expect(addDays('2026-10-24', 2)).toBe('2026-10-26') // cambio de hora el 25 de octubre en España
    expect(diffDays('2026-10-26', '2026-10-24')).toBe(2)
  })
  it('valida fechas ISO reales', () => {
    expect(isValidISO('2026-02-30')).toBe(false)
    expect(isValidISO('2026-09-30')).toBe(true)
    expect(isValidISO('ayer')).toBe(false)
    expect(isValidISO(null)).toBe(false)
  })
  it('ida y vuelta', () => {
    expect(toISO(parseISO('2026-01-05'))).toBe('2026-01-05')
  })
  it('inicial del día con X para el miércoles', () => {
    expect(['2026-09-28', '2026-09-29', '2026-09-30'].map(weekdayInitial)).toEqual(['L', 'M', 'X'])
    expect(weekdayInitial('2026-10-04')).toBe('D')
  })
  it('rango de semana', () => {
    expect(fmtRange('2026-09-28', '2026-10-04')).toBe('28 sept – 4 oct')
    expect(fmtRange('2026-09-21', '2026-09-27')).toBe('21 – 27 sept')
  })
})

describe('momento del día', () => {
  it.each([
    [3, 'snack'],
    [8, 'desayuno'],
    [11, 'desayuno'],
    [12, 'comida'],
    [15, 'comida'],
    [17, 'merienda'],
    [19, 'merienda'],
    [21, 'cena'],
    [23, 'cena'],
  ])('%i:00 -> %s', (hour, slot) => {
    expect(slotForTime(at(hour))).toBe(slot)
  })
  it('la comida termina a las 16:30', () => {
    expect(slotForTime(at(16, 29))).toBe('comida')
    expect(slotForTime(at(16, 30))).toBe('merienda')
  })
})
