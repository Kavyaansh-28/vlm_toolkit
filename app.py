import streamlit as st
from agent import RajasthanAgent
from retrieval import get_retriever, retrieve_knowledge
from planner import plan_itinerary
from tools import search_restaurants

st.set_page_config(page_title="Rajasthan Explorer AI", page_icon="✦", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
:root { --ink:#251a16; --muted:#806d63; --card:#fffdf9; }.stApp{background:radial-gradient(circle at 88% 2%,#fce2bd 0,transparent 23%),#fff8ef;color:var(--ink)}#MainMenu,footer{visibility:hidden}.block-container{max-width:1180px;padding-top:1.2rem;padding-bottom:3rem}.brand{font-size:.76rem;letter-spacing:.14em;font-weight:700;color:#9d3349;text-transform:uppercase;margin-bottom:.55rem}.hero{background:linear-gradient(116deg,#461f22,#9d3349 57%,#cf6136);color:white;border-radius:25px;padding:2.4rem 2.7rem;margin:0 0 1.25rem;box-shadow:0 16px 34px #7c3b2c30}.hero h1{font-family:Georgia,serif;font-size:3rem;margin:0 0 .45rem;letter-spacing:-.04em}.hero p{font-size:1.08rem;max-width:660px;opacity:.9;margin:0}.pill{display:inline-block;background:#fff1df;color:#9d3349;padding:.35rem .65rem;border-radius:999px;font-size:.78rem;font-weight:700;margin:.75rem .35rem 0 0}.stat{background:var(--card);border:1px solid #eadbce;border-radius:16px;padding:1rem 1.15rem;height:100%;box-shadow:0 4px 12px #4f29100b}.stat b{display:block;font-size:1.35rem;color:#9d3349}.stat span{font-size:.8rem;color:var(--muted)}.day{background:var(--card);border:1px solid #eadbce;border-left:5px solid #d85a2a;border-radius:14px;padding:1rem 1.2rem;margin:.65rem 0}.day h3{margin:0 0 .45rem;font-family:Georgia,serif;color:#4f2821}.day p{margin:.28rem 0;color:#503f37}.label{font-size:.72rem;color:#9d3349;font-weight:800;letter-spacing:.07em;text-transform:uppercase}.food-card{background:#fffdf9;border:1px solid #eadbce;border-radius:14px;padding:1rem 1.15rem;margin:.6rem 0}.food-card h3{margin:0 0 .35rem;color:#4f2821}.food-card p{color:#68574e;margin:.25rem 0}.stButton>button{background:#9d3349;color:white;border:0;border-radius:10px;font-weight:700;padding:.55rem 1.05rem}.stButton>button:hover{background:#7e2639;color:white}[data-testid="stSidebar"]{background:#351e20;color:white}[data-testid="stSidebar"] .stMarkdown{color:white}.stTextArea textarea{border-radius:14px;border:1px solid #d8c0b1;background:#fffdf9}.stTabs [data-baseweb="tab"]{font-weight:700}
</style>""", unsafe_allow_html=True)

if "agent" not in st.session_state: st.session_state.agent=RajasthanAgent()
if "context" not in st.session_state: st.session_state.context={}
if "history" not in st.session_state: st.session_state.history=[]

def run_prompt(prompt):
    prompt=(prompt or "").strip()
    if not prompt: return
    st.session_state.history.append({"role":"You","content":prompt})
    st.session_state.last_result=st.session_state.agent.run(prompt,st.session_state.context)
    st.session_state.context=st.session_state.last_result["context"]
    st.session_state.history.append({"role":"Explorer AI","content":st.session_state.last_result["answer"]})

def render_result(result):
    if not result: return
    st.success(result["answer"])
    plan=result.get("plan")
    if plan:
        budget=plan["budget"]; a,b,c=st.columns(3)
        a.markdown(f"<div class='stat'><b>₹{budget['per_person']:,}</b><span>estimated per traveller</span></div>",unsafe_allow_html=True)
        b.markdown(f"<div class='stat'><b>₹{budget['group_total']:,}</b><span>estimated group total</span></div>",unsafe_allow_html=True)
        c.markdown(f"<div class='stat'><b>{len(plan['cities'])}</b><span>cities in your route</span></div>",unsafe_allow_html=True)
        st.markdown("#### Your day-by-day route")
        for d in plan["itinerary"]:
            st.markdown(f"<div class='day'><div class='label'>Day {d['day']} · {d['city']}</div><h3>{d['morning']}</h3><p><b>Afternoon</b> — {d['afternoon']}</p><p><b>Evening</b> — {d['evening']}</p><p>🛺 {d['transport']} &nbsp; · &nbsp; 🍽 {d['meal']}</p></div>",unsafe_allow_html=True)
        with st.expander("See budget assumptions"):
            st.dataframe([{"Category":k,"Estimated INR per person":f"₹{v:,}"} for k,v in budget["breakdown_per_person"].items()],hide_index=True,use_container_width=True)
            st.caption(budget["note"])
        st.markdown("#### Stay and food guidance")
        stays=result.get("stays",{})
        if stays:
            st.info(f"**Stay approach for {stays.get('city','your route')}:** {stays.get('guidance','Confirm current availability directly.')}")
        restaurants=result.get("restaurants",[])
        if restaurants:
            for restaurant in restaurants[:4]:
                st.markdown(f"<div class='food-card'><h3>{restaurant.get('name',restaurant.get('title','Local food idea'))}</h3><p>{restaurant.get('text','Confirm menu and availability directly.')}</p><p><b>{restaurant.get('cuisine','Local cuisine')}</b> · {restaurant.get('price_level','price not verified')}</p></div>",unsafe_allow_html=True)
        else:
            st.caption("No matching local food document yet. Ask for a different dietary preference, or use a configured live search provider.")
    with st.expander("Why Explorer AI suggested this"):
        st.markdown("**Tool activity**"); st.dataframe(result.get("trace",[]),hide_index=True,use_container_width=True)
        st.markdown("**Retrieved local evidence**")
        for item in result.get("evidence",[]):
            st.markdown(f"**{item['title']}** · relevance {item['score']}"); st.caption(item['text'])
            if item.get("source_url"): st.markdown(f"[Source reference]({item['source_url']}) · {item['source_type']}")

with st.sidebar:
    st.markdown("## ✦ Explorer AI"); st.caption("Rajasthan travel planning grounded in local retrieval and transparent estimates."); st.divider(); st.markdown("**Trip preferences**")
    styles=["balanced","budget","premium"]; current=st.session_state.context.get("style","balanced")
    st.session_state.context["style"]=st.selectbox("Travel style",styles,index=styles.index(current))
    st.caption("This shapes your next request; you can also say it naturally.")
    if st.button("Start a new plan",use_container_width=True):
        st.session_state.context={"style":"balanced"}; st.session_state.history=[]; st.session_state.pop("last_result",None); st.rerun()
    st.divider(); st.caption("No reservations are made. Live listings need Google Places; local fallbacks are labelled.")

st.markdown("<div class='brand'>Intelligent travel companion · Rajasthan, India</div>",unsafe_allow_html=True)
st.markdown("<section class='hero'><h1>Travel Rajasthan with a plan that breathes.</h1><p>Build a realistic route, find food ideas, track a transparent budget, and see the evidence behind each recommendation.</p><span class='pill'>RAG-powered local knowledge</span><span class='pill'>Paced itineraries</span><span class='pill'>Honest estimates</span></section>",unsafe_allow_html=True)
tab_plan,tab_food,tab_explore,tab_budget=st.tabs(["✦ Plan a trip","🍽 Food finder","⌕ Knowledge explorer","₹ Budget studio"])

with tab_plan:
    left,right=st.columns([1.55,.95],gap="large")
    with left:
        st.markdown("### Tell me where you want to go")
        prompt=st.text_area("Your travel request",placeholder="Example: Plan Jaipur, Jodhpur and Udaipur in 8 days under ₹35,000. We love forts, local food and relaxed evenings.",label_visibility="collapsed",height=112,key="main_prompt")
        action_col,sample_col=st.columns([.45,.55])
        with action_col:
            if st.button("Create my plan ✦",type="primary",use_container_width=True): run_prompt(prompt)
        with sample_col: st.caption("Include cities, days, budget, travellers, food needs or travel style.")
        st.markdown("**Quick starts**"); q1,q2,q3=st.columns(3)
        if q1.button("5 days · first trip",use_container_width=True): run_prompt("Plan Jaipur and Udaipur in 5 days with a balanced budget")
        if q2.button("Desert + heritage",use_container_width=True): run_prompt("Plan Jodhpur and Jaisalmer in 5 days with desert experiences")
        if q3.button("Make it cheaper",use_container_width=True): run_prompt("Make my current itinerary cheaper")
    with right:
        st.markdown("### What this does")
        st.markdown("**1. Understands constraints**  \nCities, duration, style, budget, diet and follow-ups.\n\n**2. Checks evidence**  \nRetrieves relevant local passages—not the entire dataset.\n\n**3. Validates the pace**  \nKeeps transfer days and wildlife planning realistic.")
    if st.session_state.get("last_result"):
        st.divider(); render_result(st.session_state.last_result)
    if st.session_state.history:
        with st.expander("Conversation history"):
            for msg in st.session_state.history: st.markdown(f"**{msg['role']}:** {msg['content']}")

with tab_food:
    st.markdown("### Find food ideas without overpromising"); x,y,z=st.columns(3)
    city=x.selectbox("City",["Jaipur","Udaipur","Jodhpur","Jaisalmer"],key="food_city"); diet=y.selectbox("Preference",["Any","vegetarian","jain","vegan"],key="food_diet")
    z.write(""); z.write(""); find_food=z.button("Search food ideas",use_container_width=True)
    if find_food:
        result=search_restaurants(city,dietary=None if diet=="Any" else diet); st.warning(result["notice"])
        if not result["results"]: st.info("No local fallback listing matches that filter. Try ‘Any’ and confirm needs directly with restaurants.")
        for r in result["results"]: st.markdown(f"<div class='food-card'><h3>{r['name']}</h3><p>{r['text']}</p><p><b>{r['cuisine']}</b> · {r['price_level']}<br>{r['address']}</p></div>",unsafe_allow_html=True)
        if diet in {"jain","vegan"}: st.info("Jain/vegan suitability, ghee/dairy, onion/garlic and cross-contact need direct confirmation with the venue.")

with tab_explore:
    st.markdown("### Inspect the retrieval layer"); st.caption(f"{len(get_retriever().documents)} local documents indexed with TF-IDF. Results include source type and relevance score.")
    query=st.text_input("Search Rajasthan knowledge","desert safari safety",key="rag_query")
    for row in retrieve_knowledge(query,top_k=8) if query else []:
        with st.container(border=True):
            st.markdown(f"**{row['title']}** · `{row['destination']}` · relevance `{row['score']}`"); st.write(row['text']); st.caption(row['source_type'])
            if row.get("source_url"): st.link_button("Open source reference",row['source_url'])

with tab_budget:
    st.markdown("### Build a transparent estimate"); a,b,c=st.columns(3)
    days=a.number_input("Days",1,15,5,key="budget_days"); travellers=b.number_input("Travellers",1,12,2,key="budget_people"); style=c.selectbox("Style",["budget","balanced","premium"],key="budget_style")
    cities=st.multiselect("Route cities",["Jaipur","Udaipur","Jodhpur","Jaisalmer","Pushkar","Ranthambore","Mount Abu","Bundi"],default=["Jaipur","Udaipur"],key="budget_cities")
    if st.button("Estimate my trip",key="estimate"):
        p=plan_itinerary(cities,days,travellers,style); st.metric("Estimated group total",f"₹{p['budget']['group_total']:,}",help="Planning estimate; not a quote."); st.bar_chart(p["budget"]["breakdown_per_person"],color="#9d3349"); st.caption(p["budget"]["note"])
