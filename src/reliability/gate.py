"""Regression gate: fail when accuracy drops 3 or more points below the stored baseline."""
from __future__ import annotations
import json, sys

MAX_DROP_POINTS = 3.0


def check(current_acc: float, baseline_acc: float, max_drop: float = MAX_DROP_POINTS) -> tuple[bool, str]:
    drop = (baseline_acc - current_acc) * 100
    if drop >= max_drop:
        return False, f"FAIL: accuracy {current_acc:.0%} is {drop:.1f} points below baseline {baseline_acc:.0%}"
    return True, f"ok: accuracy {current_acc:.0%} vs baseline {baseline_acc:.0%} (drop {max(drop, 0):.1f} points)"


def main(results_path: str, baseline_path: str, setup: str = "improved_route_cache") -> int:
    cur = json.load(open(results_path))["suite"][setup]["accuracy"]
    base = json.load(open(baseline_path))["accuracy"]
    ok, msg = check(cur, base)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
