"""Scholarship Screening Desk — Agentic AI PoC (CA-3).

Run:  streamlit run app.py      (Ollama on http://localhost:11434 is picked up automatically)
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from agents import rules
from agents.llm import LLM, OLLAMA_HOST, inr, ollama_status, pick_model, test_model
from agents.pipeline import AGENT_ORDER, VERDICT_LABEL, Orchestrator

ROOT = Path(__file__).parent
st.set_page_config(page_title="Scholarship Screening Desk", page_icon=":material/school:", layout="wide")


# ------------------------------------------------------------------ data
@st.cache_data
def load_data():
    apps = json.loads((ROOT / "data/applications.json").read_text())
    registry = json.loads((ROOT / "data/awards_registry.json").read_text())
    sample = json.loads((ROOT / "data/sample_freeform.json").read_text())
    return apps, registry, sample


APPS, REGISTRY, SAMPLE = load_data()
APP_BY_ID = {a["app_id"]: a for a in APPS}


def esc(x) -> str:
    return html.escape(str(x))


# ------------------------------------------------------------------ styles
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Public+Sans:wght@400;500;600&display=swap');
:root{
  --paper:#EEF1F5; --sheet:#FFFFFF; --ink:#1B2A41; --ink-soft:#55627A; --rule:#C9D2DE; --hair:#E1E6ED;
  --pass:#2E7D4F; --pass-bg:#E8F3EC; --fail:#B3261E; --fail-bg:#F9E9E7; --query:#A5640C; --query-bg:#FBF1E3;
  --model:#2E5E9E; --model-bg:#E6EEF8;
  --head:'Bricolage Grotesque','Public Sans',system-ui,sans-serif; --body:'Public Sans',system-ui,sans-serif;
}
html, body, .stMarkdown, p, li, label, input, textarea, button, [data-testid="stWidgetLabel"] {font-family:var(--body);}
.block-container{padding-top:1.8rem; max-width:1280px;}
h1,h2,h3,h4{font-family:var(--head); color:var(--ink); letter-spacing:-.01em;}
.block-container h4{font-size:1.08rem; margin:1.2rem 0 .5rem;}

/* masthead */
.mast{display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; flex-wrap:wrap;
  border-bottom:2px solid var(--ink); padding-bottom:.9rem; margin-bottom:1.1rem;}
.mast h1{font-size:2.3rem; line-height:1.05; margin:0; font-weight:700;}
.mast p{margin:.4rem 0 0; color:var(--ink-soft); font-size:.98rem; max-width:62ch;}
.pill{display:inline-flex; align-items:center; gap:.45rem; font-size:.84rem; padding:.38rem .75rem;
  border-radius:999px; background:var(--sheet); border:1px solid var(--rule); color:var(--ink-soft); white-space:nowrap;}
.pill b{color:var(--ink); font-weight:600;}
.pill i{width:.55rem; height:.55rem; border-radius:50%; display:inline-block;}

/* application sheet */
.sheet{background:var(--sheet); border:1px solid var(--rule); border-radius:6px; padding:1.05rem 1.2rem;}
.sheet h4{margin:0 0 .55rem; font-size:1rem;}
.formrow{display:grid; grid-template-columns:11rem 1fr; gap:.75rem; padding:.42rem 0;
  border-bottom:1px dashed var(--rule); font-size:.92rem;}
.formrow:last-of-type{border-bottom:none;}
.formrow span:first-child{color:var(--ink-soft);} .formrow span:last-child{color:var(--ink); font-weight:500;}
.marks{font-variant-numeric:tabular-nums; white-space:pre-wrap; font-size:.86rem; color:var(--ink);
  background:#F6F8FB; border-left:3px solid var(--ink); padding:.7rem .9rem; border-radius:0 4px 4px 0;}
.clips{display:flex; gap:.4rem; flex-wrap:wrap; margin-top:.75rem;}
.clip{font-size:.78rem; padding:.2rem .55rem; border-radius:4px; border:1px solid var(--rule); color:var(--ink-soft);}
.clip.absent{border-style:dashed; color:var(--fail); border-color:#E3B3AF;}

/* live agent pipeline */
.pipe{display:grid; grid-template-columns:repeat(auto-fit,minmax(6.6rem,1fr)); gap:.4rem; margin:.2rem 0 .5rem;}
.node{border:1.5px solid var(--rule); border-radius:8px; padding:.5rem .55rem; background:var(--sheet); min-height:3.4rem;}
.node b{display:block; font-family:var(--head); font-size:.92rem; color:var(--ink-soft);}
.node small{display:block; font-size:.74rem; color:var(--ink-soft); margin-top:.15rem; line-height:1.25;}
.node.work{border-color:var(--ink); background:var(--ink);} .node.work b,.node.work small{color:#fff;}
.node.ok{border-color:var(--pass); background:var(--pass-bg);} .node.ok b{color:var(--pass);}
.node.warn{border-color:var(--query); background:var(--query-bg);} .node.warn b{color:var(--query);}
.now{font-size:.88rem; color:var(--ink-soft); margin:.1rem 0 .6rem; min-height:1.3rem;}
.now b{color:var(--ink);}
@media (prefers-reduced-motion:no-preference){
  .node.work b::after{content:""; display:inline-block; width:.45rem; height:.45rem; margin-left:.4rem; border-radius:50%;
    background:#8FB3E6; vertical-align:middle; animation:blink 1s ease-in-out infinite;}
  @keyframes blink{50%{opacity:.25}}
}

/* verdict card */
.verdict{background:var(--sheet); border:1px solid var(--rule); border-radius:8px; padding:1.1rem 1.2rem; margin:.3rem 0 .4rem;}
.vtop{display:flex; gap:1.4rem; align-items:center; flex-wrap:wrap;}
.stamp{display:inline-block; padding:.55rem 1.1rem; border:3px double currentColor; border-radius:6px;
  font-family:var(--head); font-weight:700; font-size:1.5rem; letter-spacing:.08em; text-transform:uppercase;
  transform:rotate(-4deg); opacity:.93; line-height:1; flex:none;}
.stamp small{display:block; font-size:.64rem; letter-spacing:.12em; font-weight:500; margin-top:.3rem;}
.stamp.eligible{color:var(--pass);} .stamp.not_eligible{color:var(--fail);} .stamp.needs_documents{color:var(--query);}
@media (prefers-reduced-motion:no-preference){
  .stamp.fresh{animation:press .38s cubic-bezier(.2,1.4,.4,1) both;}
  @keyframes press{from{transform:rotate(-4deg) scale(1.6); opacity:0} to{transform:rotate(-4deg) scale(1); opacity:.93}}
}
.note{font-size:.98rem; line-height:1.55; color:var(--ink); margin:0; flex:1 1 20rem; max-width:64ch;}
.meta{display:flex; gap:1.6rem; flex-wrap:wrap; border-top:1px solid var(--hair); margin-top:.9rem; padding-top:.7rem;}
.meta div{font-size:.8rem; color:var(--ink-soft);} .meta b{display:block; font-size:.98rem; color:var(--ink); font-weight:600;}

/* checks */
.checks{display:grid; gap:.35rem;}
.check{display:grid; grid-template-columns:5.4rem 1fr; gap:.6rem; font-size:.88rem; padding:.45rem .65rem;
  background:var(--sheet); border:1px solid var(--hair); border-radius:5px;}
.check .tag{font-weight:600;} .check.pass .tag{color:var(--pass);} .check.fail .tag{color:var(--fail);}
.check.missing .tag, .check.unknown .tag{color:var(--query);}
.check.fail{border-color:#EBC3BF; background:#FFFBFA;}

/* trace ledger: a sequence, so numbered */
.ledger{counter-reset:step; margin:0; padding:0; list-style:none;}
.ledger li{counter-increment:step; display:grid; grid-template-columns:1.8rem 6.4rem 1fr auto; gap:.6rem;
  padding:.55rem 0; border-bottom:1px solid var(--hair); font-size:.88rem; align-items:baseline;}
.ledger li::before{content:counter(step); font-variant-numeric:tabular-nums; color:var(--ink-soft); font-size:.8rem;}
.ledger .who{font-weight:600; color:var(--ink);}
.ledger .what small{display:block; color:var(--ink-soft); margin-top:.15rem; font-size:.83rem;}
.ledger li.warn .who{color:var(--query);} .ledger li.error .who{color:var(--fail);} .ledger li.ok .who{color:var(--pass);}
.badge{font-size:.72rem; padding:.12rem .45rem; border-radius:4px; white-space:nowrap; font-variant-numeric:tabular-nums;
  background:#EEF1F5; color:var(--ink-soft);}
.badge.ollama{background:var(--model-bg); color:var(--model); font-weight:600;}
.badge.rules{background:var(--query-bg); color:var(--query);}

.tally{display:flex; gap:2.2rem; flex-wrap:wrap; margin:.6rem 0 1rem; padding:.8rem 0;
  border-top:1px solid var(--rule); border-bottom:1px solid var(--rule);}
.tally div{font-size:.86rem; color:var(--ink-soft);}
.tally b{display:block; font-family:var(--head); font-size:1.65rem; color:var(--ink); line-height:1.1;}
.hint{font-size:.9rem; color:var(--ink-soft); background:var(--model-bg); border-radius:6px; padding:.65rem .85rem; margin-bottom:.8rem;}
.hint b{color:var(--model);}

/* sidebar model card */
.mcard{background:var(--sheet); border:1px solid var(--rule); border-radius:8px; padding:.75rem .85rem; margin-bottom:.6rem; font-size:.86rem;}
.mcard .row{display:flex; justify-content:space-between; gap:.5rem; padding:.18rem 0; color:var(--ink-soft);}
.mcard .row b{color:var(--ink); font-weight:600;}

.stTabs [data-baseweb="tab-list"]{gap:1.5rem; border-bottom:1px solid var(--rule);}
.stTabs [data-baseweb="tab"]{padding-left:0; padding-right:0; font-weight:500;}
.stButton>button[kind="primary"]{background:var(--ink); border-color:var(--ink); border-radius:6px; min-height:2.75rem;}
.stButton>button{border-radius:6px; min-height:2.5rem; cursor:pointer;}
.stButton>button:focus-visible, .stDownloadButton>button:focus-visible{outline:3px solid #7FA3D6; outline-offset:2px;}
section[data-testid="stSidebar"]{background:#E3E8EF;}
@media (max-width:640px){
  .formrow{grid-template-columns:1fr; gap:.1rem;}
  .ledger li{grid-template-columns:1.6rem 1fr;} .ledger .who,.ledger .what,.ledger .badge{grid-column:2;}
  .mast h1{font-size:1.8rem;}
}
</style>
""")


