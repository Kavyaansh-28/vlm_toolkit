# Demo and viva guide

## Three-minute demo

1. Start `python3 api.py` and `cd frontend && npm run dev`; show `/api/health` reports `llm_enabled` based on server configuration.
2. Ask: “Plan Jaipur and Udaipur in 5 days for two travellers under ₹30,000, vegetarian, balanced style.” Point out route order, computed daily itinerary, budget split and estimate label.
3. Follow up: “Make it cheaper.” Show context carries forward and the planner changes its style/budget assumptions.
4. Expand “Why this plan” to show retrieved local evidence and the tool trace. Explain that TF-IDF selects relevant passages and that the model synthesis, when configured, only writes the narrative from this data.
5. Ask about safari availability or Jain food. Show the app asks for current direct/official confirmation rather than promising availability or dietary safety.

## Short viva answers

**Why is this an agent?** It parses the request and prior context, selects allow-listed tools, retrieves evidence, composes a plan, validates route constraints and returns a trace. The tool loop is bounded.

**What is the RAG pipeline?** JSON knowledge documents are normalized by ingestion, indexed using TF-IDF word unigrams/bigrams, and ranked by cosine similarity. The top passages and source metadata are returned as evidence.

**What does the LLM do?** If configured, it receives a versioned system prompt plus bounded planner results and retrieved evidence and returns a JSON answer. Tool computation remains deterministic. Without credentials or after provider failure, the app uses its deterministic response.

**How do you reduce prompt injection and hallucinations?** User text and retrieved passages are explicitly treated as untrusted data; the model is told to use only supplied planning results/evidence, preserve computed numbers and caveats, avoid live claims, and return a constrained JSON object. The UI keeps structured itinerary and budgets separate from generated prose.

**What are the known limits?** The TF-IDF corpus is small and curated; intent parsing is rule-based; fixture hotel and restaurant records are illustrative; there is no booking, permit, or live transport transaction. Current data must be confirmed with official or provider sources.

**How is budget calculated?** Transparent per-person category assumptions are summed, a contingency is added, then multiplied by traveller count; an optional cap flags an over-budget plan. It is an estimate, not a quote.

**What tests exist?** Unit tests exercise the planner, route validation, budget computation, retrieval filters, local tool fallback, follow-up context, and prompt construction/fallback. Run `python3 -m pytest -q`.

## Rubric evidence map

| Rubric area | Evidence to show |
| --- | --- |
| Problem and suitability | README scope and multi-constraint demo request |
| Prompt engineering | `prompting.py`: version, role, untrusted-data boundary, grounding, JSON shape |
| Architecture and planning | `agent.py`, tool trace, route validator and call limit |
| RAG | `ingestion.py`, `retrieval.py`, source passages in the evidence panel |
| Tool/API integration | `tools.py`, `api.py`, `/api/health`, `/api/chat` |
| Working app | React interaction plus Streamlit alternative |
| Safety | Estimate labels, direct verification guidance, no guaranteed wildlife/diet claims |
| Testing and viva | pytest suite, this demo flow and answers |
| Timeliness | Submission timestamp / LMS receipt (outside the codebase) |
