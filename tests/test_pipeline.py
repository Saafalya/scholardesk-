"""Run with:  python -m pytest -q   (or python tests/test_pipeline.py)"""
import json
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.llm import LLM, mock_extract  # noqa: E402
from agents.pipeline import Orchestrator  # noqa: E402

APPS = json.loads((ROOT / "data/applications.json").read_text())
REG = json.loads((ROOT / "data/awards_registry.json").read_text())

# Hand-checked expected verdicts for the synthetic data set.
EXPECTED = {
    "MCM-2026-001": "eligible",          # clean case
    "MCM-2026-002": "not_eligible",      # form CGPA 8.40 vs marksheet 7.70
    "MCM-2026-003": "not_eligible",      # income above limit
    "MCM-2026-004": "needs_documents",   # SC without category certificate
    "MCM-2026-005": "not_eligible",      # attendance 69%
    "MCM-2026-006": "eligible",
    "MCM-2026-007": "eligible",
    "MCM-2026-008": "not_eligible",      # already holds a full award
    "MCM-2026-009": "eligible",          # borderline income and attendance
    "MCM-2026-010": "needs_documents",   # no income certificate
    "MCM-2026-011": "not_eligible",      # marksheet CGPA below cutoff, form inflated
    "MCM-2026-012": "eligible",
}


def run_all(llm):
    orch = Orchestrator(llm, REG, max_retries=1)
    return {a["app_id"]: orch.screen(a) for a in APPS}


def test_verdicts_match_hand_checked_labels():
    cases = run_all(LLM("mock"))
    for app_id, want in EXPECTED.items():
        assert cases[app_id].decision["verdict"] == want, app_id


def test_critic_catches_injected_extraction_mistakes():
    cases = run_all(LLM("mock", noise=True))
    for app_id, want in EXPECTED.items():
        c = cases[app_id]
        assert c.decision["verdict"] == want, app_id
        assert any(e.agent == "Orchestrator" for e in c.trace), f"{app_id}: no send-back"


def test_critic_overrides_when_retries_run_out():
    orch = Orchestrator(LLM("mock", noise=True), REG, max_retries=0)
    c = orch.screen(APPS[0])
    assert c.corrections, "Critic should force-correct when no retries are allowed"
    assert c.decision["verdict"] == "eligible"


def test_decision_is_never_contradicted_by_critic():
    for c in run_all(LLM("mock")).values():
        assert c.decision["critic_issues"] == []


def test_ollama_path_with_a_wrong_model_answer():
    """Simulate Ollama returning a bad extraction once; the Critic must catch it."""
    app = APPS[2]  # Priya Nair, income 11,80,000 -> must be not eligible
    good = mock_extract(app["form_text"], app["marksheet_text"])
    bad = dict(good, income=118000)  # model dropped a digit -> would wrongly pass income check
    replies = iter([
        {"category": "General", "steps": ["check_income"], "notes": []},  # planner skips steps
        bad, good,                                                          # extractor: wrong, then right
        "Priya Nair is not eligible because income is above the limit.",
    ])

    def fake_post(url, json=None, timeout=None):
        r = next(replies)
        body = {"message": {"content": r if isinstance(r, str) else __import__("json").dumps(r)}}
        return mock.Mock(status_code=200, json=lambda: body, raise_for_status=lambda: None)

    with mock.patch("agents.llm.requests.post", side_effect=fake_post):
        llm = LLM("ollama")
        c = Orchestrator(llm, REG, max_retries=1).screen(app)
    assert c.decision["verdict"] == "not_eligible"
    assert len(c.checks) == 6, "Planner guardrail must restore skipped checks"
    assert any(e.agent == "Orchestrator" for e in c.trace)
    assert llm.calls == 4


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("passed", name)
