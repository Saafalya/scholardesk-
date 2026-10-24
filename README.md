# Scholarship Screening Desk

An agentic AI proof of concept for CA-3. Six agents screen scholarship applications for a synthetic
Merit-cum-Means Scholarship 2026-27, check each one against the scheme rules, and explain every decision.

Saafalya Sengupta (PRN 24070126158) and Swastik Gavhane (PRN 24070126224) · AIML C1

Backup link (rule model only): https://scholardesk-wpdp.onrender.com

Report: `docs/ScholarDesk_Report.pdf` · Slides: `docs/ScholarDesk_CA3.pptx`

## What it does

A college scholarship office checks every application by hand: income limit, CGPA cutoff by category,
attendance, required documents, whether the CGPA on the form matches the marksheet, and whether the
student already holds another full award. This PoC hands that work to a team of agents and keeps a
human reviewer in charge of the final call.

| Agent | Job |
|---|---|
| Planner | Decides which checks apply to the case. A guardrail stops it from skipping mandatory rules. |
| Extractor | Pulls structured fields out of the free-text form and marksheet using the model. |
| Critic | Re-reads the source text and sends the case back when a field is wrong. Checks the final verdict against the rule results. |
| Validator | Executor. Runs each rule as a Python tool function. |
| Decision | Turns rule results into eligible, not eligible or needs documents, and scores eligible students. |
| Reporter | Writes a plain-English note for the reviewer. |

Batch mode ranks eligible students by a merit-cum-means score (60% CGPA, 40% financial need) and fills the
number of awards available.

## Run it on your laptop with Ollama

On Windows, double-click `run_windows.bat`. It sets up Python packages, starts Ollama, pulls
`llama3.2:3b` if it isn't installed, and opens the app in your browser.

By hand, on any system:

```bash
pip install -r requirements.txt
ollama pull llama3.2:3b      # any chat model works; pick it in the sidebar
streamlit run app.py
```

The sidebar shows whether Ollama is running, which models are installed, and has a "Test the model"
button that loads the model so the first case is quick. Each step in the agent trace is labelled with
who did the work (Ollama, the rule model, or plain Python) and how long it took, and you can open the
exact prompt and reply for every model call.

The "Paste a new application" tab is where Ollama matters most: the built-in rule model can't read
plain-language text like "our family earns about 3.2 lakh a year", but a local model can, and the
Critic still checks every number it returns against the source text.

If Ollama isn't running, the app falls back to the built-in rule model so the pipeline still works.

## Tests

```bash
python tests/test_pipeline.py
```

The tests check all 12 synthetic cases against hand-labelled verdicts, confirm the Critic catches injected
extraction mistakes, and simulate a wrong Ollama answer to confirm the send-back loop works.

## Optional: Render

The app runs locally with Ollama. `render.yaml` also sets up a free Render web service as a backup link,
but Render's free tier can't run Ollama, so that copy uses the built-in rule model.

## Files

```
app.py                  Streamlit UI
agents/llm.py           Ollama client and built-in rule model
agents/pipeline.py      The six agents and the orchestrator
agents/rules.py         Scheme rules as Python tools
data/                   Synthetic applications and awards registry
docs/architecture.png   Architecture diagram
tests/                  Pipeline tests
```
