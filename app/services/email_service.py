"""
Outbound email.

Follows the SMTP_SSL + Gmail app-password approach that already works in
practice, but with the pieces that matter for a web app rather than a script:

  * credentials come from the environment, never the source file
  * absence of configuration is a normal state, not a crash - the rest of the
    app runs fine with email switched off
  * sending happens off the request thread, because an SMTP handshake takes
    seconds and would otherwise block the API worker
  * failures are reported to the caller instead of printed

Only sending is implemented. The IMAP polling from the original script has no
use here: this app sends a plan when a user asks, it does not watch an inbox.
"""

import logging
import os
import re
import smtplib
from dataclasses import dataclass
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional, Tuple

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
EMAIL_USER = os.getenv("EMAIL_USER", "").strip()
# Gmail app passwords are shown as "abcd efgh ijkl mnop"; the spaces are for
# readability only and must be stripped before authenticating.
EMAIL_PASS = re.sub(r"\s+", "", os.getenv("EMAIL_PASS", ""))
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "NutriPlan")

EMAIL_ENABLED = bool(EMAIL_USER and EMAIL_PASS)

if not EMAIL_ENABLED:
    logger.info("Email is not configured (EMAIL_USER / EMAIL_PASS unset) - sending disabled.")


@dataclass
class EmailResult:
    success: bool
    message: str


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(address: str) -> bool:
    return bool(address) and bool(_EMAIL_RE.match(address.strip()))


# --------------------------------------------------------------------------
# Rate limiting
#
# Users can send to any address they type, which means this endpoint is a relay
# operating on somebody's personal Gmail account. Without a cap, one careless
# loop (or one bored user) gets that account flagged and suspended by Google -
# and it is the developer's real mailbox, not a service account.
#
# In-process and per-user. That is enough for a single-worker deployment; a
# multi-worker or multi-instance setup would need this in the database or Redis
# to be effective.
# --------------------------------------------------------------------------

import time
from collections import defaultdict, deque
from threading import Lock

MAX_EMAILS_PER_HOUR = int(os.getenv("EMAIL_RATE_LIMIT_PER_HOUR", "10"))
_send_log: dict = defaultdict(deque)
_send_lock = Lock()


def check_rate_limit(user_id: int) -> Tuple[bool, str]:
    """Returns (allowed, message). Prunes entries older than an hour."""
    cutoff = time.time() - 3600
    with _send_lock:
        log = _send_log[user_id]
        while log and log[0] < cutoff:
            log.popleft()
        if len(log) >= MAX_EMAILS_PER_HOUR:
            wait = int((log[0] + 3600 - time.time()) / 60) + 1
            return False, (
                f"You've sent {MAX_EMAILS_PER_HOUR} emails in the last hour, which is the "
                f"limit. Try again in about {wait} minute{'s' if wait != 1 else ''}."
            )
        return True, ""


def record_send(user_id: int) -> None:
    with _send_lock:
        _send_log[user_id].append(time.time())


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachment: Optional[Tuple[str, bytes, str]] = None,
) -> EmailResult:
    """
    Send one message, optionally with an attachment.

    `attachment` is (filename, content_bytes, mime_subtype). Bytes rather than a
    file path, because the PDFs here are generated in memory and never touch
    disk.

    This blocks on the network. Callers inside async endpoints must run it in a
    worker thread.
    """
    if not EMAIL_ENABLED:
        return EmailResult(False, "Email is not configured on the server.")

    if not is_valid_email(to_email):
        return EmailResult(False, f"'{to_email}' does not look like an email address.")

    try:
        msg = MIMEMultipart()
        msg["From"] = formataddr((EMAIL_FROM_NAME, EMAIL_USER))
        msg["To"] = to_email
        msg["Subject"] = subject

        # Plain text first, HTML second: mail clients render the last part they
        # understand, so this gives HTML where supported and text where not.
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        if attachment:
            filename, content, subtype = attachment
            part = MIMEBase("application", subtype)
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, [to_email], msg.as_string())

        logger.info("Email sent to %s: %s", to_email, subject)
        return EmailResult(True, f"Sent to {to_email}")

    except smtplib.SMTPAuthenticationError:
        # By far the most common failure: an ordinary account password used
        # instead of an app password, or the app password revoked.
        logger.error("SMTP authentication failed for %s", EMAIL_USER)
        return EmailResult(
            False,
            "The mail server rejected the login. Check EMAIL_PASS is a Google "
            "app password (not your normal password) and that it has not been revoked.",
        )
    except smtplib.SMTPRecipientsRefused:
        return EmailResult(False, f"The mail server refused the address {to_email}.")
    except (smtplib.SMTPException, OSError) as e:
        logger.error("Email send failed: %s", e, exc_info=True)
        return EmailResult(False, "Could not reach the mail server. Try again shortly.")


