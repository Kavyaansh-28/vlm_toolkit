"""Full-featured Rajasthan travel agent — like a real human travel agent."""
from __future__ import annotations
import re
from datetime import date
from retrieval import retrieve_knowledge
from planner import plan_itinerary, compare_routes, validate_itinerary, CITY_STOPS
from tools import (
    search_restaurants, search_hotels, search_attractions,
    get_cab_rates, rank_recommendations, search_accommodation, search_places
)


class RajasthanAgent:
    def __init__(self):
        self.max_calls = 16

    def _cities(self, text: str, existing=None) -> list:
        lowered = text.lower()
        aliases = {
            "Jaipur": ["जयपुर"], "Udaipur": ["उदयपुर"], "Jodhpur": ["जोधपुर"],
            "Jaisalmer": ["जैसलमेर"], "Pushkar": ["पुष्कर"], "Ranthambore": ["रणथंभौर", "रणथम्बोर"],
            "Sawai Madhopur": ["सवाई माधोपुर"], "Mount Abu": ["माउंट आबू"], "Bikaner": ["बीकानेर"], "Ajmer": ["अजमेर"],
        }
        found_at = []
        for city in CITY_STOPS:
            positions = [lowered.find(alias.lower()) for alias in [city, *aliases.get(city, [])] if lowered.find(alias.lower()) >= 0]
            if positions:
                found_at.append((city, min(positions)))
        found = [city for city, _ in sorted(found_at, key=lambda item: item[1])]
        return found or (existing or [])

    def _travelers(self, text: str, existing=1) -> int:
        normalized = text.translate(str.maketrans("०१२३४५६७८९", "0123456789")).lower()
        m = re.search(r"(\d+)\s*(?:people|persons?|pax|travell?ers?|adults?|of us|members?|log|लोग|व्यक्ति)", normalized)
        if m:
            return max(1, int(m.group(1)))
        if any(term in normalized for term in ("two", "couple", "2 people", "do log", "दो लोग", "दो व्यक्ति")):
            return 2
        if any(term in normalized for term in ("family", "parivar", "परिवार")):
            return 4
        if "solo" in text.lower() or "alone" in text.lower() or "myself" in text.lower():
            return 1
        return existing or 2

    @staticmethod
    def _days_from_dates(text: str) -> int | None:
        """Infer the trip length from a natural-language date range."""
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6,
            "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10,
            "नवंबर": 11, "दिसंबर": 12,
        }
        normalized = text.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
        pattern = re.compile(r"(\d{1,2})\s+([A-Za-z]+|[\u0900-\u097f]+)\s+(\d{4})", re.I)
        found = []
        for day, month, year in pattern.findall(normalized):
            month_number = month_names.get(month.lower(), month_names.get(month))
            if month_number:
                try:
                    found.append(date(int(year), month_number, int(day)))
                except ValueError:
                    continue
        if len(found) < 2:
            return None
        duration = (found[1] - found[0]).days
        return duration if 1 <= duration <= 30 else None

    def run(self, message: str, context: dict = None) -> dict:
        """Plan with deterministic tools, then optionally synthesize a grounded answer with an LLM."""
        from prompting import synthesize_answer

        result = self._run_deterministic(message, context)
        if result.pop("answer_is_final", False):
            result["prompting"] = {"strategy": "curated_travel_faq", "status": "complete"}
            return result
        language = (context or {}).get("response_language", "english")
        answer, status = synthesize_answer(message, result, language)
        result["prompting"] = {"strategy": "grounded_json_synthesis", "status": status}
        if answer:
            result["answer"] = answer
            result.setdefault("trace", []).append({"tool": "llm_synthesis", "status": "complete",
                                                   "summary": "Generated from planner output and retrieved evidence."})
        elif language == "hindi_devanagari" and not result.get("context", {}).get("question_only"):
            result["answer"] = self._hindi_fallback(result)
        return result

    @staticmethod
    def _hindi_fallback(result: dict) -> str:
        plan = result.get("plan")
        if plan:
            cities = {"Jaipur": "जयपुर", "Udaipur": "उदयपुर", "Jodhpur": "जोधपुर", "Jaisalmer": "जैसलमेर", "Pushkar": "पुष्कर", "Ranthambore": "रणथंभौर", "Sawai Madhopur": "सवाई माधोपुर", "Mount Abu": "माउंट आबू", "Ajmer": "अजमेर", "Bikaner": "बीकानेर"}
            route = " → ".join(cities.get(city, city) for city in plan.get("cities", []))
            days = len(plan.get("itinerary", []))
            budget = plan.get("budget", {})
            total = budget.get("group_total")
            people = result.get("context", {}).get("travelers", 2)
            amount = f"₹{total:,}" if isinstance(total, (int, float)) else ""
            return f"{route} के लिए {days} दिन की यात्रा योजना तैयार है। यह योजना {people} यात्रियों के लिए है। अनुमानित कुल बजट {amount} है। विस्तृत दिनवार कार्यक्रम नीचे दिया है। किराये, समय-सारणी और उपलब्धता यात्रा से पहले जाँच लें।"
        stays = result.get("stays", {})
        if stays:
            names = [hotel.get("name") for hotel in stays.get("hotels", []) if hotel.get("name")]
            city = stays.get("city", "इस शहर")
            return f"{city} में ठहरने के विकल्प: {', '.join(names) if names else 'उपयुक्त होटल और हॉस्टल की तुलना करें'}। कीमत और उपलब्धता सीधे जाँचें।"
        places = result.get("restaurants", [])
        if places:
            return "भोजन के विकल्प: " + "、".join(place.get("name", "स्थानीय विकल्प") for place in places[:5]) + "। खुलने का समय और भोजन संबंधी जानकारी सीधे जाँचें।"
        places = result.get("attractions", result.get("places", []))
        if places:
            return "देखने योग्य जगहें: " + "、".join(place.get("name", place.get("title", "स्थानीय जगह")) for place in places[:5]) + "। खुलने का समय और प्रवेश नियम आधिकारिक स्रोत से जाँचें।"
        return "मैंने आपकी यात्रा संबंधी जानकारी समझ ली है। कृपया शहर, यात्रा की अवधि और बजट बताइए, ताकि मैं आपके लिए सही सुझाव दे सकूँ।"

    def _run_deterministic(self, message: str, context: dict = None) -> dict:
        context = dict(context or {})
        trace = []
        text = message.strip()
        calls = 0

        def call(name, fn, *args, **kwargs):
            nonlocal calls
            if calls >= self.max_calls:
                return None
            calls += 1
            trace.append({"tool": name, "status": "running"})
            try:
                result = fn(*args, **kwargs)
                trace[-1]["status"] = "complete"
                trace[-1]["summary"] = f"OK — {type(result).__name__}"
                return result
            except Exception as exc:
                trace[-1]["status"] = "failed"
                trace[-1]["summary"] = str(exc)
                return None

        # ── Parse intent ───────────────────────────────────────────────────────
        cities = self._cities(text, context.get("cities"))
        origin_city = str(context.get("origin_city", "")).strip().casefold()
        if origin_city:
            cities = [city for city in cities if city.casefold() != origin_city]
        if not cities:
            cities = context.get("cities") or []
        context["cities"] = cities

        normalized = text.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
        day_match = re.search(r"(\d+)\s*(?:day|days|night|nights|din|रात|दिन)", normalized.lower())
        if day_match:
            context["days"] = int(day_match.group(1))
        else:
            hindi_number = re.search(r"\b(ek|do|teen|char|chaar|paanch|panch|chhe|cheh|saat|aath|nau|das)\s+(?:din|days?)\b|([एकदोतीनचारपाँचछहसातआठनौदस]+)\s*दिन", normalized.lower())
            number_words = {"ek": 1, "एक": 1, "do": 2, "दो": 2, "teen": 3, "तीन": 3, "char": 4, "chaar": 4, "चार": 4, "paanch": 5, "panch": 5, "पाँच": 5, "छह": 6, "saat": 7, "सात": 7, "aath": 8, "आठ": 8, "nau": 9, "नौ": 9, "das": 10, "दस": 10}
            if hindi_number:
                context["days"] = number_words.get((hindi_number.group(1) or hindi_number.group(2)).lower(), context.get("days"))
        if not day_match and not context.get("days"):
            inferred_days = self._days_from_dates(text)
            if inferred_days:
                context["days"] = inferred_days

        money = re.search(
            r"(?:₹|rs\.?|inr\s?|budget\s*(?:of|is|under)?\s*|बजट\s*(?:है|का)?\s*)(\d[\d,]*)"
            r"|(\d[\d,]*)\s*(?:budget|बजट|rupees?|रुपये?)",
            normalized.lower(),
        )
        if money:
            amount = money.group(1) or money.group(2)
            context["budget"] = int(amount.replace(",", ""))

        for style in ("budget", "balanced", "premium", "luxury", "sasta", "सस्ता", "कम बजट"):
            if style in text.lower():
                context["style"] = "premium" if style == "luxury" else "budget" if style in {"sasta", "सस्ता", "कम बजट"} else style

        dietary = next((x for x in ["jain", "vegan", "vegetarian", "non-vegetarian"] if x in text.lower()), context.get("dietary"))
        if dietary:
            context["dietary"] = dietary

        travelers = self._travelers(text, context.get("travelers", 2))
        context["travelers"] = travelers

        # ── Detect intents ─────────────────────────────────────────────────────
        lower = text.lower()
        hotel_intent = any(x in lower for x in ["hotel", "stay", "accommodation", "hostel", "resort", "palace", "where to stay", "place to stay", "रहने", "रुकने", "ठहरने"])
        restaurant_intent = any(x in lower for x in ["restaurant", "eat", "food", "cafe", "dining", "thali", "where to eat", "best food", "khana", "khaana", "खाना", "भोजन", "रेस्टोरेंट"])
        attraction_intent = any(x in lower for x in ["attraction", "visit", "see", "fort", "temple", "palace", "things to do", "sightseeing", "places to visit", "ghoom", "ghum", "देखना", "घूम", "जगह", "दर्शनीय"])
        cab_intent = any(x in lower for x in ["cab", "taxi", "transport", "how to get", "travel from", "cost to travel", "distance", "train", "bus", "flight", "ट्रेन", "बस", "उड़ान", "किराया"])
        # Duration words alone (e.g. "a 2 day stay") describe the lodging
        # request; they must not turn it into an itinerary intake flow.
        plan_intent = any(x in lower for x in ["plan", "itinerary", "trip", "route", "schedule", "guide me", "organize", "arrange", "cheaper", "budget", "add", "modify", "change", "update", "yatra", "safar", "ghoomna", "ghumna", "banao", "batao", "यात्रा", "सफर", "घूमना", "योजना", "बनाओ"])
        review_intent = any(x in lower for x in ["review", "rating", "recommend", "best", "top", "which hotel", "which restaurant"])
        places_intent = any(x in lower for x in ["nearby", "near me", "google places", "search places", "places around", "find places"])

        # ── RAG: retrieve background knowledge ─────────────────────────────────
        query = f"{text} {' '.join(cities)}"
        evidence = call("retrieve_knowledge", retrieve_knowledge, query, top_k=5) or []

        # Questions asked during guided intake must not be mistaken for a route choice.
        # Keep this deterministic fallback useful; when configured, the normal answer
        # synthesis pass can respond more naturally using this grounded answer/evidence.
        if context.get("question_only"):
            airport_question = any(term in lower for term in ("airport", "flight", "airfield", "हवाई अड्डा", "एयरपोर्ट", "हवाईजहाज"))
            ranthambore_question = any(city in cities for city in ("Ranthambore", "Sawai Madhopur"))
            curated_airport_answer = False
            curated_transport_answer = False
            if airport_question and ranthambore_question:
                curated_airport_answer = True
                if context.get("response_language") == "hindi_devanagari":
                    answer = (
                        "रणथंभौर के लिए जयपुर एयरपोर्ट (JAI) सबसे नज़दीकी प्रमुख हवाई अड्डा है—राजस्थान पर्यटन के अनुसार यह सवाई माधोपुर से लगभग 150–170 किमी दूर है। "
                        "वहाँ से सड़क मार्ग से जाएँ या सवाई माधोपुर तक ट्रेन लेकर स्थानीय टैक्सी लें। रणथंभौर पार्क सवाई माधोपुर से लगभग 14 किमी दूर है। "
                        "बुकिंग से पहले मौजूदा उड़ान, ट्रेन और सड़क यात्रा की जानकारी जाँचें। [राजस्थान पर्यटन](https://www.tourism.rajasthan.gov.in/sawaimadhopur.html)"
                    )
                else:
                    answer = (
                        "For Ranthambore, Jaipur Airport (JAI) is the nearest major airport. Rajasthan Tourism places it about 150–170 km from Sawai Madhopur. "
                        "From Jaipur, you can continue by road or take a train to Sawai Madhopur and arrange a local transfer; the park is about 14 km from town. "
                        "Check current flight, train and road schedules before booking. [Rajasthan Tourism](https://www.tourism.rajasthan.gov.in/sawaimadhopur.html)"
                    )
            elif airport_question and "Pushkar" in cities:
                curated_airport_answer = True
                if context.get("response_language") == "hindi_devanagari":
                    answer = (
                        "पुष्कर के लिए जयपुर का सांगानेर/जयपुर एयरपोर्ट सबसे नज़दीकी हवाई अड्डा है—राजस्थान पर्यटन के अनुसार लगभग 146 किमी दूर। "
                        "पुष्कर से 14 किमी दूर अजमेर रेलवे स्टेशन भी एक उपयोगी विकल्प है। उड़ानों और आगे के सड़क परिवहन की उपलब्धता यात्रा से पहले जाँचें। "
                        "[राजस्थान पर्यटन](https://www.tourism.rajasthan.gov.in/pushkar.html)"
                    )
                else:
                    answer = (
                        "For Pushkar, Jaipur’s Sanganer Airport (JAI) is the nearest airport listed by Rajasthan Tourism, about 146 km away. "
                        "Ajmer railway station, around 14 km from Pushkar, is another useful arrival point. Check current flight routes and onward transport before booking. "
                        "[Rajasthan Tourism](https://www.tourism.rajasthan.gov.in/pushkar.html)"
                    )
            elif "Pushkar" in cities and any(term in lower for term in ("bus", "bus stop", "bus stand", "बस", "बस स्टैंड")):
                curated_transport_answer = True
                if context.get("response_language") == "hindi_devanagari":
                    answer = (
                        "हाँ—राजस्थान पर्यटन के अनुसार पुष्कर से जयपुर, जोधपुर और अजमेर के लिए नियमित बस सेवाएँ हैं। "
                        "कौन-सा बस स्टॉप उपयोग करना है, उसकी पुष्टि यात्रा की तारीख के लिए स्थानीय रूप से करें; स्टॉप, ऑपरेटर और समय-सारणी बदल सकते हैं। "
                        "[राजस्थान पर्यटन](https://www.tourism.rajasthan.gov.in/pushkar.html)"
                    )
                else:
                    answer = (
                        "Yes. Rajasthan Tourism says Pushkar has regular bus connections with Jaipur, Jodhpur and Ajmer. "
                        "Confirm the exact stop, operator and departure time for your travel date, since these can change. "
                        "[Rajasthan Tourism](https://www.tourism.rajasthan.gov.in/pushkar.html)"
                    )
            elif evidence:
                if context.get("response_language") == "hindi_devanagari":
                    answer = "मेरे स्थानीय स्रोतों में इस सवाल का भरोसेमंद जवाब नहीं मिला। आप शहर और अपनी ज़रूरत—जैसे बस, ट्रेन, ठहरने या घूमने की जानकारी—बताएँ, तो मैं सही जानकारी खोजने की कोशिश करूँगा।"
                else:
                    answer = "I couldn’t find a reliable local source for that exact question. Tell me the city and whether you mean transport, places to visit, food or a stay, and I’ll narrow it down."
            else:
                if context.get("response_language") == "hindi_devanagari":
                    answer = "मैं यात्रा, घूमने की जगहों, ठहरने और खाने के बारे में मदद कर सकता हूँ। आप क्या जानना चाहेंगे?"
                else:
                    answer = "I can help with travel, places to visit, stays and food. What would you like to know?"
            return {"answer": answer, "context": context, "trace": trace, "evidence": evidence,
                    "answer_is_final": curated_airport_answer or curated_transport_answer}

        # ── No city detected for planning ──────────────────────────────────────
        if not cities and plan_intent:
            return {
                "answer": (
                    "I'd love to plan your Rajasthan trip! To get started, I need a few details:\n\n"
                    "**Which cities would you like to visit?** (Jaipur, Udaipur, Jodhpur, Jaisalmer, Ranthambore, Pushkar, Mount Abu, etc.)\n\n"
                    "**How many days do you have?**\n\n"
                    "**How many people are travelling?**\n\n"
                    "**What's your budget?** (per person or total group)\n\n"
                    "**Any preferences?** (wildlife safari, heritage forts, food travel, romantic trip, family-friendly, adventure, etc.)\n\n"
                    "Once I have these, I'll create a day-by-day plan with clearly labelled local reference data, estimates, and details that need confirmation."
                ),
                "context": context, "trace": trace, "evidence": evidence
            }

        # ── Optional place lookup ───────────────────────────────────────────────
        if places_intent:
            query_text = re.sub(r"\b(nearby|near me|google places|search places|places around|find places)\b", "", text, flags=re.I).strip() or "travel attractions"
            places_data = call("search_places", search_places, query_text, cities[0] if cities else None) or {}
            source = places_data.get("source", "local fallback")
            rows = places_data.get("results", [])
            if source == "Google Places" and rows:
                lines = [f"- **{p.get('displayName', {}).get('text', 'Place')}** — {p.get('formattedAddress', 'Address unavailable')}" for p in rows[:5]]
            else:
                lines = [f"- **{p.get('title', p.get('name', 'Local reference'))}** — {p.get('text', '')}" for p in rows[:5]]
            answer = f"Place search source: **{source}**.\n\n" + ("\n".join(lines) if lines else "No matching place records were found.")
            if places_data.get("notice"):
                answer += f"\n\n_{places_data['notice']}_"
            return {"answer": answer, "context": context, "trace": trace, "evidence": evidence,
                    "places": rows, "places_source": source}

        # ── Cab rate query ─────────────────────────────────────────────────────
        if cab_intent and len(cities) >= 2:
            route_info = call("get_cab_rates", get_cab_rates, cities[0], cities[1])
            if route_info and route_info.get("options"):
                options_text = "\n".join(
                    f"• **{o['mode']}**: {o['duration']}, {o['cost']} — Book at: {o['book_at']}"
                    for o in route_info["options"]
                )
                answer = (
                    f"## Getting from {cities[0]} to {cities[1]}\n\n"
                    f"**Distance:** {route_info.get('distance_km', '?')} km\n\n"
                    f"{options_text}\n\n"
                    f"**Recommendation:** {route_info.get('recommendation', '')}\n\n"
                    f"*{route_info.get('notice', '')}*"
                )
                return {"answer": answer, "context": context, "trace": trace, "evidence": evidence}

        # ── Hotel-only query ───────────────────────────────────────────────────
        if hotel_intent and cities and not plan_intent:
            tier_map = {"budget": "budget", "balanced": "mid-range", "premium": "luxury"}
            tier = tier_map.get(context.get("style", "balanced"), "all")
            hotels_data = call("search_hotels", search_hotels, cities[0], tier=tier, top_k=3)
            hotels = hotels_data.get("hotels", []) if hotels_data else []

            if hotels:
                hotel_lines = []
                for h in hotels:
                    hotel_lines.append(
                        f"### 🏨 {h['name']} ({h.get('tier', '').title()})\n"
                        f"**Indicative reference price:** {h['price_per_night']}/night\n"
                        
                        
                        
                        f"**Amenities:** {', '.join(h.get('amenities', [])[:5])}\n"
                        f"**Dietary options:** Confirm directly with the property.\n"
                        
                        + (f"**Travel times:** {', '.join(f'{k}: {v}' for k,v in list(h.get('travel_times', {}).items())[:3])}" if h.get('travel_times') else "")
                    )
                answer = (
                    f"## Hotel reference ideas for {cities[0]} ({tier.title()} tier)\n\n"
                    + "\n\n---\n\n".join(hotel_lines)
                    + f"\n\n*{hotels_data.get('guidance', '')}*"
                    + f"\n\n⚠️ *{hotels_data.get('notice', '')}*"
                )
            else:
                answer = (
                    f"I don't have specific hotel listings for {cities[0]} yet, but here's my guidance:\n\n"
                    f"{hotels_data.get('guidance', 'Choose a well-reviewed stay near your main attractions.')}\n\n"
                    f"Search on Booking.com or MakeMyTrip with filters for your preferred area."
                )
            return {"answer": answer, "context": context, "trace": trace, "evidence": evidence,
                    "stays": {"source": hotels_data.get("source", "planning guidance"), "city": cities[0],
                              "guidance": hotels_data.get("guidance", ""), "hotels": hotels,
                              "notice": hotels_data.get("notice", "")}}

        # ── Restaurant-only query ──────────────────────────────────────────────
        if restaurant_intent and cities and not plan_intent:
            rest_data = call("search_restaurants", search_restaurants, cities[0], dietary=dietary, top_k=4)
            restaurants = rest_data.get("results", []) if rest_data else []

            if restaurants:
                rest_lines = []
                for r in restaurants:
                    famous = ", ".join(r.get("famous_for", [])[:4])
                    rest_lines.append(
                        f"### 🍽️ {r['name']}\n"
                        f"**Cuisine:** {r.get('cuisine')} · **Avg meal:** ₹{r.get('avg_meal_inr')}/person\n"
                        
                        
                        
                        "**Dietary:** Confirm directly with the venue.\n"
                        
                        
                    )
                answer = (
                    f"## Restaurant reference ideas for {cities[0]}\n\n"
                    + "\n\n---\n\n".join(rest_lines)
                    + f"\n\n⚠️ *{rest_data.get('notice', '')}*"
                )
            else:
                answer = f"No specific restaurant data for {cities[0]}. Look for a Rajasthani thali near your stay — most areas have excellent local options. Confirm dietary requirements directly."
            return {"answer": answer, "context": context, "trace": trace, "evidence": evidence, "restaurants": restaurants}

        # ── Attraction query ───────────────────────────────────────────────────
        if attraction_intent and cities and not plan_intent:
            attr_data = call("search_attractions", search_attractions, cities[0], top_k=5)
            attractions = attr_data.get("attractions", []) if attr_data else []

            if attractions:
                attr_lines = []
                for a in attractions:
                    highlights = ", ".join(a.get("highlights", [])[:3])
                    tips = a.get("tips", [])
                    tips_text = "\n".join(f"  💡 {t}" for t in tips[:3]) if tips else ""
                    attr_lines.append(
                        f"### 🏛️ {a['name']} ({a.get('category', '').title()})\n"
                        f"**Entry:** {a['entry_fee_indian']} (Indians) / {a['entry_fee_foreigner']} (foreigners)\n"
                        f"**Timings:** {a.get('timings')} · **Best time:** {a.get('best_time')}\n"
                        f"**Indicative duration:** {a.get('duration_hours')} hours\n"
                        f"**Highlights:** {highlights}\n"
                        + (tips_text + "\n" if tips_text else "")
                    )
                answer = (
                    f"## Attraction ideas in {cities[0]}\n\n"
                    + "\n\n---\n\n".join(attr_lines)
                    + f"\n\n⚠️ *{attr_data.get('notice', '')}*"
                )
            else:
                answer = f"I have general attraction knowledge for {cities[0]}. What specifically are you looking for — forts, temples, wildlife, or experiences?"
            return {"answer": answer, "context": context, "trace": trace, "evidence": evidence, "attractions": attractions}

        # ── Full itinerary planning ────────────────────────────────────────────
        if plan_intent or cities:
            if any(word in lower for word in ("cheaper", "budget", "sasta", "सस्ता", "कम बजट")):
                context["style"] = "budget"

            if not context.get("days"):
                return {
                    "answer": (
                        f"Great choice — **{' → '.join(cities)}** is a wonderful route!\n\n"
                        f"How many days do you have? And how many people are travelling?\n\n"
                        f"A budget or travel style will help me tune the hotels, restaurants and activities to exactly what you need."
                    ),
                    "context": context, "trace": trace, "evidence": evidence
                }

            style = context.get("style", "balanced")

            # Full planning
            result = call("plan_itinerary", plan_itinerary,
                          cities, context["days"], travelers=travelers,
                          style=style, total_budget=context.get("budget"),
                          interests=text) or {}

            validation = call("validate_itinerary", validate_itinerary, result.get("itinerary", [])) or {}
            route_info = call("compare_routes", compare_routes, result.get("cities", cities)) or {}

            # Get hotels for each unique city
            hotels_by_city = {}
            hostels_by_city = {}
            place_sources = []
            for city in result.get("cities", cities):
                tier_map = {"budget": "budget", "balanced": "mid-range", "premium": "luxury"}
                tier = tier_map.get(style, "all")
                h_data = call(f"hotels_{city}", search_hotels, city, tier=tier, top_k=2)
                if h_data and h_data.get("source"):
                    place_sources.append(h_data["source"])
                if h_data and h_data.get("hotels"):
                    hotels_by_city[city] = h_data["hotels"]
                if h_data and h_data.get("hostels"):
                    hostels_by_city[city] = h_data["hostels"]

            # Keep food and activity suggestions attached to each itinerary city.
            restaurants_by_city, attractions_by_city = {}, {}
            for city in result.get("cities", cities):
                rest_data = call(f"restaurants_{city}", search_restaurants, city, dietary=dietary, top_k=3) or {}
                attr_data = call(f"attractions_{city}", search_attractions, city, top_k=3) or {}
                place_sources.extend([data.get("source", "") for data in (rest_data, attr_data)])
                if rest_data.get("results"):
                    restaurants_by_city[city] = rest_data["results"]
                if attr_data.get("attractions"):
                    attractions_by_city[city] = attr_data["attractions"]
            restaurants = restaurants_by_city.get((result.get("cities") or cities)[0], [])
            attractions = attractions_by_city.get((result.get("cities") or cities)[0], [])

            # Build rich answer
            budget = result.get("budget", {})
            route_str = " → ".join(result.get("cities", cities))
            intro_parts = [
                f"I've built a comprehensive **{style.title()} Rajasthan plan** for **{route_str}**.",
                f"The itinerary and budget are computed from local planning assumptions. Optional property and venue records are illustrative references, not live search results.",
            ]

            if route_info.get("transfers"):
                intro_parts.append(f"Your route has **{route_info['transfers']} intercity transfer(s)**.")
            if budget.get("per_person"):
                intro_parts.append(
                    f"\n**Estimated cost: ₹{budget['per_person']:,} per person** (₹{budget['group_total']:,} for {travelers} people). "
                    f"This covers accommodation, food, attractions, transport and a contingency buffer."
                )
            if budget.get("over_budget"):
                intro_parts.append(f"\n⚠️ **Budget alert:** Your stated budget looks tight for these cities and nights. Best levers: fewer cities, budget stays, trains over cabs, fewer paid experiences.")
            if validation.get("warnings"):
                intro_parts.append("\n⚠️ **Practical notes:** " + " | ".join(validation["warnings"]))

            intro_parts.append(
                "\nThe full day-by-day plan, hotel recommendations, restaurants and budget breakdown are shown below. "
                "You can say things like *'make it cheaper'*, *'add a vegetarian option'*, *'what's the best hotel in Jodhpur'*, or *'how do I get from Jaipur to Udaipur'*."
            )

            answer = " ".join(intro_parts)

            context.update({"cities": result.get("cities", cities), "last_plan": result})

            return {
                "answer": answer,
                "context": context,
                "trace": trace,
                "evidence": evidence,
                "plan": result,
                "restaurants": restaurants,
                "restaurants_by_city": restaurants_by_city,
                "hotels_by_city": hotels_by_city,
                "hostels_by_city": hostels_by_city,
                "attractions_by_city": attractions_by_city,
                "places_live": any("Google Places" in source for source in place_sources),
                "attractions": attractions,
                "stays": {
                    "guidance": result.get("stay_guidance"),
                    "notice": "Prices change seasonally — verify and book directly."
                }
            }

        # ── Fallback ───────────────────────────────────────────────────────────
        return {
            "answer": (
                "I'm your Rajasthan travel expert — I can help with:\n\n"
                "• **Full trip planning** — day-by-day itinerary with local guidance, reference records and planning estimates\n"
                "• **Stay guidance** — compare locations, amenities and reference data; verify current prices and availability\n"
                "• **Restaurant picks** — local favourites with what to order and current hours\n"
                "• **Things to do** — attractions with indicative guidance; verify current fees, access and hours\n"
                "• **Transport costs** — cab, train and bus options between cities\n"
                "• **Budget planning** — detailed cost breakdown across tiers\n\n"
                "Tell me a city or destination and what you'd like, and I'll get to work!"
            ),
            "context": context, "trace": trace, "evidence": evidence
        }
