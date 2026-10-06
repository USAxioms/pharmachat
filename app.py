"""
Pharmaceutical Ledger — chat application (corrected app.py)

Architecture
  axiomatic back end (engine.py)  ──sealed payload──▶  AI front end (LLM)  ──▶  chat interface

The back end runs the Cognitive State Ledger and returns a payload sealed with SHA-256.
This server verifies the seal, then gives the payload to a language model under a grounding
contract: the model may only state what the payload supports. If no API key is configured,
a deterministic built-in renderer writes the answer from the payload instead.

Python standard library only. Run:  python3 app.py   then open http://localhost:8000
Optional environment:
  ANTHROPIC_API_KEY     enables the LLM front end
  PHARMA_LLM_MODEL      model name (default: claude-sonnet-5-5)
  PORT                  default 8000
"""
import hashlib
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

logging.getLogger().setLevel(logging.WARNING)   # the engine logs at INFO; keep the server quiet

MODEL = os.environ.get("PHARMA_LLM_MODEL", "claude-sonnet-5-5")
API_URL = "https://api.anthropic.com/v1/messages"
MAX_BODY = 2_000_000

GROUNDING_CONTRACT = """You are the conversational front end of an axiomatic back end: the Pharmaceutical
Cognitive State Ledger. The back end has run and produced a sealed payload, given below as JSON. The server has
already verified its SHA-256 seal.

Rules you must follow:
1. State only what the payload supports. If the user asks something the payload does not contain, say the ledger
   does not establish it.
2. When you state a result, cite where it comes from: a step_id, a criterion key, or a candidate id.
3. Respect value_provenance. Values marked placeholder, illustrative, or assigned must be described that way,
   never as measured or predicted results.
4. Report criteria exactly as the payload records them. Never say superintelligence is verified unless
   content.status.superintelligence_criteria_met is true. Unmeasured criteria are "not measured".
5. When relevant, mention items from content.not_established.
6. This is a research prototype. Do not give medical advice or suggest any candidate is suitable for use in people.
7. Write in plain, clear prose. Keep answers focused on the user's question.
8. End every answer with a short section titled "Confidence and risk", taken from content.assessments:
   the confidence score (α_Dec) with its note, Λ_Total in strict mode with its primary bottleneck (and the
   original-mode value for comparison), and the high-severity risk flags. Say that α_Dec and Λ_Total are composite
   scores, not probabilities, and that the risk flags are not a measured risk."""

TARGET_KEYWORDS = [
    (re.compile(r"alzheimer|trem2", re.I), "trem2"),
    (re.compile(r"duchenne|\bdmd\b|dystroph", re.I), "dmd"),
]


# ------------------------------------------------------------------ payload transport
def sealed_transport(payload: dict) -> dict:
    """What travels to the browser: the exact canonical bytes plus their seal."""
    return {"canonical": engine.canonical_json(payload["content"]), "seal": payload["seal"]}


def open_transport(t: dict):
    """Verify a payload sent back by the browser. Returns content, or None if the seal fails."""
    try:
        canonical, seal = t["canonical"], t["seal"]["sha256"]
    except (KeyError, TypeError):
        return None
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != seal:
        return None
    content = json.loads(canonical)
    if engine.canonical_json(content) != canonical:      # must be canonical, not merely parseable
        return None
    return content


