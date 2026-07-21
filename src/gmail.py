import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


def send_email(
    recipients: list[str],
    subject: str,
    body_html: str,
    body_text: str | None = None,
    image_bytes: bytes | None = None,
    dry_run: bool = False,
) -> bool:
    """Send an email via Gmail SMTP.

    Args:
        recipients: List of email addresses (visible in To field)
        subject: Email subject line
        body_html: HTML body content
        body_text: Plain text fallback (auto-generated if not provided)
        image_bytes: Optional image to embed inline
        dry_run: If True, print email instead of sending

    Returns:
        True if sent successfully, False otherwise
    """
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GOOGLE_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        if dry_run:
            gmail_user = "test@example.com"
            gmail_password = "fake"
        else:
            print("ERROR: GMAIL_USER and GOOGLE_APP_PASSWORD must be set")
            return False

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)

    # Create alternative container for text/html
    msg_alt = MIMEMultipart("alternative")
    msg.attach(msg_alt)

    # Plain text fallback
    if body_text is None:
        # Strip HTML tags for plain text version
        import re
        body_text = re.sub(r"<[^>]+>", "", body_html)
        body_text = re.sub(r"\s+", " ", body_text).strip()

    msg_alt.attach(MIMEText(body_text, "plain"))
    msg_alt.attach(MIMEText(body_html, "html"))

    # Embed image if provided
    if image_bytes:
        img = MIMEImage(image_bytes)
        img.add_header("Content-ID", "<embedded_image>")
        img.add_header("Content-Disposition", "inline", filename="image.jpg")
        msg.attach(img)

    if dry_run:
        print("=" * 60)
        print("DRY RUN - Email would be sent:")
        print(f"From: {msg['From']}")
        print(f"To: {msg['To']}")
        print(f"Subject: {msg['Subject']}")
        print("-" * 60)
        print("HTML Body:")
        print(body_html[:500] + "..." if len(body_html) > 500 else body_html)
        print("-" * 60)
        if image_bytes:
            print(f"Image attached: {len(image_bytes)} bytes")
        print("=" * 60)
        return True

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, recipients, msg.as_string())
        print(f"Email sent to {len(recipients)} recipient(s)")
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed. Check GOOGLE_APP_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        print(f"ERROR: Failed to send email: {e}")
        return False


def get_recipients() -> list[str]:
    """Get recipient list from environment variable."""
    recipients_str = os.environ.get("RECIPIENTS", "")
    if not recipients_str:
        return []
    return [r.strip() for r in recipients_str.split(",") if r.strip()]
