#!/usr/bin/env python3
"""Generate absurdist phrases and long emails using Claude.

The prompt is rebuilt on every run rather than held constant. Current Claude
models reject temperature/top_p, so a fixed prompt produces near-identical
output month after month; the randomness has to come from the prompt itself.
Three things vary per run: the seed subjects, the sampled examples, and the
ban list derived from whatever is currently in data/.
"""

import collections
import os
import random
import sys
from pathlib import Path

import anthropic


DATA_DIR = Path(__file__).parent.parent / "data"

MODEL = "claude-opus-5"

# Thinking is on by default and is billed against max_tokens alongside the
# response text. At the default "high" effort this task spent an entire 8000
# token budget thinking and emitted no text at all, so effort is pinned down:
# writing absurdist one-liners is not a reasoning problem, and the only real
# bookkeeping is honoring the form quotas and seed coverage. Do not raise this
# to "high" without also raising max_tokens well past the values below.
EFFORT = "medium"

# Text alone is ~1200 tokens of phrases and ~2300 of emails; the rest is
# headroom for the reasoning pass. Unused headroom is not charged.
PHRASE_MAX_TOKENS = 12000
EMAIL_MAX_TOKENS = 16000

PHRASE_SEED_COUNT = 24
EMAIL_SEED_COUNT = 20
EXAMPLES_PER_RUN = 15
BANNED_OPENER_COUNT = 5

# Grouped by grammatical form because the sample is stratified across groups.
# Sample size is what controls variety *within* a batch: shown three examples
# the model treats them as the template and reproduces it, shown fifteen across
# fifteen forms it treats range itself as the pattern. Pool size controls
# variety *between* months. Both matter, so keep this list long and keep every
# bucket populated.
EXAMPLE_POOL = {
    "fake_wisdom": [
        "The wise crab knows which arguments to lose.",
        "A patient man never asks the escalator where it goes.",
        "Those who count their spoons will never sleep.",
        "The old proverb about lampshades turned out to be wrong.",
        "Wisdom is knowing the toaster remembers.",
        "The elders warned us about drop ceilings and we laughed.",
    ],
    "question": [
        "Do doors resent being held?",
        "What does a paperclip want?",
        "Has anyone checked on the gravel lately?",
        "Why does the hallway feel longer on Thursdays?",
        "Who authorized the fog?",
        "Is your thermostat telling you everything?",
    ],
    "imperative": [
        "Never trust a hallway that curves.",
        "Apologize to the appliance before unplugging it.",
        "Count the ceiling tiles again.",
        "Stop explaining yourself to the vending machine.",
        "Return the shopping cart or accept the consequences.",
        "Do not make eye contact with the self-checkout.",
    ],
    "second_person": [
        "Your coat has opinions about your other coats.",
        "You have been assigned a pigeon and it is disappointed.",
        "Everything in your junk drawer is waiting for you to leave.",
        "Your reflection has been arriving slightly late.",
        "You will be remembered chiefly by your doormat.",
        "Something in your refrigerator has been promoted.",
    ],
    "surreal_observation": [
        "Every cloud is just a shy mountain.",
        "All escalators lead to the same floor eventually.",
        "Fog is the sky forgetting its lines.",
        "Puddles are the ground practicing being a window.",
        "Static electricity is a grudge.",
        "The moon is mostly a rumor.",
    ],
    "mundane_conspiracy": [
        "The vending machine and the ATM are in regular contact.",
        "Somebody is moving the traffic cones at night.",
        "All the lost socks are in one specific building.",
        "The parking meters have unionized quietly.",
        "Someone has been editing the instruction manual.",
        "The fire hydrants are counting us.",
    ],
    "fragment": [
        "Just an entire drawer of unmatched batteries.",
        "Three hundred coat hangers and no explanation.",
        "A stapler, alone, in a field.",
        "Nothing but breadcrumbs and municipal silence.",
        "The specific hum of a laundromat at closing.",
        "One sock, load-bearing.",
    ],
    "confession": [
        "I have opinions about chairs.",
        "I have never trusted a colander.",
        "I said something unkind to a shopping cart once.",
        "I am not the person my houseplants think I am.",
        "I keep the warranty for a thing I no longer own.",
        "I have been lying about the thermostat.",
    ],
    "false_statistic": [
        "Roughly a third of all spoons are unaccounted for.",
        "Nine out of ten doorknobs report feeling underused.",
        "Most hallways are longer than they admit.",
        "Studies confirm that mud is getting worse.",
        "The average envelope contains one regret.",
        "Forty percent of all echoes are secondhand.",
    ],
    "instruction_manual": [
        "Step four: apologize to the appliance.",
        "Warning: contents may have already decided.",
        "If the fog persists, consult a different hallway.",
        "See figure 3 for the correct way to disappoint a stapler.",
        "Some assembly required, spiritually.",
        "Do not operate this device near a grudge.",
    ],
}


