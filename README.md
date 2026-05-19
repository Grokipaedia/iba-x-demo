# iba-x-demo

**Run X's real "For You" recommendation algorithm safely under IBA governance.**

- Official code from [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)
- Protected by **Intent-Bound Authorization (IBA)** — every major action needs your signed human intent.

### Current Status
- ✅ Repo cloned and ready
- ✅ IBA Desktop App ready
- 🔄 Running the full pipeline (Windows is tricky — WSL recommended)

### Super Simple Setup (when ready)

```bash
cd iba-x-demo
cd x-algorithm/phoenix
uv run run_pipeline.py --help
