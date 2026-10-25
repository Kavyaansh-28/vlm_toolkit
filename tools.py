"""Safe allow-listed tools for the Rajasthan travel agent — expanded with real data."""
from __future__ import annotations
import os, requests
from retrieval import retrieve_knowledge
from ingestion import load_documents
from budget import calculate_budget
from planner import compare_routes, validate_itinerary


# ── Helpers ───────────────────────────────────────────────────────────────────

def _docs():
    """Cached document accessor."""
    if not hasattr(_docs, "_cache"):
        _docs._cache = load_documents()
    return _docs._cache


def _filter_docs(category=None, destination=None, extra_fields=None):
    """Filter documents by category and/or destination."""
    results = []
    for d in _docs():
        if category and d.get("category", "").lower() != category.lower():
            continue
        if destination and destination.lower() not in d.get("destination", "").lower():
            continue
        if extra_fields:
            if not all(d.get(k) for k in extra_fields):
                continue
        results.append(d)
    return results


# ── Hotels ────────────────────────────────────────────────────────────────────

def search_hotels(city: str, tier: str = "all", top_k: int = 3) -> dict:
    """
    Return seeded hotel reference records for a city. Values are illustrative and are not live listings.
    """
    if os.getenv("GOOGLE_PLACES_API_KEY"):
        live = search_places("hotels", city)
        if live.get("source") == "Google Places":
            places = live.get("results", [])[:top_k]
            hostel_search = search_places("hostels and backpacker hostels", city)
            hostels = hostel_search.get("results", [])[:top_k] if hostel_search.get("source") == "Google Places" else []
            return {"source": "Google Places live search", "city": city, "hotels": [{"name": p.get("displayName", {}).get("text", "Hotel"), "address": p.get("formattedAddress"), "text": "Place listing from Google. Room availability, price and booking terms are not provided."} for p in places], "hostels": [{"name": p.get("displayName", {}).get("text", "Hostel"), "address": p.get("formattedAddress"), "text": "Hostel place listing. Dorm/room availability and prices are not provided."} for p in hostels], "notice": "Live place listings only; room availability and prices are not provided."}
    hotels = _filter_docs(category="hotel", destination=city)
    hostels = [h for h in hotels if "zostel" in h.get("name", "").lower() or "hostel" in h.get("name", "").lower()]
    hotels = [h for h in hotels if h not in hostels]
    if not hotels:
        # fallback guidance
        return {
            "source": "planning guidance",
            "city": city,
            "hotels": [],
            "guidance": _hotel_guidance(city, tier),
            "notice": "No specific hotel data available for this city yet; general guidance shown."
        }

    if tier != "all":
        filtered = [h for h in hotels if h.get("tier", "").lower() == tier.lower()]
        if filtered:
            hotels = filtered

    # Stable name ordering; local fixture ratings are not live-verified.
    hotels = sorted(hotels, key=lambda h: h.get("name", "").casefold())[:top_k]

    formatted = []
    for h in hotels:
        formatted.append({
            "name": h.get("name"),
            "tier": h.get("tier"),
            "price_per_night": f"₹{h.get('price_per_night_inr', 0):,}",
            "address": h.get("address"),
            "area": h.get("area"),
            "amenities": h.get("amenities", []),
            "check_in": h.get("check_in"),
            "check_out": h.get("check_out"),
            "dietary_options": h.get("dietary_options"),
            "travel_times": h.get("travel_time_to_attractions", {}),
            "text": "Illustrative property reference. Verify property identity, amenities, address, price and availability directly.",
        })

    return {
        "source": "illustrative local reference data",
        "city": city,
        "hotels": formatted,
        "hostels": [{"name": h.get("name"), "address": h.get("address"), "tier": h.get("tier"), "text": "Illustrative hostel reference; verify current details and availability directly."} for h in hostels[:top_k]],
        "guidance": _hotel_guidance(city, tier),
        "notice": "Illustrative local reference data only. Prices, ratings, amenities, addresses and availability are not live-verified; verify directly before relying on them."
    }


