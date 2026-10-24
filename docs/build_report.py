"""Builds docs/ScholarDesk_Report.pdf from the live pipeline results."""
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents import rules  # noqa: E402
from agents.llm import LLM, inr  # noqa: E402
from agents.pipeline import VERDICT_LABEL, Orchestrator  # noqa: E402

LIVE_URL = "https://scholardesk-wpdp.onrender.com"
REPO_URL = "https://github.com/Saafalya/scholardesk-"

# ---------------------------------------------------------------- fonts & styles
D = "/usr/share/fonts/truetype/dejavu/"
G = "/usr/share/fonts/truetype/google-fonts/"
pdfmetrics.registerFont(TTFont("Body", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Head", G + "Poppins-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Head-Med", G + "Poppins-Medium.ttf"))
pdfmetrics.registerFont(TTFont("Mono", D + "DejaVuSansMono.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body", boldItalic="Body-Bold")

INK = colors.HexColor("#1B2A41")
SOFT = colors.HexColor("#55627A")
RULE = colors.HexColor("#C9D2DE")
PAPER = colors.HexColor("#F3F5F8")
PASS, FAIL, QUERY = colors.HexColor("#2E7D4F"), colors.HexColor("#B3261E"), colors.HexColor("#A5640C")

body = ParagraphStyle("body", fontName="Body", fontSize=10, leading=15.2, textColor=INK, spaceAfter=7, alignment=TA_LEFT)
small = ParagraphStyle("small", parent=body, fontSize=8.6, leading=12, textColor=SOFT)
cell = ParagraphStyle("cell", parent=body, fontSize=8.6, leading=11.6, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Body-Bold")
h1 = ParagraphStyle("h1", fontName="Head", fontSize=17, leading=22, textColor=INK, spaceBefore=4, spaceAfter=8)
h2 = ParagraphStyle("h2", fontName="Head-Med", fontSize=12.5, leading=17, textColor=INK, spaceBefore=10, spaceAfter=5)
cap = ParagraphStyle("cap", parent=small, spaceBefore=4, spaceAfter=12)


def P(t, s=body):
    return Paragraph(t, s)


def table(rows, widths, header=True, zebra=True):
    data = [[c if not isinstance(c, str) else P(c, cellb if (header and i == 0) else cell) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if header:
        st += [("LINEBELOW", (0, 0), (-1, 0), 1.1, INK), ("BACKGROUND", (0, 0), (-1, 0), PAPER)]
    t.setStyle(TableStyle(st))
    return t


def image(path, width):
    from PIL import Image as PI
    w, h = PI.open(path).size
    return Image(str(path), width=width, height=width * h / w)


# ---------------------------------------------------------------- results from the real pipeline
APPS = json.loads((ROOT / "data/applications.json").read_text())
REG = json.loads((ROOT / "data/awards_registry.json").read_text())
cases, rows = Orchestrator(LLM("mock"), REG).screen_batch(APPS, slots=4)
noisy = [Orchestrator(LLM("mock", noise=True), REG).screen(a) for a in APPS]
caught = sum(1 for c in noisy if any(e.agent == "Orchestrator" for e in c.trace))
agree = sum(1 for a, b in zip(cases, noisy) if a.decision["verdict"] == b.decision["verdict"])
forced = [Orchestrator(LLM("mock", noise=True), REG, max_retries=0).screen(a) for a in APPS]
forced_ok = sum(1 for a, b in zip(cases, forced) if a.decision["verdict"] == b.decision["verdict"])

EXPECTED = {"MCM-2026-001": "eligible", "MCM-2026-002": "not_eligible", "MCM-2026-003": "not_eligible",
            "MCM-2026-004": "needs_documents", "MCM-2026-005": "not_eligible", "MCM-2026-006": "eligible",
            "MCM-2026-007": "eligible", "MCM-2026-008": "not_eligible", "MCM-2026-009": "eligible",
            "MCM-2026-010": "needs_documents", "MCM-2026-011": "not_eligible", "MCM-2026-012": "eligible"}
matches = sum(1 for c in cases if c.decision["verdict"] == EXPECTED[c.app["app_id"]])

# ---------------------------------------------------------------- page furniture
def on_page(c, doc):
    if doc.page == 1:
        return
    c.saveState()
    c.setFont("Body", 8)
    c.setFillColor(SOFT)
    c.drawString(20 * mm, 12 * mm, "Scholarship Screening Desk · CA-3 Agentic AI PoC · Saafalya Sengupta")
    c.drawRightString(190 * mm, 12 * mm, str(doc.page))
    c.setStrokeColor(RULE)
    c.line(20 * mm, 16 * mm, 190 * mm, 16 * mm)
    c.restoreState()


def cover(c, doc):
    c.saveState()
    W, H = A4
    c.setFillColor(INK)
    c.rect(0, H - 118 * mm, W, 118 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Head-Med", 11)
    c.drawString(22 * mm, H - 30 * mm, "CA-3 · Agentic AI Proof of Concept")
    c.setFont("Head", 34)
    c.drawString(22 * mm, H - 58 * mm, "Scholarship")
    c.drawString(22 * mm, H - 73 * mm, "Screening Desk")
    c.setFont("Body", 11.5)
    c.drawString(22 * mm, H - 88 * mm, "Six AI agents that screen scholarship applications,")
    c.drawString(22 * mm, H - 94.5 * mm, "check them against the rules and explain every decision.")
    # stamp
    c.translate(150 * mm, H - 100 * mm)
    c.rotate(-6)
    c.setStrokeColor(colors.HexColor("#7FC79A"))
    c.setFillColor(colors.HexColor("#7FC79A"))
    c.setLineWidth(1.6)
    c.roundRect(0, 0, 44 * mm, 15 * mm, 2 * mm)
    c.roundRect(1.2 * mm, 1.2 * mm, 41.6 * mm, 12.6 * mm, 1.6 * mm)
    c.setFont("Head", 13)
    c.drawCentredString(22 * mm, 6.4 * mm, "ELIGIBLE")
    c.restoreState()

    c.saveState()
    c.setFillColor(INK)
    y = H - 140 * mm
    for k, v in [("Student", "Saafalya Sengupta"), ("PRN", "24070126158"), ("Class / Division", "AIML C1"),
                 ("Domain", "Education: scholarship administration"),
                 ("Faculty", "Harshal Raut"), ("Date", "24 October 2026")]:
        c.setFont("Body", 9)
        c.setFillColor(SOFT)
        c.drawString(22 * mm, y, k)
        c.setFont("Body-Bold", 11.5)
        c.setFillColor(INK)
        c.drawString(70 * mm, y, v)
        c.setStrokeColor(RULE)
        c.line(22 * mm, y - 4 * mm, 188 * mm, y - 4 * mm)
        y -= 12 * mm
    c.setFont("Body", 9)
    c.setFillColor(SOFT)
    c.drawString(22 * mm, 30 * mm, f"Live app: {LIVE_URL}")
    c.drawString(22 * mm, 24 * mm, f"Code: {REPO_URL}")
    c.restoreState()


# ---------------------------------------------------------------- content
S = []
S.append(PageBreak())

S.append(P("1. Problem statement and domain", h1))
S.append(P(
    "Colleges run merit-cum-means scholarships every year. A student fills in a form with family income, "
    "previous-year CGPA, attendance and category, then attaches an income certificate, a marksheet and, for "
    "reserved categories, a category certificate. Office staff check each application by hand against the "
    "scheme rules and prepare a shortlist for the committee."))
S.append(P(
    "<b>Problem statement.</b> Manual screening of scholarship applications is slow, inconsistent between "
    "reviewers, and poor at catching mismatches between what a student writes on the form and what the "
    "marksheet actually says. Rejected students rarely get a clear reason."))
S.append(P("Why this domain", h2))
S.append(P(
    "Education fits an agentic approach well for three reasons. The rules are explicit, so every decision can "
    "be checked. The inputs are messy free text, which is where a language model helps. And the cost of a wrong "
    "call is real: a deserving student misses support, or money goes to someone who already holds a full award. "
    "That makes validation and explanation as important as speed, which is exactly what an agent team with a "
    "dedicated Critic can show."))

S.append(P("2. Existing challenge and proposed solution", h1))
S.append(P("How it works today", h2))
S.append(table([
    ["Step", "What staff do now", "What goes wrong"],
    ["Read the form", "Type income, CGPA and attendance into a sheet by hand", "Typing errors, missed fields"],
    ["Check documents", "Open each attachment and tick a box", "Missing papers noticed late, after the shortlist"],
    ["Apply the rules", "Compare against the income limit and the category cutoffs", "Different reviewers read rules differently"],
    ["Cross-check", "Compare form CGPA with the marksheet, if time allows", "Inflated CGPA often slips through"],
    ["Check other awards", "Search the registry for full awards", "Double funding when the search is skipped"],
    ["Shortlist", "Sort by CGPA and income in a spreadsheet", "No written reason for each rejection"],
], [32 * mm, 70 * mm, 68 * mm]))
S.append(Spacer(1, 8))
S.append(P("Proposed solution", h2))
S.append(P(
    "Scholarship Screening Desk hands this routine work to six cooperating agents. A Planner decides which "
    "checks apply. An Extractor uses a local language model (Ollama) to pull fields out of the free-text form "
    "and marksheet. A Critic independently re-reads the source text and sends the case back when a field is "
    "wrong. A Validator runs every scheme rule as a Python tool. A Decision agent turns the rule results into "
    "one of three verdicts and scores eligible students. A Reporter writes a plain-English note for the "
    "reviewer. In batch mode the system ranks eligible students and fills the number of awards available."))
S.append(P(
    "The human reviewer stays in charge. The system recommends and explains; it does not disburse money. Every "
    "step is shown in an agent trace, so a reviewer can see exactly why a case landed where it did."))

S.append(PageBreak())
S.append(P("3. Agent roles, responsibilities and orchestration", h1))
S.append(table([
    ["Agent", "Type", "Responsibility", "Uses the model?"],
    ["Planner", "Planner", "Reads the case and lists the checks to run, with notes such as relaxed cutoffs for "
     "reserved categories. A guardrail adds back any mandatory check the model leaves out.", "Yes"],
    ["Extractor", "Research", "Turns the free-text form and marksheet into structured fields: name, category, "
     "income, form CGPA, marksheet CGPA, attendance and other awards.", "Yes"],
    ["Critic", "Critic", "Re-reads the source text with a separate parser and compares field by field. On a "
     "mismatch it sends the case back with its notes. If retries run out, it overrides the wrong fields. After "
     "the verdict it checks the verdict agrees with every rule result.", "No"],
    ["Validator", "Executor", "Calls six Python tools: check_income, check_cgpa, check_attendance, "
     "check_documents, check_consistency and check_registry. Each returns pass, fail, missing or unclear with "
     "a reason.", "No"],
    ["Decision", "Business automation", "Any failed rule means not eligible. Any missing or unclear item means "
     "needs documents. Otherwise eligible, with a merit-cum-means score.", "No"],
    ["Reporter", "Business automation", "Writes a two to three sentence note naming the exact rule that failed "
     "or the document that is missing.", "Yes"],
], [24 * mm, 26 * mm, 100 * mm, 20 * mm]))
S.append(Spacer(1, 6))
S.append(P("Orchestration workflow", h2))
S.append(P(
    "A Python orchestrator runs the agents in a fixed order and passes one shared case state between them. The "
    "state holds the plan, the extracted fields, the rule results, the verdict, the note and a trace of every "
    "step. The flow for one application is:"))
S.append(P(
    "Planner → Extractor → Critic (verify fields) → [send back to Extractor, up to N times] → Validator → "
    "Decision → Critic (verify verdict) → Reporter.", ParagraphStyle("flow", parent=body, fontName="Body-Bold",
                                                                      backColor=PAPER, borderPadding=7,
                                                                      spaceBefore=4, spaceAfter=12)))
S.append(P(
    "Three decision points make this agentic rather than a fixed script. The Planner chooses the checks per case. "
    "The Critic decides whether to accept the extraction, send it back, or override it. The Decision agent "
    "chooses between three outcomes, and in batch mode the orchestrator decides who is awarded and who is "
    "waitlisted based on the number of slots. The number of send-backs is a setting in the sidebar."))
S.append(P(
    "Merit-cum-means score = 100 × (0.6 × CGPA ÷ 10 + 0.4 × (1 − income ÷ income limit)). It rewards strong "
    "marks and greater financial need together, so a student with a 7.8 CGPA and low income can rank above a "
    "student with 9.1 and a higher income.", small))

S.append(PageBreak())
S.append(P("4. Architecture", h1))
S.append(image(ROOT / "docs/architecture.png", 170 * mm))
S.append(P("Figure 1. Agents, data flow, tools and decision points. Amber boxes are the two Critic checkpoints; "
           "the dashed amber arrow is the send-back loop.", cap))
S.append(table([
    ["Layer", "What it is", "Technology"],
    ["Interface", "Single-case screening, batch shortlist, rules and design tabs", "Streamlit"],
    ["Orchestration", "Runs agents in order, holds shared case state, controls retries", "Plain Python classes"],
    ["Model", "Planner, Extractor and Reporter prompts, JSON output mode", "Ollama, llama3.2:3b (local, free)"],
    ["Fallback model", "Rule-based model with the same interface when Ollama is not reachable", "Python regex"],
    ["Tools", "Six rule functions the Validator calls", "Python"],
    ["Data", "12 synthetic applications and a synthetic awards registry", "JSON files"],
    ["Hosting", "Public demo link", "Render free web service"],
], [28 * mm, 92 * mm, 50 * mm]))

S.append(PageBreak())
S.append(P("5. Working Streamlit PoC", h1))
S.append(P(
    f"The app runs locally with Ollama and is also deployed at <b>{LIVE_URL}</b>. The sidebar shows which model "
    "is answering, lets the reviewer pick an Ollama model, and has a demo switch that makes the Extractor slip "
    "once so the Critic's send-back can be seen live."))
S.append(KeepTogether([image(ROOT / "docs/shots/02_case_top.png", 150 * mm), P("Figure 2. Screening one application. The form and marksheet sit on the left. The verdict stamp, "
           "reviewer note, rule checks and the numbered agent trace sit on the right. Here the Critic caught an "
           "extraction mistake (steps 3–6) and the case was rejected for an inflated CGPA.", cap)]))
S.append(PageBreak())
S.append(image(ROOT / "docs/shots/03_batch.png", 170 * mm))
S.append(P("Figure 3. Batch screening of all 12 applications with four awards available.", cap))
S.append(P("Synthetic data", h2))
S.append(P(
    "The 12 applications are invented but realistic, and each one is built to test a specific rule: a clean "
    "pass, an inflated CGPA, income above the limit, a missing category certificate, low attendance, a student "
    "who already holds a full award, a missing income certificate, a borderline case just inside the limits, "
    "and reserved-category students who pass on the relaxed cutoff."))

S.append(PageBreak())
S.append(P("6. Output validation and results", h1))
S.append(P(
    "Validation happens at two levels: inside the system, where the Critic checks the other agents at runtime, "
    "and outside it, where automated tests compare results against hand-checked answers."))
S.append(P("Results on the 12 synthetic applications", h2))
res = [["Application", "Name", "Category", "Verdict", "Score", "Outcome"]]
for r in rows:
    res.append([r["Application"], r["Name"] or "—", r["Category"] or "—",
                VERDICT_LABEL[next(c for c in cases if c.app["app_id"] == r["Application"]).decision["verdict"]],
                "—" if r["Score"] is None else f'{r["Score"]:.1f}', r["Outcome"]])
t = table(res, [28 * mm, 36 * mm, 20 * mm, 32 * mm, 16 * mm, 38 * mm])
colour = {"Awarded": PASS, "Waitlisted": INK, "Needs documents": QUERY, "Not eligible": FAIL}
for i, r in enumerate(rows, start=1):
    t.setStyle(TableStyle([("TEXTCOLOR", (5, i), (5, i), colour[r["Outcome"]])]))
S.append(t)
S.append(Spacer(1, 10))
S.append(P("Validation checks", h2))
S.append(table([
    ["Check", "How it is tested", "Result"],
    ["Verdict accuracy", "Each of the 12 verdicts compared with a hand-checked label", f"{matches} of 12 correct"],
    ["Critic catches extraction errors", "Demo switch injects one realistic mistake per case (dropped digit, "
     "copied value, misread number)", f"{caught} of 12 caught and sent back"],
    ["Verdicts survive injected errors", "Same 12 cases with mistakes injected and one retry allowed",
     f"{agree} of 12 verdicts unchanged"],
    ["Critic override with no retries", "Mistakes injected and retries set to zero", f"{forced_ok} of 12 verdicts unchanged"],
    ["Planner guardrail", "Simulated Ollama plan that lists only one check", "All six checks restored"],
    ["Real model path", "Simulated Ollama reply with a wrong income, then a correct one", "Caught; correct verdict"],
    ["Decision consistency", "Critic compares each verdict with the rule results", "0 contradictions"],
], [44 * mm, 86 * mm, 40 * mm]))
S.append(Spacer(1, 6))
S.append(P(
    "All tests live in tests/test_pipeline.py and run with one command. In the batch run with four awards, "
    "Kavya Iyer (ST, CGPA 7.80, income ₹3,60,000) ranks first ahead of Ananya Kulkarni (General, CGPA 9.12, "
    "income ₹5,40,000), which shows the score weighing need alongside merit as the scheme intends."))
S.append(P(
    "Speed: with the built-in model the agents screen all 12 applications in under a second. With Ollama, each "
    "case needs three model calls (plan, extract, report), so the time per case depends on the laptop running "
    "the model. Either way, every decision comes with a written reason, which manual screening rarely provides.",
    body))

S.append(P("7. Limitations", h1))
for t_ in [
    "<b>Synthetic data only.</b> The forms are clean text. Real applications arrive as scanned PDFs and photos, "
    "which would need OCR before the Extractor.",
    "<b>Critic uses the same patterns as the fallback model.</b> When Ollama is not running, the Critic and "
    "the fallback Extractor read the text the same way, so they agree unless the demo switch injects a mistake. "
    "The Critic is most useful when a real model does the extraction.",
    "<b>Small local model.</b> llama3.2:3b can misread numbers or return broken JSON. The Critic and the "
    "fallback catch this, but extraction is slower than a larger hosted model.",
    "<b>Hosted demo has no model.</b> Render's free tier has 512 MB of RAM, too little for Ollama, so the "
    "public link runs the built-in rule model.",
    "<b>Rules are fixed in code.</b> A new scheme needs a developer to change rules.py.",
    "<b>No document authenticity check.</b> The system checks that documents are attached, not that they are genuine.",
]:
    S.append(P("•  " + t_, ParagraphStyle("li", parent=body, leftIndent=10, firstLineIndent=-8)))

S.append(P("8. Future scope", h1))
for t_ in [
    "Add OCR so the Extractor can read scanned certificates and marksheets directly.",
    "Let the scholarship office edit rules in the app, so one system can run several schemes.",
    "Move orchestration to LangGraph and expose the rule tools over MCP, so other college systems can call them.",
    "Verify income certificates against government records such as DigiLocker, with the student's consent.",
    "Draft the email to each student with their result and, if needed, the documents to upload.",
    "Track reviewer overrides and use them to improve prompts and spot rules that need clarifying.",
]:
    S.append(P("•  " + t_, ParagraphStyle("li2", parent=body, leftIndent=10, firstLineIndent=-8)))

S.append(PageBreak())
S.append(P("Appendix A. Scheme rules", h1))
S.append(P(f"Scheme: {rules.SCHEME_NAME} (synthetic). Family income at most {inr(rules.INCOME_LIMIT)} a year. "
           f"Attendance at least {rules.ATTENDANCE_MIN:.0f}%. Form CGPA must match the marksheet within "
           f"{rules.CGPA_TOLERANCE}. No full-tuition award already held this year."))
S.append(table([["Category", "Minimum CGPA", "Documents required"]] +
               [[k, f"{v:.1f}", ", ".join(d.replace("_", " ") for d in rules.required_documents(k))]
                for k, v in rules.CGPA_CUTOFF.items()], [30 * mm, 30 * mm, 110 * mm]))
S.append(P("Appendix B. How to run", h1))
for line in ["pip install -r requirements.txt", "ollama pull llama3.2:3b", "streamlit run app.py",
             "python tests/test_pipeline.py"]:
    S.append(P(line, ParagraphStyle("code", parent=body, fontName="Mono", fontSize=9, backColor=PAPER,
                                    borderPadding=5, spaceAfter=9)))
S.append(P(f"Code: {REPO_URL}<br/>Live app: {LIVE_URL}", small))

out = ROOT / "docs/ScholarDesk_Report.pdf"
doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                        topMargin=20 * mm, bottomMargin=22 * mm, title="Scholarship Screening Desk — CA-3 Report",
                        author="Saafalya Sengupta")
doc.build(S, onFirstPage=cover, onLaterPages=on_page)
print("wrote", out, "| matches", matches, "caught", caught, "agree", agree, "forced_ok", forced_ok)
