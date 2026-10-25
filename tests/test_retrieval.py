from retrieval import retrieve_knowledge

def test_retrieval_finds_jaipur():
    rows=retrieve_knowledge("Jaipur fort markets", destination="Jaipur")
    assert rows and all(x["destination"] == "Jaipur" for x in rows)

def test_filter_and_empty_query():
    assert retrieve_knowledge("safari", category="wildlife")
    assert retrieve_knowledge("") == []
    assert retrieve_knowledge("nothing unfindable xyz") == []


def test_pushkar_bus_question_retrieves_transport_guidance():
    rows = retrieve_knowledge("Any bus stops near to Pushkar?", destination="Pushkar")
    assert rows
    assert "regular buses" in rows[0]["text"]
    assert rows[0]["source_url"] == "https://www.tourism.rajasthan.gov.in/pushkar.html"
