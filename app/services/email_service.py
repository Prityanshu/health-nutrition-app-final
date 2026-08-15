"""
Outbound email.

Sent over Brevo's HTTPS API rather than raw SMTP. SMTP was the original
approach and is simpler, but it does not work from most PaaS hosts (Render
included) - they block outbound SMTP ports at the network level to stop the
platform being used as a spam relay, so the connection never even reaches
Gmail's servers. HTTPS on 443 is never blocked, which is the entire reason
for going through an API instead.

The pieces that matter for a web app rather than a script carry over
unchanged from the SMTP version:

  * credentials come from the environment, never the source file
  * absence of configuration is a normal state, not a crash - the rest of the
    app runs fine with email switched off
  * sending happens off the request thread, because the HTTP call takes real
    time and would otherwise block the API worker
  * failures are reported to the caller instead of printed

Only sending is implemented. The IMAP polling from the original script has no
use here: this app sends a plan when a user asks, it does not watch an inbox.
"""

import base64
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
# The address mail comes FROM. Has to be a sender verified in the Brevo
# account (Settings -> Senders) - Brevo rejects anything else, which is what
# stops this being usable as an open relay.
EMAIL_USER = os.getenv("EMAIL_USER", "").strip()
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Kayosha")

EMAIL_ENABLED = bool(BREVO_API_KEY and EMAIL_USER)

if not EMAIL_ENABLED:
    logger.info("Email is not configured (BREVO_API_KEY / EMAIL_USER unset) - sending disabled.")


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
    reply_to: Optional[str] = None,
) -> EmailResult:
    """
    Send one message, optionally with an attachment.

    `attachment` is (filename, content_bytes, mime_subtype). Bytes rather than a
    file path, because the PDFs here are generated in memory and never touch
    disk.

    `reply_to` should be the address of the person the message is really from -
    the user sharing their plan, not this service account. It gives the
    recipient somewhere useful to reply, and a message whose replies go to a
    real human is treated more favourably by spam filters than one from an
    unattended no-reply address.

    This blocks on the network. Callers inside async endpoints must run it in a
    worker thread.
    """
    if not EMAIL_ENABLED:
        return EmailResult(False, "Email is not configured on the server.")

    if not is_valid_email(to_email):
        return EmailResult(False, f"'{to_email}' does not look like an email address.")

    payload = {
        "sender": {"name": EMAIL_FROM_NAME, "email": EMAIL_USER},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }
    if html_body:
        payload["htmlContent"] = html_body

    # Only set when it is a different, valid address - pointing it back at the
    # sending account would be noise.
    if reply_to and is_valid_email(reply_to) and reply_to.lower() != EMAIL_USER.lower():
        payload["replyTo"] = {"email": reply_to}

    if attachment:
        filename, content, _subtype = attachment
        payload["attachment"] = [{
            "name": filename,
            "content": base64.b64encode(content).decode("ascii"),
        }]

    try:
        response = requests.post(
            BREVO_API_URL,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": BREVO_API_KEY,
            },
            json=payload,
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        logger.error("Email send failed: %s", e, exc_info=True)
        return EmailResult(False, "Could not reach the mail service. Try again shortly.")

    if response.status_code in (200, 201):
        logger.info("Email sent to %s: %s", to_email, subject)
        return EmailResult(True, f"Sent to {to_email}")

    # By far the most common failure: an invalid/revoked API key, or a
    # "from" address that has not been verified as a sender in Brevo.
    if response.status_code == 401:
        logger.error("Brevo rejected the API key")
        return EmailResult(
            False,
            "The mail service rejected the API key. Check BREVO_API_KEY on the server.",
        )

    logger.error("Brevo send failed (%s): %s", response.status_code, response.text)
    if response.status_code == 400:
        return EmailResult(
            False,
            f"The mail service rejected the request - is {EMAIL_USER!r} verified "
            "as a sender in Brevo?",
        )
    return EmailResult(False, "Could not send the email. Try again shortly.")


def status() -> dict:
    """Configuration state, for a health check or settings screen."""
    return {
        "enabled": EMAIL_ENABLED,
        "provider": "Brevo",
        # Never return the API key, and only a masked sender.
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
        "— Kayosha\n\n"
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
    <div style="color:#fff;font-size:19px;font-weight:700;">Kayosha</div>
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
