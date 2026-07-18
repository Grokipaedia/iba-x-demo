# IBA × X — Zero Trust for Autonomous AI Agents

> A reference implementation of Intent-Bound Authorization applied to a production AI system.

**xAI open-sourced X's recommendation engine. This wraps it so it cannot act without your explicit, cryptographically signed intent.**

Every action Phoenix takes requires a signed human intent token. No token → blocked. Wrong scope → blocked. Expired → blocked. Forged → blocked. Always.

---

## What this is

[xAI's Phoenix + Grox](https://github.com/xai-org/x-algorithm) is the real "For You" recommendation engine, open-sourced. This repository wraps every pipeline call in a signed intent certificate — so the algorithm cannot act without explicit human authorisation at the protocol layer.

Not a monitoring tool. Not a dashboard. Not a rate limiter.

A **trust primitive**: a gate that sits in front of the pipeline and only lets verified, in-scope, unexpired requests through.

---

## Quick start

```bash
# 1. Clone this repo and the X algorithm
git clone https://github.com/Grokipaedia/iba-x-demo.git && cd iba-x-demo
git clone https://github.com/xai-org/x-algorithm.git x-algorithm

# 2. Install the one real dependency
pip install cryptography

# 3. Start the IBA gateway (wraps Phoenix on :8080)
python iba_wrapper.py

# 4. Generate a signed intent token
python iba_wrapper.py --gen-token --signer "your.name" --scope RECOMMEND

# 5. Fire a governed recommendation request
curl -X POST http://localhost:8080/recommend \
  -H 'X-IBA-Intent: <paste token here>' \
  -H 'Content-Type: application/json' \
  -d '{"candidate_ids": [1,2,3,4,5,6,7,8,9,10]}'
```

**Current state, honestly:** steps 1–5 demonstrate the real governance gate — a genuine, cryptographically signed and verified request either passes or is blocked, with a real audit trail. The response content itself is currently a stub (`_call_phoenix()` returns simulated recommendation IDs), not a live call into the cloned `x-algorithm` pipeline. Wiring the gate to real Phoenix output is the next integration step, not yet done. The gate logic itself — the actual IBA contribution — is real and tested end-to-end.

---

## Without IBA vs with IBA

| Without IBA | With IBA |
|---|---|
| Algorithm runs autonomously | Every action requires a signed intent token |
| Side-effects are implicit | Side-effects declared before execution |
| Governance bolted on after | Governance at the protocol layer |
| No audit trail | Immutable intent ledger per request |
| Trust assumed | Trust cryptographically proven — real ECDSA P-256, private key signs, public key verifies |

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
│  1. Extract intent token             │
│  2. Verify ECDSA P-256 signature     │
│     (public key must match the      │
│      pinned trusted principal)       │
│  3. Check scope (RECOMMEND etc.)     │
│  4. Check expiry (TTL 300s)          │
│  5. Log to intent ledger             │
│                                     │
│  BLOCKED if any step fails ──────►  401/403
└─────────────────┬───────────────────┘
                  │ verified only
                  ▼
         Phoenix + Grox pipeline
         (xAI recommendation engine)
         — currently stubbed, see Quick Start
                  │
                  ▼
         Response + audit_ref returned
```

---

## Repository

```
iba-x-demo/
├── iba_wrapper.py    ← IBA gateway — intent verification, scope enforcement, audit log
├── iba_crypto.py      ← ECDSA P-256 signing and verification (required by iba_wrapper.py)
├── index.html         ← Live interactive demo
└── x-algorithm/       ← xAI's Phoenix + Grox (submodule)
```

---

## About IBA

**Intent-Bound Authorization** is a protocol-level AI governance framework. It binds AI agent actions to explicit, cryptographically signed human intent — making autonomous systems auditable and governable at execution time.

**Jeffrey Williams** · Inventor of IBA
📍 Chiang Mai, Thailand
✉ [IBA@intentbound.com](mailto:IBA@intentbound.com)
🌐 [IntentBound.com](https://intentbound.com)
⚖️ Patent GB2603013.0 (Pending) · UK IPO · PCT 150+ Countries

---

## Related

- [iba-swarmforge](https://github.com/Grokipaedia/iba-swarmforge) — IBA applied to multi-agent swarms, with measured performance data

---

Proprietary · © 2026 Jeffrey Williams · All rights reserved. Covered by Patent Application GB2603013.0 (pending). No reproduction, modification, or commercial use without written permission.
