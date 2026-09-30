"""Resumen semanal, proyección, racha, logros y media móvil de peso. Todo en código, sin IA."""

from datetime import date, timedelta

from .nutrition import KCAL_PER_KG_FAT

ON_TARGET_TOLERANCE = 0.10
PROTEIN_TOLERANCE = 0.10


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def week_start(day: date) -> date:
    """Lunes de la semana de `day` (la semana empieza en lunes)."""
    return day - timedelta(days=day.weekday())


def day_status(kcal: float, target_kcal: float) -> str:
    if kcal < target_kcal * (1 - ON_TARGET_TOLERANCE):
        return "bajo"
    if kcal > target_kcal * (1 + ON_TARGET_TOLERANCE):
        return "pasado"
    return "cumplido"


def protein_met(protein: float, target_protein: float) -> bool:
    return protein >= target_protein * (1 - PROTEIN_TOLERANCE)


def project(avg_daily_balance: float) -> dict:
    """Proyección con ≈7.700 kcal = 1 kg de grasa."""
    weekly_kcal = avg_daily_balance * 7
    weekly_kg = weekly_kcal / KCAL_PER_KG_FAT
    if abs(weekly_kcal) < 350:
        return {"weekly_kg": round(weekly_kg, 2), "weeks_per_kg": None, "direction": "estable"}
    return {
        "weekly_kg": round(weekly_kg, 2),
        "weeks_per_kg": round(KCAL_PER_KG_FAT / abs(weekly_kcal), 1),
        "direction": "perdida" if weekly_kcal < 0 else "ganancia",
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_week_summary(
    *,
    start: date,
    today: date,
    days: dict[str, dict],
    targets: dict,
    weights: dict[str, float],
    previous: dict | None = None,
) -> dict:
    """`days`: fecha ISO -> {kcal, protein, carbs, fat, meals}. `weights`: fecha ISO -> kg."""
    target_kcal, tdee = targets["kcal"], targets["tdee"]
    end = start + timedelta(days=6)
    elapsed = max(0, min(7, (today - start).days + 1))

    rows = []
    for offset in range(7):
        current = start + timedelta(days=offset)
        raw = days.get(current.isoformat())
        logged = bool(raw and raw.get("meals", 0) > 0)
        row = {
            "date": current.isoformat(),
            "logged": logged,
            "kcal": round(raw["kcal"]) if logged else 0,
            "protein": round(raw["protein"]) if logged else 0,
            "carbs": round(raw["carbs"]) if logged else 0,
            "fat": round(raw["fat"]) if logged else 0,
            "status": day_status(raw["kcal"], target_kcal) if logged else "sin_registro",
            "balance": round(raw["kcal"] - tdee) if logged else 0,
            "protein_met": protein_met(raw["protein"], targets["protein"]) if logged else False,
        }
        rows.append(row)

    logged_rows = [r for r in rows if r["logged"]]
    n = len(logged_rows)
    on_target = sum(r["status"] == "cumplido" for r in logged_rows)
    balance_total = sum(r["balance"] for r in logged_rows)
    avg_balance = balance_total / n if n else 0.0

    best = worst = None
    if logged_rows:
        by_distance = sorted(logged_rows, key=lambda r: abs(r["kcal"] - target_kcal))
        best = {
            "date": by_distance[0]["date"],
            "kcal": by_distance[0]["kcal"],
            "diff": by_distance[0]["kcal"] - target_kcal,
        }
        if n > 1:
            worst = {
                "date": by_distance[-1]["date"],
                "kcal": by_distance[-1]["kcal"],
                "diff": by_distance[-1]["kcal"] - target_kcal,
            }

    week_weights = [weights[d] for d in sorted(weights) if start.isoformat() <= d <= end.isoformat()]
    prev_start = start - timedelta(days=7)
    prev_weights = [weights[d] for d in sorted(weights) if prev_start.isoformat() <= d < start.isoformat()]
    weight_avg, prev_weight_avg = _mean(week_weights), _mean(prev_weights)
    weight = {
        "avg": round(weight_avg, 2) if weight_avg is not None else None,
        "previous_avg": round(prev_weight_avg, 2) if prev_weight_avg is not None else None,
        "change": round(weight_avg - prev_weight_avg, 2)
        if weight_avg is not None and prev_weight_avg is not None
        else None,
        "entries": len(week_weights),
    }

    summary = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "complete": today > end,
        "days": rows,
        "days_elapsed": elapsed,
        "logged_days": n,
        "on_target_days": on_target,
        "deficit_days": sum(r["balance"] < 0 for r in logged_rows),
        "surplus_days": sum(r["balance"] > 0 for r in logged_rows),
        "over_target_days": sum(r["status"] == "pasado" for r in logged_rows),
        "protein_days": sum(r["protein_met"] for r in logged_rows),
        "total_kcal": sum(r["kcal"] for r in logged_rows),
        "avg_kcal": round(sum(r["kcal"] for r in logged_rows) / n) if n else 0,
        "avg_protein": round(sum(r["protein"] for r in logged_rows) / n) if n else 0,
        "avg_carbs": round(sum(r["carbs"] for r in logged_rows) / n) if n else 0,
        "avg_fat": round(sum(r["fat"] for r in logged_rows) / n) if n else 0,
        "balance_total": balance_total,
        "adherence_pct": round(on_target / elapsed * 100) if elapsed else 0,
        "projection": project(avg_balance) if n else None,
        "best_day": best,
        "worst_day": worst,
        "weight": weight,
        "targets": {k: targets[k] for k in ("kcal", "protein", "carbs", "fat", "tdee")},
    }
    summary["vs_previous"] = _compare(summary, previous)
    summary["badges"] = _badges(summary)
    return summary


