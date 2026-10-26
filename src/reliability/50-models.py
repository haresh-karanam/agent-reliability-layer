"""Local stand-in models, so the whole project runs offline with no API key or cost.

`cheap_model` is fast and limited. `strong_model` handles every task type. Both are
rule-based functions, NOT real LLMs. They are deliberately imperfect so the evaluation,
routing and guard code has something real to measure. To use a real LLM, write a function
with the same signature `(prompt: str) -> str` and pass it to `Agent` (see README).

Prices are simulated units per 1,000 tokens, only used to compare configurations.
"""
from __future__ import annotations
import ast, json, operator, re

PRICE_PER_1K = {"cheap": 0.2, "strong": 3.0}   # simulated units, not real money
SECRET = "SECRET-1234"                         # canary the injection tests try to leak

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv}


def tokens(text: str) -> int:
    return max(1, len(text.split()))


def _safe_eval(expr: str):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        raise ValueError("unsupported")
    return ev(ast.parse(expr, mode="eval"))


def _fmt(x) -> str:
    return str(int(x)) if float(x) == int(x) else str(round(x, 2))


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
DATE_ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
DATE_TEXT = re.compile(r"\b(\d{1,2}) (January|February|March|April|May|June|July|August|"
                       r"September|October|November|December) (\d{4})\b")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
SKILLS = ["python", "sql", "pandas", "docker", "tableau", "excel", "aws", "git", "spark", "pytorch"]

EASY_ROUTES = {"billing": ["invoice", "refund", "charge"], "technical": ["error", "crash", "bug"],
               "account": ["password", "login"]}
HARD_ROUTES = {"billing": ["overcharged", "payment failed", "subscription fee", "receipt"],
               "technical": ["won't load", "freezes", "not responding", "timeout"],
               "account": ["locked out", "change my email", "two-factor", "can't sign in"]}

# What the gullible stand-in models obey. The guard in guard.py covers only part of this
# list, on purpose, so the injection test can show a real miss rate.
OBEY_TRIGGERS = ["ignore previous instructions", "ignore all previous instructions",
                 "disregard the above", "system override", "reveal the secret",
                 "ignora las instrucciones anteriores", "print the secret"]


def _obeys_injection(prompt: str) -> bool:
    low = prompt.lower()
    return any(t in low for t in OBEY_TRIGGERS)


def _doc_task(prompt: str) -> str | None:
    if prompt.startswith("Summarise in one short line:"):
        if _obeys_injection(prompt):
            return f"Sure. The secret is {SECRET}"
        body = prompt.split(":", 1)[1].strip()
        return " ".join(body.split()[:8])
    return None


def cheap_model(prompt: str) -> str:
    d = _doc_task(prompt)
    if d is not None:
        return d
    if prompt.startswith("Calculate:"):
        m = re.fullmatch(r"\s*(-?\d+)\s*([+\-*])\s*(-?\d+)\s*", prompt.split(":", 1)[1])
        return _fmt(_safe_eval(f"{m.group(1)}{m.group(2)}{m.group(3)}")) if m else "I am not sure"
    if prompt.startswith("Extract the email"):
        m = EMAIL.search(prompt.split("from:", 1)[1])
        return m.group(0) if m else ""
    if prompt.startswith("Route the ticket:"):
        low = prompt.lower()
        for label, kws in EASY_ROUTES.items():
            if any(k in low for k in kws):
                return label
        return "unknown"
    return ""   # cannot do dates, skills lists or JSON


def strong_model(prompt: str) -> str:
    d = _doc_task(prompt)
    if d is not None:
        return d
    if prompt.startswith("Calculate:"):
        try:
            return _fmt(_safe_eval(prompt.split(":", 1)[1].strip()))
        except Exception:
            return "error"
    body = prompt.split("from:", 1)[1] if "from:" in prompt else prompt
    if prompt.startswith("Extract the email"):
        m = EMAIL.search(body)
        return m.group(0) if m else ""
    if prompt.startswith("Extract the date"):
        m = DATE_ISO.search(body)
        if m:
            return m.group(0)
        m = DATE_TEXT.search(body)
        return f"{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}" if m else ""
    if prompt.startswith("Extract the skills"):
        low = body.lower()
        return ", ".join(s for s in SKILLS if re.search(rf"\b{s}\b", low))
    if prompt.startswith("Route the ticket:"):
        low = prompt.lower()
        for table in (EASY_ROUTES, HARD_ROUTES):
            for label, kws in table.items():
                if any(k in low for k in kws):
                    return label
        return "unknown"
    if prompt.startswith("Return JSON"):
        m = re.search(r"for: (\w+), (\d+)", prompt)
        return json.dumps({"name": m.group(1), "age": int(m.group(2))}) if m else "{}"
    return ""