# ------------------------------------------------------------------ sidebar: model
status = ollama_status(OLLAMA_HOST)
with st.sidebar:
    st.subheader("Model")
    with st.expander("Ollama address", expanded=False):
        host = st.text_input("Address", OLLAMA_HOST, label_visibility="collapsed",
                             help="Where Ollama runs. On your laptop this is http://localhost:11434.")
    if host != OLLAMA_HOST:
        status = ollama_status(host)

    if status["up"] and status["models"]:
        default = pick_model(status["models"])
        model = st.selectbox("Ollama model", status["models"], index=status["models"].index(default),
                             help="Smaller models answer faster. llama3.2:3b is a good default.")
    else:
        model = pick_model([])

    mode = st.radio("Who answers the agents' prompts", ["Ollama", "Built-in rule model"],
                    index=0 if status["up"] else 1, horizontal=True,
                    help="The rule model works without Ollama but can't read free-form text as well.")

    up_txt = ("Running" + (f" · v{status['version']}" if status.get("version") else "")) if status["up"] else "Not running"
    st.html(f"""<div class="mcard">
      <div class="row"><span>Ollama</span><b style="color:{'#2E7D4F' if status['up'] else '#A5640C'}">{esc(up_txt)}</b></div>
      <div class="row"><span>Models installed</span><b>{len(status['models'])}</b></div>
    </div>""")

    if not status["up"]:
        st.caption("Start the Ollama app, or run `ollama serve`, then refresh this page. "
                   "Get a model with `ollama pull llama3.2:3b`.")
    elif not status["models"]:
        st.caption("Ollama is running but has no models. Run `ollama pull llama3.2:3b`.")
    else:
        if st.button("Test the model", use_container_width=True,
                     help="Sends one short prompt and loads the model into memory so the first case is quicker."):
            with st.spinner(f"Asking {model}…"):
                st.session_state["model_test"] = {"model": model, **test_model(host, model)}
        t = st.session_state.get("model_test")
        if t and t["model"] == model:
            if t["ok"]:
                st.success(f"{model} answered in {t['ms'] / 1000:.1f} s. It stays loaded for 15 minutes.")
            else:
                st.error(t["error"])

    st.subheader("Demo controls")
    noise = st.toggle("Make the Extractor slip once", value=False,
                      help="Injects one typical small-model mistake on the first read (rule model only) so "
                           "you can watch the Critic catch it and send the case back.")
    retries = st.slider("Times the Critic can send a case back", 0, 3, 1)

