# IBA × X — Intent-Bound Authorization Demo

> Run xAI's real "For You" recommendation algorithm safely under IBA governance.

**Every major action requires your signed human intent. No silent side-effects.**

---

## What is this?

This demo wraps [xAI's open recommendation engine](https://github.com/xai-org/x-algorithm) (Phoenix + Grox) with **Intent-Bound Authorization (IBA)** — a governance protocol where AI actions are bound to explicit, signed human intent at the protocol level.

| Without IBA | With IBA |
|---|---|
| Algorithm runs autonomously | Every major action requires a signed intent token |
| Side-effects are implicit | Side-effects are declared and authorized |
| Governance bolted on after | Governance baked in by design |

---

## Quick Start

```bash
git clone https://github.com/Grokipaedia/iba-x-demo.git
cd iba-x-demo
git clone https://github.com/xai-org/x-algorithm.git x-algorithm
cd x-algorithm/phoenix
uv run run_pipeline.py --help
```

> **Note:** First run downloads the ~3GB mini Phoenix model.

---

## About IBA

Intent-Bound Authorization (IBA) is an AI governance protocol invented by **Jeffrey Williams**. It binds AI agent actions to cryptographically signed human intent — making AI systems auditable and controllable at the execution layer.

- 🌐 [IntentBound.com](https://intentbound.com)
- 🌐 [GoverningLayer.com](https://governinglayer.com)
- 📄 Working Paper: *"Evolutionary Dynamics in Intent-Governed Coordination Systems"* (April 2026)
- 📧 [IBA@intentbound.com](mailto:IBA@intentbound.com)
- 📍 IGCP Chiang Mai, Thailand
- ⚖️ Patent GB2603013.0 (Pending) · PCT 150+ Countries

---

## Related

- [iba-swarmforge](https://github.com/Grokipaedia/iba-swarmforge) — IBA applied to multi-agent swarms
- [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm) — The underlying Phoenix + Grox engine

---

*MIT License*
