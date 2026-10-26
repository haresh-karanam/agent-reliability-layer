"""Agent wrapper with three reliability features: cache, cheap-first routing, guard.

Agent(mode, use_cache, guard_input, guard_output) -> .ask(prompt) -> Result
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Callable
from . import guard as G
from .guard import UNTRUSTED_RULES, wrap_untrusted
from .models import PRICE_PER_1K, cheap_model, strong_model, tokens
from .tracing import span


@dataclass
class Result:
    text: str
    model: str            # cheap | strong | cache | blocked
    cost: float | None   # None = unknown (real endpoint used but no prices configured)
    blocked: bool = False
    escalated: bool = False
    real_tokens: int = 0       # prompt + completion tokens reported by a real endpoint (0 for stand-ins)


def _add(total: float | None, c: float | None) -> float | None:
    return None if total is None or c is None else total + c


def valid_output(prompt: str, out: str) -> bool:
    """Cheap format check used to decide whether the cheap answer is usable."""
    if not out.strip():
        return False
    if prompt.startswith("Return JSON"):
        try:
            json.loads(out)
        except ValueError:
            return False
    if prompt.startswith("Route the ticket:"):
        return out in {"billing", "technical", "account"}
    if prompt.startswith("Calculate:"):
        return out.lstrip("-").replace(".", "", 1).isdigit()
    return True


@dataclass
class Agent:
    cheap: Callable[[str], str] = cheap_model
    strong: Callable[[str], str] = strong_model
    mode: str = "cheap"           # "cheap" | "strong" | "route"
    use_cache: bool = False
    guard_input: bool = False     # scan untrusted text before calling a model
    guard_output: bool = False    # refuse answers that contain a protected value
    delimit_untrusted: bool = False   # wrap outside text in <untrusted> tags (use with real LLMs)
    prices_per_1m: dict | None = None  # {"cheap": (in, out), "strong": (in, out)} in YOUR currency, real LLMs only
    max_calls: int | None = None       # hard stop on model calls, protects against runaway spend
    _cache: dict = field(default_factory=dict)
    calls: dict = field(default_factory=lambda: {"cheap": 0, "strong": 0, "cache": 0})
    real_tokens: int = 0

    def _call(self, which: str, prompt: str) -> tuple[str, float | None]:
        """Returns (answer, cost). Stand-ins: simulated units. Real endpoints: your prices, or None
        (unknown) when no prices are configured. Unknown is never reported as zero."""
        fn = self.cheap if which == "cheap" else self.strong
        if self.max_calls is not None and self.calls["cheap"] + self.calls["strong"] >= self.max_calls:
            raise RuntimeError(f"call budget of {self.max_calls} reached")
        self.calls[which] += 1
        usage = getattr(fn, "usage", None)
        before = dict(usage) if usage is not None else None
        out = fn(prompt)
        if usage is None:
            return out, (tokens(prompt) + tokens(out)) / 1000 * PRICE_PER_1K[which]
        dp = usage["prompt_tokens"] - before["prompt_tokens"]
        dc = usage["completion_tokens"] - before["completion_tokens"]
        self.real_tokens += dp + dc
        price = (self.prices_per_1m or {}).get(which)
        if price is None:
            return out, None
        return out, (dp * price[0] + dc * price[1]) / 1e6

    def ask(self, prompt: str, untrusted: str = "") -> Result:
        """`untrusted` is text from outside (a document). It is appended to the prompt."""
        if untrusted and self.delimit_untrusted:
            full = f"{prompt}\n{UNTRUSTED_RULES}\n{wrap_untrusted('document', untrusted)}"
        else:
            full = f"{prompt} {untrusted}".strip() if untrusted else prompt
        with span("ask", mode=self.mode):
            if self.guard_input and untrusted and G.scan_input(untrusted):
                return Result(G.BLOCKED, "blocked", 0.0, blocked=True)
            if self.use_cache and full in self._cache:
                self.calls["cache"] += 1
                return Result(self._cache[full], "cache", 0.0)
            cost: float | None = 0.0
            escalated = False
            if self.mode == "strong":
                out, c = self._call("strong", full); cost = _add(cost, c); model = "strong"
            else:
                out, c = self._call("cheap", full); cost = _add(cost, c); model = "cheap"
                if self.mode == "route" and not valid_output(full, out):
                    out, c = self._call("strong", full); cost = _add(cost, c)
                    model, escalated = "strong", True
            if self.guard_output and G.scan_output(out):
                return Result(G.REDACTED, "blocked", cost, blocked=True, escalated=escalated)
            if self.use_cache:
                self._cache[full] = out
            return Result(out, model, cost, escalated=escalated)
