"""Builds the 100-case evaluation suite deterministically (no randomness).

30 arithmetic, 30 extraction, 20 ticket routing, 20 JSON formatting.
Only 2 prompts repeat, so the cache helps little here; it matters more on real traffic with many repeats.
"""
from __future__ import annotations
import json

NAMES = ["Ana", "Ben", "Chen", "Dev", "Esi", "Femi", "Gus", "Hana", "Ivan", "Jo",
         "Kai", "Lia", "Mo", "Nia", "Omar", "Pia", "Quin", "Raj", "Sia", "Tom"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def build() -> list[dict]:
    cs: list[dict] = []

    def add(kind, prompt, expected, scorer):
        cs.append({"id": f"C{len(cs) + 1:03d}", "type": kind, "prompt": prompt,
                   "expected": expected, "scorer": scorer})

    # arithmetic: 15 simple, 15 compound
    for i in range(15):
        a, b = 11 + i * 3, 7 + i * 2
        op = "+-*"[i % 3]
        add("arithmetic", f"Calculate: {a} {op} {b}", str(eval(f"{a}{op}{b}")), "exact")
    for i in range(15):
        a, b, c = 4 + i, 3 + i % 5, 2 + i % 4
        add("arithmetic", f"Calculate: ({a} + {b}) * {c} - {i}", str((a + b) * c - i), "exact")
    # extraction: 10 email, 10 date, 10 skills
    for i in range(10):
        n = NAMES[i].lower()
        add("extraction", f"Extract the email address from: Please write to {NAMES[i]} at "
            f"{n}.k{i}@example.com before Friday.", f"{n}.k{i}@example.com", "exact")
    for i in range(10):
        d, m, y = 2 + i * 2, i + 1, 2026
        txt = f"{d} {MONTHS[m - 1]} {y}" if i % 2 == 0 else f"{y}-{m:02d}-{d:02d}"
        add("extraction", f"Extract the date from: The review is on {txt}, room 4.",
            f"{y}-{m:02d}-{d:02d}", "exact")
    sk = ["python", "sql", "pandas", "docker", "tableau", "excel", "aws", "git", "spark", "pytorch"]
    for i in range(10):
        pick = [sk[i], sk[(i + 3) % 10], sk[(i + 6) % 10]]
        add("extraction", f"Extract the skills from: Experience with {pick[0].title()}, "
            f"{pick[1].upper()} and {pick[2]} in team projects.", pick, "set")
    # routing: 10 easy keywords, 10 harder phrasing
    easy = [("My invoice is wrong", "billing"), ("The app shows an error", "technical"),
            ("I forgot my password", "account"), ("I want a refund", "billing"),
            ("It started to crash daily", "technical"), ("Login page rejects me", "account"),
            ("Why was I charged twice", "billing"), ("Found a bug in export", "technical"),
            ("Password reset email never came", "account"), ("Refund for order 22", "billing")]
    hard = [("I was overcharged this month", "billing"), ("The dashboard won't load", "technical"),
            ("I am locked out of my profile", "account"), ("Where is my receipt", "billing"),
            ("The page freezes on save", "technical"), ("I need to change my email", "account"),
            ("My payment failed again", "billing"), ("The tool is not responding", "technical"),
            ("Two-factor codes do not arrive", "account"), ("Subscription fee looks high", "billing")]
    for t, lab in easy + hard:
        add("routing", f"Route the ticket: {t}", lab, "exact")
    # JSON formatting: 20, with 2 exact repeats of earlier prompts at the end of the suite
    for i in range(18):
        add("json", f"Return JSON with name and age for: {NAMES[i]}, {20 + i}",
            {"name": NAMES[i], "age": 20 + i}, "json")
    for j in (0, 1):                          # repeats of two JSON prompts
        c = cs[-18 + j]
        add("json", c["prompt"], c["expected"], "json")
    assert len(cs) == 100, len(cs)
    return cs


def write(path: str) -> None:
    open(path, "w").write(json.dumps(build(), indent=1))
