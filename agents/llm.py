"""Model layer: talks to a local Ollama server, falls back to a rule-based model.

Agents only call `llm.complete_json(...)` and `llm.complete_text(...)`. After every call,
`llm.last` says which engine answered, how long it took, and what it was asked and replied,
so the UI can show exactly where Ollama was used.
"""
from __future__ import annotations

import json
import os
import random
import re
import time

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
PREFERRED = [DEFAULT_MODEL, "llama3.2:3b", "llama3.2", "llama3.1:8b", "qwen2.5:3b", "gemma4"]


# ---------------------------------------------------------------- Ollama helpers
def ollama_status(host: str = OLLAMA_HOST, timeout: float = 1.5) -> dict:
    """{'up': bool, 'models': [...], 'version': str|None} for the sidebar."""
    try:
        r = requests.get(f"{host}/api/tags", timeout=timeout)
        r.raise_for_status()
        models = sorted(m["name"] for m in r.json().get("models", []))
        try:
            version = requests.get(f"{host}/api/version", timeout=timeout).json().get("version")
        except Exception:
            version = None
        return {"up": True, "models": models, "version": version}
    except Exception:
        return {"up": False, "models": [], "version": None}


def pick_model(models: list[str]) -> str:
    """Prefer a small, fast model that is already installed."""
    for want in PREFERRED:
        if want in models:
            return want
    for want in PREFERRED:
        base = want.split(":")[0]
        for m in models:
            if m.split(":")[0] == base:
                return m
    return models[0] if models else DEFAULT_MODEL


def test_model(host: str, model: str) -> dict:
    """Send one tiny prompt; returns {'ok', 'ms', 'reply'|'error'}. Also warms the model up."""
    t = time.perf_counter()
    try:
        r = requests.post(f"{host}/api/chat", timeout=180, json={
            "model": model, "stream": False, "keep_alive": "15m",
            "messages": [{"role": "user", "content": "Reply with exactly: ready"}],
            "options": {"temperature": 0, "num_predict": 8}})
        r.raise_for_status()
        return {"ok": True, "ms": int((time.perf_counter() - t) * 1000),
                "reply": r.json()["message"]["content"].strip()}
    except Exception as exc:
        return {"ok": False, "ms": int((time.perf_counter() - t) * 1000), "error": _explain(exc, model)}


def _explain(exc: Exception, model: str) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code == 404:
        return f"Model {model} isn't installed. Run: ollama pull {model}"
    if isinstance(exc, requests.ConnectionError):
        return "Ollama isn't running. Start the Ollama app or run: ollama serve"
    if isinstance(exc, requests.Timeout):
        return "Ollama took too long to answer. Try a smaller model."
    return f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- the model wrapper
class LLM:
    def __init__(self, backend: str = "auto", model: str = DEFAULT_MODEL,
                 host: str = OLLAMA_HOST, noise: bool = False):
        self.host, self.model, self.noise = host, model, noise
        if backend == "auto":
            backend = "ollama" if ollama_status(host)["up"] else "mock"
        self.backend = backend
        self.calls = 0
        self.ollama_calls = 0
        self.ollama_ms = 0
        self.last: dict = {}

    @property
    def label(self) -> str:
        return f"Ollama · {self.model}" if self.backend == "ollama" else "Built-in rule model"

    # ------------------------------------------------------------ public API
    def complete_json(self, task: str, prompt: str, context: dict | None = None,
                      schema: dict | None = None) -> dict:
        self.calls += 1
        t = time.perf_counter()
        if self.backend == "ollama":
            try:
                raw = self._ollama(prompt, schema=schema or "json")
                out = _loose_json(raw)
                self._record("ollama", t, prompt, raw)
                return out
            except Exception as exc:
                out = self._mock_json(task, context or {})
                self._record("fallback", t, prompt, json.dumps(out), error=_explain(exc, self.model))
                return out
        out = self._mock_json(task, context or {})
        self._record("rules", t, prompt, json.dumps(out, ensure_ascii=False))
        return out

    def complete_text(self, task: str, prompt: str, context: dict | None = None) -> str:
        self.calls += 1
        t = time.perf_counter()
        if self.backend == "ollama":
            try:
                raw = self._ollama(prompt, schema=None).strip()
                self._record("ollama", t, prompt, raw)
                return raw
            except Exception as exc:
                out = self._mock_text(task, context or {})
                self._record("fallback", t, prompt, out, error=_explain(exc, self.model))
                return out
        out = self._mock_text(task, context or {})
        self._record("rules", t, prompt, out)
        return out

    # ------------------------------------------------------------ internals
    def _record(self, engine, t0, prompt, reply, error=None):
        ms = int((time.perf_counter() - t0) * 1000)
        label = {"ollama": f"Ollama · {self.model}", "rules": "Rule model",
                 "fallback": "Rule model (Ollama failed)"}[engine]
        if engine == "ollama":
            self.ollama_calls += 1
            self.ollama_ms += ms
        self.last = {"engine": engine, "label": label, "ms": ms, "prompt": prompt,
                     "reply": reply, "error": error}

    def _ollama(self, prompt: str, schema) -> str:
        body = {"model": self.model, "stream": False, "keep_alive": "15m",
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.1}}
        if schema is not None:
            body["format"] = schema
        r = requests.post(f"{self.host}/api/chat", json=body, timeout=180)
        if r.status_code >= 400 and isinstance(schema, dict):
            body["format"] = "json"           # older Ollama: no structured-output schemas
            r = requests.post(f"{self.host}/api/chat", json=body, timeout=180)
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
        return mock_report(ctx) if task == "report" else ""


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


