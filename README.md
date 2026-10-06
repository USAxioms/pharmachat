# Pharmaceutical Ledger: axiomatic back end with an AI chat front end

```
engine.py  (axiomatic back end) ──sealed payload──▶ app.py ──▶ language model ──▶ chat interface
```

The back end runs the Pharmaceutical Cognitive State Ledger, including the Λ_Total optimization engine, and returns a payload sealed with SHA-256. Every answer ends with a confidence score (α_Dec), Λ_Total, and risk flags. The server verifies the seal and gives the payload to a language model, which may only state what the payload supports. Your browser re-checks the seal and shows it under each answer.

## Run

```bash
python3 app.py                       # then open http://localhost:8000
```

Python 3.10 or later, standard library only. Without an API key, answers come from the built-in renderer. To enable the AI front end:

```bash
export ANTHROPIC_API_KEY=your-key    # optional: PHARMA_LLM_MODEL=claude-sonnet-5-5, PORT=8000
python3 app.py
```

## Use

- Ask about a target: TREM2 / Alzheimer's disease, or Duchenne muscular dystrophy.
- Upload a target definition with the paperclip button (see `sample_target.json` for the required fields).
- Ask follow-up questions about the last result (requires the AI front end).
- Copy any answer with its Copy button; start over with New chat.

## Files

| File | Purpose |
|---|---|
| `engine.py` | Corrected axiomatic back end |
| `app.py` | Corrected application: server, seal verification, LLM and built-in front ends |
| `static/index.html` | Chat interface |
| `sample_target.json` | Example target for upload |
| `test_app.py` | 20 tests: `python3 test_app.py` |
| `CHANGES.md` | Every correction, with reasons |

## Scope

Research prototype. The candidate's structure is a placeholder and its properties are illustrative fixed values, which the payload marks and the answers state. Compton-class safety and performance velocity are not measured. Nothing here is medical advice. The LLM front end was not tested against the live API in the build environment (no network access); everything else was tested.
