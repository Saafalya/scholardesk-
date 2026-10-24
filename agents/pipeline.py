"""The six agents and the orchestrator that runs them.

Flow for one application:
    Planner -> Extractor -> Critic (verify extraction, may send back once)
            -> Validator (rule tools) -> Decision -> Critic (verify decision) -> Reporter
Batch mode then ranks eligible applicants and fills the available award slots.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable

from . import rules
from .llm import LLM, inr, mock_extract

FIELD_KEYS = ["name", "programme", "category", "income", "form_cgpa",
              "attendance", "other_award", "sheet_cgpa"]
NUMERIC = {"income": 1.0, "form_cgpa": 0.001, "sheet_cgpa": 0.001, "attendance": 0.01}
VALID_STEPS = ["extract_fields", "check_documents", "check_income", "check_cgpa",
               "check_attendance", "check_consistency", "check_registry"]
AGENT_ORDER = ["Planner", "Extractor", "Critic", "Validator", "Decision", "Reporter"]

# JSON schemas handed to Ollama's structured-output mode
PLAN_SCHEMA = {"type": "object", "properties": {
    "category": {"type": "string", "enum": list(rules.CGPA_CUTOFF)},
    "steps": {"type": "array", "items": {"type": "string", "enum": VALID_STEPS}},
    "notes": {"type": "array", "items": {"type": "string"}}},
    "required": ["category", "steps", "notes"]}
_num_or_null = {"type": ["number", "null"]}
EXTRACT_SCHEMA = {"type": "object", "properties": {
    "name": {"type": ["string", "null"]}, "programme": {"type": ["string", "null"]},
    "category": {"type": "string", "enum": list(rules.CGPA_CUTOFF)},
    "income": _num_or_null, "form_cgpa": _num_or_null, "attendance": _num_or_null,
    "other_award": {"type": ["string", "null"]}, "sheet_cgpa": _num_or_null},
    "required": FIELD_KEYS}


@dataclass
class Event:
    agent: str
    action: str
    detail: str
    data: dict = field(default_factory=dict)
    ms: int = 0
    level: str = "info"   # info | warn | ok | error
    engine: str = "Python"  # who did the work: Ollama · model, Rule model, or Python


@dataclass
class CaseState:
    app: dict
    plan: dict = field(default_factory=dict)
    fields: dict = field(default_factory=dict)
    checks: list = field(default_factory=list)
    decision: dict = field(default_factory=dict)
    report: str = ""
    trace: list = field(default_factory=list)
    corrections: list = field(default_factory=list)
    listener: Callable | None = None
    started: float = field(default_factory=time.perf_counter)
    total_ms: int = 0

    def log(self, *a, **k):
        e = Event(*a, **k)
        self.trace.append(e)
        if self.listener:
            self.listener("done", e, self)

    def working(self, agent: str, what: str):
        if self.listener:
            self.listener("start", Event(agent, what, ""), self)


def _llm_meta(llm: LLM) -> dict:
    last = llm.last or {}
    return {"engine": last.get("label", "Python"),
            "model_io": {"prompt": last.get("prompt"), "reply": last.get("reply"), "error": last.get("error")}}


# ------------------------------------------------------------------ agents
class PlannerAgent:
    name = "Planner"

    def run(self, s: CaseState, llm: LLM):
        s.working(self.name, "Planning which checks apply")
        t = time.perf_counter()
        prompt = (
            "You plan the screening of a scholarship application. Read it and reply with JSON "
            '{"category": str, "steps": [str], "notes": [str]}. '
            f"Allowed steps: {VALID_STEPS}. Include every step that applies. "
            "category is one of General, EWS, OBC, SC, ST. Notes are short sentences about anything a "
            "reviewer should watch: reserved category, missing marksheet, another scholarship.\n\n"
            f"Attached documents: {s.app['documents']}\n\nApplication:\n{s.app['form_text']}"
        )
        plan = llm.complete_json("plan", prompt, {"form_text": s.app["form_text"],
                                                  "documents": s.app["documents"]}, schema=PLAN_SCHEMA)
        meta = _llm_meta(llm)
        steps = [x for x in plan.get("steps", []) if x in VALID_STEPS]
        # guardrail: the plan may reorder or annotate, but never skip a mandatory rule
        for must in VALID_STEPS:
            if must not in steps:
                steps.append(must)
        notes = [str(n) for n in plan.get("notes", []) if str(n).strip()][:4]
        s.plan = {"category": plan.get("category", "General"), "steps": steps, "notes": notes}
        s.log(self.name, "Broke the case into checks",
              f"{len(steps)} steps planned" + ("" if not notes else " · " + " ".join(notes)),
              {**s.plan, **meta}, _ms(t), engine=meta["engine"])


class ExtractorAgent:
    name = "Extractor"

    def run(self, s: CaseState, llm: LLM, attempt: int = 1, feedback: str = ""):
        s.working(self.name, "Reading the form and marksheet" + (f" again (attempt {attempt})" if attempt > 1 else ""))
        t = time.perf_counter()
        prompt = (
            "Extract fields from a scholarship application and its marksheet. Reply with JSON only, "
            f"keys: {FIELD_KEYS}. income is the annual family income as a whole number of rupees "
            "(5.4 lakh = 540000). form_cgpa is the CGPA the student wrote on the form. sheet_cgpa is the "
            "cumulative CGPA printed on the marksheet, not the form. attendance is a percentage number. "
            "category is one of General, EWS, OBC, SC, ST. other_award is null if the student holds none. "
            "Use null for anything not stated. Copy numbers exactly as written.\n"
            + (f"\nA reviewer found these errors in your last attempt, fix them: {feedback}\n" if feedback else "")
            + f"\nFORM:\n{s.app['form_text']}\n\nMARKSHEET:\n{s.app['marksheet_text']}"
        )
        raw = llm.complete_json("extract", prompt, {
            "form_text": s.app["form_text"], "marksheet_text": s.app["marksheet_text"],
            "attempt": attempt, "app_id": s.app["app_id"]}, schema=EXTRACT_SCHEMA)
        meta = _llm_meta(llm)
        s.fields = _normalise(raw)
        if "marksheet" not in s.app["documents"]:
            s.fields["sheet_cgpa"] = None
        s.log(self.name, "Read the form and marksheet" + (f" (attempt {attempt})" if attempt > 1 else ""),
              f"{sum(v is not None for v in s.fields.values())} of {len(FIELD_KEYS)} fields filled",
              {"fields": dict(s.fields), **meta}, _ms(t), engine=meta["engine"])


class CriticAgent:
    name = "Critic"

    def verify_extraction(self, s: CaseState) -> list[str]:
        """Two independent checks on every field the Extractor returned.

        1. Pattern check: a separate rule-based reader re-reads the text. Where it finds a
           value, the Extractor must agree with it.
        2. Grounding check: every number the Extractor returned must actually appear in the
           source text (5.4 lakh counts as 540000). This catches invented numbers even when
           the text is too free-form for the pattern reader.
        """
        s.working(self.name, "Checking every field against the source text")
        t = time.perf_counter()
        form, sheet = s.app["form_text"], s.app["marksheet_text"]
        truth = mock_extract(form, sheet)
        if "marksheet" not in s.app["documents"]:
            truth["sheet_cgpa"] = None
        problems = []
        for k in FIELD_KEYS:
            got, exp = s.fields.get(k), truth.get(k)
            if k in NUMERIC:
                src = sheet if k == "sheet_cgpa" else form
                if exp is not None and (got is None or abs(got - exp) > NUMERIC[k]):
                    problems.append(f"{k}: extracted {got}, source text says {exp}")
                elif got is not None and not _grounded(got, src, NUMERIC[k]):
                    problems.append(f"{k}: {got} does not appear anywhere in the "
                                    f"{'marksheet' if k == 'sheet_cgpa' else 'form'}")
            elif k == "name" and got and got.lower() not in form.lower():
                problems.append(f"name: {got!r} does not appear in the form")
            elif k == "category":
                if exp and (got or "General").lower() != exp.lower():
                    problems.append(f"category: extracted {got!r}, source text says {exp!r}")
        s.log(self.name, "Checked the extraction against the source text",
              "Every field is backed by the source text" if not problems else "Mismatch: " + "; ".join(problems),
              {"problems": problems, "pattern_reader": truth}, _ms(t), "ok" if not problems else "warn")
        self._truth = truth
        return problems

    def force_correct(self, s: CaseState, problems: list[str]):
        """Retries ran out: replace each disputed field with the pattern reader's value,
        or clear it if nothing trustworthy was found (the rule then reads 'unclear')."""
        bad = {p.split(":")[0] for p in problems}
        for k in bad:
            new = self._truth.get(k)
            if s.fields.get(k) != new:
                s.corrections.append({"field": k, "from": s.fields.get(k), "to": new})
                s.fields[k] = new
        s.log(self.name, "Overrode fields the Extractor kept getting wrong",
              f"{len(s.corrections)} field(s) replaced or cleared",
              {"corrections": s.corrections}, 0, "warn")

    def verify_decision(self, s: CaseState):
        s.working(self.name, "Checking the verdict against the rules")
        t = time.perf_counter()
        statuses = {c["status"] for c in s.checks}
        v = s.decision["verdict"]
        issues = []
        if v == "eligible" and statuses - {"pass"}:
            issues.append("Marked eligible while a check did not pass.")
        if v == "not_eligible" and "fail" not in statuses:
            issues.append("Marked not eligible without any failed rule.")
        if v == "needs_documents" and not ({"missing", "unknown"} & statuses):
            issues.append("Asked for documents though none are missing.")
        if v == "eligible" and len(s.checks) < len(VALID_STEPS) - 1:
            issues.append("Not every rule was run before approving.")
        s.decision["critic_issues"] = issues
        s.log(self.name, "Checked the decision against the rule results",
              "Decision is consistent with every rule" if not issues else "; ".join(issues),
              {"issues": issues}, _ms(t), "ok" if not issues else "error")
        return issues


class ValidatorAgent:
    """Executor: runs each planned check as a Python tool call."""
    name = "Validator"

    def run(self, s: CaseState, registry: dict):
        f, cat = s.fields, s.fields.get("category") or s.plan.get("category", "General")
        tools = {
            "check_documents": lambda: rules.check_documents(s.app["documents"], cat),
            "check_income": lambda: rules.check_income(f.get("income")),
            "check_cgpa": lambda: rules.check_cgpa(f.get("sheet_cgpa") if f.get("sheet_cgpa") is not None
                                                   else None, cat),
            "check_attendance": lambda: rules.check_attendance(f.get("attendance")),
            "check_consistency": lambda: rules.check_consistency(f.get("form_cgpa"), f.get("sheet_cgpa")),
            "check_registry": lambda: rules.check_registry(f.get("name"), f.get("other_award"), registry),
        }
        s.working(self.name, "Running the rule checks")
        s.checks = []
        for step in s.plan["steps"]:
            if step not in tools:
                continue
            t = time.perf_counter()
            res = tools[step]()
            s.checks.append(res)
            lvl = {"pass": "ok", "fail": "error"}.get(res["status"], "warn")
            s.log(self.name, f"Ran {step}()", res["detail"], res, _ms(t), lvl)


class DecisionAgent:
    name = "Decision"

    def run(self, s: CaseState):
        s.working(self.name, "Reaching a verdict")
        statuses = [c["status"] for c in s.checks]
        if "fail" in statuses:
            verdict = "not_eligible"
        elif "missing" in statuses or "unknown" in statuses:
            verdict = "needs_documents"
        else:
            verdict = "eligible"
        score = (rules.merit_need_score(s.fields["sheet_cgpa"], s.fields["income"])
                 if verdict == "eligible" else None)
        s.decision = {"verdict": verdict, "score": score,
                      "failed": [c["rule"] for c in s.checks if c["status"] == "fail"]}
        lvl = {"eligible": "ok", "not_eligible": "error"}.get(verdict, "warn")
        s.log(self.name, "Reached a verdict", VERDICT_LABEL[verdict] + (f" · score {score}" if score else ""),
              dict(s.decision), 0, lvl)


class ReporterAgent:
    name = "Reporter"

    def run(self, s: CaseState, llm: LLM):
        s.working(self.name, "Writing the reviewer note")
        t = time.perf_counter()
        ctx = {"fields": s.fields, "checks": s.checks, "decision": s.decision}
        prompt = (
            "Write a 2–3 sentence note for a scholarship reviewer explaining this decision in plain "
            "English. State the verdict first, then name the exact rule that failed or the document or "
            "detail that is missing, with the numbers involved. No bullet points, no greeting.\n\n"
            + json.dumps(ctx, ensure_ascii=False, default=str)
        )
        s.report = llm.complete_text("report", prompt, ctx).strip()
        meta = _llm_meta(llm)
        s.log(self.name, "Wrote the reviewer note", s.report[:110] + ("…" if len(s.report) > 110 else ""),
              {"report": s.report, **meta}, _ms(t), engine=meta["engine"])


VERDICT_LABEL = {"eligible": "Eligible", "not_eligible": "Not eligible",
                 "needs_documents": "Needs documents"}


# ------------------------------------------------------------------ orchestrator
class Orchestrator:
    def __init__(self, llm: LLM, registry: dict, max_retries: int = 1):
        self.llm, self.registry, self.max_retries = llm, registry, max_retries
        self.planner, self.extractor = PlannerAgent(), ExtractorAgent()
        self.critic, self.validator = CriticAgent(), ValidatorAgent()
        self.decider, self.reporter = DecisionAgent(), ReporterAgent()

    def screen(self, app: dict, listener: Callable | None = None) -> CaseState:
        s = CaseState(app=app, listener=listener)
        self.planner.run(s, self.llm)
        self.extractor.run(s, self.llm)
        problems = self.critic.verify_extraction(s)
        attempt = 1
        while problems and attempt <= self.max_retries:
            attempt += 1
            s.log("Orchestrator", "Sent the case back to the Extractor",
                  f"Retry {attempt - 1} of {self.max_retries}, with the Critic's notes in the prompt",
                  {"feedback": problems}, 0, "warn")
            self.extractor.run(s, self.llm, attempt=attempt, feedback="; ".join(problems))
            problems = self.critic.verify_extraction(s)
        if problems:
            self.critic.force_correct(s, problems)
        self.validator.run(s, self.registry)
        self.decider.run(s)
        self.critic.verify_decision(s)
        self.reporter.run(s, self.llm)
        s.total_ms = _ms(s.started)
        return s

    def screen_batch(self, apps: list[dict], slots: int) -> tuple[list[CaseState], list[dict]]:
        cases = [self.screen(a) for a in apps]
        return cases, self.rank(cases, slots)

    @staticmethod
    def rank(cases: list[CaseState], slots: int) -> list[dict]:
        eligible = sorted([c for c in cases if c.decision["verdict"] == "eligible"],
                          key=lambda c: c.decision["score"], reverse=True)
        rank = {c.app["app_id"]: i + 1 for i, c in enumerate(eligible)}
        rows = []
        for c in cases:
            r = rank.get(c.app["app_id"])
            if r is None:
                outcome = VERDICT_LABEL[c.decision["verdict"]]
            else:
                outcome = "Awarded" if r <= slots else "Waitlisted"
            rows.append({
                "Rank": r, "Application": c.app["app_id"], "Name": c.fields.get("name"),
                "Category": c.fields.get("category"), "CGPA": c.fields.get("sheet_cgpa"),
                "Income": inr(c.fields["income"]) if c.fields.get("income") else "—",
                "Score": c.decision["score"], "Outcome": outcome, "Reviewer note": c.report,
            })
        rows.sort(key=lambda r: (r["Rank"] is None, r["Rank"] or 0, r["Application"]))
        return rows


# ------------------------------------------------------------------ helpers
def _numbers_in(text: str) -> list[float]:
    """Every number written in the text, with commas removed, plus 'X lakh' as X * 1,00,000."""
    nums = [float(m.replace(",", "")) for m in re.findall(r"[0-9][0-9,]*\.?[0-9]*", text)
            if m.replace(",", "").replace(".", "").isdigit()]
    nums += [float(m) * 100_000 for m in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lac|lpa)", text, re.I)]
    return nums


def _grounded(value: float, text: str, tol: float) -> bool:
    return any(abs(value - n) <= max(tol, 1e-9) for n in _numbers_in(text))


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _normalise(raw: dict) -> dict:
    out = {}
    for k in FIELD_KEYS:
        v = raw.get(k)
        if k == "income":
            v = _num(v, int)
        elif k in ("form_cgpa", "sheet_cgpa", "attendance"):
            v = _num(v, float)
        elif k == "other_award":
            v = None if v in (None, "", "None", "none", "null", "Nil") else str(v)
        elif v is not None:
            v = str(v).strip()
        out[k] = v
    if out.get("category"):
        c = out["category"].strip()
        out["category"] = c.upper() if c.upper() in rules.RESERVED else "General"
    return out


def _num(v, cast):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return cast(v)
    s = "".join(ch for ch in str(v) if ch.isdigit() or ch == ".")
    try:
        return cast(float(s)) if s else None
    except ValueError:
        return None
