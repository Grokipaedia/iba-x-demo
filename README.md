# iba-x-demo

**Run X's real "For You" recommendation algorithm (Phoenix + Grox) safely under IBA.**

- Official code: [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)
- Protected by **Intent-Bound Authorization (IBA)** — every major action requires your signed human intent.

### How to Set Up (Simple)

```bash
# 1. Clone this repo
git clone https://github.com/Grokipaedia/iba-x-demo.git
cd iba-x-demo

# 2. Clone the official x-algorithm (recommended)
git clone https://github.com/xai-org/x-algorithm.git x-algorithm

# 3. Go to the pipeline
cd x-algorithm/phoenix

# 4. Run it (see run-under-iba.md for IBA version)
uv run run_pipeline.py --help