backend = "ollama" if (mode == "Ollama" and status["up"] and status["models"]) else "mock"
if mode == "Ollama" and backend == "mock":
    st.sidebar.warning("Ollama isn't ready, so the built-in rule model will answer for now.")


def make_orchestrator():
    llm = LLM(backend=backend, model=model, host=host, noise=noise and backend == "mock")
    return Orchestrator(llm, REGISTRY, max_retries=retries), llm


ENGINE_LABEL = f"Ollama · {model}" if backend == "ollama" else "Built-in rule model"

# ------------------------------------------------------------------ masthead
dot = "#2E7D4F" if backend == "ollama" else "#A5640C"
st.html(f"""
<div class="mast">
  <div>
    <h1>Scholarship screening desk</h1>
    <p>Six agents read each application for the {esc(rules.SCHEME_NAME)}, check it against the scheme
    rules, and explain every decision to the reviewer.</p>
  </div>
  <span class="pill"><i style="background:{dot}"></i>Answering: <b>{esc(ENGINE_LABEL)}</b></span>
</div>
""")


# ------------------------------------------------------------------ render helpers
def form_sheet(app: dict, title: str) -> str:
    rows = []
    structured = all(":" in l for l in app["form_text"].splitlines() if l.strip())
    if structured:
        for line in app["form_text"].splitlines():
            k, v = line.split(":", 1)
            rows.append(f'<div class="formrow"><span>{esc(k)}</span><span>{esc(v.strip())}</span></div>')
        body = "".join(rows)
    else:
        body = f'<div class="marks" style="border-left-color:var(--rule)">{esc(app["form_text"])}</div>'
    cat = next((l.split(":", 1)[1].strip() for l in app["form_text"].splitlines()
                if l.startswith("Category")), None)
    needed = rules.required_documents(cat) if cat else ["income_certificate", "marksheet", "category_certificate"]
    clips = []
    for d in needed:
        have = d in app["documents"]
        clips.append(f'<span class="clip{"" if have else " absent"}">{esc(d.replace("_", " ").capitalize())}'
                     f'{"" if have else " — not attached"}</span>')
    return f'<div class="sheet"><h4>{esc(title)}</h4>{body}<div class="clips">{"".join(clips)}</div></div>'


