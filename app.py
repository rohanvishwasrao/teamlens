import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import json
from metrics import compute_all_metrics
from agent import TeamLensAgent
from reasoning_engine import reason, is_reasoning_question

st.set_page_config(
    page_title="TeamLens",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Global styles ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif !important; }

/* Hide Streamlit chrome */
#MainMenu, footer { visibility: hidden; }
.stDeployButton, [data-testid="collapsedControl"] { display: none !important; }

/* Page background */
.stApp {
    background: #0B1120;
    background-image:
        radial-gradient(ellipse 90% 45% at 50% 0%, rgba(99,102,241,0.12) 0%, transparent 60%),
        radial-gradient(ellipse 45% 30% at 95% 90%, rgba(139,92,246,0.06) 0%, transparent 50%);
    min-height: 100vh;
}

/* ── Centered container ───────────────────────── */
.main .block-container {
    padding: 2.5rem 2rem 5rem !important;
    max-width: 1080px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Thin custom scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.25); border-radius: 4px; }

/* ── App header ───────────────────────────────── */
.app-header {
    display: flex; align-items: center; justify-content: space-between;
    padding-bottom: 1.75rem; margin-bottom: 2rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.brand { display: flex; align-items: center; gap: 0.9rem; }
.brand-icon {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #6366F1, #8B5CF6);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.15rem;
    box-shadow: 0 4px 20px rgba(99,102,241,0.45);
    flex-shrink: 0;
}
.brand-name {
    font-size: 1.3rem; font-weight: 800; letter-spacing: -0.5px;
    background: linear-gradient(135deg, #F1F5F9 30%, #A5B4FC 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.brand-sub { font-size: 0.72rem; color: #64748B; font-weight: 400; margin-top: 1px; }
.live-pill {
    display: flex; align-items: center; gap: 0.4rem;
    background: rgba(16,185,129,0.07);
    border: 1px solid rgba(16,185,129,0.2);
    color: #34D399; font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.6px; padding: 0.28rem 0.75rem;
    border-radius: 999px;
}
.pulse {
    width: 6px; height: 6px; background: #10B981;
    border-radius: 50%; animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── Section headers ──────────────────────────── */
.s-head { display: flex; align-items: center; gap: 0.6rem; margin: 0 0 1.1rem; }
.s-bar {
    width: 3px; height: 17px;
    background: linear-gradient(#6366F1, #8B5CF6);
    border-radius: 2px; flex-shrink: 0;
}
.s-title { font-size: 0.88rem; font-weight: 700; color: #E2E8F0; letter-spacing: -0.1px; }
.s-sub { font-size: 0.73rem; color: #64748B; margin-left: auto; letter-spacing: 0; }

/* ── Divider ──────────────────────────────────── */
.div {
    height: 1px; margin: 1.75rem 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0.06) 70%, transparent);
}

/* ── KPI cards ────────────────────────────────── */
.kpi {
    background: rgba(14,20,36,0.9);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 1.2rem 1.35rem;
    position: relative; overflow: hidden;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.kpi:hover {
    border-color: rgba(99,102,241,0.25);
    box-shadow: 0 0 20px rgba(99,102,241,0.06);
}
.kpi-top { position: absolute; top:0; left:0; right:0; height: 2px; }
.kpi-lbl {
    font-size: 0.67rem; font-weight: 600; letter-spacing: 1.1px;
    text-transform: uppercase; color: #94A3B8; margin-bottom: 0.5rem;
}
.kpi-num { font-size: 2rem; font-weight: 800; letter-spacing: -1.5px; line-height: 1; }
.kpi-hint { font-size: 0.69rem; color: #64748B; margin-top: 0.28rem; }

/* ── Burnout cards ────────────────────────────── */
.bc {
    background: rgba(14,20,36,0.85);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 1rem 1rem;
    transition: border-color 0.2s;
}
.bc:hover { border-color: rgba(99,102,241,0.2); }
.bc-av {
    width: 32px; height: 32px; border-radius: 8px;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 0.78rem; font-weight: 800; margin-bottom: 0.6rem;
}
.bc-name { font-size: 0.78rem; font-weight: 600; color: #CBD5E1; }
.bc-score { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.5px; line-height: 1.1; }
.bc-bar {
    height: 3px; background: rgba(255,255,255,0.07);
    border-radius: 2px; margin: 0.5rem 0 0.4rem; overflow: hidden;
}
.bc-fill { height: 100%; border-radius: 2px; }
.bc-badge {
    display: inline-block; font-size: 0.6rem; font-weight: 700;
    letter-spacing: 0.3px; text-transform: uppercase;
    padding: 0.14rem 0.5rem; border-radius: 999px;
}
.bc-carry { font-size: 0.66rem; color: #64748B; margin-top: 0.3rem; }

/* ── Blocker items ────────────────────────────── */
.blk {
    padding: 0.65rem 0.85rem;
    background: rgba(8,12,24,0.7);
    border-left: 2px solid #F59E0B;
    border-radius: 0 8px 8px 0;
    margin-bottom: 0.4rem; overflow: hidden;
}
.blk-t { font-weight: 600; color: #F1F5F9; font-size: 0.82rem; }
.blk-d { color: #F59E0B; font-size: 0.75rem; font-weight: 600; float: right; }
.blk-r { color: #94A3B8; font-size: 0.77rem; margin-top: 0.2rem; clear: both; }

/* Expanders */
[data-testid="stExpander"] {
    background: rgba(8,12,24,0.7) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important; margin-bottom: 0.4rem !important;
}
[data-testid="stExpander"] > details > summary {
    font-size: 0.82rem !important; color: #94A3B8 !important;
    padding: 0.65rem 1rem !important; font-weight: 500 !important;
}
[data-testid="stExpander"] > details > summary:hover { color: #E2E8F0 !important; }

/* ── Tabs (segment-control style) ────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    background: rgba(8,12,24,0.8) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 9px !important; padding: 3px !important;
    display: inline-flex !important; margin-bottom: 2rem !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; border: none !important;
    border-radius: 6px !important; color: #8B9CB8 !important;
    font-weight: 500 !important; font-size: 0.8rem !important;
    padding: 0.42rem 1.15rem !important; outline: none !important;
    transition: all 0.18s !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(99,102,241,0.14) !important; color: #A5B4FC !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── Suggestion chips ─────────────────────────── */
.stButton > button {
    background: transparent !important;
    color: #94A3B8 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 999px !important;
    font-size: 0.8rem !important; font-weight: 500 !important;
    padding: 0.5rem 1rem !important; height: auto !important;
    text-align: center !important; line-height: 1.45 !important;
    transition: all 0.18s !important;
    white-space: normal !important;
}
.stButton > button:hover {
    background: rgba(99,102,241,0.09) !important;
    border-color: rgba(99,102,241,0.35) !important;
    color: #E2E8F0 !important;
    box-shadow: none !important; transform: none !important;
}

/* ── Chat messages (Anthropic/OpenAI style) ──── */
.cm { padding: 1rem 1.2rem; border-radius: 14px; margin-bottom: 0.7rem; }
.cm-u {
    background: rgba(99,102,241,0.08);
    border: 1px solid rgba(99,102,241,0.15);
}
.cm-a {
    background: rgba(14,20,36,0.7);
    border: 1px solid rgba(255,255,255,0.06);
}
.cm-lbl {
    font-size: 0.67rem; font-weight: 700;
    letter-spacing: 0.7px; text-transform: uppercase; margin-bottom: 0.38rem;
}
.cm-lbl-u { color: #818CF8; }
.cm-lbl-a { color: #64748B; }
.cm-body { font-size: 0.875rem; line-height: 1.72; color: #CBD5E1; }

/* Chat input */
[data-testid="stChatInput"] {
    background: rgba(14,20,36,0.9) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: rgba(99,102,241,0.4) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.08) !important;
}
[data-testid="stChatInput"] textarea {
    font-size: 0.875rem !important; color: #E2E8F0 !important;
}

/* Misc */
.stSpinner > div { border-top-color: #6366F1 !important; }
.stCaption, small { color: #64748B !important; font-size: 0.72rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────
DIVIDER = '<div class="div"></div>'
AVATAR_PALETTES = [
    ("#4338CA", "rgba(99,102,241,0.18)"),
    ("#BE185D", "rgba(236,72,153,0.18)"),
    ("#065F46", "rgba(16,185,129,0.18)"),
    ("#B45309", "rgba(245,158,11,0.15)"),
    ("#1D4ED8", "rgba(59,130,246,0.18)"),
    ("#6D28D9", "rgba(167,139,250,0.18)"),
]

def section_header(title, sub=""):
    sub_html = f'<span class="s-sub">{sub}</span>' if sub else ""
    st.markdown(
        f'<div class="s-head"><div class="s-bar"></div>'
        f'<span class="s-title">{title}</span>{sub_html}</div>',
        unsafe_allow_html=True,
    )

# Shared Plotly theme
_PLOT = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#64748B", family="Inter, sans-serif", size=11),
    legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#64748B")),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, tickfont=dict(color="#64748B")),
    margin=dict(t=5, b=10, l=10, r=10),
    hovermode="x unified",
)
_PLOT_H = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#64748B", family="Inter, sans-serif", size=11),
    coloraxis_showscale=False,
    margin=dict(t=5, b=10, l=90, r=10),
    hovermode="y unified",
    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, tickfont=dict(color="#64748B")),
    yaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#94A3B8")),
)

# ── Data & State ──────────────────────────────────────────────────
@st.cache_data
def load_metrics():
    return compute_all_metrics()

if "agent" not in st.session_state:
    st.session_state.agent = TeamLensAgent()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

metrics = load_metrics()

# ── App header ────────────────────────────────────────────────────
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

# ── Top-level tabs ────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["  Dashboard  ", "  Ask AI  ", "  Data  "])


# ════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ════════════════════════════════════════════════════════════════
with tab1:

    # ── Team Health ───────────────────────────────────────────
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

    # ── KPI strip ─────────────────────────────────────────────
    section_header("Key Metrics")
    velocity     = metrics["sprint_velocity"]
    avg_comp     = sum(v["completion_pct"] for v in velocity) / len(velocity)
    inc_trend    = metrics["incident_trend"]
    latest_inc   = inc_trend[-1]["total"] if inc_trend else 0
    cycle_times  = metrics["cycle_time_by_engineer"]
    avg_cycle    = sum(c["avg_cycle_time_days"] for c in cycle_times) / len(cycle_times)
    blocked      = metrics["blocked_work"]
    total_blk    = sum(e["total_blocked_days"] for e in blocked)

    k1, k2, k3, k4 = st.columns(4)
    kpi_defs = [
        (k1, "Sprint Completion", f"{avg_comp:.0f}%", f"avg over {len(velocity)} sprints",
         "#818CF8", "linear-gradient(90deg,#6366F1,#818CF8)"),
        (k2, "Latest Incidents",  str(latest_inc),     "this period",
         "#F472B6", "linear-gradient(90deg,#EC4899,#F472B6)"),
        (k3, "Avg Cycle Time",   f"{avg_cycle:.1f}d",  "days per ticket",
         "#34D399", "linear-gradient(90deg,#10B981,#34D399)"),
        (k4, "Blocked Days",     f"{total_blk}d",       "across all engineers",
         "#FBBF24", "linear-gradient(90deg,#F59E0B,#FBBF24)"),
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

    # ── Charts — row 1 ────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        section_header("Sprint Velocity")
        sprints = [v["sprint"] for v in velocity]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Committed", x=sprints,
                             y=[v["committed"] for v in velocity],
                             marker_color="rgba(99,102,241,0.2)"))
        fig.add_trace(go.Bar(name="Completed", x=sprints,
                             y=[v["completed"] for v in velocity],
                             marker_color="#6366F1", opacity=0.9))
        fig.update_layout(barmode="overlay", height=290, **_PLOT)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with c2:
        section_header("Incident Trend")
        months = [t["month"] for t in inc_trend]
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            name="Total", x=months, y=[t["total"] for t in inc_trend],
            mode="lines+markers",
            line=dict(color="#8B5CF6", width=2.5),
            marker=dict(size=6, color="#8B5CF6", line=dict(color="#0B1120", width=2)),
            fill="tozeroy", fillcolor="rgba(139,92,246,0.07)"
        ))
        fig2.add_trace(go.Scatter(
            name="P0/P1", x=months, y=[t["p0_p1"] for t in inc_trend],
            mode="lines+markers",
            line=dict(color="#EF4444", width=1.8, dash="dot"),
            marker=dict(size=5, color="#EF4444")
        ))
        fig2.update_layout(height=290, **_PLOT)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.markdown(DIVIDER, unsafe_allow_html=True)

    # ── Charts — row 2 ────────────────────────────────────────
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

    # ── Work Blockers ─────────────────────────────────────────
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


# ════════════════════════════════════════════════════════════════
# TAB 2 — CHAT  (Claude / OpenAI-style centered column)
# ════════════════════════════════════════════════════════════════
with tab2:
    _, chat_col, _ = st.columns([1, 4, 1])
    with chat_col:

        # Welcome header
        st.markdown("""
        <div style="text-align:center;padding:2rem 0 1.5rem;">
            <div style="font-size:2rem;margin-bottom:0.5rem;">🔭</div>
            <div style="font-size:1.15rem;font-weight:700;color:#E2E8F0;letter-spacing:-0.3px;">
                Ask TeamLens AI
            </div>
            <div style="font-size:0.82rem;color:#64748B;margin-top:0.35rem;">
                Powered by Claude · reasoning over live metrics
            </div>
        </div>""", unsafe_allow_html=True)

        # Suggestion chips — 2 × 2
        SUGGESTIONS = [
            "What should I discuss in my 1:1 with emily.zhang?",
            "Why did reliability degrade in February?",
            "Who is at highest risk of burnout?",
            "What is the current sprint completion rate?",
        ]
        sc1, sc2 = st.columns(2)
        for i, s in enumerate(SUGGESTIONS):
            target = sc1 if i % 2 == 0 else sc2
            with target:
                if st.button(s, key=f"sq_{i}", use_container_width=True):
                    st.session_state.pending_question = s

        st.markdown(DIVIDER, unsafe_allow_html=True)

        # Chat history
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="cm cm-u">
                    <div class="cm-lbl cm-lbl-u">You</div>
                    <div class="cm-body">{msg['content']}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="cm cm-a">
                    <div class="cm-lbl cm-lbl-a">TeamLens AI</div>
                    <div class="cm-body">{msg['content']}</div>
                </div>""", unsafe_allow_html=True)
                if msg.get("thinking"):
                    with st.expander("View reasoning"):
                        st.caption(msg["thinking"][:1000] + "...")
                if msg.get("model"):
                    st.caption(f"Model: {msg['model']}")

        # Handle suggestion click
        if "pending_question" in st.session_state:
            question = st.session_state.pending_question
            del st.session_state.pending_question
            st.session_state.chat_history.append({"role": "user", "content": question})
            st.markdown(f"""
            <div class="cm cm-u">
                <div class="cm-lbl cm-lbl-u">You</div>
                <div class="cm-body">{question}</div>
            </div>""", unsafe_allow_html=True)
            with st.spinner("Thinking..."):
                if is_reasoning_question(question):
                    result = reason(question)
                    answer, thinking, model = result["answer"], result.get("thinking", ""), result["model"]
                else:
                    res = st.session_state.agent.run(question)
                    answer = res if isinstance(res, str) else res.get("answer", "")
                    thinking, model = "", "llama-3.3-70b-versatile"
            st.markdown(f"""
            <div class="cm cm-a">
                <div class="cm-lbl cm-lbl-a">TeamLens AI</div>
                <div class="cm-body">{answer}</div>
            </div>""", unsafe_allow_html=True)
            if thinking:
                with st.expander("View reasoning"):
                    st.caption(thinking[:1000] + "...")
            st.caption(f"Model: {model}")
            st.session_state.chat_history.append({"role": "assistant", "content": answer, "thinking": thinking, "model": model})
            st.rerun()

        # Chat input
        if question := st.chat_input("Ask about your team..."):
            st.session_state.chat_history.append({"role": "user", "content": question})
            st.markdown(f"""
            <div class="cm cm-u">
                <div class="cm-lbl cm-lbl-u">You</div>
                <div class="cm-body">{question}</div>
            </div>""", unsafe_allow_html=True)
            with st.spinner("Thinking..."):
                if is_reasoning_question(question):
                    result = reason(question)
                    answer, thinking, model = result["answer"], result.get("thinking", ""), result["model"]
                else:
                    res = st.session_state.agent.run(question)
                    answer = res if isinstance(res, str) else res.get("answer", "")
                    thinking, model = "", "llama-3.3-70b-versatile"
            st.markdown(f"""
            <div class="cm cm-a">
                <div class="cm-lbl cm-lbl-a">TeamLens AI</div>
                <div class="cm-body">{answer}</div>
            </div>""", unsafe_allow_html=True)
            if thinking:
                with st.expander("View reasoning"):
                    st.caption(thinking[:1000] + "...")
            st.caption(f"Model: {model}")
            st.session_state.chat_history.append({"role": "assistant", "content": answer, "thinking": thinking, "model": model})
            st.rerun()


# ════════════════════════════════════════════════════════════════
# TAB 3 — DATA EXPLORER
# ════════════════════════════════════════════════════════════════
with tab3:
    section_header("Data Explorer", "Raw data from integrated systems")
    d1, d2, d3 = st.tabs(["Jira Tickets", "PagerDuty Incidents", "Computed Metrics"])
    with d1:
        section_header("Jira sprint and ticket data")
        with open("mock_data/jira_mock.json") as f:
            st.json(json.load(f))
    with d2:
        section_header("PagerDuty incident data")
        with open("mock_data/pagerduty_mock.json") as f:
            st.json(json.load(f))
    with d3:
        section_header("Computed metrics from all sources")
        st.json(metrics)
