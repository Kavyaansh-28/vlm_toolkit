from agent import RajasthanAgent

def test_agent_tools_and_evidence():
    result=RajasthanAgent().run("Plan Jaipur and Udaipur in 5 days under ₹30000")
    assert result["plan"] and result["evidence"]
    assert len([x for x in result["trace"] if x["tool"] != "llm_synthesis"]) <= RajasthanAgent().max_calls

def test_agent_followup_context():
    agent=RajasthanAgent(); first=agent.run("Plan Jaipur in 3 days")
    next_result=agent.run("Make it cheaper", first["context"])
    assert next_result["context"]["style"] == "budget"

def test_agent_hotel_guidance():
    result=RajasthanAgent().run("Suggest a premium hotel stay strategy in Udaipur")
    assert result["stays"]["city"] == "Udaipur"
    assert "guidance" in result["stays"]

def test_two_day_hotel_request_is_not_misclassified_as_itinerary():
    result = RajasthanAgent().run(
        "suggest good hotels for a 2 day stay in Jaipur",
        {"cities": ["Jaipur"], "days": 2},
    )
    assert result.get("plan") is None
    assert result["stays"]["city"] == "Jaipur"

def test_agent_preserves_requested_city_order():
    result=RajasthanAgent().run("Plan Bikaner, Jaisalmer and Jodhpur in 7 days")
    assert result["plan"]["cities"] == ["Bikaner", "Jaisalmer", "Jodhpur"]

def test_plan_with_food_words_still_creates_itinerary():
    result=RajasthanAgent().run("Plan a 3 day trip to Ranthambore with hotel, food spots, activities and budget")
    assert result["plan"] and result["restaurants"] and result["stays"]


def test_places_intent_calls_allowlisted_tool(monkeypatch):
    import agent

    def fake_search(query, city=None):
        return {"source": "local fallback", "results": [{"title": "Jaipur guide", "text": "Verify before visiting."}], "notice": "Local reference."}

    monkeypatch.setattr(agent, "search_places", fake_search)
    result = RajasthanAgent().run("find places near Jaipur")
    assert result["places_source"] == "local fallback"
    assert "Jaipur guide" in result["answer"]
    assert any(item["tool"] == "search_places" for item in result["trace"])


def test_agent_understands_devanagari_city_and_day_input_without_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = RajasthanAgent().run("उदयपुर में ५ दिन की यात्रा योजना बनाओ", {"response_language": "hindi_devanagari"})
    assert result["plan"]
    assert result["context"]["days"] == 5
    assert "उदयपुर" in result["answer"]


def test_agent_understands_romanized_hindi_cities_and_travelers():
    agent = RajasthanAgent()
    assert agent._cities("udaipur aur phir jaipur") == ["Udaipur", "Jaipur"]
    assert agent._travelers("hum 3 log hain") == 3


def test_agent_understands_romanized_hindi_trip_request(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = RajasthanAgent().run("udaipur ke liye 3 din ka safar banao")
    assert result["plan"]["cities"] == ["Udaipur"]
    assert result["context"]["days"] == 3


def test_agent_infers_trip_length_from_followup_date_range():
    result = RajasthanAgent().run(
        "17 October 2026 to 24 October 2026, 2 people, 60000 budget",
        {"cities": ["Udaipur", "Jaipur"], "origin_city": "Pune"},
    )
    assert result["plan"]
    assert len(result["plan"]["itinerary"]) == 7
    assert result["context"]["travelers"] == 2
    assert result["context"]["budget"] == 60000


def test_agent_infers_trip_length_from_hindi_date_range():
    result = RajasthanAgent().run(
        "17 अक्टूबर 2026 से 24 अक्टूबर 2026, 2 लोग, बजट 60000",
        {"cities": ["उदयपुर", "जयपुर"], "response_language": "hindi_devanagari"},
    )
    assert result["plan"]
    assert len(result["plan"]["itinerary"]) == 7


def test_agent_answers_airport_question_without_turning_city_into_trip(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = RajasthanAgent().run(
        "Which airport is nearest to Ranthambore?",
        {"cities": ["Ranthambore"], "origin_city": "Mumbai", "question_only": True},
    )
    assert result.get("plan") is None
    assert "Jaipur Airport" in result["answer"]
    assert "150–170 km" in result["answer"]
    assert "Rajasthan Tourism" in result["answer"]


def test_agent_answers_airport_question_in_selected_hindi(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = RajasthanAgent().run(
        "रणथंभौर के लिए सबसे नज़दीकी एयरपोर्ट कौन सा है?",
        {"cities": ["Ranthambore"], "question_only": True, "response_language": "hindi_devanagari"},
    )
    assert "जयपुर एयरपोर्ट" in result["answer"]
    assert "Jaipur Airport" not in result["answer"]


def test_agent_answers_pushkar_airport_question_without_allowing_irrelevant_synthesis(monkeypatch):
    import prompting

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(prompting, "synthesize_answer", lambda *args: ("Brahma Temple is a famous attraction.", "generated"))
    result = RajasthanAgent().run(
        "Nearest airport to Pushkar?",
        {"cities": ["Pushkar"], "question_only": True},
    )
    assert result.get("plan") is None
    assert "Sanganer Airport" in result["answer"]
    assert "146 km" in result["answer"]


def test_agent_answers_pushkar_bus_question_from_relevant_local_knowledge(monkeypatch):
    import prompting

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(prompting, "synthesize_answer", lambda *args: ("Brahma Temple is a famous attraction.", "generated"))
    result = RajasthanAgent().run(
        "Any bus stops near to Pushkar?",
        {"cities": ["Pushkar"], "question_only": True},
    )
    assert "regular bus connections" in result["answer"]
    assert "Jaipur, Jodhpur and Ajmer" in result["answer"]
    assert "Brahma Temple" not in result["answer"]
