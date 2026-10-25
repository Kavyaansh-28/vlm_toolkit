import json

from prompting import PROMPT_VERSION, SYSTEM_PROMPT, build_messages, synthesize_answer


def test_prompt_is_versioned_and_marks_inputs_untrusted():
    messages = build_messages("Plan Jaipur", {"answer": "Estimate", "evidence": [{"title": "Guide", "text": "Useful", "category": "tips"}]})
    assert PROMPT_VERSION in messages[1]["content"]
    assert "untrusted data" in SYSTEM_PROMPT
    assert "never paste an unrelated passage" in SYSTEM_PROMPT
    assert messages[0]["role"] == "system"
    payload = messages[1]["content"].split("<request_data>\n", 1)[1].split("\n</request_data>", 1)[0]
    assert json.loads(payload)["traveler_request_untrusted"] == "Plan Jaipur"


def test_prompt_includes_selected_devanagari_response_language():
    messages = build_messages("जयपुर की यात्रा बनाओ", {"answer": "Estimate"}, "hindi_devanagari")
    payload = messages[1]["content"].split("<request_data>\n", 1)[1].split("\n</request_data>", 1)[0]
    assert json.loads(payload)["preferred_response_language"] == "hindi_devanagari"
    assert "Do not repeat or quote" in messages[0]["content"]


def test_model_is_optional_and_falls_back(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    answer, status = synthesize_answer("Plan Jaipur", {"answer": "Deterministic plan"})
    assert answer is None
    assert status == "fallback"


def test_model_uses_strict_json_schema_and_validates_result(monkeypatch):
    from io import BytesIO
    import prompting

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({"choices": [{"message": {"content": json.dumps({"answer": "Grounded answer", "warnings": [], "follow_up_questions": []})}}]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        return Response()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(prompting, "urlopen", fake_urlopen)
    answer, status = synthesize_answer("Plan Jaipur", {"answer": "Estimate", "evidence": []})
    assert (answer, status) == ("Grounded answer", "generated")
    schema = captured["payload"]["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False


def test_groq_uses_compatible_json_object_mode(monkeypatch):
    import prompting

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            content = json.dumps({"answer": "Answer", "warnings": [], "follow_up_questions": []})
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        return Response()

    monkeypatch.setenv("OPENAI_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(prompting, "urlopen", fake_urlopen)
    answer, status = synthesize_answer("Nearest airport?", {"answer": "Airport information"})
    assert (answer, status) == ("Answer", "generated")
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["model"] == "openai/gpt-oss-120b"
