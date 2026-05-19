# iba-x-demo

**Run X's real "For You" recommendation algorithm (Phoenix + Grox) safely under IBA.**

- Official code: [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)
- Protected by **Intent-Bound Authorization (IBA)** — every major action requires your signed human intent.

### Quick Setup

```bash
git clone https://github.com/Grokipaedia/iba-x-demo.git
cd iba-x-demo

git clone https://github.com/xai-org/x-algorithm.git x-algorithm

cd x-algorithm/phoenix
uv run run_pipeline.py --help
