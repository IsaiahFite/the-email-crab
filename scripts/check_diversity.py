#!/usr/bin/env python3
"""Report lexical variety in the generated content files.

Pure local analysis, no API calls. Run after a regeneration to see whether the
prompt constraints actually held: the failure this catches is a batch that
collapses onto one opening template, which is invisible unless counted.

Always exits 0. Warnings are advisory so a bland batch never blocks the
monthly workflow from committing.
"""

import collections
import re
import sys
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"

# Share of a single opening word-pair above which a batch reads as repetitive.
OPENER_WARN_SHARE = 0.15
QUESTION_WARN_SHARE = 0.10

# Only forms detectable by exact string tests are reported. Sentence fragments
# would need real part-of-speech tagging to count: a word-list verb detector
# scores any unlisted verb as a fragment, which put the rate near 60% on a
# batch that had almost none. A wrong number is worse than a missing one.
IMPERATIVE_STARTS = {
    "do", "don't", "never", "always", "stop", "remember", "consider", "avoid",
    "count", "apologize", "return", "keep", "check", "ask", "tell", "watch",
    "leave", "take", "put", "hold", "listen", "look", "try", "let", "make",
    "give", "find", "bring", "call", "write", "read", "open", "close", "turn",
    "walk", "wait", "trust", "assume", "report", "file", "submit", "consult",
    "refer", "note", "beware", "mind", "please", "stay", "step", "begin",
}


def load_lines(filename: str) -> list[str]:
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def opener(text: str, words: int = 2) -> str:
    return " ".join(text.split()[:words]).rstrip(".,!?;:").lower()


def report_phrases() -> None:
    phrases = load_lines("phrases.txt")
    print("phrases.txt")
    if not phrases:
        print("  (empty or missing)")
        return

    total = len(phrases)
    unique = len(set(phrases))
    print(f"  {total} phrases, {unique} unique")
    if unique < total:
        print(f"  WARN: {total - unique} exact duplicate(s)")

    counts = collections.Counter(opener(p) for p in phrases)
    print("  most repeated openers:")
    for text, n in counts.most_common(5):
        flag = "  <-- WARN" if n / total > OPENER_WARN_SHARE else ""
        print(f"    {n:3}  {100 * n / total:5.1f}%  {text}...{flag}")

    questions = sum(1 for p in phrases if p.endswith("?"))
    second = sum(1 for p in phrases if re.search(r"\byou(r|rs)?\b", p, re.I))
    imperative = sum(
        1 for p in phrases if p.split()[0].rstrip(",.").lower() in IMPERATIVE_STARTS
    )

    print("  form coverage (categories overlap):")
    for label, n in [
        ("questions", questions),
        ("second person", second),
        ("imperatives", imperative),
    ]:
        print(f"    {label:15} {n:3}  {100 * n / total:5.1f}%")

    if questions / total < QUESTION_WARN_SHARE:
        print("  WARN: very few questions, batch is likely all declarative")


def report_emails() -> None:
    path = DATA_DIR / "long_emails.txt"
    print("\nlong_emails.txt")
    if not path.exists():
        print("  (missing)")
        return

    with open(path) as f:
        emails = [e.strip() for e in f.read().split("---") if e.strip()]
    if not emails:
        print("  (empty)")
        return

    total = len(emails)
    unique = len(set(emails))
    words = [len(e.split()) for e in emails]
    print(f"  {total} emails, {unique} unique")
    print(f"  words: min {min(words)}, mean {sum(words) // total}, max {max(words)}")
    if unique < total:
        print(f"  WARN: {total - unique} exact duplicate(s)")

    counts = collections.Counter(opener(e, words=3) for e in emails)
    repeated = [(t, n) for t, n in counts.most_common(3) if n > 1]
    if repeated:
        print("  repeated openings:")
        for text, n in repeated:
            print(f"    {n:3}  {text}...")
    else:
        print("  no repeated openings")


def main() -> int:
    report_phrases()
    report_emails()
    return 0


if __name__ == "__main__":
    sys.exit(main())