def load_lines(filename: str) -> list[str]:
    """Load non-empty, non-comment lines from a data file."""
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def load_long_emails() -> list[str]:
    """Load long emails from file (delimited by ---)."""
    path = DATA_DIR / "long_emails.txt"
    if not path.exists():
        return []
    with open(path) as f:
        return [e.strip() for e in f.read().split("---") if e.strip()]


def opener(text: str) -> str:
    """Normalized first two words, the unit both the ban list and caps use."""
    return " ".join(text.split()[:2]).rstrip(".,!?;:").lower()


def pick_examples(count: int, banned: list[str]) -> list[str]:
    """Sample examples spanning every form bucket, skipping banned openers.

    One per bucket before any random fill: an unstratified sample can land on
    fifteen declaratives, which is the failure this is meant to prevent.
    Examples are filtered against the ban list because the pool necessarily
    contains the templates that get banned once they take over a batch, and a
    prompt that bans an opener while demonstrating it contradicts itself.
    """
    blocked = set(banned)

    def allowed(bucket: list[str]) -> list[str]:
        # Fall back to the whole bucket rather than drop the form entirely.
        return [p for p in bucket if opener(p) not in blocked] or bucket

    picked = [random.choice(allowed(bucket)) for bucket in EXAMPLE_POOL.values()]
    if count > len(picked):
        remaining = [
            phrase
            for bucket in EXAMPLE_POOL.values()
            for phrase in allowed(bucket)
            if phrase not in picked
        ]
        picked.extend(
            random.sample(remaining, min(count - len(picked), len(remaining)))
        )
    random.shuffle(picked)
    return picked[:count]


def top_openers(phrases: list[str], count: int, min_count: int = 3) -> list[str]:
    """Opening word-pairs repeated enough to be worth banning next batch.

    The min_count floor matters: without it the list fills up with openers used
    once, spending ban slots on non-problems and needlessly ruling out forms.
    """
    openers = collections.Counter(
        opener(p) for p in phrases if len(p.split()) >= 2
    )
    return [
        text for text, n in openers.most_common(count) if n >= min_count
    ]


def build_phrases_prompt(
    seeds: list[str], examples: list[str], banned: list[str], existing: list[str]
) -> str:
    """Assemble the phrase-generation prompt for this run."""
    sections = [
        "Generate 100 absurdist, surreal, non-sequitur phrases.",
        "",
        "Grammatical form quotas. These are requirements, not suggestions:",
        "- 20 must be questions",
        "- 15 must be imperatives or commands",
        "- 10 must be sentence fragments with no main verb",
        '- 15 must address the reader as "you"',
        "- the remaining 40 are declarative statements",
        "",
        "Subjects. Each of these must appear in at least 2 phrases:",
        ", ".join(seeds),
        "",
        "Variety rules:",
        "- No more than 2 phrases may begin with the same two words.",
        "- Keep each phrase under 15 words.",
        "- Light on puns and dad jokes.",
    ]

    if banned:
        sections.append(
            "- Do not begin any phrase with: "
            + ", ".join(f'"{b}"' for b in banned)
        )

    sections += [
        "",
        "Format:",
        "- One phrase per line",
        "- No numbering, bullets, or quotation marks",
        "- Output only the phrases, with no preamble or commentary",
        "",
        "The following show the range of styles to cover. Match their variety, "
        "not their wording, and do not imitate any one of them closely:",
        "\n".join(examples),
    ]

    if existing:
        sections += [
            "",
            "Avoid these phrases and anything semantically close to them:",
            "\n".join(existing),
        ]

    return "\n".join(sections)


