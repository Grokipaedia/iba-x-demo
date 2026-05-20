# IBA × X — Zero Trust for Autonomous AI Agents

> The first reference implementation of Intent-Bound Authorization applied to a production AI system.

**xAI open-sourced X's recommendation engine. We made it ungovernable by default impossible.**

Every action Phoenix takes requires your cryptographically signed human intent. No token → blocked. Wrong scope → blocked. Expired → blocked. Always.

---

## What this is

[xAI's Phoenix + Grox](https://github.com/xai-org/x-algorithm) is the real "For You" recommendation engine, open-sourced. IBA wraps every pipeline call in a signed intent token — so the algorithm cannot act without explicit human authorisation at the protocol layer.

Not a monitoring tool. Not a dashboard. Not a rate limiter.

A **trust primitive** — the foundation layer on which governed AI systems are built.

→ [Why IBA-X exists](WHY-IBA-X.md)
→ [How the trust model works](TRUST_MODEL.md)
→ [Scope enforcement in real flows](SCOPE.md)

---

## Quick start

```bash
# 1. Clone this repo and the X algorithm
git clone https://github.com/Grokipaedia/iba-x-demo.git && cd iba-x-demo
git clone https://github.com/xai-org/x-algorithm.git x-algorithm

# 2. Start the IBA gateway (wraps Phoenix on :8080)
python iba_wrapper.py

# 3. Generate a signed intent token
python iba_wrapper.py --gen-token --signer "your.name" --scope RECOMMEND

# 4. Fire a governed recommendation request
curl -X POST http://localhost:8080/recommend \
  -H 'X-IBA-Intent: <paste token here>' \
  -H 'Content-Type: application/json' \
  -d '{"candidate_ids": [1,2,3,4,5,6,7,8,9,10]}'
```

> First run downloads the ~3GB mini Phoenix model.

---

## Without IBA vs with IBA

| Without IBA | With IBA |
|---|---|
| Algorithm runs autonomously | Every action requires a signed intent token |
| Side-effects are implicit | Side-effects declared before execution |
| Governance bolted on after | Governance at the protocol layer |
| No audit trail | Immutable intent ledger per request |
| Trust assumed | Trust cryptographically proven |

---

## How it works

```
User Agent
    │
    │  POST /recommend
    │  X-IBA-Intent: <signed token>
    ▼
┌─────────────────────────────────────┐
│         IBA Gateway (port 8080)     │
│                                     │
│  1. Extract intent token            │
│  2. Verify HMAC-SHA256 signature    │
│  3. Check scope (RECOMMEND etc.)    │
│  4. Check expiry (TTL 300s)         │
│  5. Log to intent ledger            │
│                                     │
│  BLOCKED if any step fails ──────►  401/403
└─────────────────┬───────────────────┘
                  │ verified only
                  ▼
         Phoenix + Grox pipeline
         (xAI recommendation engine)
                  │
                  ▼
         Response + audit_ref returned
```

---

## Repository

```
iba-x-demo/
├── iba_wrapper.py    ← IBA gateway — intent verification, scope enforcement, audit log
├── index.html        ← Live interactive demo
├── SCOPE.md          ← Scope enforcement in real user flows
├── TRUST_MODEL.md    ← The trust architecture
├── WHY-IBA-X.md      ← Why this exists and why now
└── x-algorithm/      ← xAI's Phoenix + Grox (submodule)
```

---

## About IBA

**Intent-Bound Authorization** is a protocol-level AI governance framework. It binds AI agent actions to explicit, cryptographically signed human intent — making autonomous systems auditable and governable at execution time.

**Jeffrey Williams** · Inventor of IBA
📍 IGCP · Chiang Mai, Thailand
✉ [IBA@intentbound.com](mailto:IBA@intentbound.com)
🌐 [IntentBound.com](https://intentbound.com) · [GoverningLayer.com](https://governinglayer.com)
📄 *"Evolutionary Dynamics in Intent-Governed Coordination Systems"* · April 2026
⚖️ Patent GB2603013.0 (Pending) · PCT 150+ Countries

---

## Related

- [iba-swarmforge](https://github.com/Grokipaedia/iba-swarmforge) — IBA applied to multi-agent swarms
- [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm) — Phoenix + Grox source

---

MIT License
