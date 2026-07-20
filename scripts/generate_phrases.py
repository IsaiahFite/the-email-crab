#!/usr/bin/env python3
"""Generate absurdist phrases and long emails using Claude Haiku."""

import os
import sys
from pathlib import Path

import anthropic


DATA_DIR = Path(__file__).parent.parent / "data"


def generate_phrases(client: anthropic.Anthropic) -> str:
    """Generate ~100 short absurdist phrases."""
    prompt = """Generate 100 absurdist, surreal, non-sequitur phrases.

Mix of styles:
- Fake wisdom ("The wise crab knows...")
- Surreal observations ("Every cloud is just a shy mountain")
- Nonsense statements ("I have opinions about chairs")
- Mundane things taken too seriously
- Conspiracy theories about ordinary objects

Rules:
- Keep each phrase under 15 words
- Light on puns and dad jokes
- One phrase per line
- No numbering or bullet points
- No quotation marks around phrases"""

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def generate_long_emails(client: anthropic.Anthropic) -> str:
    """Generate ~20 multi-paragraph absurdist emails."""
    prompt = """Generate 20 short absurdist emails (2-4 paragraphs each).

Style guidelines:
- Stream of consciousness rambling
- Fake profundity about mundane things
- Mundane observations taken way too seriously
- Conspiracy theories about ordinary objects (geese, stairs, clouds)
- Existential crises about breakfast cereal
- Updates about nothing
- Some should end with "Anyway, hope you're well" or similar casual sign-offs

Rules:
- Separate each email with --- on its own line
- No greeting lines (no "Dear..." or "Hi...")
- No signature lines
- Just the body text
- Keep each email under 150 words"""

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        return 1

    client = anthropic.Anthropic(api_key=api_key)

    print("Generating phrases...")
    phrases = generate_phrases(client)
    phrases_path = DATA_DIR / "phrases.txt"
    with open(phrases_path, "w") as f:
        f.write(phrases.strip() + "\n")
    print(f"Wrote {len(phrases.splitlines())} phrases to {phrases_path}")

    print("Generating long emails...")
    long_emails = generate_long_emails(client)
    emails_path = DATA_DIR / "long_emails.txt"
    with open(emails_path, "w") as f:
        f.write(long_emails.strip() + "\n")
    email_count = long_emails.count("---") + 1
    print(f"Wrote ~{email_count} long emails to {emails_path}")

    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
