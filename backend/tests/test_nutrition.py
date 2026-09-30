import pytest

from app.nutrition import (
    MAX_DAILY_DEFICIT,
    MIN_KCAL,
    bmr_mifflin,
    calculate_targets,
    validate_custom_targets,
    weekly_change_kg,
)

BASE = dict(sex="hombre", age=30, weight_kg=80, height_cm=180, activity="moderado")


def codes(plan):
    return {w["code"] for w in plan["warnings"]}


def test_bmr_mifflin_hombre():
    # 10·80 + 6,25·180 − 5·30 + 5
    assert bmr_mifflin("hombre", 80, 180, 30) == pytest.approx(1780)


def test_bmr_mifflin_mujer():
    # 10·60 + 6,25·165 − 5·28 − 161
    assert bmr_mifflin("mujer", 60, 165, 28) == pytest.approx(1330.25)


def test_mantenimiento_es_bmr_por_actividad():
    plan = calculate_targets(**BASE, goal="mantenimiento")
    assert plan["bmr"] == 1780
    assert plan["tdee"] == round(1780 * 1.55)
    assert plan["kcal"] == 2760  # 2759 redondeado a la decena
    assert plan["adjustment_pct"] == pytest.approx(0, abs=0.1)
    assert plan["warnings"] == []


@pytest.mark.parametrize(
    ("goal", "pct"),
    [
        ("definicion_ligera", -15),
        ("definicion_agresiva", -25),
        ("volumen", 7.5),
        ("mantenimiento", 0),
        ("recomposicion", -2.5),
    ],
)
def test_ajuste_por_objetivo(goal, pct):
    plan = calculate_targets(**BASE, goal=goal)
    assert plan["adjustment_pct"] == pytest.approx(pct, abs=0.3)
    assert plan["kcal"] == pytest.approx(1780 * 1.55 * (1 + pct / 100), abs=5)


@pytest.mark.parametrize(
    "goal", ["definicion_ligera", "definicion_agresiva", "volumen", "mantenimiento", "recomposicion"]
)
def test_macros_en_rango_y_suman_las_calorias(goal):
    plan = calculate_targets(**BASE, goal=goal)
    assert 1.8 * 80 <= plan["protein"] <= 2.2 * 80
    assert 0.8 * 80 <= plan["fat"] <= 1.0 * 80
    from_macros = plan["protein"] * 4 + plan["carbs"] * 4 + plan["fat"] * 9
    assert from_macros == pytest.approx(plan["kcal"], abs=4)


def test_recomposicion_lleva_proteina_alta():
    assert calculate_targets(**BASE, goal="recomposicion")["protein"] == round(2.2 * 80)


def test_minimo_calorico_mujer():
    plan = calculate_targets(
        sex="mujer", age=45, weight_kg=50, height_cm=155, activity="sedentario", goal="definicion_agresiva"
    )
    assert plan["kcal"] == MIN_KCAL["mujer"]
    assert "minimo_calorico" in codes(plan)


def test_minimo_calorico_hombre():
    plan = calculate_targets(
        sex="hombre", age=60, weight_kg=58, height_cm=165, activity="sedentario", goal="definicion_agresiva"
    )
    assert plan["kcal"] >= MIN_KCAL["hombre"]


def test_deficit_nunca_supera_el_maximo():
    plan = calculate_targets(
        sex="hombre", age=25, weight_kg=140, height_cm=195, activity="muy_alto", goal="definicion_agresiva"
    )
    assert plan["tdee"] - plan["kcal"] <= MAX_DAILY_DEFICIT + 5
    assert "deficit_maximo" in codes(plan)


def test_bajo_peso_no_permite_deficit():
    plan = calculate_targets(
        sex="mujer", age=25, weight_kg=45, height_cm=170, activity="ligero", goal="definicion_ligera"
    )
    assert "bajo_peso" in codes(plan)
    assert plan["kcal"] == pytest.approx(plan["tdee"], abs=5)


def test_obesidad_usa_peso_de_referencia_para_los_macros():
    plan = calculate_targets(
        sex="hombre", age=40, weight_kg=150, height_cm=175, activity="sedentario", goal="definicion_ligera"
    )
    assert plan["ref_weight_kg"] == pytest.approx(30 * 1.75**2, abs=0.1)
    assert plan["protein"] == round(2.0 * plan["ref_weight_kg"])


def test_hidratos_nunca_negativos():
    plan = calculate_targets(
        sex="mujer", age=50, weight_kg=95, height_cm=150, activity="sedentario", goal="definicion_agresiva"
    )
    assert plan["carbs"] >= 0


def test_menor_de_edad_avisa():
    assert "menor" in codes(calculate_targets(**{**BASE, "age": 16}, goal="mantenimiento"))


def test_peso_objetivo_incoherente_y_semanas():
    plan = calculate_targets(**BASE, goal="definicion_ligera", target_weight_kg=75)
    assert plan["weekly_kg"] < 0
    # −5 kg al ritmo semanal previsto (≈ −0,37 kg/semana)
    assert plan["weeks_to_target"] == pytest.approx(-5 / plan["weekly_kg"], abs=1)
    assert "objetivo_incoherente" in codes(calculate_targets(**BASE, goal="definicion_ligera", target_weight_kg=90))


def test_cambio_semanal_7700_kcal_por_kilo():
    assert weekly_change_kg(1900, 3000) == pytest.approx(-1.0)
    assert weekly_change_kg(2500, 2500) == 0


def test_objetivos_manuales_avisan():
    assert validate_custom_targets(sex="mujer", kcal=1000, tdee_kcal=1900)[0]["code"] == "minimo_calorico"
    assert validate_custom_targets(sex="hombre", kcal=1800, tdee_kcal=3000)[0]["code"] == "deficit_maximo"
    assert validate_custom_targets(sex="hombre", kcal=2600, tdee_kcal=2700) == []
