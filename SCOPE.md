# IBA Scope Enforcement in Real User Flows

> How Intent-Bound Authorization controls what Phoenix + Grox can and cannot do.

---

## The problem scope solves

When you grant an AI system access to act on your behalf, you rarely mean *unlimited* access.

You mean: **do this specific thing, in this specific way, right now.**

Without scope enforcement, a recommendation agent that's been told to "show me posts I'd like" could silently re-rank, filter, promote, or suppress content beyond what you intended. IBA makes that impossible at the protocol layer.

---

## The four scopes

| Scope | Endpoint | What it permits | What it blocks |
|---|---|---|---|
| `RECOMMEND` | `POST /recommend` | Retrieve and return candidate posts | Re-ranking, filtering, explaining — different endpoint, different token required |
| `RERANK` | `POST /rerank` | Re-order an existing candidate set | Retrieval, filtering, explaining |
| `FILTER` | `POST /filter` | Remove candidates matching an exclude list | Retrieval, re-ranking, explaining |
| `EXPLAIN` | `POST /explain` | Return scoring rationale for candidates | Any action that modifies the result set |

Each scope is **atomic** and mapped to exactly one endpoint. An agent with a `RECOMMEND` token cannot call `/rerank` — even with the same request pattern. Separate action, separate endpoint, separate token, verified by exact match.

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
IBA Gateway receives POST /recommend + token
    ✓ signature valid (ECDSA P-256)
    ✓ not expired
    ✓ scope RECOMMEND matches endpoint /recommend
    │
    ▼
Phoenix retrieves candidates (currently stubbed — see main README)
    │
    ▼
Response returned
    │
    ▼
Audit log: intent_id, signer, scope, timestamp, result count
```

---

### Flow 2 — Agent tries to exceed its scope

```
Agent holds RECOMMEND token
    │
    ▼
Agent attempts to call /rerank with it
    X-IBA-Intent: <RECOMMEND token>
    POST /rerank
    │
    ▼
IBA Gateway checks
    ✓ signature valid
    ✓ not expired
    ✗ scope mismatch — token scoped RECOMMEND, endpoint requires RERANK
    │
    ▼
403 Forbidden
    {"error": "Scope violation: RERANK requires an intent token scoped to
               RERANK, this token is scoped to RECOMMEND"}
    │
    ▼
Blocked attempt logged — signer, scope requested, scope granted, timestamp
```

**Verified directly**, not just described: a `/rerank` call with a `RECOMMEND` token returns 403 with exactly this message. The reverse (a `RERANK` token calling `/recommend`) is blocked the same way.

---

### Flow 3 — Legitimate multi-step flow

User wants retrieval *and* re-ranking. Two actions, two tokens, two explicit intent declarations, two different endpoints.

```
Step 1: User signs RECOMMEND intent
    token_A: scope=RECOMMEND, ttl=300s
    → POST /recommend → candidate_ids: [1, 2, 3, ..., 10]

Step 2: User signs RERANK intent
    token_B: scope=RERANK, ttl=60s
    (shorter TTL — re-ranking is a tighter action)
    → POST /rerank with token_B and the candidates from Step 1
    → returns reordered set

Step 3: Both actions logged separately
    intent_A: RECOMMEND — 10 candidates retrieved
    intent_B: RERANK    — 10 candidates reordered
```

Reranking in the current stub reverses the input order — deliberately, so it's visibly obvious the action actually ran rather than passing data through untouched.

`/filter` (exclude-list based) and `/explain` (per-candidate rationale) work the same way, each behind their own scope.

---

### Flow 4 — Expired token mid-session

```
User granted RECOMMEND token at T+0 (TTL: 300s)
    │
    ▼
Request arrives after expiry
    │
    ▼
IBA Gateway checks expiry
    ✗ token expired
    │
    ▼
401 Unauthorized
    {"error": "Token expired — re-authorise to continue"}
    │
    ▼
Expired attempt logged
```

401 here (not 403) is deliberate: an expired token is an *authentication* failure — the gateway doesn't have valid credentials to know who's asking. 403 is reserved for the case where authentication succeeded but the specific action isn't covered by what was granted (Flow 2). The user must explicitly re-authorise. The system cannot self-extend a token.

---

## Why not just one broad token?

A single `DO_EVERYTHING` token defeats the purpose of IBA entirely.

Scope granularity is what makes intent *meaningful*. When you sign a `RECOMMEND` token you are declaring: *"I authorise retrieval of candidate posts on `/recommend`. Nothing else, on no other endpoint."*

That declaration is:
- **Auditable** — logged with the exact scope you granted
- **Bounded** — expires, cannot be re-used beyond TTL
- **Non-transferable** — signed by you (ECDSA P-256), verified against your identity, not a shared secret

This is governance at the protocol layer — not a policy document, not a terms of service. A cryptographic constraint, enforced per-endpoint.

---

## Scope enforcement in `iba_wrapper.py`

```python
VALID_SCOPES = {"RECOMMEND", "RERANK", "FILTER", "EXPLAIN"}

def verify_token(encoded: str, required_scope: str) -> tuple[bool, str, dict, int]:
    ...
    # Authentication (401 territory): signature, trust, expiry all checked first.
    ...
    # Authorization (403 territory): does THIS certificate's declared scope
    # cover THIS specific endpoint being called? Not "is it any valid scope" —
    # an exact match against the endpoint actually being requested.
    if cert.declared_intent != required_scope:
        return False, f"Scope violation: {required_scope} requires an intent " \
                       f"token scoped to {required_scope}, this token is " \
                       f"scoped to {cert.declared_intent}", token_dict, 403
    ...
```

Four endpoints (`/recommend`, `/rerank`, `/filter`, `/explain`) each require a token scoped to exactly that action. A `RECOMMEND` token cannot call `/rerank`, and a `RERANK` token cannot call `/recommend` — verified directly, not just described.

---

## Coming next

- Composite scopes — declaring multi-step intent in a single signed token
- Scope delegation — agent A granting a sub-scope to agent B
- On-chain intent ledger — immutable audit trail beyond the session

---

*Jeffrey Williams · Inventor of IBA*
*IBA@intentbound.com · IntentBound.com*
*Patent GB2603013.0 (Pending) · PCT 150+ Countries*
