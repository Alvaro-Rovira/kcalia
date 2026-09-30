"""Cálculo de objetivos en código (sin IA): Mifflin-St Jeor × actividad + ajuste por objetivo."""

from dataclasses import dataclass

KCAL_PER_KG_FAT = 7700
KCAL_PROTEIN = 4
KCAL_CARBS = 4
KCAL_FAT = 9

ACTIVITY_FACTORS: dict[str, float] = {
    "sedentario": 1.2,
    "ligero": 1.375,
    "moderado": 1.55,
    "alto": 1.725,
    "muy_alto": 1.9,
}


@dataclass(frozen=True)
class GoalSpec:
    label: str
    adjustment: float
    protein_gkg: float
    fat_gkg: float


GOALS: dict[str, GoalSpec] = {
    "definicion_ligera": GoalSpec("Definición ligera", -0.15, 2.0, 0.9),
    "definicion_agresiva": GoalSpec("Definición agresiva", -0.25, 2.2, 0.8),
    "volumen": GoalSpec("Volumen", 0.075, 1.8, 1.0),
    "mantenimiento": GoalSpec("Mantenimiento", 0.0, 1.8, 0.9),
    "recomposicion": GoalSpec("Recomposición corporal", -0.025, 2.2, 0.9),
}

MIN_KCAL = {"hombre": 1500, "mujer": 1200}
MAX_DAILY_DEFICIT = 1000
MIN_CARBS_G = 50
MIN_FAT_GKG = 0.6
# Por encima de este IMC la proteína y la grasa se calculan con un peso de referencia,
# no con el peso real, para no proponer cantidades desproporcionadas.
REF_WEIGHT_BMI_CAP = 30.0
UNDERWEIGHT_BMI = 18.5


def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "hombre" else base - 161


def tdee(bmr: float, activity: str) -> float:
    return bmr * ACTIVITY_FACTORS[activity]


def bmi(weight_kg: float, height_cm: float) -> float:
    m = height_cm / 100
    return weight_kg / (m * m)


def reference_weight(weight_kg: float, height_cm: float) -> float:
    m = height_cm / 100
    return min(weight_kg, REF_WEIGHT_BMI_CAP * m * m)


def _round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def _warn(code: str, text: str, level: str = "warn") -> dict:
    return {"code": code, "level": level, "text": text}


def weekly_change_kg(kcal: float, tdee_kcal: float) -> float:
    """Cambio de peso semanal estimado para una ingesta diaria dada."""
    return (kcal - tdee_kcal) * 7 / KCAL_PER_KG_FAT