def _compare(current: dict, previous: dict | None) -> dict | None:
    if not previous or not previous.get("logged_days") or not current["logged_days"]:
        return None
    return {
        "avg_kcal": current["avg_kcal"] - previous["avg_kcal"],
        "avg_protein": current["avg_protein"] - previous["avg_protein"],
        "adherence_pct": current["adherence_pct"] - previous["adherence_pct"],
        "balance_total": current["balance_total"] - previous["balance_total"],
        "logged_days": current["logged_days"] - previous["logged_days"],
    }


def _badges(s: dict) -> list[dict]:
    badges = []
    if s["on_target_days"] == 7:
        badges.append({"key": "semana_redonda", "label": "Semana redonda", "tone": "kcal"})
    elif s["on_target_days"] >= 5:
        badges.append(
            {"key": "buena_semana", "label": f"Objetivo cumplido {s['on_target_days']}/7 días", "tone": "kcal"}
        )
    if s["protein_days"] >= 5:
        badges.append({"key": "proteina", "label": f"Proteína cumplida {s['protein_days']}/7 días", "tone": "protein"})
    if s["logged_days"] == 7:
        badges.append({"key": "constancia", "label": "Siete de siete registrados", "tone": "neutral"})
    if s["logged_days"] >= 5 and s["over_target_days"] == 0:
        badges.append({"key": "sin_excesos", "label": "Ni un día pasado", "tone": "carbs"})
    comparison = s.get("vs_previous")
    if comparison and comparison["adherence_pct"] > 0:
        badges.append({"key": "mejora", "label": "Mejor que la semana pasada", "tone": "fat"})
    return badges


def streak(statuses: dict[str, str], today: date) -> dict:
    """Días seguidos cumpliendo el objetivo. El día en curso no rompe la racha."""

    def run_ending(day: date) -> int:
        count = 0
        while statuses.get(day.isoformat()) == "cumplido":
            count += 1
            day -= timedelta(days=1)
        return count

    today_done = statuses.get(today.isoformat()) == "cumplido"
    current = run_ending(today) if today_done else run_ending(today - timedelta(days=1))

    best = run = 0
    previous: date | None = None
    for iso in sorted(statuses):
        day = parse_date(iso)
        if statuses[iso] == "cumplido":
            run = run + 1 if previous and (day - previous).days == 1 else 1
            previous = day
            best = max(best, run)
        else:
            run, previous = 0, None
    return {"current": current, "best": max(best, current), "today_done": today_done}


