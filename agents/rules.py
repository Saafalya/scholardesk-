"""Scheme rules for the synthetic Merit-cum-Means Scholarship 2026-27.

Every rule is a plain Python function so the Validator agent can call it as a tool
and the result can be traced and explained.
"""

from .llm import inr

SCHEME_NAME = "Merit-cum-Means Scholarship 2026-27"

INCOME_LIMIT = 800_000          # annual family income, in rupees
ATTENDANCE_MIN = 75.0           # percent
CGPA_CUTOFF = {                 # minimum previous-year CGPA by category
    "General": 8.0,
    "EWS": 7.5,
    "OBC": 7.5,
    "SC": 7.0,
    "ST": 7.0,
}
CGPA_TOLERANCE = 0.05           # allowed gap between form CGPA and marksheet CGPA
RESERVED = {"EWS", "OBC", "SC", "ST"}


def required_documents(category: str) -> list[str]:
    docs = ["income_certificate", "marksheet"]
    if category in RESERVED:
        docs.append("category_certificate")
    return docs


def check_income(income: int | None) -> dict:
    if income is None:
        return _result("income", "unknown", "Family income could not be read from the form.")
    ok = income <= INCOME_LIMIT
    return _result(
        "income",
        "pass" if ok else "fail",
        f"Family income {inr(income)} is {'within' if ok else 'above'} the {inr(INCOME_LIMIT)} limit.",
    )


def check_cgpa(cgpa: float | None, category: str) -> dict:
    cutoff = CGPA_CUTOFF.get(category, CGPA_CUTOFF["General"])
    if cgpa is None:
        return _result("cgpa", "unknown", "CGPA could not be read from the marksheet.")
    ok = cgpa >= cutoff
    return _result(
        "cgpa",
        "pass" if ok else "fail",
        f"Marksheet CGPA {cgpa:.2f} is {'at or above' if ok else 'below'} the {category} cutoff of {cutoff:.1f}.",
    )


def check_attendance(attendance: float | None) -> dict:
    if attendance is None:
        return _result("attendance", "unknown", "Attendance could not be read from the form.")
    ok = attendance >= ATTENDANCE_MIN
    return _result(
        "attendance",
        "pass" if ok else "fail",
        f"Attendance {attendance:.0f}% is {'at or above' if ok else 'below'} the {ATTENDANCE_MIN:.0f}% minimum.",
    )


def check_documents(submitted: list[str], category: str) -> dict:
    missing = [d for d in required_documents(category) if d not in submitted]
    if missing:
        names = ", ".join(d.replace("_", " ") for d in missing)
        return _result("documents", "missing", f"Missing: {names}.", missing=missing)
    return _result("documents", "pass", "All required documents are attached.")


def check_consistency(form_cgpa: float | None, sheet_cgpa: float | None) -> dict:
    if form_cgpa is None or sheet_cgpa is None:
        return _result("consistency", "unknown", "Could not compare form CGPA with marksheet CGPA.")
    gap = abs(form_cgpa - sheet_cgpa)
    ok = gap <= CGPA_TOLERANCE
    return _result(
        "consistency",
        "pass" if ok else "fail",
        f"Form says {form_cgpa:.2f}, marksheet says {sheet_cgpa:.2f}"
        + ("." if ok else f" — a gap of {gap:.2f}, so the form figure is not accepted."),
    )


def check_registry(name: str | None, other_award: str | None, registry: dict) -> dict:
    holders = {a["student"].lower(): a["award"] for a in registry.get("full_awards", [])}
    if name and name.lower() in holders:
        return _result(
            "registry", "fail",
            f"Already holds {holders[name.lower()]} this year. Full awards cannot be combined.",
        )
    if other_award and "full" in other_award.lower():
        return _result("registry", "fail", f"Form declares a full award: {other_award}.")
    return _result("registry", "pass", "No overlapping full award found in the registry.")


def merit_need_score(cgpa: float, income: int) -> float:
    """Ranking score for eligible students: 60% merit, 40% financial need."""
    merit = min(cgpa / 10.0, 1.0)
    need = max(0.0, 1.0 - income / INCOME_LIMIT)
    return round(100 * (0.6 * merit + 0.4 * need), 1)


def _result(rule: str, status: str, detail: str, **extra) -> dict:
    return {"rule": rule, "status": status, "detail": detail, **extra}
