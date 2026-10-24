"""Scholarship Screening Desk — Agentic AI PoC (CA-3).

Run locally:   streamlit run app.py
With Ollama:   ollama pull llama3.2:3b   (the app finds it on http://localhost:11434)
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from agents import rules
from agents.llm import DEFAULT_MODEL, LLM, OLLAMA_HOST, inr, ollama_status
from agents.pipeline import VERDICT_LABEL, Orchestrator

ROOT = Path(__file__).parent
st.set_page_config(page_title="Scholarship Screening Desk", page_icon="🎓", layout="wide")


# ------------------------------------------------------------------ data
@st.cache_data
def load_data():
    apps = json.loads((ROOT / "data/applications.json").read_text())
    registry = json.loads((ROOT / "data/awards_registry.json").read_text())
    return apps, registry


APPS, REGISTRY = load_data()
APP_BY_ID = {a["app_id"]: a for a in APPS}


# ------------------------------------------------------------------ styles
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Public+Sans:wght@400;500;600&display=swap');
:root{
  --paper:#EEF1F5; --sheet:#FFFFFF; --ink:#1B2A41; --ink-soft:#55627A; --rule:#C9D2DE;
  --pass:#2E7D4F; --fail:#B3261E; --query:#A5640C;
}
html, body, [class*="css"], .stMarkdown, p, li, label, input, textarea, button {
  font-family:'Public Sans', system-ui, sans-serif;
}
.block-container{padding-top:2.2rem; max-width:1240px;}
h1,h2,h3,h4{font-family:'Bricolage Grotesque','Public Sans',system-ui,sans-serif; color:var(--ink); letter-spacing:-.01em;}

/* masthead */
.mast{display:flex; justify-content:space-between; align-items:flex-end; gap:1rem;
  border-bottom:2px solid var(--ink); padding-bottom:.9rem; margin-bottom:1.4rem; flex-wrap:wrap;}
.mast h1{font-size:2.35rem; line-height:1.05; margin:0; font-weight:700;}
.mast p{margin:.35rem 0 0; color:var(--ink-soft); font-size:.98rem; max-width:60ch;}
.chip{font-size:.82rem; padding:.3rem .65rem; border:1px solid var(--rule); border-radius:999px;
  background:var(--sheet); color:var(--ink-soft); white-space:nowrap;}
.chip b{color:var(--ink); font-weight:600;}
.dot{display:inline-block; width:.5rem; height:.5rem; border-radius:50%; margin-right:.4rem; vertical-align:middle;}

/* application sheet: ruled like a printed form */
.sheet{background:var(--sheet); border:1px solid var(--rule); border-radius:4px; padding:1.1rem 1.25rem;}
.sheet h4{margin:0 0 .6rem; font-size:1.02rem;}
.block-container h4{font-size:1.15rem; margin-top:1.1rem;}
.formrow{display:grid; grid-template-columns:11.5rem 1fr; gap:.75rem; padding:.42rem 0;
  border-bottom:1px dashed var(--rule); font-size:.92rem;}
.formrow:last-child{border-bottom:none;}
.formrow span:first-child{color:var(--ink-soft);}
.formrow span:last-child{color:var(--ink); font-weight:500;}
.marks{font-family:'Public Sans',system-ui,sans-serif; font-variant-numeric:tabular-nums; white-space:pre-wrap;
  font-size:.86rem; color:var(--ink); background:#F6F8FB; border-left:3px solid var(--ink);
  padding:.7rem .9rem; margin-top:.4rem;}
.clips{display:flex; gap:.4rem; flex-wrap:wrap; margin-top:.7rem;}
.clip{font-size:.78rem; padding:.18rem .55rem; border-radius:3px; border:1px solid var(--rule); color:var(--ink-soft);}
.clip.absent{border-style:dashed; color:var(--fail); border-color:#E3B3AF;}

/* agent ledger: the run is a sequence, so it is numbered */
.ledger{counter-reset:step; margin:0; padding:0; list-style:none;}
.ledger li{counter-increment:step; display:grid; grid-template-columns:2rem 6.6rem 1fr; gap:.6rem;
  padding:.55rem 0; border-bottom:1px solid #E1E6ED; font-size:.88rem; align-items:baseline;}
.ledger li::before{content:counter(step); font-variant-numeric:tabular-nums; color:var(--ink-soft); font-size:.8rem;}
.ledger .who{font-weight:600; color:var(--ink);}
.ledger .what{color:var(--ink);}
.ledger .what small{display:block; color:var(--ink-soft); margin-top:.15rem; font-size:.83rem;}
.ledger li.warn .who{color:var(--query);} .ledger li.error .who{color:var(--fail);}
.ledger li.ok .who{color:var(--pass);}

/* the stamp */
.verdict{display:flex; align-items:center; gap:1.4rem; flex-wrap:wrap; margin:.4rem 0 1rem;}
.stamp{display:inline-block; padding:.55rem 1.1rem; border:3px double currentColor; border-radius:6px;
  font-family:'Bricolage Grotesque','Public Sans',system-ui,sans-serif; font-weight:700; font-size:1.55rem; letter-spacing:.08em;
  text-transform:uppercase; transform:rotate(-4deg); opacity:.92; line-height:1;}
.stamp small{display:block; font-size:.66rem; letter-spacing:.12em; font-weight:500; margin-top:.3rem;}
.stamp.eligible{color:var(--pass);} .stamp.not_eligible{color:var(--fail);} .stamp.needs_documents{color:var(--query);}
@media (prefers-reduced-motion:no-preference){
  .stamp.fresh{animation:press .38s cubic-bezier(.2,1.4,.4,1) both;}
  @keyframes press{from{transform:rotate(-4deg) scale(1.6); opacity:0} to{transform:rotate(-4deg) scale(1); opacity:.92}}
}
.note{font-size:.95rem; line-height:1.55; max-width:62ch; color:var(--ink);}

/* rule checklist */
.checks{display:grid; gap:.35rem; margin-top:.4rem;}
.check{display:grid; grid-template-columns:5.2rem 1fr; gap:.6rem; font-size:.88rem; padding:.4rem .6rem;
  background:var(--sheet); border:1px solid #E1E6ED; border-radius:3px;}
.check .tag{font-weight:600;}
.check.pass .tag{color:var(--pass);} .check.fail .tag{color:var(--fail);}
.check.missing .tag, .check.unknown .tag{color:var(--query);}

.tally{display:flex; gap:2.2rem; flex-wrap:wrap; margin:.6rem 0 1rem; padding:.8rem 0;
  border-top:1px solid var(--rule); border-bottom:1px solid var(--rule);}
.tally div{font-size:.88rem; color:var(--ink-soft);}
.tally b{display:block; font-family:'Bricolage Grotesque','Public Sans',system-ui,sans-serif; font-size:1.7rem; color:var(--ink); line-height:1.1;}

.stTabs [data-baseweb="tab-list"]{gap:1.6rem; border-bottom:1px solid var(--rule);}
.stTabs [data-baseweb="tab"]{padding-left:0; padding-right:0; font-weight:500;}
.stButton>button[kind="primary"]{background:var(--ink); border-color:var(--ink); border-radius:4px;}
.stButton>button:focus-visible{outline:3px solid #7FA3D6; outline-offset:2px;}
section[data-testid="stSidebar"]{background:#E3E8EF;}
@media (max-width:640px){
  .formrow{grid-template-columns:1fr; gap:.1rem;}
  .ledger li{grid-template-columns:1.6rem 1fr;} .ledger .who{grid-column:2;} .ledger .what{grid-column:2;}
  .mast h1{font-size:1.8rem;}
}
</style>
""")


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.subheader("Model")
    host = st.text_input("Ollama address", OLLAMA_HOST,
                         help="Where your Ollama server runs. On your laptop this is usually localhost.")
    status = ollama_status(host)
    choice = st.radio("Use", ["Ollama if it's running", "Ollama only", "Built-in rule model"], index=0)
    model = DEFAULT_MODEL
    if status["up"]:
        st.caption(f"Ollama is running with {len(status['models'])} model(s).")
        if status["models"]:
            idx = status["models"].index(DEFAULT_MODEL) if DEFAULT_MODEL in status["models"] else 0
            model = st.selectbox("Ollama model", status["models"], index=idx)
    else:
        st.caption("Ollama isn't reachable at that address, so the built-in rule model will answer. "
                   "Start it with `ollama serve` and pull a model with `ollama pull llama3.2:3b`.")

    st.subheader("Demo controls")
    noise = st.toggle("Make the Extractor slip once", value=False,
                      help="Injects one typical small-model mistake on the first read so you can watch "
                           "the Critic catch it and send the case back.")
    retries = st.slider("Times the Critic can send a case back", 0, 3, 1)