def build_emails_prompt(seeds: list[str], existing: list[str]) -> str:
    """Assemble the long-email generation prompt for this run."""
    sections = [
        "Generate 20 short absurdist emails of 2-4 paragraphs each.",
        "",
        "Subjects. Each of these must appear in at least one email:",
        ", ".join(seeds),
        "",
        "Style: stream of consciousness rambling, fake profundity about "
        "mundane things, ordinary observations taken far too seriously, "
        "conspiracy theories about ordinary objects, existential crises about "
        "trivia, and updates about nothing.",
        "",
        "Variety rules:",
        "- No more than 2 emails may open with the same first three words.",
        "- Vary the register across the batch: some frantic, some flat and "
        "bureaucratic, some overly formal, some resigned, some cheerful.",
        "- A few should end with a casual sign-off. Most should not.",
        "- Keep each email under 150 words.",
        "",
        "Format:",
        "- Separate each email with --- on its own line",
        "- No greeting lines and no signature lines, body text only",
        "- Output only the emails, with no preamble or commentary",
    ]

    if existing:
        sections += [
            "",
            "Avoid these emails and anything semantically close to them:",
            "\n---\n".join(existing),
        ]

    return "\n".join(sections)


def generate(client: anthropic.Anthropic, prompt: str, max_tokens: int) -> str:
    """Send one generation request and return the concatenated text blocks."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        output_config={"effort": EFFORT},
        messages=[{"role": "user", "content": prompt}],
    )

    blocks = collections.Counter(b.type for b in response.content)
    print(
        f"  {response.usage.input_tokens} in / "
        f"{response.usage.output_tokens} out tokens, "
        f"blocks: {dict(blocks)}, stop_reason: {response.stop_reason}"
    )
    if response.stop_reason == "max_tokens":
        print(f"  WARNING: hit max_tokens ({max_tokens}), output may be cut off")
    if not blocks.get("text"):
        print("  WARNING: no text block returned; budget likely spent thinking")

    parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(parts).strip()


def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        return 1

    seed_pool = load_lines("seed_nouns.txt")
    if not seed_pool:
        print("ERROR: data/seed_nouns.txt is missing or empty")
        return 1

    client = anthropic.Anthropic(api_key=api_key)
    existing_phrases = load_lines("phrases.txt")
    existing_emails = load_long_emails()

    banned = top_openers(existing_phrases, BANNED_OPENER_COUNT)
    if banned:
        print(f"Banning openers: {', '.join(banned)}")

    print(f"Generating phrases (model={MODEL}, effort={EFFORT})...")
    phrase_seeds = random.sample(seed_pool, PHRASE_SEED_COUNT)
    # Logged because the seeds are the run's main randomness source: without
    # them in the log there is no way to tell afterwards whether a bland batch
    # got bland subjects or ignored good ones.
    print(f"  seeds: {', '.join(phrase_seeds)}")
    phrases = generate(
        client,
        build_phrases_prompt(
            seeds=phrase_seeds,
            examples=pick_examples(EXAMPLES_PER_RUN, banned),
            banned=banned,
            existing=existing_phrases,
        ),
        PHRASE_MAX_TOKENS,
    )
    if not phrases:
        print("ERROR: phrase generation returned nothing, keeping existing file")
        return 1

    phrases_path = DATA_DIR / "phrases.txt"
    with open(phrases_path, "w") as f:
        f.write(phrases + "\n")
    print(f"Wrote {len(phrases.splitlines())} phrases to {phrases_path}")

    print("Generating long emails...")
    email_seeds = random.sample(seed_pool, EMAIL_SEED_COUNT)
    print(f"  seeds: {', '.join(email_seeds)}")
    long_emails = generate(
        client,
        build_emails_prompt(seeds=email_seeds, existing=existing_emails),
        EMAIL_MAX_TOKENS,
    )
    if not long_emails:
        print("ERROR: email generation returned nothing, keeping existing file")
        return 1

    emails_path = DATA_DIR / "long_emails.txt"
    with open(emails_path, "w") as f:
        f.write(long_emails + "\n")
    print(f"Wrote ~{long_emails.count('---') + 1} long emails to {emails_path}")

    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
