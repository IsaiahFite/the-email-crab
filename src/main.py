import os
import random
import sys
from datetime import datetime

from . import content
from . import gmail


def should_send_today(state: dict) -> bool:
    """Determine if we should send an email today.

    Logic:
    - If never sent: send
    - If sent today (0 days): skip
    - If 4+ days since last send: must send
    - If 1-3 days: weighted random (70%, 80%, 90%)
    """
    last_send = state.get("last_send_date")
    if not last_send:
        print("No previous send, will send today")
        return True

    try:
        last_date = datetime.strptime(last_send, "%Y-%m-%d").date()
    except ValueError:
        print(f"Invalid last_send_date: {last_send}, will send today")
        return True

    today = datetime.now().date()
    days_since = (today - last_date).days

    if days_since == 0:
        print("Already sent today, skipping")
        return False

    if days_since >= 4:
        print(f"{days_since} days since last send, must send today")
        return True

    # 1-3 days: increasing probability
    probability = 0.6 + (days_since * 0.1)  # 70%, 80%, 90%
    roll = random.random()
    should = roll < probability
    print(
        f"{days_since} day(s) since last send, "
        f"probability={probability:.0%}, roll={roll:.2f}, "
        f"{'sending' if should else 'skipping'}"
    )
    return should


def run() -> int:
    """Main entry point. Returns exit code."""
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run:
        print("DRY RUN MODE - No emails will be sent")

    # Load state
    state = content.load_state()
    content.prune_used_phrases(state)

    # Check if we should send
    if not should_send_today(state):
        content.save_state(state)  # Save pruned state
        return 0

    # Get recipients
    recipients = gmail.get_recipients()
    if not recipients and not dry_run:
        print("ERROR: No recipients configured (set RECIPIENTS env var)")
        return 1

    if not recipients:
        recipients = ["test@example.com"]

    print(f"Recipients: {recipients}")

    # Generate content
    subject, html_body, image_bytes, content_to_track = (
        content.generate_email_content(state)
    )

    print(f"Subject: {subject}")

    # Send email
    success = gmail.send_email(
        recipients=recipients,
        subject=subject,
        body_html=html_body,
        image_bytes=image_bytes,
        dry_run=dry_run,
    )

    if success:
        # Update state
        state["last_send_date"] = datetime.now().date().strftime("%Y-%m-%d")
        if content_to_track:
            content.mark_phrase_used(state, content_to_track)
        content.save_state(state)
        print("State updated")
        return 0
    else:
        print("Email send failed")
        return 1


def main() -> None:
    """Entry point for python -m src.main"""
    sys.exit(run())


if __name__ == "__main__":
    main()