def marksheet(app: dict) -> str:
    if "marksheet" not in app["documents"]:
        return '<div class="marks">No marksheet attached.</div>'
    return f'<div class="marks">{esc(app["marksheet_text"])}</div>'


def pipeline_html(states: dict, notes: dict) -> str:
    out = []
    for a in AGENT_ORDER:
        out.append(f'<div class="node {states.get(a, "")}"><b>{a}</b><small>{esc(notes.get(a, "Waiting"))}</small></div>')
    return f'<div class="pipe" role="list" aria-label="Agent progress">{"".join(out)}</div>'


def badge(engine: str, ms: int) -> str:
    cls = "ollama" if engine.startswith("Ollama") else ("rules" if engine.startswith("Rule") else "")
    t = f" · {ms / 1000:.1f}s" if ms >= 100 else ""
    return f'<span class="badge {cls}">{esc(engine)}{t}</span>'


def ledger(trace) -> str:
    items = []
    for e in trace:
        items.append(f'<li class="{e.level}"><span class="who">{esc(e.agent)}</span>'
                     f'<span class="what">{esc(e.action)}<small>{esc(e.detail)}</small></span>'
                     f'{badge(e.engine, e.ms)}</li>')
    return f'<ol class="ledger">{"".join(items)}</ol>'


def secs(ms: int) -> str:
    return "under 0.1 s" if ms < 100 else f"{ms / 1000:.1f} s"