def calculate_targets(
    *,
    sex: str,
    age: int,
    weight_kg: float,
    height_cm: float,
    activity: str,
    goal: str,
    target_weight_kg: float | None = None,
) -> dict:
    spec = GOALS[goal]
    factor = ACTIVITY_FACTORS[activity]
    bmr = bmr_mifflin(sex, weight_kg, height_cm, age)
    maintenance = bmr * factor
    current_bmi = bmi(weight_kg, height_cm)
    warnings: list[dict] = []

    adjustment = spec.adjustment
    if adjustment < 0 and current_bmi < UNDERWEIGHT_BMI:
        adjustment = 0.0
        warnings.append(
            _warn(
                "bajo_peso",
                "Tu IMC está por debajo de 18,5. No es recomendable un déficit, así que el plan "
                "se ha calculado en mantenimiento. Coméntalo con un profesional sanitario.",
                "danger",
            )
        )

    kcal = maintenance * (1 + adjustment)

    if maintenance - kcal > MAX_DAILY_DEFICIT:
        kcal = maintenance - MAX_DAILY_DEFICIT
        warnings.append(
            _warn(
                "deficit_maximo",
                f"El déficit se ha limitado a {MAX_DAILY_DEFICIT} kcal al día: ir más allá "
                "compromete la masa muscular y es difícil de sostener.",
            )
        )

    floor = MIN_KCAL[sex]
    if kcal < floor:
        kcal = floor
        warnings.append(
            _warn(
                "minimo_calorico",
                f"El cálculo quedaba por debajo de {floor} kcal, el mínimo razonable sin "
                "supervisión profesional, así que se ha ajustado a ese valor.",
            )
        )

    kcal_target = _round_to(kcal, 10)

    ref_weight = reference_weight(weight_kg, height_cm)
    protein = round(spec.protein_gkg * ref_weight)
    fat_gkg = spec.fat_gkg
    fat = round(fat_gkg * ref_weight)
    carbs = (kcal_target - protein * KCAL_PROTEIN - fat * KCAL_FAT) / KCAL_CARBS

    if carbs < MIN_CARBS_G:
        fat_gkg = MIN_FAT_GKG
        fat = round(fat_gkg * ref_weight)
        carbs = (kcal_target - protein * KCAL_PROTEIN - fat * KCAL_FAT) / KCAL_CARBS
        warnings.append(
            _warn(
                "hidratos_bajos",
                "Con estas calorías queda poco margen para hidratos; se ha reducido la grasa "
                "al mínimo saludable para darles algo de espacio.",
                "info",
            )
        )
    carbs = max(0, round(carbs))

    if kcal_target < bmr:
        warnings.append(
            _warn(
                "bajo_basal",
                "El objetivo queda por debajo de tu metabolismo basal. Puede valer durante "
                "unas semanas, pero no lo mantengas mucho tiempo.",
                "info",
            )
        )
    if age < 18:
        warnings.append(
            _warn(
                "menor",
                "Estas fórmulas están pensadas para adultos. Si estás en edad de crecimiento, "
                "consulta con un profesional antes de restringir calorías.",
            )
        )
    if target_weight_kg is not None:
        if bmi(target_weight_kg, height_cm) < UNDERWEIGHT_BMI:
            warnings.append(
                _warn(
                    "objetivo_bajo",
                    "Tu peso objetivo corresponde a un IMC inferior a 18,5. Plantéate un objetivo algo más alto.",
                )
            )
        if adjustment < 0 and target_weight_kg > weight_kg + 0.5:
            warnings.append(
                _warn(
                    "objetivo_incoherente",
                    "Tu peso objetivo es mayor que el actual, pero el plan es de déficit. Revisa uno de los dos.",
                    "info",
                )
            )
        if adjustment > 0 and target_weight_kg < weight_kg - 0.5:
            warnings.append(
                _warn(
                    "objetivo_incoherente",
                    "Tu peso objetivo es menor que el actual, pero el plan es de superávit. Revisa uno de los dos.",
                    "info",
                )
            )

    maintenance_r = round(maintenance)
    weekly_kg = weekly_change_kg(kcal_target, maintenance)
    weeks_to_target = None
    if target_weight_kg is not None and abs(weekly_kg) >= 0.05:
        delta = target_weight_kg - weight_kg
        if delta * weekly_kg > 0:
            weeks_to_target = round(delta / weekly_kg)

    effective_pct = round((kcal_target / maintenance - 1) * 100, 1)
    return {
        "kcal": kcal_target,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "bmr": round(bmr),
        "tdee": maintenance_r,
        "activity_factor": factor,
        "adjustment_pct": effective_pct,
        "protein_gkg": spec.protein_gkg,
        "fat_gkg": fat_gkg,
        "ref_weight_kg": round(ref_weight, 1),
        "bmi": round(current_bmi, 1),
        "weekly_kg": round(weekly_kg, 2),
        "weeks_to_target": weeks_to_target,
        "goal_label": spec.label,
        "warnings": warnings,
    }


def validate_custom_targets(*, sex: str, kcal: int, tdee_kcal: int) -> list[dict]:
    """Avisos para objetivos introducidos a mano. No bloquea: informa."""
    warnings: list[dict] = []
    floor = MIN_KCAL[sex]
    if kcal < floor:
        warnings.append(
            _warn(
                "minimo_calorico",
                f"{kcal} kcal está por debajo de {floor} kcal, el mínimo razonable sin supervisión profesional.",
                "danger",
            )
        )
    elif tdee_kcal - kcal > MAX_DAILY_DEFICIT:
        warnings.append(
            _warn(
                "deficit_maximo",
                f"Supone un déficit de más de {MAX_DAILY_DEFICIT} kcal al día, difícil de sostener sin perder músculo.",
            )
        )
    elif kcal < tdee_kcal * 0.75:
        warnings.append(_warn("deficit_alto", "Es un déficit superior al 25 %: mejor no alargarlo."))
    return warnings
