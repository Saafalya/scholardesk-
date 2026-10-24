# Scholarship Screening Desk

An agentic AI proof of concept for CA-3. Six agents screen scholarship applications for a synthetic
Merit-cum-Means Scholarship 2026-27, check each one against the scheme rules, and explain every decision.

Saafalya Sengupta · PRN 24070126158 · AIML C1

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

```bash
pip install -r requirements.txt
ollama pull llama3.2:3b      # any chat model works; pick it in the sidebar
ollama serve                 # if it isn't already running
streamlit run app.py
```

If Ollama isn't running, the app uses a built-in rule model so the full agent pipeline still works.

## Tests

```bash
python tests/test_pipeline.py
```

The tests check all 12 synthetic cases against hand-labelled verdicts, confirm the Critic catches injected
extraction mistakes, and simulate a wrong Ollama answer to confirm the send-back loop works.

## Deploy on Render

`render.yaml` sets up a free Python web service. Render's free tier has 512 MB of RAM, which is not enough
to run an Ollama model, so the hosted app uses the built-in rule model unless `OLLAMA_HOST` points to a
reachable Ollama server.

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
