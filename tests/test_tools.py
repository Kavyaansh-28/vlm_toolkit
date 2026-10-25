from tools import search_places, search_restaurants, rank_recommendations, get_transport_options, search_hotels

def test_local_fallback_and_ranking(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    assert search_places("fort", "Jaipur")["source"] == "local fallback"
    result=search_restaurants("Udaipur")
    assert result["results"]
    assert "match_score" in rank_recommendations(result["results"], "lake vegetarian")[0]


def test_seeded_hotel_data_does_not_expose_unverified_reviews(monkeypatch):
    from tools import search_hotels

    rows = search_hotels("Jaipur", tier="luxury")["hotels"]
    assert rows
    assert all("rating" not in row and "review_count" not in row and "top_review" not in row for row in rows)
    assert "not live-verified" in search_hotels("Jaipur", tier="luxury")["notice"]


def test_hostels_are_separate_from_hotels_and_transport_is_labeled_as_estimate(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    lodging = search_hotels("Jaipur")
    assert all("zostel" not in row["name"].lower() for row in lodging["hotels"])
    assert any("zostel" in row["name"].lower() for row in lodging["hostels"])
    route = get_transport_options("Jaipur", "Udaipur")
    assert {option["mode"] for option in route["options"]} >= {"Train", "Private Cab (AC)"}
    assert route["live_schedules"] is False
    assert route["flight"]["status"] == "provider_required"