def _hotel_guidance(city: str, tier: str) -> str:
    tiers = {
        "budget": "For hotels, compare guesthouses and budget properties by location, recent reviews, cooling/heating, and cancellation terms. Hostels are listed separately; compare dorm/private-room options and rules directly.",
        "mid-range": "For mid-range: prioritize well-reviewed hotels in the main tourist area — compare breakfast inclusion, pickup convenience, and recent reviews. Heritage-style properties offer great value.",
        "luxury": "For luxury: heritage palaces and boutique properties offer unique experiences beyond standard 5-stars. Compare by location, inclusions, and current reviews — not brand name alone.",
        "all": "Compare stays across tiers by location, recent reviews, and inclusions. Consider heritage properties for a uniquely Rajasthani experience.",
    }
    city_note = ""
    if city.lower() in {"ranthambore", "sawai madhopur"}:
        city_note = " For Ranthambore: confirm safari zone and reporting point before booking — proximity matters enormously."
    elif city.lower() == "jaisalmer":
        city_note = " In Jaisalmer: staying inside or near the fort is atmospheric; Sam Road hotels are better for desert access."
    return tiers.get(tier, tiers["all"]) + city_note


# ── Restaurants ───────────────────────────────────────────────────────────────

def search_restaurants(city: str, cuisine: str = None, dietary: str = None, top_k: int = 3) -> dict:
    """
    Return seeded restaurant reference records. Values are illustrative and are not live listings.
    """
    if os.getenv("GOOGLE_PLACES_API_KEY"):
        live = search_places("restaurants", city)
        if live.get("source") == "Google Places":
            places = live.get("results", [])[:top_k]
            return {"source": "Google Places live search", "city": city, "results": [{"name": p.get("displayName", {}).get("text", "Restaurant"), "address": p.get("formattedAddress"), "text": "Current place listing. Check today's opening hours, menu and dietary preparation directly."} for p in places], "notice": "Live place listings only; hours, menus and dietary preparation are not verified."}
    restaurants = _filter_docs(category="restaurant", destination=city)

    if cuisine:
        restaurants = [r for r in restaurants if cuisine.lower() in r.get("cuisine", "").lower() + r.get("text", "").lower()]
    if dietary:
        restaurants = [r for r in restaurants if dietary.lower() in r.get("dietary", "").lower() + r.get("text", "").lower()]

    restaurants = sorted(restaurants, key=lambda r: r.get("name", "").casefold())[:top_k]

    if not restaurants:
        return {
            "source": "planning guidance",
            "city": city,
            "results": [],
            "notice": f"No specific restaurant data for {city}. Seek a well-reviewed local thali restaurant near your stay. Confirm dietary needs directly."
        }

    formatted = []
    for r in restaurants:
        formatted.append({
            "name": r.get("name"),
            "cuisine": r.get("cuisine"),
            "dietary": r.get("dietary"),
            "price_level": r.get("price_level"),
            "avg_meal_inr": r.get("avg_meal_inr"),
            "address": r.get("address"),
            "hours": r.get("hours"),
            "famous_for": r.get("famous_for", []),
            "text": "Illustrative venue reference. Verify menus, opening hours, prices, venue details and dietary preparation directly.",
        })

    return {
        "source": "illustrative local reference data",
        "city": city,
        "results": formatted,
        "notice": "Illustrative local reference data only. Ratings, menus, hours and prices are not live-verified. Confirm current details and dietary preparation directly."
    }


# ── Attractions ───────────────────────────────────────────────────────────────

