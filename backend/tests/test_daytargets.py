"""Objetivos por tipo de día. Mismos casos que el espejo del móvil (frontend/src/lib/dayTargets.test.ts)."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.daytargets import kind_for, targets_for
from app.schemas import Prefs

CASES = json.loads((Path(__file__).parent / "fixtures" / "day_target_cases.json").read_text())


@pytest.mark.parametrize("case", CASES["cases"], ids=[c["name"] for c in CASES["cases"]])
def test_casos_compartidos(case):
    prefs = Prefs.model_validate(case["prefs"])
    kind = kind_for(date.fromisoformat(case["date"]), prefs, case["overrides"])
    assert kind == case["kind"]
    assert targets_for(case.get("base", CASES["base"]), prefs, kind, case["exercise"]) == case["targets"]
