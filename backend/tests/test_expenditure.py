"""Gasto real: lo que de verdad se gasta según lo apuntado y la tendencia del peso."""

from datetime import date, timedelta

import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.daytargets import targets_for
from app.expenditure import KCAL_PER_KG, estimate
from app.nutrition import calculate_targets
from app.schemas import Prefs

TODAY = date(2026, 10, 14)
NOISE = (0.4, -0.3, 0.1, -0.4, 0.2, 0.3, -0.2, -0.1, 0.4, -0.3, 0.0, 0.2, -0.4, 0.1)


def days(n: int, start_back: int = 28) -> list[str]:
    first = TODAY - timedelta(days=start_back)
    return [(first + timedelta(days=i)).isoformat() for i in range(n)]


def simulate(true_tdee=2500, eat=2200, n_days=28, weigh_every=1, start_kg=80.0, noise=True):
    isos = days(n_days)
    intake = {iso: eat for iso in isos}
    per_day = (eat - true_tdee) / KCAL_PER_KG
    weights = {
        iso: round(start_kg + per_day * i + (NOISE[i % len(NOISE)] if noise else 0), 1)
        for i, iso in enumerate(isos)
        if i % weigh_every == 0
    }
    return intake, weights


def run(intake, weights, formula=2600, target=2100):
    return estimate(
        intake=intake, targets_by_day=dict.fromkeys(intake, target), weights=weights, formula_tdee=formula, today=TODAY
    )


def test_recovers_the_true_expenditure_within_3_percent():
    intake, weights = simulate()
    result = run(intake, weights)
    assert result["status"] == "ok"
    assert result["observed"] == pytest.approx(2500, rel=0.03)
    assert result["weight_factor"] == 1  # 28 días apuntados y 27 de pesajes: ya no pesa la fórmula
    assert result["estimate"] == result["observed"]


def test_little_data_mixes_with_the_formula():
    intake, weights = simulate(n_days=14)
    result = run(intake, weights)
    assert result["status"] == "ok" and 0 < result["weight_factor"] < 1
    assert min(result["observed"], 2600) <= result["estimate"] <= max(result["observed"], 2600)


def test_needs_ten_complete_days():
    intake, weights = simulate(n_days=9)
    result = run(intake, weights)
    assert result["status"] == "insuficiente" and "10 días" in result["reason"]
    assert result["estimate"] is None


def test_incomplete_days_are_ignored():
    intake, weights = simulate()
    for iso in list(intake)[:20]:
        intake[iso] = 600  # menos de la mitad del objetivo: casi seguro, día sin apuntar entero
    result = run(intake, weights)
    assert result["status"] == "insuficiente" and result["days"] == 8


def test_needs_four_weighins_over_ten_days():
    intake, weights = simulate()
    few = dict(list(weights.items())[:3])
    assert "pesajes" in run(intake, few)["reason"]
    close = {k: v for k, v in list(weights.items())[:5]}  # 5 pesajes en 4 días
    assert run(intake, close)["status"] == "insuficiente"


def test_water_jump_gives_a_doubtful_result():
    intake, _ = simulate()
    isos = list(intake)
    weights = {isos[0]: 80.0, isos[6]: 79.8, isos[12]: 79.7, isos[13]: 81.9}
    result = run(intake, weights)
    assert result["status"] == "dudoso" and result["estimate"] is None
    assert "agua" in result["reason"] or "apuntado" in result["reason"]


def test_today_is_not_counted():
    intake, weights = simulate()
    intake[TODAY.isoformat()] = 5000
    assert run(intake, weights)["observed"] == run(*simulate())["observed"]


def test_targets_with_a_measured_maintenance():
    base = dict(sex="hombre", age=30, weight_kg=80, height_cm=180, activity="moderado", goal="definicion_ligera")
    plan = calculate_targets(**base, maintenance_override=2400)
    assert plan["tdee"] == 2400 and plan["kcal"] == round(2400 * 0.85 / 10) * 10


def test_measured_maintenance_already_includes_training():
    base = {"kcal": 2000, "protein": 150, "carbs": 200, "fat": 70}
    prefs = Prefs(add_exercise_kcal=True)
    assert targets_for(base, prefs, None, exercise_kcal=300, measured=True)["kcal"] == 2000
    assert targets_for(base, prefs, None, exercise_kcal=300)["kcal"] == 2300


# ------------------------------------------------------------------ API


@pytest.fixture(scope="module")
def client():
    reset_database()
    create_user("gasto")
    from app.main import app

    with TestClient(app) as c:
        login(c, "gasto")
        profile = dict(sex="hombre", age=30, height_cm=180, weight_kg=80, activity="moderado", goal="definicion_ligera")
        assert c.put("/api/profile", json={**profile, "today": days(1)[0]}).status_code == 200
        yield c


def _log(client, intake, weights):
    for n, (iso, kcal) in enumerate(intake.items()):
        item = {"name": "comida", "qty": 1, "unit": "g", "grams": 500, "kcal": kcal, "protein": 100, "carbs": 200,
                "fat": 60, "manual": True}  # fmt: skip
        body = {"client_id": f"gasto-{n:04d}", "date": iso, "slot": "comida", "name": "Comida", "text": "",
                "items": [item], "source": "manual", "dish_id": None}  # fmt: skip
        assert client.post("/api/meals", json=body).status_code == 201
    for iso, kg in weights.items():
        assert client.put("/api/weight", json={"date": iso, "kg": kg}).status_code == 200


def test_api_measures_applies_and_undoes(client, monkeypatch):
    from app.routers import profile as profile_router

    monkeypatch.setattr(profile_router, "today_local", lambda *_: TODAY)
    intake, weights = simulate()
    _log(client, intake, weights)
    measured = client.get("/api/expenditure").json()
    assert measured["status"] == "ok" and measured["mode"] == "formula"
    applied = client.post("/api/expenditure/apply").json()
    assert applied["targets"]["tdee_mode"] == "real"
    assert applied["targets"]["tdee"] == measured["estimate"] == applied["targets"]["tdee_real"]
    assert client.get("/api/expenditure").json()["suggest_update"] is False
    back = client.post("/api/expenditure/formula").json()
    assert back["targets"]["tdee_mode"] == "formula" and back["targets"]["tdee_real"] is None


def test_api_refuses_to_apply_without_data(monkeypatch):
    reset_database()
    create_user("nuevo")
    from app.main import app

    with TestClient(app) as c:
        login(c, "nuevo")
        profile = dict(sex="mujer", age=40, height_cm=165, weight_kg=60, activity="ligero", goal="mantenimiento")
        c.put("/api/profile", json={**profile, "today": TODAY.isoformat()})
        assert c.get("/api/expenditure").json()["status"] == "insuficiente"
        assert c.post("/api/expenditure/apply").status_code == 409
