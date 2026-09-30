import json
from pathlib import Path

import pytest

from app.matching import SIMILARITY_THRESHOLD, find_similar, similarity
from app.textnorm import food_key, normalize, parse_part, split_parts

CASES = json.loads((Path(__file__).parent / "fixtures" / "normalize_cases.json").read_text())


@pytest.mark.parametrize(("text", "expected"), CASES["normalize"])
def test_normalize(text, expected):
    assert normalize(text) == expected


@pytest.mark.parametrize(("text", "expected"), CASES["food_key"])
def test_food_key(text, expected):
    assert food_key(text) == expected


@pytest.mark.parametrize(("text", "expected"), CASES["parse_part"])
def test_parse_part(text, expected):
    assert list(parse_part(text)) == expected


@pytest.mark.parametrize(("text", "expected"), CASES["split_parts"])
def test_split_parts(text, expected):
    assert split_parts(text) == expected


@pytest.mark.parametrize(("a", "b", "match"), CASES["similar"])
def test_similar(a, b, match):
    found = find_similar(normalize(a), [(1, normalize(b))])
    assert bool(found) is match


def test_normalize_es_idempotente():
    for text, _ in CASES["normalize"]:
        once = normalize(text)
        assert normalize(once) == once


def test_similarity_acotada():
    assert similarity("", "algo") == 0
    assert similarity("cafe con leche", "cafe con leche") == 1
    assert 0 < similarity("cafe con leche", "cafe solo") < SIMILARITY_THRESHOLD


def test_find_similar_ordena_y_limita():
    candidates = [(1, "tostada tomate aceite"), (2, "tostadas tomate aceite"), (3, "tostada tomate"), (4, "paella")]
    found = find_similar("tostada tomate aceit", candidates, limit=2)
    assert len(found) == 2
    assert found[0][1] >= found[1][1]
    assert 4 not in [dish_id for dish_id, _ in found]


def test_find_similar_excluye_la_exacta():
    assert find_similar("cafe con leche", [(1, "cafe con leche")]) == []
