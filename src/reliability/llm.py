"""Optional LLM adapter for any OpenAI-compatible chat endpoint (OpenAI, Ollama, LM Studio, vLLM...).

Nothing here runs unless you configure it. No provider is assumed:

    export LLM_BASE_URL=http://localhost:11434/v1     # example: a local Ollama server
    export LLM_MODEL=<model name you have pulled>
    export LLM_API_KEY=<key, only if the endpoint needs one>

The key is read from the environment only. It is never printed, logged or stored.
Status: the request/response handling is tested against a fake HTTP server. It has NOT been
run against a real model in the environment this was written in.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
import httpx


class LLMConfigError(Exception):
    pass


class LLMError(Exception):
    pass


class LLMBudgetError(Exception):
    """Raised when the shared call limit is reached. Not caught by fallbacks or judges."""


class CallBudget:
    """One counter shared by every client in a run (agent calls, judge calls, everything)."""

    def __init__(self, limit: int):
        self.limit, self.used = limit, 0

    def take(self) -> None:
        if self.used >= self.limit:
            raise LLMBudgetError(f"call limit of {self.limit} reached")
        self.used += 1


@dataclass
class LLMClient:
    base_url: str
    model: str
    api_key: str = field(default="", repr=False)
    timeout: float = 60.0
    max_tokens: int = 400
    transport: object = None                    # tests pass an httpx.MockTransport
    budget: "CallBudget | None" = None          # shared call limit; checked before every request
    usage: dict = field(default_factory=lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})

    @classmethod
    def from_env(cls, prefix: str = "LLM", **kw) -> "LLMClient":
        base, model = os.environ.get(f"{prefix}_BASE_URL"), os.environ.get(f"{prefix}_MODEL")
        if not base or not model:
            raise LLMConfigError(f"set {prefix}_BASE_URL and {prefix}_MODEL (and {prefix}_API_KEY if needed)")
        return cls(base_url=base.rstrip("/"), model=model, api_key=os.environ.get(f"{prefix}_API_KEY", ""), **kw)

    def __call__(self, prompt: str, system: str | None = None) -> str:
        if self.budget is not None:
            self.budget.take()
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {"model": self.model, "messages": msgs, "temperature": 0, "max_tokens": self.max_tokens}
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as c:
                r = c.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"] or ""
        except httpx.HTTPStatusError as e:
            raise LLMError(f"LLM endpoint returned HTTP {e.response.status_code}") from None
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LLMError(f"LLM call failed: {type(e).__name__}") from None
        u = data.get("usage") or {}
        self.usage["calls"] += 1
        self.usage["prompt_tokens"] += int(u.get("prompt_tokens", 0))
        self.usage["completion_tokens"] += int(u.get("completion_tokens", 0))
        return text
