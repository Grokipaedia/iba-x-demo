# IBA Scope Enforcement in Real User Flows

> How Intent-Bound Authorization controls what Phoenix + Grox can and cannot do.

---

## The problem scope solves

When you grant an AI system access to act on your behalf, you rarely mean *unlimited* access.

You mean: **do this specific thing, in this specific way, right now.**

Without scope enforcement, a recommendation agent that's been told to "show me posts I'd like" could silently re-rank, filter, promote, or suppress content beyond what you intended. IBA makes that impossible at the protocol layer.

---

## The four scopes

| Scope | What it permits | What it blocks |
|---|---|---|
| `RECOMMEND` | Retrieve and return candidate posts | Re-ranking, filtering, any write action |
| `RERANK` | Re-order an existing candidate set | New retrieval, filtering, any write action |
| `FILTER` | Remove candidates matching a predicate | Retrieval, re-ranking, any write action |
| `EXPLAIN` | Return scoring rationale for candidates | Any action that modifies the result set |

Each scope is **atomic**. An agent with `RECOMMEND` cannot also `RERANK` — even in the same request. Separate intent, separate token.

---

## Real user flows

### Flow 1 — Standard "For You" feed

```
User opens feed
    │
    ▼
Agent generates intent token
    scope: RECOMMEND
    signer: user@example.com
    ttl: 300s
    │
    ▼
IBA Gateway receives request + token
    ✓ signature valid
    ✓ scope: RECOMMEND — retrieval permitted
    ✓ not expired
    │
    ▼
Phoenix retrieves 48 candidates
    │
    ▼
Response returned — 10 posts shown
    │
    ▼
Audit log: intent_id, signer, scope, timestamp, result count
```

**What cannot happen:** The agent cannot silently pass results through Grox re-ranking. `RECOMMEND` does not cover `RERANK`. Separate action, separate intent required.

---

### Flow 2 — Agent tries to exceed its scope

```
Agent holds RECOMMEND token
    │
    ▼
Agent attempts to also re-rank results
    X-IBA-Intent: <RECOMMEND token>
    action: rerank
    │
    ▼
IBA Gateway intercepts
    ✓ signature valid
    ✓ not expired
    ✗ scope mismatch — RECOMMEND does not permit RERANK
    │
    ▼
403 Forbidden
    {"error": "Scope violation: RERANK requires explicit intent token"}
    │
    ▼
Blocked attempt logged — signer, scope requested, scope granted, timestamp
```

**The Phoenix pipeline is never reached.** The block happens at the gateway boundary.

---

### Flow 3 — Legitimate multi-step flow

User wants retrieval *and* re-ranking. Two actions, two tokens, two explicit intent declarations.

```
Step 1: User signs RECOMMEND intent
    token_A: scope=RECOMMEND, ttl=300s

Step 2: Phoenix retrieves 48 candidates
    → returns candidate_ids: [1, 4, 7, 12, ...]

Step 3: User signs RERANK intent
    token_B: scope=RERANK, ttl=60s
    (shorter TTL — re-ranking is a tighter action)

Step 4: Grox re-ranks candidate set
    → returns final 10

Step 5: Both actions logged separately
    intent_A: RECOMMEND — 48 candidates retrieved
    intent_B: RERANK   — 10 candidates finalised
```

**Full audit trail.** Every action has its own signed intent. Nothing is bundled silently.

---

### Flow 4 — Expired token mid-session

```
User granted RECOMMEND token at T+0 (TTL: 300s)
    │
    ▼
Request arrives at T+310s (10s after expiry)
    │
    ▼
IBA Gateway checks expiry
    ✗ token expired 10s ago
    │
    ▼
401 Unauthorized
    {"error": "Intent token expired — re-authorise to continue"}
    │
    ▼
Expired attempt logged
```

The user must explicitly re-authorise. The system cannot self-extend a token. **Intent cannot be assumed — only declared.**

---

## Why not just one broad token?

A single `DO_EVERYTHING` token defeats the purpose of IBA entirely.

Scope granularity is what makes intent *meaningful*. When you sign a `RECOMMEND` token you are declaring: *"I authorise retrieval of candidate posts. Nothing else."*

That declaration is:
- **Auditable** — logged with the exact scope you granted
- **Bounded** — expires, cannot be re-used beyond TTL
- **Non-transferable** — signed by you, verified against your identity

This is governance at the protocol layer — not a policy document, not a terms of service. A cryptographic constraint.

---

## Scope enforcement in `iba_wrapper.py`

```python
VALID_SCOPES = {"RECOMMEND", "RERANK", "FILTER", "EXPLAIN"}

def verify_token(encoded: str) -> tuple[bool, str, dict]:
    ...
    # Scope check — happens before Phoenix is touched
    if token["scope"] not in VALID_SCOPES:
        return False, f"Unknown scope: {token['scope']}", {}
    ...
```

The gateway enforces scope before the request reaches Phoenix. The pipeline never sees an unauthorised action.

---

## Coming next

- Composite scopes — declaring multi-step intent in a single signed token
- Scope delegation — agent A granting a sub-scope to agent B
- On-chain intent ledger — immutable audit trail beyond the session

---

*Jeffrey Williams · Inventor of IBA*
*IBA@intentbound.com · IntentBound.com · GoverningLayer.com*
*Patent GB2603013.0 (Pending) · PCT 150+ Countries*