def verdict_card(case, fresh: bool) -> str:
    v = case.decision["verdict"]
    sub = f"Score {case.decision['score']}" if case.decision.get("score") else "Merit-cum-Means"
    llm_steps = [e for e in case.trace if e.engine.startswith("Ollama")]
    return f"""<div class="verdict">
      <div class="vtop">
        <span class="stamp {v} {"fresh" if fresh else ""}">{esc(VERDICT_LABEL[v])}<small>{esc(sub)}</small></span>
        <p class="note">{esc(case.report)}</p>
      </div>
      <div class="meta">
        <div><b>{secs(case.total_ms)}</b>Time to decide</div>
        <div><b>{len(llm_steps)}</b>Ollama calls</div>
        <div><b>{sum(1 for e in case.trace if e.agent == "Orchestrator")}</b>Sent back by the Critic</div>
        <div><b>{len(case.checks)}</b>Rules checked</div>
      </div>
    </div>"""


def checklist(case) -> str:
    label = {"pass": "Passed", "fail": "Failed", "missing": "Missing", "unknown": "Unclear"}
    return '<div class="checks">' + "".join(
        f'<div class="check {c["status"]}"><span class="tag">{label[c["status"]]}</span><span>{esc(c["detail"])}</span></div>'
        for c in case.checks) + "</div>"


def run_live(app: dict):
    """Run the agents on one case while the pipeline strip and trace update as each agent works."""
    orch, llm = make_orchestrator()
    states, notes = {}, {}
    pipe_ph, now_ph, trace_ph = st.empty(), st.empty(), st.empty()
    pipe_ph.html(pipeline_html(states, notes))

    def listener(kind, e, s):
        if e.agent == "Orchestrator":
            states["Extractor"], notes["Extractor"] = "warn", "Sent back by the Critic"
            states["Critic"], notes["Critic"] = "warn", "Found a wrong field"
        elif kind == "start":
            states[e.agent], notes[e.agent] = "work", e.action
            who = f" with {model}" if backend == "ollama" and e.agent in ("Planner", "Extractor", "Reporter") else ""
            now_ph.html(f'<p class="now"><b>{esc(e.agent)}</b> is {esc(e.action[0].lower() + e.action[1:])}{esc(who)}…</p>')
        else:
            states[e.agent] = "warn" if e.level == "warn" else "ok"
            notes[e.agent] = e.detail[:60] + ("…" if len(e.detail) > 60 else "")
        pipe_ph.html(pipeline_html(states, notes))
        trace_ph.html(ledger(s.trace))

    case = orch.screen(app, listener=listener)
    now_ph.empty()
    pipe_ph.empty()
    trace_ph.empty()
    return case


def summary(case):
    """Short end-of-run label for each agent in the pipeline strip."""
    sent_back = sum(1 for e in case.trace if e.agent == "Orchestrator")
    failed = sum(1 for c in case.checks if c["status"] == "fail")
    unclear = sum(1 for c in case.checks if c["status"] in ("missing", "unknown"))
    eng = lambda a: next((e.engine for e in case.trace if e.agent == a), "Python")
    short = lambda x: "Ollama" if x.startswith("Ollama") else ("Rule model" if x.startswith("Rule") else x)
    filled = sum(v is not None for v in case.fields.values())
    notes = {
        "Planner": f"{len(case.plan.get('steps', []))} checks · {short(eng('Planner'))}",
        "Extractor": f"{filled} fields · {short(eng('Extractor'))}" + (f" · re-read {sent_back}×" if sent_back else ""),
        "Critic": f"Sent back {sent_back}×" if sent_back else "All fields backed by text",
        "Validator": f"{failed} failed" + (f", {unclear} unclear" if unclear else "") if (failed or unclear) else "All 6 passed",
        "Decision": VERDICT_LABEL[case.decision["verdict"]],
        "Reporter": f"Note written · {short(eng('Reporter'))}",
    }
    states = {a: "ok" for a in AGENT_ORDER}
    if sent_back:
        states["Critic"] = "warn"
    return states, notes


