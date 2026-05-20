# IBA × X — Intent-Bound Authorization

> xAI open-sourced X's recommendation algorithm. We put a governance layer on it.

**Every action Phoenix takes requires your signed human intent. No token → blocked.**

---

## The idea in one sentence

[xAI's Phoenix + Grox](https://github.com/xai-org/x-algorithm) is the real "For You" engine, open-sourced. IBA wraps every pipeline call in a cryptographically signed intent token — so the algorithm can't act without explicit human authorisation at the protocol level.

---

## Quick start

```bash
# 1. Clone this repo and the X algorithm
git clone https://github.com/Grokipaedia/iba-x-demo.git && cd iba-x-demo
git clone https://github.com/xai-org/x-algorithm.git x-algorithm

# 2. Start the IBA gateway (wraps Phoenix on :8080)
python iba_wrapper.py

# 3. Generate an IBA intent token
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
│  2. Verify HMAC signature           │
│  3. Check scope (RECOMMEND etc.)    │
│  4. Check expiry (TTL 300s)         │
│  5. Log to intent ledger            │
│                                     │
│  BLOCKED if any step fails ──────►  401/403
└─────────────────┬───────────────────┘
                  │ verified
                  ▼
         Phoenix + Grox pipeline
         (xAI recommendation engine)
                  │
                  ▼
         Response + audit_ref back to caller
```

---

## Intent token anatomy

```json
{
  "intent_id":  "f3a8b2c1-...",
  "signer":     "jeffrey.williams",
  "scope":      "RECOMMEND",
  "issued_at":  1748000000,
  "expires_at": 1748000300,
  "signature":  "a3f8d19c..."
}
```

Valid scopes: `RECOMMEND` · `RERANK` · `FILTER` · `EXPLAIN`

---

## About IBA

**Intent-Bound Authorization** is a protocol-level AI governance framework invented by **Jeffrey Williams**. It binds AI agent actions to explicit, cryptographically signed human intent — making AI systems governable at execution time, not just observable after the fact.

This is the first public implementation of IBA applied to a live recommender system.

**Jeffrey Williams** · Inventor of IBA  
📍 IGCP · Chiang Mai, Thailand  
✉ [IBA@intentbound.com](mailto:IBA@intentbound.com)  
🌐 [IntentBound.com](https://intentbound.com) · [GoverningLayer.com](https://governinglayer.com)  
📄 "Evolutionary Dynamics in Intent-Governed Coordination Systems" (April 2026)  
⚖️ Patent GB2603013.0 (Pending) · PCT 150+ Countries

---

MIT License
