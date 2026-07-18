# IBA Trust Model

> Trust in autonomous AI systems is not a feeling. It is a cryptographic proof.

---

## Core principle

An AI agent is trusted to perform an action **if and only if** a human has explicitly declared that intent, signed it, and the signature has been verified — immediately before execution.

Trust is not assumed from prior behaviour. Not inferred from training. Not delegated implicitly.

**It is declared. Signed. Verified. Logged.**

---

## Trust is not binary

Traditional access control asks: *does this entity have permission?*

IBA asks three questions simultaneously, verified for every request:

| Question | Mechanism |
|---|---|
| **Who** authorised this? | `principal` field, verified against a pinned trusted public key — not a name you can type in, a signature you cannot forge |
| **What** exactly was authorised? | `declared_intent`, checked for an exact match against the specific endpoint being called |
| **When** was it authorised? | `issued_at` + `hard_expiry_seconds`, enforced at verification |

All three must be satisfied. Any failure blocks execution.

*(An earlier version of this document listed a fourth, independent "why" dimension. In the current implementation, the declared purpose and the scope are the same field — there is no separate human-readable rationale captured beyond the scope name itself. If a genuinely separate "why" is wanted, that's a real schema addition, not something already present.)*

---

## The trust stack

```
┌─────────────────────────────────────────────────────┐
│                   HUMAN INTENT LAYER                │
│  Explicit declaration · Signed · Time-bounded       │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                  IBA VERIFICATION LAYER             │
│  Signature check · Scope validation · Expiry check  │
└──────────────────────────┬──────────────────────────┘
                           │ verified only
┌──────────────────────────▼──────────────────────────┐
│                   EXECUTION LAYER                   │
│  Phoenix + Grox pipeline (currently stubbed)        │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                    AUDIT LAYER                      │
│  Log · intent_id · signer · scope · result          │
└─────────────────────────────────────────────────────┘
```

The execution layer is only reachable through verified intent. There is no side door — tested directly by attempting to reach it with missing, expired, forged, and wrong-scope credentials; all four are rejected before the stub pipeline is ever called.

---

## Token anatomy

This is the actual structure, generated and printed directly from the real implementation — not an idealized example:

```json
{
  "agent_id": "G-0001",
  "principal": "jeffrey.williams",
  "declared_intent": "RECOMMEND",
  "scope": {"allowed_scope": "RECOMMEND"},
  "default_posture": "DENY_ALL",
  "hard_expiry_seconds": 300,
  "issued_at": 1784344714.0152059,
  "signature": "MEUCIQDJvWMcNZDO67Kgk+HTn86eqNYP2EtE0KfZnOEdl6cfgwIgKbLi8kmqKq8zeclYqpMy5jMFL+Lz7lYTI/lYRMQL010=",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
}
```

- **agent_id** — identifies the request, not globally tracked for replay prevention in the current implementation (a real replay-protection mechanism would need to track used `agent_id`s — not yet built)
- **principal** — human identity; verified against `public_key_pem`, not trusted just because the field says so
- **declared_intent** — the atomic action permitted, checked for an exact match against the specific endpoint
- **issued_at / hard_expiry_seconds** — hard time boundary, checked at every verification
- **signature** — real ECDSA P-256 (asymmetric), verified against the embedded `public_key_pem` before any action proceeds. The gateway additionally checks that public key against a separately pinned trusted key — an attacker who signs with their *own* keypair produces a validly-formed but untrusted token, correctly rejected.

---

## Scope is atomic

Scopes do not stack. `RECOMMEND` does not imply `RERANK`. An agent holding a `RECOMMEND` token that attempts a `RERANK` action is blocked — verified directly, not just described (see [SCOPE.md](SCOPE.md) for the full test results).

| Scope | Endpoint | Permits | Does not permit |
|---|---|---|---|
| `RECOMMEND` | `/recommend` | Candidate retrieval | Re-ranking, filtering, explaining |
| `RERANK` | `/rerank` | Re-ordering existing candidates | Retrieval, filtering, explaining |
| `FILTER` | `/filter` | Removing candidates by exclude-list | Retrieval, re-ranking, explaining |
| `EXPLAIN` | `/explain` | Returning scoring rationale | Any result modification |

If a workflow requires multiple actions, it requires multiple signed intents, each to its own endpoint. This is by design, and tested.

---

## Trust is not delegated silently — verified

The core claim: one agent's token cannot be reused to authorise a different action, and nothing can mint a new valid token without the trusted private key. Tested directly, three scenarios:

1. **A token scoped for one action, used for another** — blocked (403, scope mismatch).
2. **A "rogue" party signs its own new token with its own keypair**, attempting to act as though authorised — blocked (401, untrusted signer: the gateway only accepts the one pinned trusted public key, not any validly-formed signature).
3. **A genuine new human-signed token for the specific action** — succeeds.

This holds with the architecture as it exists today: one gateway, one trusted signer, four scoped endpoints. It does not require, and does not currently include, any orchestration hierarchy.

### What's still conceptual, not built

An earlier version of this document described a specific **Orchestrator Agent → Sub-Agent** hierarchy, with a dedicated `ORCHESTRATE` scope and multi-tier delegation. That's a reasonable design direction, but it does not exist in the current code — there's no `ORCHESTRATE` scope, no orchestrator concept, no sub-agent chaining logic. The general no-silent-delegation *property* above is real and tested; the specific multi-tier *architecture* pictured for it was aspirational. Building it for real is a separate, larger task — a genuine architecture decision (how many tiers, how scopes narrow at each level, whether sub-agents get their own keypairs or shared ones) worth deciding deliberately rather than something to bolt on quietly.

---

## What IBA trust is not

**Not role-based access control (RBAC)**
RBAC grants permissions to identities. IBA grants authorisation for specific actions at specific moments. An agent with RBAC permission to "recommend" can recommend any time, forever. An IBA token expires — 300 seconds by default in this implementation, configurable at issuance.

**Not OAuth**
OAuth delegates access to resources. IBA binds execution to declared human intent, checked per action rather than once at grant time.

**Not behavioural monitoring**
Monitoring observes what agents do, after the fact. IBA constrains what agents can do, before the action executes — verified by the fact that a blocked request never reaches the stub pipeline at all, not just that it gets flagged afterward.

---

## The audit trail as a trust artifact

Every verified IBA action produces a log entry. Real output, from an actual run:

```
[03:19:10] [VERIFIED] intent=42db9055... signer=jeffrey.williams scope=RECOMMEND
[03:19:10] [DELIVERED] intent=42db9055... signer=jeffrey.williams scope=RECOMMEND | RECOMMEND — 10 items
[03:19:10] [BLOCKED ] intent=42db9055... signer=- scope=- | Scope violation: FILTER requires an intent token scoped to FILTER, this token is scoped to RECOMMEND
```

*(Current limitation, stated plainly: this audit log is printed to console and held in memory for the life of the process — it is not yet a persistent or externally-anchored store. "Immutable" currently means "not editable by the running process once written," not "written to tamper-proof storage outside the process." A real persistent audit store is a roadmap item, not current state.)*

---

## Formal basis

*"Evolutionary Dynamics in Intent-Governed Coordination Systems"* — Jeffrey Williams, April 2026. Available on request: IBA@intentbound.com. This document itself has not been independently reviewed as part of the verification pass covering the rest of this material.

---

## Zero Trust for AI agents

The Zero Trust security model established one principle that changed enterprise security: **never trust, always verify.**

IBA applies that principle to autonomous AI systems at the execution layer, not the network layer — and, as of this pass, that application is actually demonstrated end-to-end, not just described.

---

*Jeffrey Williams · Inventor of IBA*
*Patent GB2603013.0 (Pending) · PCT 150+ Countries*
*IBA@intentbound.com · IntentBound.com*
