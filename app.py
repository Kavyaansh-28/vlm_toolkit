from __future__ import annotations

import json
import hashlib
import html
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml
from PIL import Image, ImageDraw

from claims.graph import graph_data
from core.pipeline import run
from database.db import recent, save
from evaluation.metrics import classification_metrics
from vlm import providers

try:
    from streamlit_paste_button import paste_image_button
except ImportError:
    paste_image_button = None


st.set_page_config(page_title="VLM Reliability Layer", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
CONFIG = yaml.safe_load(Path("config/config.yaml").read_text())


def inject_styles() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root { --bg:#0b0c10; --surface:#111319; --surface-2:#171a22; --line:#262a35; --text:#eceef4; --muted:#9298a8; --purple:#a78bfa; --cyan:#71d6e8; --green:#70d6a1; --amber:#f2bd70; --red:#ff8088; }
    html, body, [class*="css"] { font-family:'Manrope',sans-serif; }
    .stApp { background: radial-gradient(ellipse at 78% -10%, rgba(92,70,160,.15), transparent 34%), var(--bg); color:var(--text); }
    [data-testid="stHeader"] { background:rgba(11,12,16,.76); border-bottom:1px solid rgba(255,255,255,.06); backdrop-filter:blur(18px); }
    [data-testid="stSidebar"] { background:#0e1015; border-right:1px solid var(--line); }
    [data-testid="stSidebar"] > div:first-child { padding-top:1.1rem; }
    .block-container { max-width:1500px; padding-top:2rem; padding-bottom:4rem; }
    h1,h2,h3 { letter-spacing:-.045em !important; color:var(--text) !important; }
    p, label, .stMarkdown { color:#c5c9d3; }
    code, .mono { font-family:'DM Mono',monospace !important; }
    .brand { display:flex; align-items:center; gap:10px; padding:7px 0 22px; font-weight:800; font-size:15px; letter-spacing:-.04em; color:#f4f3fb; }
    .brand-mark { width:28px; height:28px; display:grid; place-items:center; border-radius:9px; color:#d8ccff; background:linear-gradient(145deg,#3b2a70,#201d36); border:1px solid #56448b; font-size:18px; }
    .eyebrow { color:var(--purple); font:500 11px 'DM Mono',monospace; letter-spacing:.13em; text-transform:uppercase; }
    .hero { position:relative; overflow:hidden; padding:44px 46px 34px; margin:0 0 24px; border:1px solid #292b38; border-radius:22px; background:linear-gradient(115deg,rgba(27,26,39,.98),rgba(17,19,25,.94) 54%,rgba(22,27,35,.96)); }
    .hero:after { content:''; position:absolute; width:380px;height:380px;right:-85px;top:-205px;border-radius:50%;background:radial-gradient(circle,rgba(139,111,220,.22),transparent 68%);pointer-events:none; }
    .hero h1 { font-size:clamp(38px,5vw,62px) !important; line-height:1.02 !important; max-width:760px; margin:15px 0 !important; }
    .hero-copy { color:#a9adba; font-size:15px; max-width:590px; line-height:1.7; }
    .hero-flow { display:flex;align-items:center;gap:11px;flex-wrap:wrap;margin-top:32px;padding-top:22px;border-top:1px solid rgba(255,255,255,.08); }
    .flow-step { font:11px 'DM Mono',monospace;letter-spacing:.08em;color:#c6c9d3;padding:9px 12px;border:1px solid #303441;border-radius:8px;background:rgba(255,255,255,.025); }
    .flow-arrow { color:#706b81;font:16px 'DM Mono',monospace; }
    .section-head { display:flex;align-items:center;gap:10px;margin:28px 0 14px;color:#e8eaf0;font-size:17px;font-weight:700;letter-spacing:-.03em; }
    .surface { background:var(--surface); border:1px solid var(--line); border-radius:15px; padding:19px 20px; }
    .metric-label { color:var(--muted);font:10px 'DM Mono',monospace;letter-spacing:.09em;text-transform:uppercase; }
    .metric-value { color:#f0f1f5;font-size:28px;font-weight:700;letter-spacing:-.055em;margin-top:6px; }
    .metric-note { color:#838998;font-size:11px;margin-top:3px; }
    .tag { display:inline-flex;align-items:center;padding:5px 9px;border-radius:99px;border:1px solid #333744;background:#191c24;color:#b9bfcc;font:10px 'DM Mono',monospace;letter-spacing:.04em; }
    .tag-good { color:var(--green);border-color:rgba(112,214,161,.27);background:rgba(112,214,161,.07); }
    .tag-warn { color:var(--amber);border-color:rgba(242,189,112,.27);background:rgba(242,189,112,.07); }
    .tag-bad { color:var(--red);border-color:rgba(255,128,136,.27);background:rgba(255,128,136,.07); }
    .claim-id { color:var(--purple);font:11px 'DM Mono',monospace; }
    .decision { display:flex;align-items:center;gap:11px;padding:16px 18px;border:1px solid #303441;border-radius:13px;background:linear-gradient(110deg,#171a22,#12141a); }
    .decision-mark { width:32px;height:32px;display:grid;place-items:center;border-radius:10px;background:#232634;color:var(--purple);font-size:16px; }
    .decision-title { font-weight:800;letter-spacing:.04em;color:#f0eff7;font-size:13px; }
    .decision-copy { font-size:12px;color:#969baa;margin-top:3px; }
    .empty { text-align:center;padding:38px 22px;border:1px dashed #343846;border-radius:14px;background:rgba(255,255,255,.012); }
    .empty-mark { font-size:24px;color:#a78bfa;margin-bottom:8px; }
    .empty-title { color:#eceef4;font-weight:700; }
    .empty-copy { color:#898f9e;font-size:12px;margin-top:5px; }
    .stButton>button, .stDownloadButton>button { border-radius:9px;border:1px solid #373441;background:#1b1923;color:#e9e5f3;font-weight:700;transition:transform .18s ease,border-color .18s ease,background .18s ease; }
    .stButton>button:hover,.stDownloadButton>button:hover { border-color:#7763a7;background:#24202f;transform:translateY(-1px);color:white; }
    button[kind="primary"] { background:linear-gradient(130deg,#7661b9,#5d4a99) !important;border:1px solid #9280c6 !important;color:white !important;box-shadow:0 6px 22px rgba(99,77,157,.16); }
    [data-testid="stFileUploaderDropzone"] { border:1px dashed #474459;background:rgba(255,255,255,.018);border-radius:13px; }
    [data-testid="stTabs"] button { color:#9298a8; font-size:12px; }
    [data-testid="stTabs"] button[aria-selected="true"] { color:#ddd3ff; }
    [data-testid="stMetric"] { background:#111319;border:1px solid #262a35;border-radius:12px;padding:15px 16px; }
    [data-testid="stMetricLabel"] { color:#9ca2b0; }
    [data-testid="stMetricValue"] { color:#f0f1f5;letter-spacing:-.04em; }
    [data-testid="stDataFrame"] { border:1px solid #262a35;border-radius:12px;overflow:hidden; }
    [data-testid="stExpander"] { border-color:#292d38;border-radius:11px;background:#111319; }
    [data-testid="stSelectbox"], [data-testid="stTextInput"], [data-testid="stTextArea"] { color:#e5e7ee; }
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div { background:#12141a;border-color:#303441; }
    @keyframes arrive { from { opacity:0;transform:translateY(7px) } to { opacity:1;transform:translateY(0) } }
    .surface,.decision,.hero { animation:arrive .42s ease both; }
    @media(max-width:760px){ .hero{padding:30px 23px 24px}.hero h1{font-size:39px!important}.hero-flow{gap:6px}.flow-step{font-size:9px;padding:7px 8px}.flow-arrow{font-size:12px}.block-container{padding-left:1rem;padding-right:1rem} }
    @media(prefers-reduced-motion:reduce){ *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important} }
    </style>
    """, unsafe_allow_html=True)


def persist_image(upload, pasted) -> str:
    suffix = Path(upload.name).suffix if upload else ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as target:
        if upload:
            target.write(upload.getbuffer())
        else:
            pasted.convert("RGB").save(target.name, "PNG")
        return target.name


def evidence_color(status: str) -> str:
    return {"SUPPORTED": "#65d49b", "CONTRADICTED": "#ff737e", "UNSUPPORTED": "#ff737e", "AMBIGUOUS": "#e9b66d"}.get(status, "#939aaa")


def annotated(image: Image.Image, candidate, selected_id: str | None = None) -> Image.Image:
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    by_claim = {item.claim_id: item for item in candidate.evidence}
    for claim in candidate.claims:
        item = by_claim.get(claim.id)
        if not item:
            continue
        active = claim.id == selected_id
        color = evidence_color(item.status)
        for box in item.boxes:
            width = 5 if active else 2
            draw.rectangle(tuple(box), outline=color, width=width)
            if active:
                label = f"{claim.id} · {item.status}"
                y = max(0, int(box[1]) - 18)
                draw.rectangle((int(box[0]), y, int(box[0]) + max(65, len(label) * 7), y + 16), fill=color)
                draw.text((int(box[0]) + 4, y + 2), label, fill="#111319")
    return canvas


def status_tag(status: str) -> str:
    cls = "tag-good" if status == "SUPPORTED" else "tag-warn" if status == "AMBIGUOUS" else "tag-bad"
    return f'<span class="tag {cls}">{status.replace("_", " ")}</span>'


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(f'<div class="surface"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)


def hero() -> None:
    st.markdown('''<div class="hero"><div class="eyebrow">VLM RELIABILITY LAYER · VISUAL CLAIM VERIFICATION</div>
    <h1>AI shouldn't be the<br>only one checking AI.</h1>
    <div class="hero-copy">A model can generate an answer. We inspect the image, claim by claim, to see whether the evidence actually supports it.</div>
    <div class="hero-flow"><span class="flow-step">VLM OUTPUT</span><span class="flow-arrow">→</span><span class="flow-step">CLAIMS</span><span class="flow-arrow">→</span><span class="flow-step">VISUAL EVIDENCE</span><span class="flow-arrow">→</span><span class="flow-step">RELIABILITY</span><span class="flow-arrow">→</span><span class="flow-step">DECISION</span></div></div>''', unsafe_allow_html=True)


def claim_rows(candidate) -> list[dict]:
    evidence = {item.claim_id: item for item in candidate.evidence}
    rows = []
    for claim in candidate.claims:
        item = evidence.get(claim.id)
        value = claim.value if claim.value is not None else "exists"
        rows.append({"ID": claim.id, "Type": claim.type.upper(), "Claim": f"{claim.subject} · {claim.attribute + ' ' if claim.attribute else ''}{value}", "Status": item.status if item else "AMBIGUOUS", "Score": item.score if item else None, "Verified": item.verified_value if item else None, "Diagnosis": item.diagnosis if item else None})
    return rows


def claim_graph_dot(graph: dict, selected_claim_id: str | None = None) -> str:
    """Render only graph nodes/edges supplied by claims.graph.graph_data."""
    lines = [
        'digraph claims {',
        'graph [bgcolor="transparent", rankdir=LR, pad="0.22", nodesep="0.42", ranksep="0.7"];',
        'node [shape=box, style="rounded,filled", fillcolor="#171a22", color="#393d4b", fontcolor="#e5e6ec", fontname="Manrope", fontsize=11, margin="0.16,0.10"];',
        'edge [color="#626778", fontcolor="#a5a9b6", fontname="DM Mono", fontsize=9, arrowsize=0.7];',
    ]
    node_ids = {str(node["id"]) for node in graph.get("nodes", [])}
    for node in graph.get("nodes", []):
        node_id = str(node["id"])
        label = str(node.get("label", node_id))
        kind = str(node.get("kind", "object"))
        fill = "#211d32" if kind == "attribute_value" else "#171a22"
        lines.append(f'{json.dumps(node_id)} [label={json.dumps(label)}, fillcolor={json.dumps(fill)}];')
    for edge in graph.get("edges", []):
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if source not in node_ids or target not in node_ids:
            continue
        active = bool(selected_claim_id and edge.get("claim_id") == selected_claim_id)
        color = "#a78bfa" if active else "#626778"
        width = "2.2" if active else "1"
        lines.append(f'{json.dumps(source)} -> {json.dumps(target)} [label={json.dumps(str(edge.get("label", "")))}, color={json.dumps(color)}, penwidth={width}];')
    lines.append("}")
    return "\n".join(lines)


inject_styles()
with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">◈</span><span>VLM Reliability Layer</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">WORKSPACE</div>', unsafe_allow_html=True)
    page = st.radio("Workspace", ["Analyze", "Evaluation", "Experiments"], label_visibility="collapsed", key="main_page")
    st.markdown("---")
    st.markdown('<div class="eyebrow">MODEL & POLICY</div>', unsafe_allow_html=True)
    available = providers()
    configured = CONFIG["vlm"].get("provider", "groq")
    provider = st.selectbox("VLM provider", available, index=available.index(configured) if configured in available else 0, key="provider_select")
    verifier_provider = st.selectbox("Independent verifier VLM", available, index=available.index(configured) if configured in available else 0, key="verifier_provider_select")
    candidate_count = st.slider("Candidates per run", 1, 3, CONFIG["vlm"]["candidate_count"])
    with st.expander("Reliability policy", expanded=False):
        verification_weight = st.slider("Visual verification weight", .0, 1.0, CONFIG["reliability"]["lambda_verification"], .05)
        agreement_weight = st.slider("Candidate agreement weight", .0, 1.0, CONFIG["reliability"]["lambda_agreement"], .05)
        high_threshold = st.slider("Accept threshold", .5, 1.0, CONFIG["reliability"]["high_threshold"], .05)
        low_threshold = st.slider("Correct threshold", .0, .5, CONFIG["reliability"]["low_threshold"], .05)
    st.caption("Token probabilities are unavailable from this VLM call; the configured weight is redistributed to visual verification.")
    st.markdown("---")
    st.caption("LOCAL RESEARCH WORKSPACE · EVIDENCE FIRST")


analysis = st.session_state.get("analysis")

if page == "Analyze":
    hero()
    st.markdown('<div class="section-head">01 <span style="color:#979bab;font-size:13px;font-weight:500">Provide an image and define the question</span></div>', unsafe_allow_html=True)
    left, right = st.columns([1.2, .8], gap="large")
    with left:
        upload = st.file_uploader("Drop an image here or browse files", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed", key="image_upload")
        if paste_image_button:
            pasted_result = paste_image_button("Paste from clipboard", key="clipboard", errors="ignore")
            if pasted_result.image_data is not None:
                st.session_state["pasted"] = pasted_result.image_data.copy()
        pasted = st.session_state.get("pasted")
        image = Image.open(upload) if upload else pasted
        if image:
            st.image(image, caption=f"{upload.name if upload else 'Clipboard image'} · {image.width} × {image.height}", width="stretch")
        else:
            st.markdown('<div class="empty"><div class="empty-mark">⌁</div><div class="empty-title">Your evidence canvas</div><div class="empty-copy">The image and claim-linked regions will appear here once analysis is run.</div></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="eyebrow">ANALYSIS INPUT</div>', unsafe_allow_html=True)
        query = st.text_input("Prompt", "Describe the objects and their colors.", help="This prompt is passed directly to the existing VLM pipeline.")
        manual = st.text_area("Candidate override · optional", placeholder="Paste a candidate response, or separate responses with |||", height=120, help="Useful for controlled experiments. Manual candidates still go through the normal verification pipeline.")
        st.markdown('<div class="surface" style="margin:10px 0 18px"><div class="metric-label">PIPELINE</div><div style="margin-top:10px;color:#d8dae2;font-size:12px;line-height:1.9">Generate candidates <span style="color:#706b81">→</span> extract typed claims<br>Verify relevant visual evidence <span style="color:#706b81">→</span> score & decide</div></div>', unsafe_allow_html=True)
        run_clicked = st.button("Run reliability analysis  →", type="primary", disabled=image is None, width="stretch")
        if run_clicked:
            image_path = persist_image(upload, pasted)
            try:
                image_id = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
                with st.spinner("Running the verification pipeline…"):
                    candidates, error = run(image_path, query, candidate_count, {"verification": verification_weight, "probability": CONFIG["reliability"].get("lambda_probability", 0.0), "agreement": agreement_weight}, manual, high_threshold, low_threshold, provider, verifier_provider)
            finally:
                Path(image_path).unlink(missing_ok=True)
            if error:
                st.warning(error)
            if candidates:
                configuration = {"generator_provider": provider, "verifier_provider": verifier_provider,
                                 "candidate_count": candidate_count,
                                 "weights": {"verification": verification_weight,
                                             "probability": CONFIG["reliability"].get("lambda_probability", 0.0),
                                             "agreement": agreement_weight},
                                 "high_threshold": high_threshold, "low_threshold": low_threshold}
                experiment_id = save(query, {"query": query, "image_id": image_id,
                                             "configuration": configuration,
                                             "candidates": [candidate.export() for candidate in candidates]})
                st.session_state["analysis"] = {"image": image.copy(), "query": query,
                                                "experiment_id": experiment_id, "candidates": candidates}
                st.rerun()
            else:
                st.error("Verification engine unavailable. Check provider configuration or use a manual candidate override.")

    analysis = st.session_state.get("analysis")
    if analysis:
        candidates = analysis["candidates"]
        best = candidates[0]
        by_claim = {item.claim_id: item for item in best.evidence}
        selected_id = st.session_state.get("selected_claim")
        st.markdown('<div class="section-head">02 <span style="color:#979bab;font-size:13px;font-weight:500">Analysis workspace</span></div>', unsafe_allow_html=True)
        dcols = st.columns([1.5, 1.5, 1.2, 1.1])
        dcols[0].metric("Toolkit reliability", f"{best.reliability:.0%}")
        dcols[1].metric("Claim evidence mean", f"{(sum(e.score for e in best.evidence)/len(best.evidence) if best.evidence else 0):.0%}" if best.evidence else "—")
        dcols[2].metric("Decision", best.decision)
        dcols[3].metric("Claims", len(best.claims))
        st.markdown(f'<div class="decision"><div class="decision-mark">{"✓" if best.decision in ["ACCEPT", "RERANK"] else "↻" if best.decision == "CORRECT" else "○"}</div><div><div class="decision-title">{best.decision}</div><div class="decision-copy">{("All high-confidence claims are supported by visual evidence." if best.decision == "ACCEPT" else "The strongest candidate was selected after verification." if best.decision == "RERANK" else "Some claims require correction or the evidence remains insufficient.")}</div></div></div>', unsafe_allow_html=True)
        tabs = st.tabs(["Overview", "Claim inspector", "Evidence", "Candidates", "Correction"])
        with tabs[0]:
            img_col, response_col = st.columns([1.1, 1], gap="large")
            with img_col:
                st.markdown('<div class="eyebrow">VISUAL EVIDENCE</div>', unsafe_allow_html=True)
                selection_options = ["All claims"] + [f"{claim.id} · {claim.subject} · {claim.value if claim.value is not None else claim.type}" for claim in best.claims]
                selected_label = st.selectbox("Focus claim", selection_options, label_visibility="collapsed", key="claim_focus")
                selected_claim_id = selected_label.split(" · ")[0] if selected_label != "All claims" else None
                st.session_state["selected_claim"] = selected_claim_id
                overlay = annotated(analysis["image"], best, selected_claim_id)
                zoom = st.slider("Image scale", 50, 150, 100, 10, key="viewer_zoom")
                st.image(overlay, width=int(min(760, overlay.width * zoom / 100)), caption="Claim-linked boxes · green supported · amber ambiguous · red contradicted/unsupported")
            with response_col:
                st.markdown('<div class="eyebrow">MODEL RESPONSE</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="surface" style="font-size:17px;line-height:1.7;color:#e5e6ec">{html.escape(best.text)}</div>', unsafe_allow_html=True)
                st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
                if best.claims:
                    st.markdown('<div class="eyebrow">EXTRACTED CLAIMS</div>', unsafe_allow_html=True)
                    for claim in best.claims:
                        item = by_claim.get(claim.id)
                        value = claim.value if claim.value is not None else "exists"
                        c1, c2 = st.columns([.73, .27])
                        c1.markdown(f'<div style="padding:10px 0;border-bottom:1px solid #242833"><span class="claim-id">{html.escape(claim.id)}</span>&nbsp;&nbsp;<span style="color:#e5e6ec">{html.escape(claim.subject)}</span><span style="color:#9298a8"> · {html.escape(str(claim.attribute) + " " if claim.attribute else "")}{html.escape(str(value))}</span></div>', unsafe_allow_html=True)
                        c2.markdown(f'<div style="padding:10px 0;text-align:right">{status_tag(item.status if item else "AMBIGUOUS")}</div>', unsafe_allow_html=True)
                else:
                    st.info("No typed claims were extracted from this response.")
                st.caption(f"Model: {best.model} · Candidate: {best.id} · agreement {best.agreement:.0%}")
        with tabs[1]:
            rows = claim_rows(best)
            if not rows:
                st.markdown('<div class="empty"><div class="empty-title">No claims to inspect</div><div class="empty-copy">The VLM response did not produce typed claims.</div></div>', unsafe_allow_html=True)
            else:
                chosen = st.selectbox("Select a claim to inspect", [row["ID"] for row in rows], format_func=lambda item_id: next(f'{row["ID"]} · {row["Claim"]}' for row in rows if row["ID"] == item_id), key="inspector_claim")
                claim = next(claim for claim in best.claims if claim.id == chosen)
                item = by_claim.get(chosen)
                a, b, c = st.columns([1.35, 1, 1])
                a.markdown(f'<div class="surface"><div class="metric-label">CLAIM {html.escape(claim.id)}</div><div class="metric-value" style="font-size:21px">{html.escape(claim.subject.upper())}</div><div style="color:#aaaeb9;margin-top:6px">{html.escape(claim.attribute or claim.type)} · {html.escape(str(claim.value if claim.value is not None else "exists"))}</div></div>', unsafe_allow_html=True)
                b.markdown(f'<div class="surface"><div class="metric-label">STATUS</div><div style="margin-top:12px">{status_tag(item.status if item else "AMBIGUOUS")}</div><div class="metric-note" style="margin-top:11px">{item.diagnosis if item and item.diagnosis else "No diagnosis available"}</div></div>', unsafe_allow_html=True)
                c.markdown(f'<div class="surface"><div class="metric-label">CLAIM SCORE</div><div class="metric-value">{f"{item.score:.0%}" if item else "—"}</div><div class="metric-note">Candidate reliability {best.reliability:.0%}</div></div>', unsafe_allow_html=True)
                if item:
                    x, y = st.columns([1, 1])
                    with x:
                        st.markdown("**Claim evidence**")
                        st.progress(max(0.0, min(1.0, float(item.score))))
                        st.caption(item.explanation or "No explanation returned by verifier.")
                        st.markdown(f"**Verified value:** {item.verified_value if item.verified_value is not None else 'Unavailable'}")
                    with y:
                        st.markdown("**Signals**")
                        st.json(item.signals or {}, expanded=True)
                        st.caption(f"Sources: {', '.join(item.source) if item.source else 'Unavailable'} · verifier estimate (uncalibrated) {item.confidence:.0%}")
                graph = graph_data(best.claims)
                if graph["nodes"]:
                    st.markdown('<div class="eyebrow" style="margin:25px 0 7px">CLAIM GRAPH · EXTRACTED STRUCTURE</div>', unsafe_allow_html=True)
                    st.caption("Object and attribute relationships from the claim extractor. Select a claim above to emphasize its edge.")
                    st.graphviz_chart(claim_graph_dot(graph, chosen), width="stretch")
                    with st.expander("Graph data", expanded=False):
                        st.json(graph, expanded=False)
        with tabs[2]:
            ev_left, ev_right = st.columns([1.05, .95], gap="large")
            with ev_left:
                st.image(annotated(analysis["image"], best), width="stretch", caption="Evidence overlay · boxes are returned by the verifier")
            with ev_right:
                if not best.evidence:
                    st.markdown('<div class="empty"><div class="empty-title">Evidence unavailable</div><div class="empty-copy">The verifier did not return evidence for this candidate.</div></div>', unsafe_allow_html=True)
                for item in best.evidence:
                    with st.expander(f"{item.claim_id} · {item.status} · {item.diagnosis or 'Evidence detail'}", expanded=False):
                        st.write(item.explanation or "No explanation returned.")
                        st.caption(f"Score {item.score:.0%} · verifier estimate (uncalibrated) {item.confidence:.0%} · quality {item.evidence_quality if item.evidence_quality is not None else 'unavailable'}")
                        st.json(item.signals or {}, expanded=False)
            evidence_status = {"Supported": sum(item.status == "SUPPORTED" for item in best.evidence), "Contradicted": sum(item.status in ("CONTRADICTED", "UNSUPPORTED") for item in best.evidence), "Ambiguous": sum(item.status == "AMBIGUOUS" for item in best.evidence)}
            st.markdown("**Evidence distribution**")
            st.bar_chart(pd.DataFrame.from_dict(evidence_status, orient="index", columns=["Claims"]), color="#9d86eb", height=180)
        with tabs[3]:
            if len(candidates) == 1:
                st.markdown('<div class="empty"><div class="empty-title">Single candidate run</div><div class="empty-copy">Increase candidate count in the policy panel, or provide multiple responses separated by |||, to compare candidates.</div></div>', unsafe_allow_html=True)
            else:
                st.markdown("**Ranked by measured toolkit reliability**")
                comp = pd.DataFrame([{"Rank": index + 1, "Candidate": candidate.id, "Reliability": candidate.reliability, "Agreement": candidate.agreement, "Decision": candidate.decision, "Claims": len(candidate.claims)} for index, candidate in enumerate(candidates)])
                st.dataframe(comp, width="stretch", hide_index=True)
                st.bar_chart(comp.set_index("Candidate")[["Reliability", "Agreement"]], color=["#9d86eb", "#62b7c8"], height=240)
                for index, candidate in enumerate(candidates):
                    with st.expander(f"#{index+1} · {candidate.id} · {candidate.decision} · {candidate.reliability:.0%}"):
                        st.write(candidate.text)
                        st.caption(f"{len(candidate.claims)} claims · {len(candidate.evidence)} evidence records · {candidate.model}")
                        st.dataframe(pd.DataFrame(claim_rows(candidate)), width="stretch", hide_index=True)
        with tabs[4]:
            st.markdown('<div class="eyebrow">EVIDENCE-BACKED CORRECTION</div>', unsafe_allow_html=True)
            if best.corrected_text and best.corrected_text != best.text:
                original_col, corrected_col = st.columns(2, gap="large")
                with original_col:
                    st.markdown('<div class="surface"><div class="metric-label">ORIGINAL RESPONSE</div><div style="margin-top:12px;color:#c5c9d3;line-height:1.7">'+html.escape(best.text)+'</div></div>', unsafe_allow_html=True)
                with corrected_col:
                    st.markdown('<div class="surface"><div class="metric-label">VERIFIED CORRECTION</div><div style="margin-top:12px;color:#e8e4f5;line-height:1.7">'+html.escape(best.corrected_text)+'</div></div>', unsafe_allow_html=True)
                st.markdown("**Diagnoses**")
                for diagnosis in best.diagnosis:
                    st.markdown(f"- `{diagnosis}`")
                st.caption("Only claims with sufficient contradictory visual evidence are changed; unsupported and ambiguous claims are retained.")
            else:
                st.markdown('<div class="empty"><div class="empty-mark">✓</div><div class="empty-title">No evidence-backed correction</div><div class="empty-copy">The verifier did not find a sufficiently supported change. This is not presented as a correction.</div></div>', unsafe_allow_html=True)
            st.download_button("Export selected candidate JSON", json.dumps(best.export(), indent=2), "experiment.json", "application/json")

elif page == "Evaluation":
    st.markdown('<div class="eyebrow">RESEARCH WORKSPACE · EVALUATION</div>', unsafe_allow_html=True)
    st.title("Measure what the evidence can support.")
    st.markdown('<div class="hero-copy">Evaluation metrics are computed only from labelled records. No synthetic baseline or benchmark results are shown.</div>', unsafe_allow_html=True)
    metrics = classification_metrics([])
    st.markdown('<div class="section-head">Labelled evaluation</div>', unsafe_allow_html=True)
    st.markdown('<div class="empty"><div class="empty-mark">⌗</div><div class="empty-title">No labelled evaluation set connected</div><div class="empty-copy">Run labelled experiments and provide expected-reliability labels before reporting precision, recall, F1, calibration, or correction success.</div></div>', unsafe_allow_html=True)
    st.info(metrics["message"])
    st.markdown('<div class="section-head">Available metrics when labels exist</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for col, label in zip(cols, ["Precision / recall / F1", "Brier score", "Calibration / ECE", "Correction success"]):
        with col:
            metric_card(label, "—", "Requires labelled evaluation records")
    st.caption("The local evaluator currently accepts labelled records programmatically; the application does not imply unrun benchmark scores.")

else:
    st.markdown('<div class="eyebrow">RESEARCH WORKSPACE · EXPERIMENTS</div>', unsafe_allow_html=True)
    st.title("Every run, traceable.")
    st.markdown('<div class="hero-copy">A local record of the prompts, candidates, and reliability experiments this workspace has performed.</div>', unsafe_allow_html=True)
    rows = recent()
    if not rows:
        st.markdown('<div class="empty"><div class="empty-mark">◷</div><div class="empty-title">No experiments yet</div><div class="empty-copy">Your completed analyses will appear here, with full exports available for review.</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="section-head">{len(rows)} recent experiments</div>', unsafe_allow_html=True)
        selected = st.selectbox("Review saved experiment", rows, format_func=lambda row: f"#{row[0]} · {row[1]} · {row[2]}", key="history_select")
        payload = json.loads(selected[3])
        st.markdown(f'<div class="surface"><div class="metric-label">EXPERIMENT #{selected[0]} · {html.escape(str(selected[1]))}</div><div style="font-size:17px;color:#eceef4;margin-top:8px">{html.escape(str(selected[2]))}</div></div>', unsafe_allow_html=True)
        st.json(payload, expanded=False)
        st.download_button("Export experiment JSON", json.dumps(payload, indent=2), f"experiment-{selected[0]}.json", "application/json")
        st.download_button("Export candidates CSV", pd.json_normalize(payload.get("candidates", [])).to_csv(index=False), f"experiment-{selected[0]}.csv", "text/csv")
