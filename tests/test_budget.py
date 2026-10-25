from budget import calculate_budget

def test_budget_and_constraint():
    b=calculate_budget(3, travelers=2, style="budget", cities=2, total_budget=1000, scope="group")
    assert b["group_total"] > 0 and b["over_budget"]
    assert b["per_person"] * 2 == b["group_total"]
