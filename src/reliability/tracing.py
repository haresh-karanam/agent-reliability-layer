"""Optional Langfuse tracing.

Off unless `langfuse` is installed AND LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set
(set LANGFUSE_HOST for a self-hosted server). Only metadata is sent (mode, model tier,
tokens, timing). Prompt and answer text are NOT sent.

Status: the Langfuse calls below follow the langfuse 4.x Python API and were run with fake
keys against an unreachable host, to check that nothing crashes. They have NOT been checked
against a real Langfuse server or dashboard. A tracing failure never breaks the agent.
"""
from __future__ import annotations
import os, time
from contextlib import contextmanager

EVENTS: list[dict] = []   # in-memory record, handy for tests and local debugging
_client = None
_tried = False


def _get_client():
    global _client, _tried
    if _tried:
        return _client
    _tried = True
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import Langfuse
            _client = Langfuse()
        except Exception:
            _client = None
    return _client


def reset_for_tests() -> None:
    global _client, _tried
    _client, _tried = None, False


@contextmanager
def span(name: str, **meta):
    t0 = time.perf_counter()
    rec = {"name": name, **meta}
    client = _get_client()
    cm = None
    if client is not None:
        try:
            cm = client.start_as_current_observation(name=name, as_type="span", metadata=dict(meta))
            cm.__enter__()
        except Exception:
            cm = None
    try:
        yield rec
    finally:
        rec["ms"] = round((time.perf_counter() - t0) * 1000, 3)
        EVENTS.append(rec)
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass
