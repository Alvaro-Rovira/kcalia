from datetime import date

import pytest

from app.summary import (
    build_week_summary,
    day_status,
    evaluate_achievements,
    moving_average,
    project,
    streak,
    week_start,
)

TARGETS = {"kcal": 2000, "protein": 150, "carbs": 200, "fat": 67, "tdee": 2500}
MONDAY = date(2026, 9, 21)


def day(kcal, protein=150):
    return {"kcal": kcal, "protein": protein, "carbs": 200, "fat": 60, "meals": 3}


def test_la_semana_empieza_en_lunes():
    assert week_start(date(2026, 9, 27)) == MONDAY  # domingo
    assert week_start(MONDAY) == MONDAY
    assert week_start(date(2026, 9, 28)) == date(2026, 9, 28)


def test_estado_del_dia_con_margen_del_10_por_ciento():
    assert day_status(1799, 2000) == "bajo"
    assert day_status(1800, 2000) == "cumplido"
    assert day_status(2200, 2000) == "cumplido"
    assert day_status(2201, 2000) == "pasado"


def test_proyeccion_7700_kcal_por_kilo():
    # −550 kcal/día = −3.850 kcal/semana = medio kilo por semana -> 1 kg cada 2 semanas
    p = project(-550)
    assert p["weekly_kg"] == pytest.approx(-0.5)
    assert p["weeks_per_kg"] == 2.0
    assert p["direction"] == "perdida"


def test_proyeccion_superavit_y_estable():
    assert project(275)["weeks_per_kg"] == 4.0
    assert project(275)["direction"] == "ganancia"
    assert project(20) == {"weekly_kg": 0.02, "weeks_per_kg": None, "direction": "estable"}


def test_resumen_semanal_completo():
    days = {
        "2026-09-21": day(2000),
        "2026-09-22": day(1950),
        "2026-09-23": day(2600, 90),  # pasado de objetivo y en superávit
        "2026-09-24": day(1500, 100),  # bajo
        "2026-09-25": day(2100),
        # sábado sin registrar
        "2026-09-27": day(2050),
    }
    s = build_week_summary(start=MONDAY, today=date(2026, 9, 28), days=days, targets=TARGETS, weights={})
    assert s["complete"] is True
    assert s["logged_days"] == 6 and s["days_elapsed"] == 7
    assert s["on_target_days"] == 4
    assert s["over_target_days"] == 1
    assert s["deficit_days"] == 5 and s["surplus_days"] == 1
    assert s["protein_days"] == 4
    assert s["total_kcal"] == 12200
    assert s["avg_kcal"] == round(12200 / 6)
    assert s["balance_total"] == 12200 - 6 * 2500
    assert s["adherence_pct"] == round(4 / 7 * 100)
    assert s["best_day"]["date"] == "2026-09-21" and s["best_day"]["diff"] == 0
    assert s["worst_day"]["date"] == "2026-09-23"
    assert s["days"][5]["status"] == "sin_registro"
    # −2.800 kcal en 6 días -> −466,7/día -> −3.266,7/semana
    assert s["projection"]["weeks_per_kg"] == pytest.approx(7700 / (2800 / 6 * 7), abs=0.05)


def test_semana_en_curso_cuenta_solo_los_dias_transcurridos():
    days = {"2026-09-21": day(2000), "2026-09-22": day(2000)}
    s = build_week_summary(start=MONDAY, today=date(2026, 9, 23), days=days, targets=TARGETS, weights={})
    assert s["complete"] is False
    assert s["days_elapsed"] == 3
    assert s["adherence_pct"] == 67


def test_semana_vacia():
    s = build_week_summary(start=MONDAY, today=date(2026, 9, 28), days={}, targets=TARGETS, weights={})
    assert s["logged_days"] == 0 and s["projection"] is None and s["best_day"] is None
    assert s["badges"] == [] and s["vs_previous"] is None


def test_insignias_y_comparacion_con_la_semana_anterior():
    perfect = {f"2026-09-{d}": day(2000) for d in range(21, 28)}
    previous = build_week_summary(
        start=date(2026, 9, 14),
        today=date(2026, 9, 28),
        days={"2026-09-14": day(2600), "2026-09-15": day(2000)},
        targets=TARGETS,
        weights={},
    )
    s = build_week_summary(
        start=MONDAY,
        today=date(2026, 9, 28),
        days=perfect,
        targets=TARGETS,
        weights={"2026-09-15": 81.0, "2026-09-22": 80.4, "2026-09-26": 80.0},
        previous=previous,
    )
    keys = {b["key"] for b in s["badges"]}
    assert {"semana_redonda", "proteina", "constancia", "sin_excesos", "mejora"} <= keys
    assert s["vs_previous"]["avg_kcal"] == 2000 - 2300
    assert s["vs_previous"]["adherence_pct"] == 100 - 14
    assert s["weight"] == {"avg": 80.2, "previous_avg": 81.0, "change": -0.8, "entries": 2}


def test_racha():
    statuses = {
        "2026-09-20": "cumplido",
        "2026-09-21": "cumplido",
        "2026-09-22": "pasado",
        "2026-09-23": "cumplido",
        "2026-09-24": "cumplido",
        "2026-09-25": "cumplido",
    }
    # Hoy (26) aún sin cerrar: la racha de ayer sigue viva.
    assert streak(statuses, date(2026, 9, 26)) == {"current": 3, "best": 3, "today_done": False}
    statuses["2026-09-26"] = "cumplido"
    assert streak(statuses, date(2026, 9, 26)) == {"current": 4, "best": 4, "today_done": True}
    # Un día entero sin cumplir la rompe.
    assert streak(statuses, date(2026, 9, 28))["current"] == 0
    assert streak({}, date(2026, 9, 28)) == {"current": 0, "best": 0, "today_done": False}


def test_racha_no_salta_huecos():
    statuses = {"2026-09-20": "cumplido", "2026-09-22": "cumplido"}
    assert streak(statuses, date(2026, 9, 22))["best"] == 1


def test_media_movil_de_7_dias():
    entries = [("2026-09-01", 80.0), ("2026-09-02", 81.0), ("2026-09-04", 79.0), ("2026-09-10", 78.0)]
    series = moving_average(entries)
    assert [p["avg"] for p in series] == [80.0, 80.5, 80.0, 78.5]
    assert moving_average([]) == []


def test_logros():
    assert evaluate_achievements({}) == set()
    unlocked = evaluate_achievements({"meals": 60, "best_streak": 8, "saved": 12, "weights": 1, "photos": 1})
    assert unlocked == {"primera_comida", "comidas_50", "racha_3", "racha_7", "ahorro_10", "primer_peso", "foto"}
