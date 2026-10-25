from planner import plan_itinerary, compare_routes, validate_itinerary

def test_multicity_itinerary_and_routes():
    p=plan_itinerary(["Jaipur","Jodhpur","Udaipur"], 6)
    assert len(p["itinerary"]) == 6
    assert compare_routes(p["cities"])["transfers"] == 2
    assert "warnings" in validate_itinerary(p["itinerary"])