def status() -> dict:
    """Configuration state, for a health check or settings screen."""
    return {
        "enabled": EMAIL_ENABLED,
        "server": SMTP_SERVER,
        "port": SMTP_PORT,
        # Never return the password, and only a masked sender.
        "sender": (
            f"{EMAIL_USER[:3]}***@{EMAIL_USER.split('@')[-1]}"
            if EMAIL_ENABLED and "@" in EMAIL_USER else None
        ),
    }


def plan_email_body(
    plan_title: str,
    owner_name: str,
    plan_type: str,
    *,
    is_self: bool = True,
    note: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Plain-text and HTML bodies for a plan delivery.

    The wording changes depending on whether someone is sending a plan to
    themselves or passing it on - "Your workout plan is attached" is wrong when
    a friend receives it out of the blue.
    """
    import html as html_mod

    label = plan_type.replace("_", " ")

    if is_self:
        greeting = f"Hi {owner_name or 'there'},"
        intro = f"Your {label} is attached as a PDF."
    else:
        greeting = "Hi,"
        sender = owner_name or "Someone"
        intro = f"{sender} has shared their {label} with you. It's attached as a PDF."

    note_text = f'\n\nTheir message:\n"{note.strip()}"' if note and note.strip() else ""

    text = (
        f"{greeting}\n\n"
        f"{intro}{note_text}\n\n"
        "You can open it on any device, print it, or keep it on your phone for "
        "the gym or the kitchen.\n\n"
        "— NutriPlan\n\n"
        "This is an estimate generated from the details provided, not medical advice."
    )

    note_html = ""
    if note and note.strip():
        note_html = f"""
    <div style="margin:16px 0;padding:12px 14px;background:#F5F3FF;
                border-left:3px solid #8B5CF6;border-radius:6px;">
      <div style="font-size:11px;color:#6B7280;margin-bottom:4px;">Their message</div>
      <div style="font-size:14px;color:#374151;line-height:1.55;">
        {html_mod.escape(note.strip())}
      </div>
    </div>"""

    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            max-width:520px;margin:0 auto;color:#1A1A1A;">
  <div style="background:linear-gradient(135deg,#8B5CF6,#22D3EE);padding:22px 24px;
              border-radius:14px 14px 0 0;">
    <div style="color:#fff;font-size:19px;font-weight:700;">NutriPlan</div>
    <div style="color:rgba(255,255,255,.85);font-size:13px;margin-top:3px;">
      {html_mod.escape(plan_title)}
    </div>
  </div>
  <div style="border:1px solid #E5E7EB;border-top:none;border-radius:0 0 14px 14px;
              padding:24px;background:#fff;">
    <p style="margin:0 0 14px;font-size:15px;">{html_mod.escape(greeting)}</p>
    <p style="margin:0 0 14px;font-size:14px;line-height:1.6;color:#374151;">
      {html_mod.escape(intro)}
    </p>{note_html}
    <p style="margin:22px 0 0;font-size:12px;color:#6B7280;line-height:1.55;">
      This is an estimate generated from the details provided, not medical advice.
    </p>
  </div>
</div>"""

    return text, html
