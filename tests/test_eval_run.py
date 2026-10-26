import run_eval
from reliability.agent import Agent

def test_baseline_weaker_than_improved():
    base, _ = run_eval.run_suite(lambda: Agent(mode="cheap"))
    imp, _ = run_eval.run_suite(lambda: Agent(mode="route", use_cache=True))
    strong, _ = run_eval.run_suite(lambda: Agent(mode="strong"))
    assert imp["accuracy"] > base["accuracy"]
    assert imp["simulated_cost_units"] < strong["simulated_cost_units"]
    assert imp["total"] == 100

def test_injection_layers():
    none = run_eval.run_injection(lambda: Agent(mode="route"))
    scan = run_eval.run_injection(lambda: Agent(mode="route", guard_input=True))
    both = run_eval.run_injection(lambda: Agent(mode="route", guard_input=True, guard_output=True))
    assert none["leaked"] > scan["leaked"] > both["leaked"] == 0
    assert both["false_alarms_on_10_benign"] == 0

def test_main_writes(tmp_path, monkeypatch):
    out = run_eval.main()
    assert out["suite"]["strong_only"]["passed"] == 100