# ---------------------------------------------------------------- rule-based model
_NUM = r"([0-9][0-9,]*\.?[0-9]*)"
CATEGORIES = ("General", "EWS", "OBC", "SC", "ST")


def _grab(pattern: str, text: str):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _to_int(s):
    return int(float(s.replace(",", ""))) if s else None


def _to_float(s):
    try:
        return float(s.replace(",", "")) if s else None
    except ValueError:
        return None


def find_income(text: str):
    """Reads 'Rs 5,40,000', '₹540000' or '5.4 lakh' near the word income."""
    lakh = re.search(r"income[^.\n]{0,60}?([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lac|lpa)", text, re.I)
    if lakh:
        return int(round(float(lakh.group(1)) * 100_000))
    v = _grab(r"income[^0-9\n]{0,40}?(?:rs\.?|inr|₹)?\s*" + _NUM, text)
    n = _to_int(v) if v else None
    return n if n and n >= 1000 else None


def _name_in_prose(text: str):
    """'My name is Riya Pawar and…' -> 'Riya Pawar' (capitalised words only)."""
    m = re.search(r"(?i:my name is|i am)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)", text)
    return m.group(1) if m else None


def mock_extract(form_text: str, marksheet_text: str) -> dict:
    other = _grab(r"Other scholarships?(?: currently)? held:\s*(.+)", form_text)
    cat = _grab(r"Category:\s*(\w+)", form_text) or _grab(r"\b(EWS|OBC|SC|ST)\b", form_text) or "General"
    return {
        "name": _grab(r"Name:\s*(.+)", form_text) or _name_in_prose(form_text),
        "programme": _grab(r"Programme:\s*(.+)", form_text),
        "category": cat,
        "income": find_income(form_text),
        "form_cgpa": _to_float(_grab(r"CGPA[^0-9\n]{0,25}([0-9]{1,2}\.[0-9]{1,2})", form_text)),
        "attendance": _to_float(_grab(r"Attendance[^0-9\n]{0,30}" + _NUM, form_text)
                                or _grab(r"([0-9]{2,3}(?:\.[0-9])?)\s*%\s*attendance", form_text)),
        "other_award": None if (other or "").strip().lower() in ("", "none", "nil", "no") else other,
        "sheet_cgpa": _to_float(_grab(r"Cumulative CGPA[^0-9\n]{0,10}([0-9]{1,2}\.[0-9]{1,2})", marksheet_text)
                                or _grab(r"CGPA[^0-9\n]{0,10}([0-9]{1,2}\.[0-9]{1,2})", marksheet_text)),
    }


def mock_plan(form_text: str, documents: list[str]) -> dict:
    category = mock_extract(form_text, "")["category"]
    steps = ["extract_fields", "check_documents", "check_income", "check_cgpa",
             "check_attendance", "check_consistency", "check_registry"]
    notes = []
    if category != "General":
        notes.append(f"Reserved category ({category}): apply relaxed CGPA cutoff and require a category certificate.")
    if "marksheet" not in documents:
        notes.append("No marksheet attached: CGPA checks will rely on the form only and be flagged.")
    other = _grab(r"Other scholarships?(?: currently)? held:\s*(.+)", form_text) or ""
    if other.strip().lower() not in ("", "none", "nil", "no"):
        notes.append("Applicant declares another scholarship: run the registry check carefully.")
    return {"category": category, "steps": steps, "notes": notes}


def mock_report(ctx: dict) -> str:
    f, decision = ctx["fields"], ctx["decision"]
    name = f.get("name") or "The applicant"
    first = name.split()[0]
    fails = [c["detail"] for c in ctx["checks"] if c["status"] == "fail"]
    missing = [c["detail"] for c in ctx["checks"] if c["status"] in ("missing", "unknown")]
    if decision["verdict"] == "eligible":
        return (f"{name} meets every rule of the scheme. Marksheet CGPA is "
                f"{f['sheet_cgpa']:.2f} and family income is {inr(f['income'])}, giving a merit-cum-means "
                f"score of {decision['score']}. Recommend for the shortlist.")
    if decision["verdict"] == "needs_documents":
        return (f"{name}'s application cannot be decided yet. {' '.join(missing)} "
                f"Ask {first} for the missing details. All other checks passed.")
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