# ------------------------------------------------------------------ front ends
def call_llm(content: dict, conversation: list) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    system = GROUNDING_CONTRACT + "\n\nPAYLOAD:\n" + json.dumps(content, ensure_ascii=False)
    messages = [{"role": m["role"], "content": m["content"]} for m in conversation
                if m.get("role") in ("user", "assistant") and m.get("content")][-20:]
    body = json.dumps({"model": MODEL, "max_tokens": 1500, "system": system, "messages": messages}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def fmt(x, digits=3):
    return f"{x:.{digits}f}" if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def confidence_and_risk(content: dict) -> list:
    """Closing section for every answer: confidence score, Λ_Total, and risk flags."""
    a = next(iter(content.get("assessments", {}).values()), None)
    if not a:
        return []
    st, og = a["lambda"]["strict"], a["lambda"]["original"]
    out = ["", "**Confidence and risk**",
           f"- Confidence (α_Dec): {fmt(a['confidence']['value'])}. A composite score of the ledger's reasoning, "
           f"not a probability of being correct.",
           f"- Λ_Total (strict): {fmt(st['lambda_total'])}; primary bottleneck {st['primary_bottleneck']}. "
           f"The original mode reports {fmt(og['lambda_total'])} because it cuts costs by 50% automatically.",
           f"- {len(a['lambda']['assumed_inputs'])} of the Λ inputs are assumed, not produced by the ledger."]
    high = [f["flag"] for f in a["risk_flags"] if f["severity"] == "high"]
    out.append(f"- Risk flags: {len(a['risk_flags'])} ({len(high)} high). These are not a measured risk.")
    seen = set()
    for f in high:
        label = "Safety validation failed in R3 iterations" if f.startswith("R3 iteration") else f
        if label in seen:
            continue
        seen.add(label)
        count = sum(1 for h in high if h.startswith("R3 iteration")) if f.startswith("R3 iteration") else None
        out.append(f"  - {label}" + (f" ({count} of {content['r3']['iterations']})" if count else ""))
    return out


def render_offline(content: dict, question: str) -> str:
    """Deterministic front end: writes the answer directly from the payload."""
    pid, pathway = next(iter(content["pathways"].items()))
    cid, cand = next(iter(content["candidates"].items()))
    crit = content["criteria"]
    lines = [f"**{pathway['query']}**", ""]
    lines.append(f"The ledger completed {content['r3']['iterations']} refinement cycles and produced candidate "
                 f"`{cid}` for {cand['target']}. Its structure is a placeholder and its molecular properties are "
                 f"illustrative fixed values, so they are not predictions about a real molecule.")
    lines += ["", "**Criteria**"]
    names = {"natural_emergence": "Natural emergence", "compton_safety": "Compton-class safety",
             "performance_velocity": "Performance velocity", "cognitive_transparency": "Cognitive transparency"}
    for k, v in crit.items():
        status = "met" if v["met"] else ("not measured" if not v["measured"] else "not met")
        val = f" ({v['metric']} = {fmt(v['value'])}, target {v['target']})" if v["measured"] else f" (target {v['target']})"
        lines.append(f"- {names.get(k, k)}: {status}{val}")
    overall = "met" if content["status"]["superintelligence_criteria_met"] else "not met"
    lines += ["", f"Overall, the superintelligence criteria are **{overall}**.", "", "**Reasoning steps**"]
    for st in pathway["steps"]:
        lines.append(f"- `{st['step_id']}`: {st['transformation']} (grounded in {', '.join(st['grounding_axioms'])}; "
                     f"confidence {fmt(st['confidence'], 2)})")
    lines += ["", f"Pathway strength {fmt(pathway['pathway_strength'])}; axiom coverage {fmt(pathway['axiom_coverage'], 2)}.",
              "", "**Not established**"]
    lines += [f"- {item}" for item in content["not_established"][:6]]
    if len(content["not_established"]) > 6:
        lines.append(f"- …and {len(content['not_established']) - 6} more in the payload.")
    lines += confidence_and_risk(content)
    lines += ["", "Answered by the built-in renderer. Set `ANTHROPIC_API_KEY` to enable the AI front end."]
    return "\n".join(lines)


# ------------------------------------------------------------------ request handling
def summarize_assessment(content: dict):
    a = next(iter(content.get("assessments", {}).values()), None)
    if not a:
        return None
    sev = [f["severity"] for f in a["risk_flags"]]
    return {"confidence": a["confidence"]["value"], "lambda_strict": a["lambda"]["strict"]["lambda_total"],
            "risk": {k: sev.count(k) for k in ("high", "medium", "low")}}


def pick_target(text: str, uploaded: dict):
    if uploaded:
        return engine.target_from_dict(uploaded)
    for pat, key in TARGET_KEYWORDS:
        if pat.search(text or ""):
            return engine.target_from_dict(engine.PRESET_TARGETS[key])
    return None


def handle_chat(req: dict) -> dict:
    conversation = req.get("messages") or []
    question = next((m["content"] for m in reversed(conversation) if m.get("role") == "user"), "")
    content, transport, notice = None, None, None

    try:
        target = pick_target(question, req.get("target"))
    except ValueError as e:
        return {"reply": f"The uploaded target was rejected: {e}. Every listed field is required.", "error": True}

    if target is not None:
        payload = engine.run_discovery({f: getattr(target, f) for f in engine.TARGET_FIELDS})
        content, transport = payload["content"], sealed_transport(payload)
    elif req.get("payload"):
        content = open_transport(req["payload"])
        if content is None:
            return {"reply": "The ledger payload failed seal verification, so it was not used. "
                             "Start a new chat to run the ledger again.", "error": True}
        transport = req["payload"]

    if content is None:
        return {"reply": "Name a target to run the ledger, for example TREM2 in Alzheimer's disease or Duchenne "
                         "muscular dystrophy, or upload a target definition (.json).", "payload": None}

    mode = "offline"
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            reply, mode = call_llm(content, conversation), "llm"
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            reply = render_offline(content, question)
            notice = f"The AI front end was unreachable ({type(e).__name__}); the built-in renderer answered instead."
    else:
        reply = render_offline(content, question)
        if target is None:   # a follow-up question about an earlier run
            reply = ("The built-in renderer can only summarize what the ledger established; it can't interpret "
                     "follow-up questions. Set ANTHROPIC_API_KEY to enable the AI front end for that. "
                     "Here is the ledger's sealed result:\n\n" + reply)

    return {"reply": reply, "payload": transport, "mode": mode, "notice": notice,
            "verdict": {"criteria_met": content["status"]["superintelligence_criteria_met"],
                        "assessment": summarize_assessment(content),
                        "criteria": {k: ("met" if v["met"] else "not measured" if not v["measured"] else "not met")
                                     for k, v in content["criteria"].items()},
                        "not_established": len(content["not_established"])}}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self._send(200, {"front_end": "llm" if os.environ.get("ANTHROPIC_API_KEY") else "offline", "model": MODEL})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/chat":
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return self._send(400, {"error": "request body missing or too large"})
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {"error": "request body is not valid JSON"})
        self._send(200, handle_chat(req))

    def log_message(self, fmt_, *args):
        pass


def main():
    port = int(os.environ.get("PORT", "8000"))
    # Hosting platforms such as Render set RENDER and route traffic to 0.0.0.0:$PORT.
    # Locally the app stays on 127.0.0.1 so it isn't exposed to your network.
    host = os.environ.get("HOST") or ("0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1")
    mode = "AI front end enabled" if os.environ.get("ANTHROPIC_API_KEY") else "built-in renderer (no API key set)"
    print(f"Pharmaceutical Ledger listening on {host}:{port}  [{mode}]", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