def show_case(case, key: str):
    fresh = st.session_state.pop("fresh", None) == key
    st.html(verdict_card(case, fresh))
    st.markdown("#### Rule checks")
    st.html(checklist(case))
    if case.corrections:
        st.warning("The Critic replaced or cleared " + ", ".join(c["field"] for c in case.corrections)
                   + " after the Extractor failed to fix them.")
    st.markdown("#### How the agents got here")
    st.html(pipeline_html(*summary(case)))
    st.html(ledger(case.trace))
    model_steps = [e for e in case.trace if e.data.get("model_io", {}).get("prompt")]
    if model_steps:
        with st.expander(f"What the model was asked ({len(model_steps)} prompts)"):
            for e in model_steps:
                io = e.data["model_io"]
                st.markdown(f"**{e.agent}** · {e.engine} · {e.ms / 1000:.1f}s")
                if io.get("error"):
                    st.caption(io["error"])
                st.code(io["prompt"], language=None, wrap_lines=True)
                st.code(io["reply"] or "", language="json" if e.agent != "Reporter" else None, wrap_lines=True)
    with st.expander("Extracted fields and plan"):
        st.json({"plan": case.plan, "fields": case.fields, "decision": case.decision})


# ------------------------------------------------------------------ tabs
tab1, tab2, tab3, tab4 = st.tabs([":material/person_search: Screen one application",
                                  ":material/edit_note: Paste a new application",
                                  ":material/groups: Screen the whole batch",
                                  ":material/rule: Scheme rules and design"])

with tab1:
    names = {a["app_id"]: a["form_text"].splitlines()[0].split(":", 1)[1].strip() for a in APPS}
    pick = st.selectbox("Application", list(names), format_func=lambda k: f"{k} · {names[k]}")
    app = APP_BY_ID[pick]
    left, right = st.columns([5, 7], gap="large")
    with left:
        st.html(form_sheet(app, f"Application {app['app_id']}"))
        st.markdown("#### Marksheet")
        st.html(marksheet(app))
    with right:
        key = f"case::{pick}::{backend}::{model}::{noise}::{retries}"
        if st.button("Screen this application", type="primary", use_container_width=True, key="go1"):
            st.session_state[key] = run_live(app)
            st.session_state["fresh"] = key
        case = st.session_state.get(key)
        if case is None:
            st.html(pipeline_html({}, {}))
            st.caption("Press the button to watch the six agents work through this application.")
        else:
            show_case(case, key)

with tab2:
    st.html('<div class="hint"><b>This is where Ollama earns its place.</b> Paste an application written in '
            'plain language. The rule model can\'t read phrases like "earns about 3.2 lakh a year"; a local '
            'model can, and the Critic still checks every number it returns against the text.</div>')
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        form_text = st.text_area("Application text", SAMPLE["form_text"], height=210)
    with c2:
        sheet_text = st.text_area("Marksheet text", SAMPLE["marksheet_text"], height=120)
        st.markdown("Documents attached")
        docs = [d for d, label in [("income_certificate", "Income certificate"), ("marksheet", "Marksheet"),
                                   ("category_certificate", "Category certificate")]
                if st.checkbox(label, True, key=f"doc_{d}")]
    new_app = {"app_id": "NEW-2026-101", "form_text": form_text, "marksheet_text": sheet_text, "documents": docs}
    key2 = f"new::{hash((form_text, sheet_text, tuple(docs)))}::{backend}::{model}::{retries}"
    if st.button("Screen this application", type="primary", key="go2", disabled=not form_text.strip()):
        st.session_state[key2] = run_live(new_app)
        st.session_state["fresh"] = key2
    case2 = st.session_state.get(key2)
    if case2 is None:
        st.caption("Try it with the rule model first, then with Ollama, and compare the verdicts.")
    else:
        r1, r2 = st.columns([1, 1], gap="large")
        with r1:
            fresh = st.session_state.pop("fresh", None) == key2
            st.html(verdict_card(case2, fresh))
            st.markdown("#### Rule checks")
            st.html(checklist(case2))
        with r2:
            st.markdown("#### How the agents got here")
            st.html(pipeline_html(*summary(case2)))
            st.html(ledger(case2.trace))
        with st.expander("What the model was asked"):
            for e in [e for e in case2.trace if e.data.get("model_io", {}).get("prompt")]:
                io = e.data["model_io"]
                st.markdown(f"**{e.agent}** · {e.engine} · {e.ms / 1000:.1f}s")
                st.code(io["prompt"], language=None, wrap_lines=True)
                st.code(io["reply"] or "", language=None, wrap_lines=True)

