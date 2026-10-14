import pytest

from app.bench import EXACT, EXACT_SPEC
from app.foodtable import table


@pytest.mark.parametrize(("case", "spec"), list(zip(EXACT, EXACT_SPEC, strict=True)))
def test_bench_references_come_from_the_official_table(case, spec):
    entries = table().entries
    text, kcal, protein, carbs, fat = case
    got = [sum(getattr(entries[i], f"{m}100") * g / 100 for i, g in spec) for m in ("kcal", "protein", "carbs", "fat")]
    assert (round(got[0]), round(got[1], 1), round(got[2], 1), round(got[3], 1)) == (kcal, protein, carbs, fat), text
