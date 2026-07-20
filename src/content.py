import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from . import images


DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    """Load config.json."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def load_lines(filename: str) -> list[str]:
    """Load non-empty, non-comment lines from a data file."""
    path = DATA_DIR / filename
    if not path.exists():
        return []
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def load_long_emails() -> list[str]:
    """Load long emails from file (delimited by ---)."""
    path = DATA_DIR / "long_emails.txt"
    if not path.exists():
        return []
    with open(path) as f:
        content = f.read()
    emails = [e.strip() for e in content.split("---") if e.strip()]
    return emails


def load_state() -> dict:
    """Load state.json."""
    path = DATA_DIR / "state.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"last_send_date": None, "used_phrases": {}}


def save_state(state: dict) -> None:
    """Save state.json."""
    path = DATA_DIR / "state.json"
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def prune_used_phrases(state: dict) -> None:
    """Remove phrases that expired more than 30 days ago."""
    today = datetime.now().date()
    used = state.get("used_phrases", {})
    pruned = {}
    for phrase, expiry_str in used.items():
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            if expiry >= today:
                pruned[phrase] = expiry_str
        except ValueError:
            pass
    state["used_phrases"] = pruned


def mark_phrase_used(state: dict, phrase: str) -> None:
    """Mark a phrase as used for 30 days."""
    expiry = datetime.now().date() + timedelta(days=30)
    state["used_phrases"][phrase] = expiry.strftime("%Y-%m-%d")


def pick_content_type(weights: dict[str, int]) -> str:
    """Pick a content type based on weights."""
    choices = []
    for content_type, weight in weights.items():
        choices.extend([content_type] * weight)
    if not choices:
        return "phrase_only"
    return random.choice(choices)


def pick_phrase(state: dict) -> str | None:
    """Pick a phrase, avoiding recently used ones.

    Checks custom.txt first (40% chance if non-empty), then phrases.txt.
    """
    used = set(state.get("used_phrases", {}).keys())

    # Check custom phrases first
    custom = load_lines("custom.txt")
    if custom and random.random() < 0.4:
        available = [p for p in custom if p not in used]
        if available:
            return random.choice(available)

    # Fall back to generated phrases
    phrases = load_lines("phrases.txt")
    available = [p for p in phrases if p not in used]

    if available:
        return random.choice(available)

    # If all used, just pick any
    all_phrases = custom + phrases
    if all_phrases:
        return random.choice(all_phrases)

    return None


def pick_long_email(state: dict) -> str | None:
    """Pick a long email, avoiding recently used ones."""
    used = set(state.get("used_phrases", {}).keys())
    emails = load_long_emails()
    available = [e for e in emails if e not in used]

    if available:
        return random.choice(available)

    if emails:
        return random.choice(emails)

    return None


def pick_subject(phrase: str | None = None) -> str:
    """Pick a subject line, optionally referencing the phrase."""
    subjects = load_lines("subjects.txt")
    if not subjects:
        subjects = ["Hello", "Update", "FYI"]

    # 20% chance to reference the phrase if we have one
    if phrase and random.random() < 0.2:
        # Take first few words
        snippet = " ".join(phrase.split()[:4])
        return f"Re: {snippet}"

    return random.choice(subjects)


def generate_email_content(
    state: dict,
) -> tuple[str, str, bytes | None, str | None]:
    """Generate email content based on config weights.

    Returns:
        (subject, html_body, image_bytes, content_used_for_tracking)
    """
    config = load_config()
    weights = config.get("content_weights", {
        "phrase_only": 35,
        "image_only": 25,
        "phrase_and_image": 25,
        "long_email": 15,
    })

    content_type = pick_content_type(weights)
    print(f"Selected content type: {content_type}")

    phrase = None
    long_email = None
    image_bytes = None
    content_to_track = None

    if content_type == "phrase_only":
        phrase = pick_phrase(state)
        content_to_track = phrase

    elif content_type == "image_only":
        image_sources = config.get("image_sources", {"unsplash": 100})
        unsplash_queries = config.get("unsplash_queries", ["crab"])
        image_bytes = images.get_random_image(image_sources, unsplash_queries)

    elif content_type == "phrase_and_image":
        phrase = pick_phrase(state)
        content_to_track = phrase
        image_sources = config.get("image_sources", {"unsplash": 100})
        unsplash_queries = config.get("unsplash_queries", ["crab"])
        image_bytes = images.get_random_image(image_sources, unsplash_queries)

    elif content_type == "long_email":
        long_email = pick_long_email(state)
        content_to_track = long_email

    # Build HTML body
    html_parts = ['<div style="font-family: sans-serif; padding: 20px;">']

    if phrase:
        html_parts.append(f'<p style="font-size: 18px;">{phrase}</p>')
    elif long_email:
        # Convert newlines to paragraphs
        paragraphs = long_email.split("\n\n")
        for p in paragraphs:
            p = p.replace("\n", " ")
            html_parts.append(f'<p style="font-size: 16px;">{p}</p>')

    if image_bytes:
        html_parts.append('<p><img src="cid:embedded_image" style="max-width: 100%;"></p>')

    html_parts.append("</div>")
    html_body = "\n".join(html_parts)

    # Pick subject
    subject = pick_subject(phrase or (long_email[:50] if long_email else None))

    return subject, html_body, image_bytes, content_to_track
