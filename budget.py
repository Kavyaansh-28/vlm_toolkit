"""Transparent deterministic estimates; values are planning assumptions, not quotes."""
def calculate_budget(days, travelers=1, style="balanced", cities=1, total_budget=None, scope="per person"):
    days, travelers, cities = max(1, int(days)), max(1, int(travelers)), max(1, int(cities))
    profiles = {"budget": (1200, 700, 300, 500), "balanced": (3000, 1200, 600, 900), "premium": (7000, 2500, 1300, 1800)}
    stay, food, local, activities = profiles.get(style.lower(), profiles["balanced"])
    per = {"Accommodation": stay * days, "Food": food * days, "Local transport": local * days,
           "Attractions & experiences": activities * days, "Intercity transport": max(0, cities-1) * 1600,
           "Contingency": 0}
    per["Contingency"] = round(sum(per.values()) * .10)
    per_total = sum(per.values()); group_total = per_total * travelers
    cap = float(total_budget) if total_budget else None
    applicable_total = cap if scope.lower() == "group" else (cap * travelers if cap else None)
    return {"per_person": per_total, "group_total": group_total, "breakdown_per_person": per,
            "budget_limit_total": applicable_total, "over_budget": bool(applicable_total and group_total > applicable_total),
            "note": "Planning estimates in INR, not live quotes or ticket prices."}
