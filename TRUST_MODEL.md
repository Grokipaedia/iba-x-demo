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

IBA asks four questions simultaneously:

| Question | Mechanism |
|---|---|
| **Who** authorised this? | Signer identity in intent token |
| **What** exactly was authorised? | Scope field — atomic, non-combinable |
| **When** was it authorised? | Issued-at + TTL enforced at verification |
| **Why** — for what declared purpose? | Intent payload, human-readable |

All four must be satisfied. Any failure blocks execution.

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
│  Phoenix + Grox · Any AI pipeline · Any agent       │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                    AUDIT LAYER                      │
│  Immutable log · intent_id · signer · scope · result│
└─────────────────────────────────────────────────────┘
```

The execution layer is only reachable through verified intent. There is no side door.

---

## Token anatomy

Every IBA intent token carries five verifiable fields:

```json
{
  "intent_id":  "f3a8b2c1-9d4e-4a1b-8c7f-2e5d6a3b1c0d",
  "signer":     "jeffrey.williams",
  "scope":      "RECOMMEND",
  "issued_at":  1748000000,
  "expires_at": 1748000300,
  "signature":  "a3f8d19c4b2e7f1a..."
}
```

- **intent_id** — globally unique, non-replayable
- **signer** — human identity, not agent identity
- **scope** — the atomic action permitted, nothing more
- **issued_at / expires_at** — hard time boundary, not soft guideline
- **signature** — HMAC-SHA256, verified before any action proceeds

---

## Scope is atomic

Scopes do not stack. `RECOMMEND` does not imply `RERANK`. An agent holding a `RECOMMEND` token that attempts a `RERANK` action is blocked — not warned, not logged-and-allowed. **Blocked.**

| Scope | Permits | Does not permit |
|---|---|---|
| `RECOMMEND` | Candidate retrieval | Re-ranking, filtering, writes |
| `RERANK` | Re-ordering existing candidates | New retrieval, filtering, writes |
| `FILTER` | Removing candidates by predicate | Retrieval, re-ranking, writes |
| `EXPLAIN` | Returning scoring rationale | Any result modification |

If a workflow requires multiple actions, it requires multiple signed intents. This is by design.

---

## Trust is not delegated silently

An agent cannot pass its trust to another agent without explicit human re-authorisation.

Agent A holding a `RECOMMEND` token cannot instruct Agent B to act under that token. Agent B requires its own signed intent token, issued by a human, for its specific action.

This eliminates a class of attack — **privilege escalation through agent chaining** — that no existing framework addresses.

---

## What IBA trust is not

**Not role-based access control (RBAC)**
RBAC grants permissions to identities. IBA grants authorisation for specific actions at specific moments. An agent with RBAC permission to "recommend" can recommend any time, forever. An IBA token expires in 300 seconds.

**Not OAuth**
OAuth delegates access to resources. IBA binds execution to declared human intent. The difference: OAuth says *you may access this*. IBA says *a human just told you to do this specific thing, right now*.

**Not behavioural monitoring**
Monitoring observes what agents do. IBA constrains what agents can do. Observation after the fact is not governance.

---

## The audit trail as a trust artifact

Every verified IBA action produces an immutable log entry:

```
[09:14:22] [VERIFIED ] intent=f3a8b2c1 signer=jeffrey.williams scope=RECOMMEND
[09:14:22] [DELIVERED] intent=f3a8b2c1 signer=jeffrey.williams scope=RECOMMEND | returned 10 items
```

```
[09:15:41] [BLOCKED  ] intent=none signer=- scope=- | No X-IBA-Intent header
```

The audit trail is not an afterthought. It is a natural output of the verification architecture — every transaction leaves a signed, timestamped, scope-tagged record.

This is what regulators mean when they require "demonstrable human oversight." Not a policy document. A cryptographic proof per action.

---

## Trust in multi-agent systems

In swarm architectures, trust propagation follows a strict hierarchy:

```
Human
  │
  │ signs intent (scope: ORCHESTRATE)
  ▼
Orchestrator Agent
  │
  │ cannot self-delegate — must request human re-authorisation
  │ for each sub-agent action scope
  ▼
Sub-Agent A          Sub-Agent B
(RECOMMEND token)    (FILTER token)
     │                    │
     ▼                    ▼
   Phoenix              Phoenix
```

No agent in the chain can act beyond its explicitly authorised scope. The human intent propagates downward — but only as far as explicitly declared.

Trust does not flow. It is re-established at each layer.

---

## Formal basis

The trust model is formalised in:

*"Evolutionary Dynamics in Intent-Governed Coordination Systems"*
Jeffrey Williams · April 2026

Available on request: IBA@intentbound.com

---

## Zero Trust for AI agents

The Zero Trust security model established one principle that changed enterprise security:

**Never trust, always verify.**

IBA applies that principle to autonomous AI systems — at the execution layer, not the network layer.

Every agent. Every action. Every time.

---

*Jeffrey Williams · Inventor of IBA*
*Patent GB2603013.0 (Pending) · PCT 150+ Countries*
*IBA@intentbound.com · IntentBound.com · GoverningLayer.com*
