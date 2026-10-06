# Corrections to engine.py and app.py

## engine.py
| Problem in the uploaded file | Correction |
|---|---|
| Saved with chat formatting (a markdown header and code fences), so Python failed on line 3 | Formatting removed; the file runs as Python |
| Crashed before writing its report and JSON export: `sorted()` cannot order the MDM enum values | Sorted by component name; the report and payload are now written |
| Required numpy, and one score used a random number, so results changed between runs | Standard library only (`statistics`, `math`); the random value is replaced by a fixed, documented value |
| Read the drug candidate from the wrong step, so it always fell back to a default scaffold | Reads the step that generated candidates |
| Compton-class safety and performance velocity were recorded as met without being measured | Both are recorded as not measured and not met |
| Report and demo printed "VERIFIED", "CONFIRMED", "READY FOR DEPLOYMENT", "21 seconds", and "30-million-fold" regardless of results | Every status line reflects what the run actually established |
| The JSON export lacked each step's reasoning, the candidate's structure and ADME data, and any integrity seal | The export is now a complete, sealed payload (below) |

### The sealed payload (the contract with the front end)
`export_ledger_json()` returns `{"content": …, "seal": {"sha256": …}}`, where the seal is the SHA-256 of the canonical JSON of `content`. The content includes:
- every reasoning step's transformation, inputs, outputs, axioms, and trace;
- each criterion's target, whether it was measured, its value, and whether it was met;
- `value_provenance` marking placeholder, illustrative, and assigned values;
- `not_established`, a list of everything the run did not establish, including each failed safety validation.

New functions: `run_discovery()`, `verify_payload()`, `canonical_json()`, `target_from_dict()`, and `PRESET_TARGETS`.

## Λ_Total optimization engine: connected, with strict mode
The uploaded engine defined `LambdaOptimizationEngine` but never called it. Running it on real ledger output showed:

| Finding | Correction |
|---|---|
| Λ_Total was always 0: the feature extractor only read dictionaries, so the target and pathway objects yielded just two features, no step counted as grounded, and U_Sub = 0 | Objects are read like dictionaries: 79 features, 3 of 5 steps grounded, U_Sub = 0.6 |
| An automatic "50% optimization" halved every cost, doubling Λ with no optimization performed | Off in strict mode; on in original mode, and recorded as an event |
| α_Dec values from 0.73 to 0.75 were raised to 0.75 ("threshold promotion") | Withheld in strict mode; applied in original mode; recorded either way |
| Refinement rewrote inputs: set the ethics score to 0.95 and patient safety to true, raised novelty, cut the timeline by 10% | Strict mode records the suggestions but leaves inputs as the ledger produced them |
| Several inputs were assumed defaults | Listed in the payload as `assumed_inputs` |

`LambdaOptimizationEngine(strict=True)` is the default; `strict=False` reproduces the original behavior exactly. Every discovery now runs both, and the payload's `assessments` section reports:
- **confidence:** α_Dec (decision accuracy), with a note that it is a composite score, not a probability;
- **lambda:** strict and original Λ_Total, all components, bottlenecks, suggestions, convergence, events, and the original-to-strict ratio;
- **risk_flags:** high, medium, and low flags from failed validations, unmeasured criteria, placeholders, unmet targets, Λ bottlenecks, and assumptions, labeled as flags rather than a measured risk.

Reference run (TREM2 or DMD): α_Dec 0.968; Λ strict 17.693; Λ original 35.386 (×2.00, the cost cut); primary bottleneck E_C/R_C; 11 risk flags (7 high, 2 medium, 2 low). Λ is identical for both targets because its inputs barely depend on the target while candidate properties remain fixed placeholders.

## app.py
The uploaded `app.py` was a partial copy of the engine that stopped mid-line at line 763, with no application code. It is replaced by the chat application:
- a standard-library web server that serves the chat interface;
- runs the engine for a named or uploaded target and seals the result;
- verifies the seal on every follow-up and refuses a tampered payload;
- passes the verified payload to a language model under a grounding contract (state only what the payload supports, cite steps, respect provenance, report criteria exactly, no medical advice);
- falls back to a deterministic built-in renderer when no API key is set or the model is unreachable;
- ends every answer, from either front end, with a "Confidence and risk" section, and shows confidence, Λ, and risk-flag counts on the seal.

## Unchanged
The six axioms, the reasoning steps, the MDM engine, and the R³ processor keep their original logic; the Λ engine's original logic remains available as `strict=False`. The engine still uses floating-point arithmetic internally; porting it to WAD-18 is a separate step.
