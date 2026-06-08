import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import json
import time
import datetime
from metrics import compute_all_metrics
from agent import TeamLensAgent
from reasoning_engine import reason, is_reasoning_question

st.set_page_config(
    page_title="TeamLens",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════
DIVIDER = '<div class="div"></div>'
AVATAR_PALETTES = [
    ("#4338CA", "rgba(99,102,241,0.18)"),
    ("#BE185D", "rgba(236,72,153,0.18)"),
    ("#065F46", "rgba(16,185,129,0.18)"),
    ("#B45309", "rgba(245,158,11,0.15)"),
    ("#1D4ED8", "rgba(59,130,246,0.18)"),
    ("#6D28D9", "rgba(167,139,250,0.18)"),
]
_SUGGESTIONS = [
    "What should I discuss in my 1:1 with emily.zhang?",
    "Why did reliability degrade in February?",
    "Who is at highest risk of burnout?",
    "What is the current sprint completion rate?",
]
_SPLASH = """
<div style="position:fixed;top:0;left:0;right:0;bottom:0;background:#090c14;
z-index:9999;display:flex;flex-direction:column;align-items:center;
justify-content:center;font-family:'Inter',system-ui,sans-serif;">
  <div style="position:relative;width:80px;height:80px;margin-bottom:2rem;">
    <div style="position:absolute;inset:0;border-radius:50%;
    border:2px solid transparent;border-top-color:#4af0a4;
    border-right-color:rgba(74,240,164,0.25);
    animation:tl-cw 1.2s linear infinite;"></div>
    <div style="position:absolute;inset:12px;border-radius:50%;
    border:2px solid transparent;border-bottom-color:#7c9eff;
    border-left-color:rgba(124,158,255,0.25);
    animation:tl-ccw 0.85s linear infinite;"></div>
    <div style="position:absolute;inset:0;display:flex;align-items:center;
    justify-content:center;font-size:1.7rem;">🔭</div>
  </div>
  <div style="font-size:1.55rem;font-weight:800;letter-spacing:-0.5px;
  background:linear-gradient(135deg,#d8e2f5 30%,#7c9eff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;margin-bottom:0.3rem;">TeamLens</div>
  <div style="font-size:0.68rem;color:#2e3a52;letter-spacing:2px;
  text-transform:uppercase;margin-bottom:2.5rem;">Engineering Health Dashboard</div>
  <div style="height:1.2rem;position:relative;overflow:hidden;
  width:300px;text-align:center;margin-bottom:1.5rem;">
    <div style="position:absolute;width:100%;font-size:0.78rem;color:#4af0a4;
    font-family:'Courier New',monospace;animation:tl-s1 3s steps(1,end) infinite;">
      Connecting to metrics pipeline...</div>
    <div style="position:absolute;width:100%;font-size:0.78rem;color:#4af0a4;
    font-family:'Courier New',monospace;opacity:0;animation:tl-s2 3s steps(1,end) infinite;">
      Loading team health data...</div>
    <div style="position:absolute;width:100%;font-size:0.78rem;color:#4af0a4;
    font-family:'Courier New',monospace;opacity:0;animation:tl-s3 3s steps(1,end) infinite;">
      Warming up AI reasoning engine...</div>
  </div>
  <div style="width:220px;height:2px;background:#1c2235;border-radius:2px;overflow:hidden;">
    <div style="height:100%;background:linear-gradient(90deg,#4af0a4,#7c9eff);
    border-radius:2px;animation:tl-bar 2.5s ease-out forwards;width:0%;"></div>
  </div>
  <div style="position:fixed;bottom:1.5rem;right:2rem;font-family:'Courier New',monospace;
  font-size:0.6rem;color:#1c2235;letter-spacing:1.5px;text-transform:uppercase;">
    Powered by Claude</div>
  <style>
    @keyframes tl-cw  { to { transform:rotate(360deg); } }
    @keyframes tl-ccw { to { transform:rotate(-360deg); } }
    @keyframes tl-bar { from{width:0%} to{width:100%} }
    @keyframes tl-s1  { 0%,33%{opacity:1} 34%,100%{opacity:0} }
    @keyframes tl-s2  { 0%,33%{opacity:0} 34%,66%{opacity:1} 67%,100%{opacity:0} }
    @keyframes tl-s3  { 0%,66%{opacity:0} 67%,100%{opacity:1} }
  </style>
</div>
"""

_PLOT = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#64748B", family="Inter, sans-serif", size=11),
    legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#64748B")),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False,
               tickfont=dict(color="#64748B")),
    margin=dict(t=5, b=10, l=10, r=10),
    hovermode="x unified",
)
_PLOT_H = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#64748B", family="Inter, sans-serif", size=11),
    coloraxis_showscale=False,
    margin=dict(t=5, b=10, l=90, r=10),
    hovermode="y unified",
    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False,
               tickfont=dict(color="#64748B")),
    yaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#94A3B8")),
)