def search_attractions(city: str, category: str = None, top_k: int = 4) -> dict:
    """
    Return locally curated attraction guidance; time-sensitive details require verification.
    """
    if os.getenv("GOOGLE_PLACES_API_KEY"):
        live = search_places("tourist attractions", city)
        if live.get("source") == "Google Places":
            places = live.get("results", [])[:top_k]
            return {"source": "Google Places live search", "city": city, "attractions": [{"name": p.get("displayName", {}).get("text", "Place"), "address": p.get("formattedAddress"), "status": "Place listing only; access, fees and operating hours are not verified."} for p in places], "notice": "Live place listings only; confirm official access details before visiting."}
    attractions = [d for d in _docs() if d.get("destination", "").lower() == city.lower()
                   and d.get("category") not in {"hotel", "restaurant", "accommodation", "general", "planning guidance"}]

    if category:
        attractions = [a for a in attractions if category.lower() in a.get("category", "").lower()]

    attractions = sorted(attractions, key=lambda a: (a.get("title") or a.get("name", "")).casefold())[:top_k]

    formatted = []
    for a in attractions:
        formatted.append({
            "name": a.get("title") or a.get("name"),
            "category": a.get("category"),
            "entry_fee_indian": f"₹{a.get('entry_fee_inr', 0)}",
            "entry_fee_foreigner": f"₹{a.get('entry_fee_foreigner_inr', 0)}",
            "timings": a.get("timings"),
            "best_time": a.get("best_time"),
            "duration_hours": a.get("duration_hours"),
            "highlights": a.get("highlights", []),
            "tips": a.get("tips", []),
            "status": "Verify current access and operating status with an official source.",
        })

    return {
        "source": "curated local reference data",
        "city": city,
        "attractions": formatted,
        "notice": "Locally curated reference data. Entry fees, timings and access are not live-verified; check current official guidance."
    }


# ── Cab / Transport ───────────────────────────────────────────────────────────

INTERCITY_ROUTES = {
    ("Jaipur", "Udaipur"): {"distance_km": 393, "road_hours": 6, "train_hours": 7, "cab_inr": 3500, "bus_inr": 400, "train_inr": 350},
    ("Jaipur", "Jodhpur"): {"distance_km": 345, "road_hours": 5, "train_hours": 4.5, "cab_inr": 3000, "bus_inr": 350, "train_inr": 280},
    ("Jaipur", "Jaisalmer"): {"distance_km": 575, "road_hours": 8, "train_hours": 10, "cab_inr": 5000, "bus_inr": 550, "train_inr": 400},
    ("Jaipur", "Pushkar"): {"distance_km": 146, "road_hours": 2.5, "train_hours": None, "cab_inr": 1500, "bus_inr": 150, "train_inr": None},
    ("Jaipur", "Ranthambore"): {"distance_km": 180, "road_hours": 3, "train_hours": 2, "cab_inr": 1800, "bus_inr": None, "train_inr": 200},
    ("Jaipur", "Mount Abu"): {"distance_km": 490, "road_hours": 7.5, "train_hours": 8, "cab_inr": 4500, "bus_inr": 500, "train_inr": 380},
    ("Udaipur", "Jodhpur"): {"distance_km": 270, "road_hours": 4.5, "train_hours": 6, "cab_inr": 2800, "bus_inr": 300, "train_inr": 260},
    ("Udaipur", "Mount Abu"): {"distance_km": 185, "road_hours": 3, "train_hours": None, "cab_inr": 2000, "bus_inr": 200, "train_inr": None},
    ("Jodhpur", "Jaisalmer"): {"distance_km": 285, "road_hours": 4.5, "train_hours": 5.5, "cab_inr": 2800, "bus_inr": 280, "train_inr": 250},
    ("Jodhpur", "Bikaner"): {"distance_km": 250, "road_hours": 4, "train_hours": 5, "cab_inr": 2500, "bus_inr": 250, "train_inr": 220},
    ("Ranthambore", "Jaipur"): {"distance_km": 180, "road_hours": 3, "train_hours": 2, "cab_inr": 1800, "bus_inr": None, "train_inr": 200},
    ("Ranthambore", "Agra"): {"distance_km": 250, "road_hours": 4, "train_hours": 3.5, "cab_inr": 2500, "bus_inr": None, "train_inr": 280},
}