def moving_average(entries: list[tuple[str, float]], window: int = 7) -> list[dict]:
    """Media de las pesadas de los últimos `window` días naturales, para suavizar el ruido diario."""
    ordered = sorted(entries)
    parsed = [(parse_date(d), kg) for d, kg in ordered]
    out = []
    for index, (day, kg) in enumerate(parsed):
        since = day - timedelta(days=window - 1)
        window_values = [v for d, v in parsed[: index + 1] if d >= since]
        out.append(
            {"date": day.isoformat(), "kg": round(kg, 2), "avg": round(sum(window_values) / len(window_values), 2)}
        )
    return out


ACHIEVEMENTS: list[dict] = [
    {"key": "primera_comida", "title": "Primer bocado", "text": "Registra tu primera comida", "icon": "utensils"},
    {"key": "comidas_50", "title": "Medio centenar", "text": "Registra 50 comidas", "icon": "notebook"},
    {"key": "comidas_250", "title": "Libro de cocina", "text": "Registra 250 comidas", "icon": "book"},
    {"key": "racha_3", "title": "Buen arranque", "text": "3 días seguidos en objetivo", "icon": "flame"},
    {"key": "racha_7", "title": "Semana de fuego", "text": "7 días seguidos en objetivo", "icon": "flame"},
    {"key": "racha_30", "title": "Imparable", "text": "30 días seguidos en objetivo", "icon": "flame"},
    {
        "key": "semana_redonda",
        "title": "Semana redonda",
        "text": "7 de 7 días en objetivo en una semana",
        "icon": "trophy",
    },
    {
        "key": "proteina_5",
        "title": "Proteína al día",
        "text": "Cumple la proteína 5 días de una semana",
        "icon": "beef",
    },
    {"key": "primer_peso", "title": "A la báscula", "text": "Registra tu primer peso", "icon": "scale"},
    {"key": "peso_10", "title": "Con los pies en la báscula", "text": "Registra 10 pesadas", "icon": "scale"},
    {"key": "meta_peso", "title": "Meta alcanzada", "text": "Llega a tu peso objetivo", "icon": "target"},
    {"key": "ahorro_10", "title": "Memoria de elefante", "text": "Ahorra 10 consultas a la IA", "icon": "zap"},
    {"key": "ahorro_100", "title": "Ahorrador nato", "text": "Ahorra 100 consultas a la IA", "icon": "piggy"},
    {"key": "favorito", "title": "Lo de siempre", "text": "Marca una comida como favorita", "icon": "star"},
    {"key": "foto", "title": "Ojo clínico", "text": "Registra una comida con una foto", "icon": "camera"},
    {"key": "voz", "title": "De viva voz", "text": "Registra una comida dictándola", "icon": "mic"},
]


def evaluate_achievements(stats: dict) -> set[str]:
    """`stats`: meals, best_streak, weeks (resúmenes), weights, saved, favorites, photos, voice, target_reached."""
    unlocked = set()
    rules = {
        "primera_comida": stats.get("meals", 0) >= 1,
        "comidas_50": stats.get("meals", 0) >= 50,
        "comidas_250": stats.get("meals", 0) >= 250,
        "racha_3": stats.get("best_streak", 0) >= 3,
        "racha_7": stats.get("best_streak", 0) >= 7,
        "racha_30": stats.get("best_streak", 0) >= 30,
        "semana_redonda": stats.get("max_on_target_week", 0) >= 7,
        "proteina_5": stats.get("max_protein_week", 0) >= 5,
        "primer_peso": stats.get("weights", 0) >= 1,
        "peso_10": stats.get("weights", 0) >= 10,
        "meta_peso": bool(stats.get("target_reached")),
        "ahorro_10": stats.get("saved", 0) >= 10,
        "ahorro_100": stats.get("saved", 0) >= 100,
        "favorito": stats.get("favorites", 0) >= 1,
        "foto": stats.get("photos", 0) >= 1,
        "voz": stats.get("voice", 0) >= 1,
    }
    for key, ok in rules.items():
        if ok:
            unlocked.add(key)
    return unlocked