# ══════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════
def inject_global_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif !important; }

#MainMenu, footer { visibility: hidden; }
.stDeployButton, [data-testid="collapsedControl"] { display: none !important; }

.stApp {
    background: #0B1120;
    background-image:
        radial-gradient(ellipse 90% 45% at 50% 0%, rgba(99,102,241,0.12) 0%, transparent 60%),
        radial-gradient(ellipse 45% 30% at 95% 90%, rgba(139,92,246,0.06) 0%, transparent 50%);
    min-height: 100vh;
}
.main .block-container {
    padding: 2.5rem 2rem 5rem !important;
    max-width: 1080px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.25); border-radius: 4px; }

/* ── App header ── */
.app-header {
    display: flex; align-items: center; justify-content: space-between;
    padding-bottom: 1.25rem; margin-bottom: 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.brand { display: flex; align-items: center; gap: 0.9rem; }
.brand-icon {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #6366F1, #8B5CF6);
    border-radius: 10px; display: flex; align-items: center;
    justify-content: center; font-size: 1.15rem;
    box-shadow: 0 4px 20px rgba(99,102,241,0.45); flex-shrink: 0;
}
.brand-name {
    font-size: 1.3rem; font-weight: 800; letter-spacing: -0.5px;
    background: linear-gradient(135deg, #F1F5F9 30%, #A5B4FC 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.brand-sub { font-size: 0.72rem; color: #64748B; font-weight: 400; margin-top: 1px; }
.live-pill {
    display: flex; align-items: center; gap: 0.4rem;
    background: rgba(16,185,129,0.07); border: 1px solid rgba(16,185,129,0.2);
    color: #34D399; font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.6px; padding: 0.28rem 0.75rem; border-radius: 999px;
}
.pulse { width: 6px; height: 6px; background: #10B981; border-radius: 50%; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── Section headers ── */
.s-head { display: flex; align-items: center; gap: 0.6rem; margin: 0 0 1.1rem; }
.s-bar { width: 3px; height: 17px; background: linear-gradient(#6366F1, #8B5CF6); border-radius: 2px; flex-shrink: 0; }
.s-title { font-size: 0.88rem; font-weight: 700; color: #E2E8F0; letter-spacing: -0.1px; }
.s-sub { font-size: 0.73rem; color: #64748B; margin-left: auto; letter-spacing: 0; }

/* ── Divider ── */
.div {
    height: 1px; margin: 1.75rem 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0.06) 70%, transparent);
}

/* ── KPI cards ── */
.kpi {
    background: rgba(14,20,36,0.9); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 1.2rem 1.35rem;
    position: relative; overflow: hidden; transition: border-color 0.2s, box-shadow 0.2s;
}
.kpi:hover { border-color: rgba(99,102,241,0.25); box-shadow: 0 0 20px rgba(99,102,241,0.06); }
.kpi-top { position: absolute; top:0; left:0; right:0; height: 2px; }
.kpi-lbl { font-size: 0.67rem; font-weight: 600; letter-spacing: 1.1px; text-transform: uppercase; color: #94A3B8; margin-bottom: 0.5rem; }
.kpi-num { font-size: 2rem; font-weight: 800; letter-spacing: -1.5px; line-height: 1; }
.kpi-hint { font-size: 0.69rem; color: #64748B; margin-top: 0.28rem; }

/* ── Burnout cards ── */
.bc {
    background: rgba(14,20,36,0.85); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 1rem; transition: border-color 0.2s;
}
.bc:hover { border-color: rgba(99,102,241,0.2); }
.bc-av { width: 32px; height: 32px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.78rem; font-weight: 800; margin-bottom: 0.6rem; }
.bc-name { font-size: 0.78rem; font-weight: 600; color: #CBD5E1; }
.bc-score { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.5px; line-height: 1.1; }
.bc-bar { height: 3px; background: rgba(255,255,255,0.07); border-radius: 2px; margin: 0.5rem 0 0.4rem; overflow: hidden; }
.bc-fill { height: 100%; border-radius: 2px; }
.bc-badge { display: inline-block; font-size: 0.6rem; font-weight: 700; letter-spacing: 0.3px; text-transform: uppercase; padding: 0.14rem 0.5rem; border-radius: 999px; }
.bc-carry { font-size: 0.66rem; color: #64748B; margin-top: 0.3rem; }

/* ── Blockers ── */
.blk { padding: 0.65rem 0.85rem; background: rgba(8,12,24,0.7); border-left: 2px solid #F59E0B; border-radius: 0 8px 8px 0; margin-bottom: 0.4rem; overflow: hidden; }
.blk-t { font-weight: 600; color: #F1F5F9; font-size: 0.82rem; }
.blk-d { color: #F59E0B; font-size: 0.75rem; font-weight: 600; float: right; }
.blk-r { color: #94A3B8; font-size: 0.77rem; margin-top: 0.2rem; clear: both; }

/* ── Expanders ── */
[data-testid="stExpander"] { background: #0a0d16 !important; border: 1px solid #1c2235 !important; border-radius: 10px !important; margin-bottom: 0.4rem !important; }
[data-testid="stExpander"] > details > summary { font-size: 0.82rem !important; color: #94A3B8 !important; padding: 0.65rem 1rem !important; font-weight: 500 !important; }
[data-testid="stExpander"] > details > summary:hover { color: #d8e2f5 !important; }
[data-testid="stExpander"] p, [data-testid="stExpander"] span { color: #8a9bb8 !important; }
[data-testid="stExpander"] .stCaption, [data-testid="stExpander"] small { color: #8a9bb8 !important; font-size: 0.8rem !important; }

/* ══════════════════════════════════════════════
   TAB BAR — st.radio restyled as pill nav.
   We keep st.radio as the actual Streamlit widget
   (so clicks trigger reruns) but restyle it to
   look like a modern segment control.
   ══════════════════════════════════════════════ */

/* Outer pill container */
div[data-testid="stRadio"] {
    background: rgba(8,12,24,0.75) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    padding: 3px !important;
    display: inline-flex !important;
    width: auto !important;
    margin-top: 1.25rem !important;
    margin-bottom: 1.75rem !important;
}

/* Row of labels */
div[data-testid="stRadio"] > div {
    flex-direction: row !important;
    gap: 0 !important;
    align-items: center !important;
}

/* Each label pill */
div[data-testid="stRadio"] > div > label {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    padding: 7px 20px !important;
    border-radius: 7px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #64748B !important;
    cursor: pointer !important;
    border: none !important;
    background: transparent !important;
    margin: 0 !important;
    transition: color 0.15s ease, background 0.15s ease !important;
    letter-spacing: -0.1px !important;
    white-space: nowrap !important;
    /* Pull the label text and hide the radio circle affordance */
    -webkit-text-fill-color: #64748B !important;
}

div[data-testid="stRadio"] > div > label:hover {
    color: #CBD5E1 !important;
    -webkit-text-fill-color: #CBD5E1 !important;
    background: rgba(255,255,255,0.04) !important;
}

/* Active / selected pill */
div[data-testid="stRadio"] > div > label:has(input:checked) {
    background: rgba(99,102,241,0.15) !important;
    color: #A5B4FC !important;
    -webkit-text-fill-color: #A5B4FC !important;
    font-weight: 600 !important;
}

/* Hide the actual radio circle — completely */
div[data-testid="stRadio"] input[type="radio"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    position: absolute !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* Hide the visual radio dot span Streamlit renders */
div[data-testid="stRadio"] > div > label > div:first-child {
    display: none !important;
}

/* ── Suggestion chips ── */
.stButton > button {
    background: transparent !important; color: #94A3B8 !important;
    border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 999px !important;
    font-size: 0.8rem !important; font-weight: 500 !important;
    padding: 0.5rem 1rem !important; height: auto !important;
    text-align: center !important; line-height: 1.45 !important;
    transition: all 0.18s !important; white-space: normal !important;
}
.stButton > button:hover {
    background: rgba(99,102,241,0.09) !important;
    border-color: rgba(99,102,241,0.35) !important; color: #E2E8F0 !important;
    box-shadow: none !important; transform: none !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div,
[data-testid="stChatInput"] [data-baseweb="textarea"],
[data-testid="stChatInput"] [data-baseweb="base-input"] {
    background-color: #0f1420 !important; border-radius: 12px !important;
}
[data-testid="stChatInput"] { border: 1px solid rgba(255,255,255,0.22) !important; outline: none !important; }
[data-testid="stChatInput"]:focus-within { border-color: rgba(99,102,241,0.5) !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important; outline: none !important; }
div[data-testid="stChatInput"] textarea {
    background-color: #0f1420 !important; color: #d8e2f5 !important;
    -webkit-text-fill-color: #d8e2f5 !important; border-color: #1c2235 !important;
    caret-color: #4af0a4 !important;
}
div[data-testid="stChatInput"] textarea::placeholder {
    color: rgba(138,155,184,0.45) !important;
    -webkit-text-fill-color: rgba(138,155,184,0.45) !important; opacity: 1 !important;
}
div[data-testid="stChatInput"] textarea:focus {
    border-color: #4af0a4 !important;
    box-shadow: 0 0 0 1px rgba(74,240,164,0.15) !important; outline: none !important;
}

/* Misc */
.stSpinner > div { border-top-color: #6366F1 !important; }
.stCaption, small { color: #64748B !important; font-size: 0.72rem !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════
def section_header(title, sub=""):
    sub_html = f'<span class="s-sub">{sub}</span>' if sub else ""
    st.markdown(
        f'<div class="s-head"><div class="s-bar"></div>'
        f'<span class="s-title">{title}</span>{sub_html}</div>',
        unsafe_allow_html=True,
    )


@st.cache_data
def load_metrics():
    return compute_all_metrics()


def process_query(query: str):
    """Compute AI answer and append to chat_history. Never calls st.rerun()."""
    if is_reasoning_question(query):
        result = reason(query)
        answer = result["answer"]
        thinking = result.get("thinking", "")
        model = result["model"]
    else:
        res = st.session_state.agent.run(query)
        answer = res if isinstance(res, str) else res.get("answer", "")
        thinking = ""
        model = "llama-3.3-70b-versatile"
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer,
        "thinking": thinking,
        "model": model,
        "ts": datetime.datetime.now().strftime("%H:%M"),
    })


# ══════════════════════════════════════════════════════════════════════
# RENDER — DASHBOARD
# ══════════════════════════════════════════════════════════════════════
def render_dashboard(metrics):
    section_header("Team Health", "Burnout risk · carry-overs · blocker density")
    burnout = metrics["burnout_risk"]
    max_score = max((e["burnout_score"] for e in burnout), default=10)

    cols = st.columns(len(burnout))
    for i, eng in enumerate(burnout):
        with cols[i]:
            risk = eng["risk_level"]
            score = eng["burnout_score"]
            name = eng["engineer"].split(".")[0].capitalize()
            pct = min(100, int(score / max(max_score, 1) * 100))
            txt_c, bg_c = AVATAR_PALETTES[i % len(AVATAR_PALETTES)]
            if "High" in risk:
                sc, bb, bc = "#EF4444", "rgba(239,68,68,0.1)", "rgba(239,68,68,0.25)"
            elif "Medium" in risk:
                sc, bb, bc = "#F59E0B", "rgba(245,158,11,0.1)", "rgba(245,158,11,0.25)"
            else:
                sc, bb, bc = "#10B981", "rgba(16,185,129,0.1)", "rgba(16,185,129,0.25)"
            st.markdown(f"""
            <div class="bc">
                <div class="bc-av" style="background:{bg_c};color:{txt_c};">{name[0]}</div>
                <div class="bc-name">{name}</div>
                <div class="bc-score" style="color:{sc};">{score}</div>
                <div class="bc-bar"><div class="bc-fill" style="width:{pct}%;background:{sc};"></div></div>
                <span class="bc-badge" style="background:{bb};color:{sc};border:1px solid {bc};">{risk}</span>
                <div class="bc-carry">{eng['carry_overs']} carry-overs</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(DIVIDER, unsafe_allow_html=True)

    section_header("Key Metrics")
    velocity    = metrics["sprint_velocity"]
    avg_comp    = sum(v["completion_pct"] for v in velocity) / len(velocity)
    inc_trend   = metrics["incident_trend"]
    latest_inc  = inc_trend[-1]["total"] if inc_trend else 0
    cycle_times = metrics["cycle_time_by_engineer"]
    avg_cycle   = sum(c["avg_cycle_time_days"] for c in cycle_times) / len(cycle_times)
    blocked     = metrics["blocked_work"]
    total_blk   = sum(e["total_blocked_days"] for e in blocked)

    k1, k2, k3, k4 = st.columns(4)
    kpi_defs = [
        (k1, "Sprint Completion", f"{avg_comp:.0f}%",  f"avg over {len(velocity)} sprints", "#818CF8", "linear-gradient(90deg,#6366F1,#818CF8)"),
        (k2, "Latest Incidents",  str(latest_inc),      "this period",                       "#F472B6", "linear-gradient(90deg,#EC4899,#F472B6)"),
        (k3, "Avg Cycle Time",    f"{avg_cycle:.1f}d",  "days per ticket",                   "#34D399", "linear-gradient(90deg,#10B981,#34D399)"),
        (k4, "Blocked Days",      f"{total_blk}d",      "across all engineers",               "#FBBF24", "linear-gradient(90deg,#F59E0B,#FBBF24)"),
    ]
    for col, lbl, val, hint, color, grad in kpi_defs:
        with col:
            st.markdown(f"""
            <div class="kpi">
                <div class="kpi-top" style="background:{grad};"></div>
                <div class="kpi-lbl">{lbl}</div>
                <div class="kpi-num" style="color:{color};">{val}</div>
                <div class="kpi-hint">{hint}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(DIVIDER, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        section_header("Sprint Velocity")
        sprints = [v["sprint"] for v in velocity]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Committed", x=sprints, y=[v["committed"] for v in velocity], marker_color="rgba(99,102,241,0.2)"))
        fig.add_trace(go.Bar(name="Completed",  x=sprints, y=[v["completed"]  for v in velocity], marker_color="#6366F1", opacity=0.9))
        fig.update_layout(barmode="overlay", height=290, **_PLOT)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with c2:
        section_header("Incident Trend")
        months = [t["month"] for t in inc_trend]
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(name="Total", x=months, y=[t["total"] for t in inc_trend],
            mode="lines+markers", line=dict(color="#8B5CF6", width=2.5),
            marker=dict(size=6, color="#8B5CF6", line=dict(color="#0B1120", width=2)),
            fill="tozeroy", fillcolor="rgba(139,92,246,0.07)"))
        fig2.add_trace(go.Scatter(name="P0/P1", x=months, y=[t["p0_p1"] for t in inc_trend],
            mode="lines+markers", line=dict(color="#EF4444", width=1.8, dash="dot"),
            marker=dict(size=5, color="#EF4444")))
        fig2.update_layout(height=290, **_PLOT)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.markdown(DIVIDER, unsafe_allow_html=True)

    c3, c4 = st.columns(2)
    with c3:
        section_header("Cycle Time by Engineer")
        fig3 = px.bar(cycle_times, x="avg_cycle_time_days", y="engineer", orientation="h",
                      color="avg_cycle_time_days",
                      color_continuous_scale=["#10B981", "#F59E0B", "#EF4444"],
                      labels={"avg_cycle_time_days": "Days", "engineer": ""})
        fig3.update_layout(height=275, **_PLOT_H)
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    with c4:
        section_header("Oncall Burden Score")
        oncall = metrics["oncall_burden"]
        fig4 = px.bar(oncall, x="burden_score", y="engineer", orientation="h",
                      color="burden_score",
                      color_continuous_scale=["#10B981", "#F59E0B", "#EC4899"],
                      labels={"burden_score": "Score", "engineer": ""})
        fig4.update_layout(height=275, **_PLOT_H)
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

    st.markdown(DIVIDER, unsafe_allow_html=True)

    section_header("Work Blockers", "Issues preventing engineers from making progress")
    for engineer in blocked:
        if engineer["blocked_tickets"]:
            with st.expander(f"{engineer['engineer']}  ·  {engineer['total_blocked_days']}d blocked"):
                for t in engineer["blocked_tickets"]:
                    st.markdown(f"""
                    <div class="blk">
                        <span class="blk-t">{t['ticket']}</span>
                        <span class="blk-d">{t['days']}d</span>
                        <div class="blk-r">{t['reason']}</div>
                    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# RENDER — ASK AI
# ══════════════════════════════════════════════════════════════════════
def render_ask_ai():
    _, chat_col, _ = st.columns([1, 4, 1])
    with chat_col:

        # Handle pending chip query — process then fall through to render
        if st.session_state.get("pending_query"):
            query = st.session_state.pending_query
            st.session_state.pending_query = None
            st.session_state.chat_history.append({"role": "user", "content": query})
            with st.spinner("Thinking..."):
                process_query(query)

        # ── HEADER + CHIPS — always visible regardless of chat state ──
        st.markdown("""
        <div style="text-align:center;padding:2rem 0 1.5rem;">
            <div style="font-size:2rem;margin-bottom:0.5rem;">🔭</div>
            <div style="font-size:1.15rem;font-weight:700;color:#d8e2f5;letter-spacing:-0.3px;">
                Ask TeamLens AI
            </div>
            <div style="font-size:0.78rem;color:#4a5568;margin-top:0.35rem;
            font-family:'Courier New',monospace;letter-spacing:0.5px;">
                Powered by Claude · reasoning over live metrics
            </div>
        </div>""", unsafe_allow_html=True)

        sc1, sc2 = st.columns(2)
        for i, s in enumerate(_SUGGESTIONS):
            with (sc1 if i % 2 == 0 else sc2):
                if st.button(s, key=f"chip_{i}", use_container_width=True):
                    st.session_state.pending_query = s
                    st.session_state["_pending_tab"] = "Ask AI"
                    st.rerun()

        # ── CONVERSATION HISTORY — only when messages exist ──
        if st.session_state.chat_history:
            st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"""
                    <div style="display:flex;justify-content:flex-end;margin:8px 0 4px;">
                      <div style="background:#1a2540;color:#d8e2f5;border:1px solid #2e3a52;
                      border-radius:18px 18px 4px 18px;padding:11px 16px;max-width:70%;
                      font-size:14px;line-height:1.65;">{msg['content']}</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="display:flex;align-items:flex-start;gap:10px;margin:4px 0 8px;">
                      <div style="width:28px;height:28px;border-radius:50%;flex-shrink:0;
                      background:#0f1420;border:1px solid rgba(74,240,164,0.35);
                      display:flex;align-items:center;justify-content:center;
                      font-size:13px;color:#4af0a4;">⬡</div>
                      <div style="background:#0f1420;color:#a8b4c8;border:1px solid #1c2235;
                      border-radius:4px 18px 18px 18px;padding:13px 17px;max-width:78%;
                      font-size:14px;line-height:1.75;">{msg['content']}</div>
                    </div>""", unsafe_allow_html=True)
                    if msg.get("thinking"):
                        with st.expander("View reasoning"):
                            st.markdown(f"""<div style="background:#0a0d16;
                            border-left:2px solid rgba(124,158,255,0.4);
                            padding:12px 16px;border-radius:0 6px 6px 0;
                            font-family:'Courier New',monospace;font-size:12px;
                            line-height:1.7;color:#8a9bb8;white-space:pre-wrap;">{msg['thinking'][:1000]}...</div>""",
                            unsafe_allow_html=True)
                    if msg.get("ts"):
                        st.markdown(f"""<div style="text-align:center;font-size:11px;
                        color:#2e3a52;font-family:monospace;margin:4px 0 16px;">{msg['ts']}</div>""",
                        unsafe_allow_html=True)

        # ── Input bar — always last, always exactly once ──
        if user_input := st.chat_input("Ask about your team..."):
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            st.session_state["_pending_tab"] = "Ask AI"
            with st.spinner("Thinking..."):
                process_query(user_input)
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# RENDER — DATA
# ══════════════════════════════════════════════════════════════════════
def render_data(metrics):
    section_header("Data Explorer", "Raw data from integrated systems")
    with st.expander("Jira Tickets", expanded=True):
        section_header("Jira sprint and ticket data")
        with open("mock_data/jira_mock.json") as f:
            st.json(json.load(f))
    with st.expander("PagerDuty Incidents"):
        section_header("PagerDuty incident data")
        with open("mock_data/pagerduty_mock.json") as f:
            st.json(json.load(f))
    with st.expander("Computed Metrics"):
        section_header("Computed metrics from all sources")
        st.json(metrics)


# ══════════════════════════════════════════════════════════════════════
# SESSION STATE — zero rendering, just defaults
# ══════════════════════════════════════════════════════════════════════
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None
if "app_initialized" not in st.session_state:
    st.session_state.app_initialized = False
if "_active_tab" not in st.session_state:
    st.session_state["_active_tab"] = "Dashboard"
if "_pending_tab" not in st.session_state:
    st.session_state["_pending_tab"] = None

# ══════════════════════════════════════════════════════════════════════
# CSS — always first
# ══════════════════════════════════════════════════════════════════════
inject_global_css()

# ══════════════════════════════════════════════════════════════════════
# SPLASH
# ══════════════════════════════════════════════════════════════════════
_splash_slot = st.empty()

if not st.session_state.app_initialized:
    _splash_slot.markdown(_SPLASH, unsafe_allow_html=True)
    metrics = load_metrics()
    st.session_state.agent = TeamLensAgent()
    time.sleep(0.3)
    _splash_slot.empty()
    st.session_state.app_initialized = True
else:
    metrics = load_metrics()
    if "agent" not in st.session_state:
        st.session_state.agent = TeamLensAgent()

# ══════════════════════════════════════════════════════════════════════
# APP HEADER
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <div class="brand">
        <div class="brand-icon">🔭</div>
        <div>
            <div class="brand-name">TeamLens</div>
            <div class="brand-sub">Engineering Health Dashboard</div>
        </div>
    </div>
    <div class="live-pill"><div class="pulse"></div>Live</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# TAB NAVIGATION
# st.radio is the actual Streamlit widget — clicks trigger reruns.
# CSS above strips all radio circle affordances and reskins it as
# a modern pill segment control. No hidden widgets, no JS hacks.
# _pending_tab lets chip clicks and chat submits lock the tab.
# ══════════════════════════════════════════════════════════════════════
_TAB_OPTS = ["Dashboard", "Ask AI", "Data"]

# Apply any programmatic tab switch before the radio renders
_initial = st.session_state.get("_active_tab", "Dashboard")
if st.session_state.get("_pending_tab"):
    _initial = st.session_state["_pending_tab"]
    st.session_state["_pending_tab"] = None
    st.session_state["_active_tab"] = _initial

selected_tab = st.radio(
    label="",
    options=_TAB_OPTS,
    index=_TAB_OPTS.index(_initial),
    horizontal=True,
    label_visibility="collapsed",
    key="tab_radio",
)
# Persist manual tab clicks
st.session_state["_active_tab"] = selected_tab

if selected_tab == "Dashboard":
    render_dashboard(metrics)
elif selected_tab == "Ask AI":
    render_ask_ai()
elif selected_tab == "Data":
    render_data(metrics)