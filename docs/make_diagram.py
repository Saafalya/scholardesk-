"""Draws docs/architecture.svg and renders docs/architecture.png (hand-placed, 16:9)."""
from pathlib import Path

W, H = 1600, 900
INK, SOFT, RULE, PAPER = "#1B2A41", "#55627A", "#C9D2DE", "#F6F8FB"
AMBER, GREEN = "#A5640C", "#2E7D4F"
out = []


def box(x, y, w, h, title, sub="", fill="white", stroke=INK, tc=INK, r=10, sw=1.6):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    cy = y + h / 2 + (-8 if sub else 6)
    out.append(f'<text x="{x+w/2}" y="{cy}" text-anchor="middle" font-size="19" font-weight="700" fill="{tc}">{title}</text>')
    for i, line in enumerate(sub.split("\n") if sub else []):
        out.append(f'<text x="{x+w/2}" y="{cy+24+i*20}" text-anchor="middle" font-size="15" fill="{tc if fill==INK else SOFT}">{line}</text>')


def arrow(d, color=SOFT, dash="", w=1.8, label="", lx=0, ly=0, lc=None):
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" {f"stroke-dasharray=\"{dash}\"" if dash else ""} marker-end="url(#a{color[1:]})"/>')
    if label:
        out.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="14" fill="{lc or color}">{label}</text>')


def line(d, color=SOFT, dash="3 5", w=1.6):
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-dasharray="{dash}"/>')


def frame(x, y, w, h, label, color=RULE, dash="6 6", lc=SOFT):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="none" stroke="{color}" stroke-width="1.6" {f"stroke-dasharray=\"{dash}\"" if dash else ""}/>')
    out.append(f'<text x="{x+18}" y="{y+26}" font-size="15" font-weight="600" fill="{lc}">{label}</text>')


def cylinder(x, y, w, h, title, sub):
    e = 14
    out.append(f'<path d="M{x},{y+e} a{w/2},{e} 0 0,1 {w},0 v{h-2*e} a{w/2},{e} 0 0,1 {-w},0 z" fill="#E3E8EF" stroke="{INK}" stroke-width="1.6"/>')
    out.append(f'<path d="M{x},{y+e} a{w/2},{e} 0 0,0 {w},0" fill="none" stroke="{INK}" stroke-width="1.6"/>')
    out.append(f'<text x="{x+w/2}" y="{y+h/2+4}" text-anchor="middle" font-size="18" font-weight="700" fill="{INK}">{title}</text>')
    for i, l in enumerate(sub.split("\n")):
        out.append(f'<text x="{x+w/2}" y="{y+h/2+28+i*19}" text-anchor="middle" font-size="14.5" fill="{SOFT}">{l}</text>')


# ---- title
out.append(f'<text x="40" y="52" font-size="28" font-weight="700" fill="{INK}">Scholarship Screening Desk — agent architecture</text>')
out.append(f'<text x="40" y="80" font-size="16" fill="{SOFT}">Python orchestrator with shared case state · Streamlit UI · Ollama or built-in rule model</text>')

# ---- top band: inputs, UI, output
frame(40, 108, 430, 150, "Inputs (synthetic data)")
for i, (t, s) in enumerate([("Form", "free text"), ("Marksheet", "text"), ("Documents", "attached list")]):
    box(58 + i * 138, 146, 126, 92, t, s, fill=PAPER, r=6)
box(640, 140, 300, 100, "Streamlit UI", "single case · whole batch", fill=INK, stroke=INK, tc="white")
box(1150, 128, 410, 124, "Result", "Eligible / Not eligible / Needs documents\nranked shortlist within award slots\nreviewer note + agent trace",
    fill="#EAF4EE", stroke=GREEN)
arrow("M470,190 L632,190", label="case", lx=550, ly=180)
arrow("M1150,190 L948,190", label="shown to reviewer", lx=1050, ly=180)

# ---- orchestrator band
frame(40, 318, 1520, 246, "Orchestrator — runs agents in order, keeps one shared state per case", color=INK, dash="", lc=INK)
agents = [("Planner", "picks the checks"), ("Extractor", "fields from text"), ("Critic", "verifies fields"),
          ("Validator", "runs rule tools"), ("Decision", "verdict + score"), ("Critic", "verifies verdict"),
          ("Reporter", "reviewer note")]
bw, gap, x0, y0, bh = 182, 36, 66, 444, 96
xs = []
for i, (t, s) in enumerate(agents):
    x = x0 + i * (bw + gap)
    xs.append(x)
    critic = t == "Critic"
    box(x, y0, bw, bh, t, s, fill="#FFF6E8" if critic else "white", stroke=AMBER if critic else INK)
    if i:
        arrow(f"M{x-gap+2},{y0+bh/2} L{x-6},{y0+bh/2}")
# UI -> Planner, Reporter -> Result
arrow(f"M790,240 L790,290 L{xs[0]+bw/2},290 L{xs[0]+bw/2},{y0-6}")
arrow(f"M{xs[6]+bw/2},{y0-2} L{xs[6]+bw/2},292 L1355,292 L1355,260")
# critic loop back to extractor
cx, ex = xs[2] + bw / 2, xs[1] + bw / 2
arrow(f"M{cx},{y0} C{cx},{y0-58} {ex},{y0-58} {ex},{y0-6}", color=AMBER, dash="7 5", w=2,
      label="mismatch → send back (max N)", lx=(cx + ex) / 2, ly=y0 - 50)

# ---- bottom band
cylinder(150, 640, 380, 150, "Ollama · llama3.2:3b", "local model, free\nfalls back to built-in rule model")
for i in (0, 1):
    line(f"M{xs[i]+bw/2},{y0+bh} L{xs[i]+bw/2},640")
line(f"M{xs[6]+bw/2},{y0+bh} L{xs[6]+bw/2},605 L470,605 L470,646")
out.append(f'<text x="340" y="826" text-anchor="middle" font-size="14" fill="{SOFT}">Planner, Extractor and Reporter call the model.</text>')
out.append(f'<text x="340" y="846" text-anchor="middle" font-size="14" fill="{SOFT}">Validator and Critic use plain Python.</text>')

frame(630, 630, 600, 236, "Python tools (called by the Validator)")
tools = [("check_income", 648, 674), ("check_cgpa", 840, 674), ("check_attendance", 1032, 674),
         ("check_documents", 648, 760), ("check_consistency", 840, 760), ("check_registry", 1032, 760)]
for t, x, y in tools:
    out.append(f'<rect x="{x}" y="{y}" width="184" height="58" rx="6" fill="{PAPER}" stroke="{INK}" stroke-width="1.4"/>')
    out.append(f'<text x="{x+92}" y="{y+35}" text-anchor="middle" font-size="13.5" font-family="DejaVu Sans Mono, monospace" fill="{INK}">{t}()</text>')
arrow(f"M{xs[3]+bw/2},{y0+bh} L{xs[3]+bw/2},622", color=INK)
cylinder(1290, 690, 250, 130, "Awards registry", "JSON · students with\na full award this year")
line("M1216,789 L1290,765")

defs = "".join(
    f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c in (SOFT, INK, AMBER))
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="DejaVu Sans, Helvetica, Arial, sans-serif"><defs>{defs}</defs>'
       f'<rect width="{W}" height="{H}" fill="white"/>{"".join(out)}</svg>')
here = Path(__file__).parent
(here / "architecture.svg").write_text(svg)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
    pg.set_content(f"<html><body style='margin:0'>{svg}</body></html>")
    pg.screenshot(path=str(here / "architecture.png"), clip={"x": 0, "y": 0, "width": W, "height": H})
    b.close()
print("ok")
