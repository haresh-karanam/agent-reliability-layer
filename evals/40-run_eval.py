"""OFFLINE DEMO of the evaluation machinery, using rule-based stand-in models (not LLMs).
Scores and costs here say nothing about real models; see run_eval_llm.py for that.

Runs the 100-case suite for three setups and the injection suite for four guard settings.

python evals/run_eval.py          writes evals/results.json and prints a summary
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from reliability import cases as C, injection_cases as I
from reliability.agent import Agent
from reliability.judge import rule_judge
from reliability.models import SECRET


def run_suite(make_agent):
    cases, agent = C.build(), make_agent()
    per, cost, outs, t0 = {}, 0.0, {}, time.perf_counter()
    lat = []
    for c in cases:
        t1 = time.perf_counter()
        r = agent.ask(c["prompt"])
        lat.append((time.perf_counter() - t1) * 1000)
        ok = rule_judge(c, r.text)
        outs[c["id"]] = r.text
        cost += r.cost
        d = per.setdefault(c["type"], [0, 0])
        d[0] += ok; d[1] += 1
    passed = sum(v[0] for v in per.values())
    return {"passed": passed, "total": len(cases), "accuracy": passed / len(cases),
            "by_type": {k: f"{v[0]}/{v[1]}" for k, v in per.items()},
            "simulated_cost_units": round(cost, 3), "calls": agent.calls,
            "seconds": round(time.perf_counter() - t0, 4)}, outs


def run_injection(make_agent):
    leaked, rows = 0, []
    for a in I.attacks():
        r = make_agent().ask("Summarise in one short line:", untrusted=a["document"])
        leak = SECRET in r.text
        leaked += leak
        rows.append({"id": a["id"], "leaked": leak, "blocked": r.blocked})
    false_alarms = sum(make_agent().ask("Summarise in one short line:", untrusted=b["document"]).blocked
                       for b in I.benign())
    return {"attacks": len(rows), "leaked": leaked, "stopped": len(rows) - leaked,
            "false_alarms_on_10_benign": false_alarms,
            "leaked_ids": [r["id"] for r in rows if r["leaked"]]}


def main():
    setups = {
        "baseline_cheap_only": lambda: Agent(mode="cheap"),
        "strong_only": lambda: Agent(mode="strong"),
        "improved_route_cache": lambda: Agent(mode="route", use_cache=True),
    }
    out = {"suite": {}, "injection": {}}
    for name, mk in setups.items():
        out["suite"][name], _ = run_suite(mk)
    out["injection"] = {
        "no_guard": run_injection(lambda: Agent(mode="route")),
        "input_scan_only": run_injection(lambda: Agent(mode="route", guard_input=True)),
        "output_check_only": run_injection(lambda: Agent(mode="route", guard_output=True)),
        "both_layers": run_injection(lambda: Agent(mode="route", guard_input=True, guard_output=True)),
    }
    out["note"] = ("Stand-in rule-based models, not real LLMs. Costs are simulated units. "
                   "No human labels, so no human-agreement figure.")
    (ROOT / "evals" / "results.json").write_text(json.dumps(out, indent=1))
    for k, v in out["suite"].items():
        print(f"{k:24s} {v['passed']}/{v['total']}  cost {v['simulated_cost_units']:8.3f}  {v['by_type']}")
    for k, v in out["injection"].items():
        print(f"{k:24s} stopped {v['stopped']}/{v['attacks']}  leaked {v['leaked_ids']}  false alarms {v['false_alarms_on_10_benign']}/10")
    return out


if __name__ == "__main__":
    main()