with tab3:
    c1, c2 = st.columns([2, 3])
    with c1:
        slots = st.number_input("Awards available this round", 1, len(APPS), 4)
    with c2:
        st.write("")
        st.write("")
        go = st.button(f"Screen all {len(APPS)} applications", type="primary")
    if backend == "ollama":
        st.caption(f"With {model}, each application needs three model calls, so the batch takes a few minutes "
                   "on a laptop. Rows appear as each one finishes.")
    if go:
        orch, llm = make_orchestrator()
        bar = st.progress(0.0, text="Starting…")
        live = st.empty()
        cases = []
        for i, a in enumerate(APPS):
            bar.progress(i / len(APPS), text=f"Screening {a['app_id']} ({i + 1} of {len(APPS)})")
            cases.append(orch.screen(a))
            live.dataframe(pd.DataFrame([{"Application": c.app["app_id"], "Name": c.fields.get("name"),
                                          "Verdict": VERDICT_LABEL[c.decision["verdict"]],
                                          "Time": secs(c.total_ms)} for c in cases]),
                           hide_index=True, use_container_width=True)
        bar.empty()
        live.empty()
        st.session_state["batch"] = {
            "rows": Orchestrator.rank(cases, slots), "calls": llm.ollama_calls, "label": llm.label,
            "secs": sum(c.total_ms for c in cases) / 1000,
            "retries": sum(1 for c in cases for e in c.trace if e.agent == "Orchestrator")}
    b = st.session_state.get("batch")
    if not b:
        st.caption("Set how many awards are available, then screen the whole batch. Eligible students are "
                   "ranked by a merit-cum-means score: 60% CGPA, 40% financial need.")
    else:
        df = pd.DataFrame(b["rows"])
        counts = df["Outcome"].value_counts()
        st.html(f"""<div class="tally">
          <div><b>{counts.get('Awarded', 0)}</b>Awarded</div>
          <div><b>{counts.get('Waitlisted', 0)}</b>Waitlisted</div>
          <div><b>{counts.get('Needs documents', 0)}</b>Need documents</div>
          <div><b>{counts.get('Not eligible', 0)}</b>Not eligible</div>
          <div><b>{b['retries']}</b>Sent back by the Critic</div>
          <div><b>{b['calls']}</b>Ollama calls</div>
          <div><b>{secs(int(b['secs'] * 1000))}</b>{esc(b['label'])}</div>
        </div>""")
        view = df.copy()
        view["Rank"] = view["Rank"].map(lambda r: "—" if pd.isna(r) else str(int(r)))
        view["Score"] = view["Score"].map(lambda v: "—" if pd.isna(v) else f"{v:.1f}")
        view["CGPA"] = view["CGPA"].map(lambda v: "—" if pd.isna(v) else f"{v:.2f}")
        colour = {"Awarded": "#2E7D4F", "Waitlisted": "#1B2A41", "Needs documents": "#A5640C", "Not eligible": "#B3261E"}
        styled = view.style.map(lambda v: f"color:{colour.get(v, '')}; font-weight:600" if v in colour else "",
                                subset=["Outcome"])
        st.dataframe(styled, use_container_width=True, hide_index=True, height=38 * (len(view) + 1),
                     column_config={"Reviewer note": st.column_config.TextColumn(width="large")})
        st.download_button("Download the shortlist as CSV", df.to_csv(index=False).encode(), "shortlist.csv", "text/csv")

with tab4:
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
| Agent | Job | Uses Ollama |
|---|---|---|
| Planner | Reads the case and decides which checks apply, such as relaxed cutoffs for reserved categories. A guardrail adds back any check the model skips. | Yes |
| Extractor | Pulls income, CGPA, attendance and other fields from the form and marksheet, using a JSON schema so the model's answer is always structured. | Yes |
| Critic | Re-reads the source with a pattern reader and checks every number the model returned actually appears in the text. Sends the case back when something is off, and checks the final verdict. | No |
| Validator | Runs each rule as a Python tool and records pass, fail, missing or unclear. | No |
| Decision | Turns rule results into eligible, not eligible or needs documents, and scores eligible students. | No |
| Reporter | Writes a plain-English note for the reviewer. | Yes |
""")
