import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { kindFor, targetsFor } from './dayTargets'
import type { DayKind, DayTargetsValues, Prefs } from './types'

// Los mismos casos que el backend: los dos lados deben calcular igual.
const fixture = fileURLToPath(new URL('../../../backend/tests/fixtures/day_target_cases.json', import.meta.url))
const data = JSON.parse(readFileSync(fixture, 'utf8')) as {
  base: DayTargetsValues
  cases: { name: string; prefs: Partial<Prefs>; date: string; overrides: Record<string, DayKind>; exercise: number; kind: DayKind | null; targets: DayTargetsValues; base?: DayTargetsValues }[]
}

describe('objetivos por tipo de día (casos compartidos con el servidor)', () => {
  for (const c of data.cases) {
    it(c.name, () => {
      const kind = kindFor(c.date, c.prefs, c.overrides)
      expect(kind).toBe(c.kind)
      expect(targetsFor(c.base ?? data.base, c.prefs, kind, c.exercise)).toEqual(c.targets)
    })
  }
})