def get_cab_rates(from_city: str, to_city: str) -> dict:
    """Return intercity transport options and costs."""
    key = (from_city, to_city)
    rev_key = (to_city, from_city)
    route = INTERCITY_ROUTES.get(key) or INTERCITY_ROUTES.get(rev_key)

    if not route:
        return {
            "from": from_city, "to": to_city,
            "message": f"No specific route data for {from_city} → {to_city}. Approximate private cab: ₹15-18/km. Verify current options.",
            "source": "planning guidance"
        }

    options = []
    if route.get("train_inr"):
        options.append({"mode": "Train", "duration": f"{route['train_hours']} hrs", "cost": f"₹{route['train_inr']}–{route['train_inr']*2} (sleeper to AC)", "book_at": "irctc.co.in"})
    options.append({"mode": "Private Cab (AC)", "duration": f"{route['road_hours']} hrs", "cost": f"₹{route['cab_inr']:,}", "book_at": "Hotel desk, Ola, local operators"})
    if route.get("bus_inr"):
        options.append({"mode": "Rajasthan State Bus / Volvo", "duration": f"{route['road_hours']+0.5} hrs", "cost": f"₹{route['bus_inr']}–{int(route['bus_inr']*2.5)}", "book_at": "rsrtc.rajasthan.gov.in or bus stand"})

    return {
        "from": from_city, "to": to_city,
        "distance_km": route["distance_km"],
        "options": options,
        "recommendation": "Train is most comfortable and punctual for longer routes. Cab offers flexibility for multi-stop days.",
        "notice": "Prices are estimates — verify current fares before booking.",
        "source": "local transport knowledge"
    }


def get_transport_options(from_city: str, to_city: str) -> dict:
    """Return known planning estimates without implying live timetables or fares."""
    def title(value: str) -> str:
        return " ".join(word.capitalize() for word in value.strip().split())

    origin, destination = title(from_city), title(to_city)
    route = get_cab_rates(origin, destination)
    return {
        "from": origin,
        "to": destination,
        "options": route.get("options", []),
        "flight": {"status": "provider_required", "message": "Flight schedules and fares are not connected yet; check a flight booking provider for live options."},
        "notice": route.get("notice") or route.get("message") or "No route-specific estimates are available. Check current schedules and fares with the operator.",
        "source": route.get("source", "planning guidance"),
        "live_schedules": False,
    }


# ── Accommodation (legacy wrapper) ───────────────────────────────────────────

def search_accommodation(city: str, style: str = "balanced") -> dict:
    """Legacy wrapper — delegates to search_hotels with tier mapping."""
    tier_map = {"budget": "budget", "balanced": "mid-range", "premium": "luxury"}
    tier = tier_map.get(style.lower(), "all")
    return search_hotels(city, tier=tier)


# ── Ranking ──────────────────────────────────────────────────────────────────

def rank_recommendations(items: list, preferences: str = None) -> list:
    """Rank a list of items against user preferences."""
    if not preferences:
        return items
    pref_words = [w for w in preferences.lower().split() if len(w) > 2]
    ranked = []
    for item in items:
        text = " ".join(str(v) for v in item.values()).lower()
        score = sum(1 for w in pref_words if w in text)
        ranked.append({**item, "match_score": score, "why": "Matches your stated preferences."})
    return sorted(ranked, key=lambda x: x["match_score"], reverse=True)


# ── Live Places (Google) ─────────────────────────────────────────────────────

def search_places(query: str, city: str = None) -> dict:
    """Try Google Places API; fall back to local data if unconfigured."""
    key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:
        local = [d for d in _docs() if
                 (not city or d.get("destination", "").lower() == city.lower()) and
                 query.lower() in (d.get("title", "") + d.get("text", "")).lower()][:5]
        return {"source": "local fallback", "results": [{k: d.get(k) for k in ("title", "name", "destination", "category", "text", "source_type", "source_url")} for d in local], "notice": "Google Places not configured; showing illustrative local reference data."}
    try:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.displayName,places.formattedAddress"},
            json={"textQuery": f"{query} {city or 'Rajasthan'}"},
            timeout=8
        )
        r.raise_for_status()
        return {"source": "Google Places", "results": r.json().get("places", [])}
    except requests.RequestException as e:
        local = [d for d in _docs() if (not city or d.get("destination", "").lower() == city.lower()) and query.lower() in (d.get("title", "") + d.get("text", "")).lower()][:5]
        safe = [{k: d.get(k) for k in ("title", "name", "destination", "category", "text", "source_type", "source_url")} for d in local]
        return {"source": "local fallback", "results": safe, "notice": f"Live search unavailable ({e.__class__.__name__}); showing illustrative local reference data."}


# ── Budget ────────────────────────────────────────────────────────────────────

def estimate_travel_costs(*args, **kwargs):
    return calculate_budget(*args, **kwargs)
