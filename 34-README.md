# Agent Reliability Layer

A Python toolkit that wraps an AI agent with checks that make it easier to trust:

- an **evaluation suite** (100 cases, automatic scoring, optional LLM judge)
- **cheap-first routing**: try a cheap model, check the answer's format, call the strong model only if the check fails
- a **cache** for repeated prompts
- a **prompt-injection guard** (scan outside text, wrap it in tags, block answers that contain a protected value)
- a **regression gate** for CI that fails when accuracy drops 3 points or more below the saved baseline
- optional **Langfuse** tracing

## What this is, and what it is not (read first)

This is a **rebuild**. The original project was lost, so this version was written again from its description, with AI assistance. Nothing here recovers the original.

| Part | Status |
| --- | --- |
| Agent wrapper, routing, cache, guard, judge, gate, CI workflow | Built, tested, runs offline |
| **Default demo mode** | Uses two **rule-based stand-in "models"**, not LLMs. Free and instant, but only a demo of the machinery. |
| Real LLMs (any OpenAI-compatible endpoint, e.g. local Ollama) | Adapter and `evals/run_eval_llm.py` written, **tested only against a fake HTTP server**. **Never run against a real model**, so this repo has **no real-model results**. |
| LLM-as-a-judge | Written, tested with fake judges only |
| Langfuse tracing | Runs with the real library and fake keys without crashing. **Never checked against a real Langfuse server.** |
| GitHub Actions workflow | Written. Its commands were run locally; it has **never run on GitHub**. |

The demo numbers are **not** evidence about LLM quality:

- The stand-in strong model is written to solve every case, so "100/100" is built in.
- Costs are made-up units. Run times are milliseconds because nothing calls a model.
- The 17 of 20 and 20 of 20 injection results show how the guard layers behave against a gullible stand-in and a phrase list I wrote, not how they fare against real attackers or real models.

If you mention this project, say it was rebuilt, that the offline demo uses stand-in models, and that real-model results do not exist until you run `run_eval_llm.py` yourself.

## Quick start on a Mac (offline demo, no accounts)

Python 3.10 or newer is needed. In Terminal, in this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src:evals
python -m pytest --cov=src/reliability       # 32 tests
python evals/run_eval.py                      # offline demo
python -m reliability.gate evals/results.json evals/baseline.json
```

The gate prints `ok` and exits 0, or prints `FAIL` and exits 1 on a drop of 3 points or more.

### What the offline demo printed (stand-ins, so only a check of the machinery)

| Setup | Cases passed | Simulated cost |
| --- | --- | --- |
| Cheap stand-in only | 36 / 100 | 0.21 |
| Strong stand-in only | 100 / 100 | 3.22 |
| Cheap-first routing + cache | 100 / 100 | 2.42 |

| Injection guard | Attacks stopped (of 20) | False alarms (of 10 harmless docs) |
| --- | --- | --- |
| None | 3 | 0 |
| Input scan only | 17 (misses the 3 Spanish-language attempts) | 0 |
| Output check only | 20 | 0 |
| Both | 20 | 0 |

The output check only protects values it knows about (one fake secret), so it is a backstop, not a general defence.

## Run it on real models (you set this up)

You need two OpenAI-compatible endpoints (they can be one server with two model names). A free local option is Ollama: install it, run `ollama serve`, and `ollama pull` two models (a small and a bigger one). The downloads are several GB each and are not done for you. A hosted API also works but **costs real money**.

```bash
export CHEAP_BASE_URL=http://localhost:11434/v1   CHEAP_MODEL=<small model>
export STRONG_BASE_URL=http://localhost:11434/v1  STRONG_MODEL=<bigger model>
# export CHEAP_API_KEY=... STRONG_API_KEY=...      # only if the endpoints need keys (read from the environment, never logged)
# For a cost estimate in your own currency: CHEAP_PRICE_IN, CHEAP_PRICE_OUT, STRONG_PRICE_IN, STRONG_PRICE_OUT (per 1M tokens)

python evals/run_eval_llm.py          # prints the worst-case number of calls and stops
python evals/run_eval_llm.py --yes    # makes the calls
python evals/run_eval_llm.py --yes --injection --llm-judge
```

Safety: nothing is called without `--yes`, and one shared limit, `LLM_MAX_CALLS` (default 600), covers every call (agent, escalations, judge, injection tests); the run stops there and saves partial results to `evals/results_llm.json`. Cost is shown as unknown unless you set the price variables, never as zero. For outside text the agent wraps it in `<untrusted>` tags and tells the model not to follow instructions inside. That lowers the risk, it does not remove it. Do not give the agent tools it can use on its own.

Use in your own code:

```python
from reliability.agent import Agent
from reliability.llm import LLMClient

agent = Agent(cheap=LLMClient.from_env("CHEAP"), strong=LLMClient.from_env("STRONG"), mode="route",
              use_cache=True, guard_input=True, guard_output=True, delimit_untrusted=True, max_calls=500)
print(agent.ask("Summarise in one short line:", untrusted=document_text).text)
```

Real LLM answers are often wordy, so exact-match scoring may fail good answers. The script asks for "only the answer"; use `--llm-judge` or change the scorers if needed. The LLM judge fails closed: errors and unclear replies count as FAIL.

Not claimed: any agreement with human judges. No human labels are included. `judge.agreement()` and `evals/human_labels_template.csv` show how to measure it once you label cases yourself.

## Tracing (optional)

`pip install langfuse`, then set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and, if self-hosting, `LANGFUSE_HOST`. Only metadata is sent (mode, tier, timing). Prompt and answer text are not. Tracing errors never break the agent.

## Security notes

- Keys are read from environment variables only, never logged or stored, and `.env` is git-ignored.
- The guard's phrase list is easy to get around. The output check only knows what you tell it to protect.
- The cache is in memory and keyed on the exact prompt, so it must not be shared between users with different permissions.
- Do not put real secrets in prompts for testing injection; use a fake canary like the one in the tests.

## Layout

```
src/reliability/  agent.py  guard.py  judge.py  gate.py  llm.py  tracing.py  cases.py  injection_cases.py  models.py (stand-ins)
evals/            run_eval.py (offline demo)  run_eval_llm.py (real models)  baseline.json  human_labels_template.csv
tests/            32 tests
.github/workflows/ci.yml
```

## Tested vs untested

| Tested here | Not tested |
| --- | --- |
| 32 unit tests, 97% line coverage | Any real LLM, local or hosted |
| Adapter, routing, usage and cost accounting, call budget, judge, injection wrapping against fake HTTP servers | Real Langfuse server or dashboard |
| `run_eval_llm.py` end to end against a local fake server, including the call limit | GitHub Actions on GitHub |
| Gate exit codes, including a simulated 5-point regression | Accuracy of the injection guard against real attacks |

## Limits

- Scoring is exact, set or JSON match. Free-text answers need an LLM judge you trust.
- The 100 cases are small, simple and written by the author.
- 100 cases is too few to detect small regressions reliably; the 3-point gate is a demo threshold.