backend = {"Ollama if it's running": "auto", "Ollama only": "ollama",
           "Built-in rule model": "mock"}[choice]
if backend == "ollama" and not status["up"]:
    st.sidebar.error("Ollama isn't reachable. Switch to another option or start Ollama.")
    backend = "mock"


def make_orchestrator():
    llm = LLM(backend=backend, model=model, host=host, noise=noise)
    return Orchestrator(llm, REGISTRY, max_retries=retries), llm


_, probe = make_orchestrator()
live = probe.backend == "ollama"


# ------------------------------------------------------------------ masthead
st.markdown(f"""
<div class="mast">
  <div>
    <h1>Scholarship screening desk</h1>
    <p>Six agents read each application for the {rules.SCHEME_NAME}, check it against the scheme rules,
    and explain every decision to the reviewer.</p>
  </div>
  <span class="chip"><span class="dot" style="background:{'#2E7D4F' if live else '#A5640C'}"></span>
  Answering: <b>{html.escape(probe.label)}</b></span>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ render helpers
def esc(x) -> str:
    return html.escape(str(x))


def form_sheet(app: dict) -> str:
    rows = []
    for line in app["form_text"].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            rows.append(f'<div class="formrow"><span>{esc(k)}</span><span>{esc(v.strip())}</span></div>')
    clips = []
    cat = next((l.split(":", 1)[1].strip() for l in app["form_text"].splitlines()
                if l.startswith("Category")), "General")
    for d in rules.required_documents(cat):
        cls = "clip" if d in app["documents"] else "clip absent"
        mark = "" if d in app["documents"] else " — not attached"
        clips.append(f'<span class="{cls}">{esc(d.replace("_", " ").capitalize())}{mark}</span>')
    return (f'<div class="sheet"><h4>Application {esc(app["app_id"])}</h4>{"".join(rows)}'
            f'<div class="clips">{"".join(clips)}</div></div>')


def marksheet(app: dict) -> str:
    if "marksheet" not in app["documents"]:
        return '<div class="marks">No marksheet attached.</div>'
    return f'<div class="marks">{esc(app["marksheet_text"])}</div>'


def ledger(trace) -> str:
    items = []
    for e in trace:
        items.append(f'<li class="{e.level}"><span class="who">{esc(e.agent)}</span>'
                     f'<span class="what">{esc(e.action)}<small>{esc(e.detail)}</small></span></li>')
    return f'<ol class="ledger">{"".join(items)}</ol>'


def stamp(case, fresh=True) -> str:
    v = case.decision["verdict"]
    sub = f"Score {case.decision['score']}" if case.decision.get("score") else rules.SCHEME_NAME.split(" 20")[0]
    return (f'<div class="verdict"><span class="stamp {v} {"fresh" if fresh else ""}">'
            f'{esc(VERDICT_LABEL[v])}<small>{esc(sub)}</small></span></div>')


def checklist(case) -> str:
    label = {"pass": "Passed", "fail": "Failed", "missing": "Missing", "unknown": "Unclear"}
    out = []
    for c in case.checks:
        out.append(f'<div class="check {c["status"]}"><span class="tag">{label[c["status"]]}</span>'
                   f'<span>{esc(c["detail"])}</span></div>')
    return f'<div class="checks">{"".join(out)}</div>'


# ------------------------------------------------------------------ tabs
tab1, tab2, tab3 = st.tabs(["Screen one application", "Screen the whole batch", "Scheme rules and design"])

with tab1:
    names = {a["app_id"]: a["form_text"].splitlines()[0].split(":", 1)[1].strip() for a in APPS}
    pick = st.selectbox("Application", list(names), format_func=lambda k: f"{k} · {names[k]}")
    app = APP_BY_ID[pick]
    left, right = st.columns([5, 6], gap="large")
    with left:
        st.markdown(form_sheet(app), unsafe_allow_html=True)
        st.markdown("#### Marksheet")
        st.markdown(marksheet(app), unsafe_allow_html=True)
    with right:
        run = st.button("Screen this application", type="primary", use_container_width=True)
        key = f"case::{pick}::{backend}::{model}::{noise}::{retries}"
        if run:
            orch, llm = make_orchestrator()
            with st.spinner("Agents are working through the checks…"):
                st.session_state[key] = orch.screen(app)
            st.session_state["fresh"] = key
        case = st.session_state.get(key)
        if case is None:
            st.info("Press the button to run the Planner, Extractor, Critic, Validator, Decision and "
                    "Reporter agents on this application.")
        else:
            st.markdown(stamp(case, fresh=st.session_state.pop("fresh", None) == key), unsafe_allow_html=True)
            st.markdown(f'<p class="note">{esc(case.report)}</p>', unsafe_allow_html=True)
            st.markdown("#### Rule checks")
            st.markdown(checklist(case), unsafe_allow_html=True)
            if case.corrections:
                st.warning("The Critic overrode " + ", ".join(c["field"] for c in case.corrections)
                           + " after the Extractor failed to fix them.")
            st.markdown("#### How the agents got here")
            st.markdown(ledger(case.trace), unsafe_allow_html=True)
            with st.expander("Extracted fields and plan (raw)"):
                st.json({"plan": case.plan, "fields": case.fields, "decision": case.decision})

with tab2:
    c1, c2 = st.columns([2, 3])
    with c1:
        slots = st.number_input("Awards available this round", 1, len(APPS), 4)
    with c2:
        st.write("")
        st.write("")
        go = st.button(f"Screen all {len(APPS)} applications", type="primary")
    if go:
        orch, llm = make_orchestrator()
        bar = st.progress(0.0, text="Screening…")
        cases = []
        for i, a in enumerate(APPS):
            cases.append(orch.screen(a))
            bar.progress((i + 1) / len(APPS), text=f"Screened {a['app_id']}")
        bar.empty()
        rows = Orchestrator.rank(cases, slots)
        st.session_state["batch"] = {"rows": rows, "calls": llm.calls, "label": llm.label,
                                     "corrections": sum(len(c.corrections) for c in cases),
                                     "retries": sum(1 for c in cases for e in c.trace if e.agent == "Orchestrator")}
    b = st.session_state.get("batch")
    if not b:
        st.info("Set how many awards are available, then screen the whole batch. Eligible students are "
                "ranked by a merit-cum-means score: 60% CGPA, 40% financial need.")
    else:
        df = pd.DataFrame(b["rows"])
        counts = df["Outcome"].value_counts()
        st.markdown(f"""<div class="tally">
          <div><b>{counts.get('Awarded', 0)}</b>Awarded</div>
          <div><b>{counts.get('Waitlisted', 0)}</b>Waitlisted</div>
          <div><b>{counts.get('Needs documents', 0)}</b>Need documents</div>
          <div><b>{counts.get('Not eligible', 0)}</b>Not eligible</div>
          <div><b>{b['retries']}</b>Sent back by the Critic</div>
          <div><b>{b['calls']}</b>Model calls · {esc(b['label'])}</div>
        </div>""", unsafe_allow_html=True)

        colour = {"Awarded": "#2E7D4F", "Waitlisted": "#1B2A41", "Needs documents": "#A5640C", "Not eligible": "#B3261E"}
        view = df.copy()
        view["Rank"] = view["Rank"].map(lambda r: "—" if pd.isna(r) else str(int(r)))
        view["Score"] = view["Score"].map(lambda v: "—" if pd.isna(v) else f"{v:.1f}")
        view["CGPA"] = view["CGPA"].map(lambda v: "—" if pd.isna(v) else f"{v:.2f}")
        styled = view.style.map(lambda v: f"color:{colour.get(v, '')}; font-weight:600" if v in colour else "",
                                subset=["Outcome"])
        st.dataframe(styled, use_container_width=True, hide_index=True, height=38 * (len(view) + 1),
                     column_config={"Reviewer note": st.column_config.TextColumn(width="large")})
        st.download_button("Download the shortlist as CSV", df.to_csv(index=False).encode(),
                           "shortlist.csv", "text/csv")

with tab3:
    st.markdown("#### Scheme rules the Validator applies")
    st.markdown(
        f"Family income at most **{inr(rules.INCOME_LIMIT)}** a year. Attendance at least "
        f"**{rules.ATTENDANCE_MIN:.0f}%**. CGPA on the form must match the marksheet within "
        f"**{rules.CGPA_TOLERANCE}**. Students who already hold a full-tuition award are not eligible.")
    st.dataframe(pd.DataFrame([{"Category": k, "Minimum CGPA": v,
                                "Documents required": ", ".join(d.replace('_', ' ') for d in rules.required_documents(k))}
                               for k, v in rules.CGPA_CUTOFF.items()]),
                 hide_index=True, use_container_width=True)
    diagram = ROOT / "docs/architecture.png"
    if diagram.exists():
        st.markdown("#### Architecture")
        st.image(str(diagram), use_container_width=True)
    st.markdown("#### Who does what")
    st.markdown("""
| Agent | Job |
|---|---|
| Planner | Reads the case and decides which checks apply, such as relaxed cutoffs for reserved categories. |
| Extractor | Pulls income, CGPA, attendance and other fields from the form and marksheet text using the model. |
| Critic | Re-reads the source text, sends the case back when the extraction is wrong, and later checks the verdict matches the rules. |
| Validator | Runs each rule as a Python tool and records pass, fail or missing. |
| Decision | Turns rule results into eligible, not eligible or needs documents, and scores eligible students. |
| Reporter | Writes a plain-English note for the reviewer. |
""")
