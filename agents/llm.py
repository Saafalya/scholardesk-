"""Model layer: talks to a local Ollama server, falls back to a rule-based mock.

The rest of the system only calls `llm.complete_json(...)` and `llm.complete_text(...)`,
so the agents do not care which backend answered.
"""
from __future__ import annotations

import json
import os
import random
import re

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")


def ollama_status(host: str = OLLAMA_HOST, timeout: float = 1.5) -> dict:
    """Return {'up': bool, 'models': [...]} for the sidebar."""
    try:
        r = requests.get(f"{host}/api/tags", timeout=timeout)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"up": True, "models": models}
    except Exception:
        return {"up": False, "models": []}


class LLM:
    def __init__(self, backend: str = "auto", model: str = DEFAULT_MODEL,
                 host: str = OLLAMA_HOST, noise: bool = False):
        self.host = host
        self.model = model
        self.noise = noise          # demo switch: mock makes one extraction mistake
        if backend == "auto":
            backend = "ollama" if ollama_status(host)["up"] else "mock"
        self.backend = backend
        self.calls = 0

    @property
    def label(self) -> str:
        return f"Ollama · {self.model}" if self.backend == "ollama" else "Built-in rule model"

    # ---------------------------------------------------------------- public API
    def complete_json(self, task: str, prompt: str, context: dict | None = None) -> dict:
        self.calls += 1
        if self.backend == "ollama":
            try:
                raw = self._ollama(prompt, as_json=True)
                return _loose_json(raw)
            except Exception as exc:  # network error or bad JSON: fall back, but say so
                out = self._mock_json(task, context or {})
                out["_fallback"] = f"Ollama call failed ({type(exc).__name__}); used rule model."
                return out
        return self._mock_json(task, context or {})

    def complete_text(self, task: str, prompt: str, context: dict | None = None) -> str:
        self.calls += 1
        if self.backend == "ollama":
            try:
                return self._ollama(prompt, as_json=False).strip()
            except Exception:
                pass
        return self._mock_text(task, context or {})

    # ---------------------------------------------------------------- backends
    def _ollama(self, prompt: str, as_json: bool) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if as_json:
            body["format"] = "json"
        r = requests.post(f"{self.host}/api/chat", json=body, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"]

    def _mock_json(self, task: str, ctx: dict) -> dict:
        if task == "plan":
            return mock_plan(ctx["form_text"], ctx["documents"])
        if task == "extract":
            fields = mock_extract(ctx["form_text"], ctx["marksheet_text"])
            if self.noise and ctx.get("attempt", 1) == 1:
                fields = _inject_mistake(fields, ctx.get("app_id", ""))
            return fields
        return {}

    def _mock_text(self, task: str, ctx: dict) -> str:
        if task == "report":
            return mock_report(ctx)
        return ""


def inr(n: int) -> str:
    """Indian digit grouping: 360000 -> ₹3,60,000."""
    s = str(int(n))
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups) + "," + tail


# ---------------------------------------------------------------- mock "model"
_NUM = r"([0-9][0-9,]*\.?[0-9]*)"


def _grab(pattern: str, text: str):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _to_int(s):
    return int(s.replace(",", "")) if s else None


def _to_float(s):
    try:
        return float(s.replace(",", "")) if s else None
    except ValueError:
        return None


def mock_extract(form_text: str, marksheet_text: str) -> dict:
    other = _grab(r"Other scholarships currently held:\s*(.+)", form_text)
    return {
        "name": _grab(r"Name:\s*(.+)", form_text),
        "programme": _grab(r"Programme:\s*(.+)", form_text),
        "category": (_grab(r"Category:\s*(\w+)", form_text) or "General"),
        "income": _to_int(_grab(r"income:\s*Rs\.?\s*" + _NUM, form_text)),
        "form_cgpa": _to_float(_grab(r"Previous year CGPA:\s*" + _NUM, form_text)),
        "attendance": _to_float(_grab(r"Attendance[^:]*:\s*" + _NUM, form_text)),
        "other_award": None if (other or "").lower() in ("", "none", "nil") else other,
        "sheet_cgpa": _to_float(_grab(r"Cumulative CGPA:\s*" + _NUM, marksheet_text)),
    }


def mock_plan(form_text: str, documents: list[str]) -> dict:
    category = _grab(r"Category:\s*(\w+)", form_text) or "General"
    steps = ["extract_fields", "check_documents", "check_income", "check_cgpa",
             "check_attendance", "check_consistency", "check_registry"]
    notes = []
    if category != "General":
        notes.append(f"Reserved category ({category}): apply relaxed CGPA cutoff and require a category certificate.")
    if "marksheet" not in documents:
        notes.append("No marksheet attached: CGPA checks will rely on the form only and be flagged.")
    other = _grab(r"Other scholarships currently held:\s*(.+)", form_text) or ""
    if other.strip().lower() not in ("", "none", "nil"):
        notes.append("Applicant declares another scholarship: run the registry check carefully.")
    return {"category": category, "steps": steps, "notes": notes}


def mock_report(ctx: dict) -> str:
    f, decision = ctx["fields"], ctx["decision"]
    name = f.get("name") or "The applicant"
    first = name.split()[0]
    fails = [c["detail"] for c in ctx["checks"] if c["status"] == "fail"]
    missing = [c["detail"] for c in ctx["checks"] if c["status"] == "missing"]
    if decision["verdict"] == "eligible":
        return (f"{name} meets every rule of the scheme. Marksheet CGPA is "
                f"{f['sheet_cgpa']:.2f} and family income is {inr(f['income'])}, giving a merit-cum-means "
                f"score of {decision['score']}. Recommend for the shortlist.")
    if decision["verdict"] == "needs_documents":
        return (f"{name}'s application cannot be decided yet. {' '.join(missing)} "
                f"Ask {first} to upload the missing papers. All other checks passed.")
    return f"{name} is not eligible this round. " + " ".join(fails)


def _inject_mistake(fields: dict, app_id: str) -> dict:
    """Simulate a typical small-model slip so the Critic has something to catch."""
    rnd = random.Random(app_id)
    options = ["income", "sheet_cgpa", "attendance"]
    rnd.shuffle(options)
    for choice in options:
        f = dict(fields)
        if choice == "income" and f.get("income"):
            f["income"] = int(str(f["income"])[:-1] or 0)        # dropped a digit
        elif choice == "sheet_cgpa" and f.get("sheet_cgpa") is not None:
            f["sheet_cgpa"] = f.get("form_cgpa")                 # copied the form value
        elif choice == "attendance" and f.get("attendance") is not None:
            f["attendance"] = round(f["attendance"] + 10, 1)     # misread a number
        if f != fields:
            return f
    return dict(fields)


def _loose_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise
        return json.loads(m.group(0))
