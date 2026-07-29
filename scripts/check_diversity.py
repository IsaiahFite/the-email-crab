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

# The generator asks for 24 seed subjects at 2+ uses each. Warn a little under
# that so one or two the model couldn't place naturally isn't a red flag.
SEED_WARN_COUNT = 20

# Questions and second-person are exact string tests. Imperatives are not
# decidable without part-of-speech tagging, so they are approximated and
# labelled as such; sentence fragments are not reported at all.
#
# The approximation: a phrase opening with a word outside the closed classes
# below, followed by a determiner or preposition, is a bare verb in command
# position ("Bury the extension cord") rather than a plural subject with a
# finite verb ("Doorstops hold the only real elections"). Only closed-class
# words are enumerated here because those sets are finite and stable across
# batches; listing verbs instead scored 6 imperatives in a batch that had 15.
#
# Known error: noun-plus-prepositional-phrase fragments ("Mustard on the
# ledger, again") match the same shape and inflate the count by a couple.
NON_INITIAL = re.compile(
    r"^(the|a|an|every|all|some|most|no|my|your|his|her|their|our|its|i|you|he|"
    r"she|it|we|they|this|that|these|those|there|here|if|when|what|why|who|how|"
    r"where|in|on|at|for|by|with|from|under|over|between|after|before|inside|"
    r"just|nothing|someone|somebody|something|somewhere|anyone|everyone|nobody|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|forty|roughly|several|"
    r"warning|step|see)$",
    re.IGNORECASE,
)

DETERMINERS_AND_PREPS = {
    "the", "a", "an", "your", "its", "this", "that", "every", "all", "to",
    "for", "with", "over", "into", "through", "on", "at", "in", "up", "down",
    "out", "off", "toward", "against", "beneath", "beside", "around",
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


def looks_imperative(phrase: str) -> bool:
    """Approximate: see the note on NON_INITIAL for what this can and can't see."""
    if phrase.endswith("?"):
        return False
    words = [w.strip(",.;:").lower() for w in phrase.split()]
    if len(words) < 2 or NON_INITIAL.match(words[0]):
        return False
    return words[1] in DETERMINERS_AND_PREPS


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
    imperative = sum(1 for p in phrases if looks_imperative(p))

    print("  form coverage (categories overlap):")
    for label, n in [
        ("questions", questions),
        ("second person", second),
        ("imperatives ~", imperative),
    ]:
        print(f"    {label:15} {n:3}  {100 * n / total:5.1f}%")

    if questions / total < QUESTION_WARN_SHARE:
        print("  WARN: very few questions, batch is likely all declarative")

    report_seed_usage(phrases)


def report_seed_usage(phrases: list[str]) -> None:
    """How many seed subjects actually made it into the batch.

    Scans the whole pool rather than the run's sample: which nouns were drawn
    is only in the generator's log, not in any file this can read. A count of
    seeds present is a good enough health signal without that coupling.
    """
    seeds = load_lines("seed_nouns.txt")
    if not seeds:
        return

    text = "\n".join(phrases).lower()
    used = {
        seed: len(re.findall(rf"\b{re.escape(seed.lower())}s?\b", text))
        for seed in seeds
    }
    present = [s for s, n in used.items() if n]
    twice = [s for s, n in used.items() if n >= 2]

    print(f"  seed subjects: {len(present)} present, {len(twice)} used 2+ times")
    if len(twice) < SEED_WARN_COUNT:
        print(
            f"  WARN: under {SEED_WARN_COUNT} seeds used twice, "
            "the subject quota may be getting ignored"
        )


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
