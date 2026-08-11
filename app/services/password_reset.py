"""
Getting back into an account you cannot log into.

WHY THIS EXISTS
---------------
Passwords are stored as bcrypt hashes, which is a one-way function - not even
the person running the server can read them. That is the correct design, and it
means the only honest answer to "what is my password?" is "nobody knows". So
there has to be a way to set a NEW one without anybody reading the old one.

THE THREATS THIS IS BUILT AGAINST
---------------------------------
A reset flow is the softest part of most authentication systems, because it is
a deliberate bypass of the password. Four things have to hold:

  1. A token must be unguessable. 256 bits from `secrets`, not a uuid4, not a
     timestamp, not anything derived from the user.
  2. The database must not contain anything that can reset a password. Only a
     SHA-256 of the token is stored; the token itself lives in the email.
  3. A token must work exactly once, and not for long. Spent and expired are
     tracked separately so the user can be told which happened.
  4. Asking for a reset must not reveal whether an account exists. The endpoint
     answers identically either way - otherwise it becomes a way to test which
     of your friends signed up.

WHAT RESETTING DOES
-------------------
Sets the password, marks the token spent, and invalidates every other
outstanding token for that user. Someone who requested three resets while
confused should not leave two live tickets lying in their inbox.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.database import PasswordResetToken, User

logger = logging.getLogger(__name__)

# Long enough to walk to a laptop, short enough that a link left in an inbox
# stops being a key. Most services use somewhere between 15 minutes and a day.
TOKEN_LIFETIME = timedelta(minutes=45)

# 32 bytes -> 43 url-safe characters. Guessing one is not a realistic attack at
# this size, which is why no lockout or throttle is needed on the token itself.
TOKEN_BYTES = 32

# A ceiling on live tokens per account. Requesting a hundred resets should not
# fill the table, and it caps how many valid links can exist at once.
MAX_LIVE_TOKENS = 3

# The shortest password a reset may set. Matches registration.
MIN_PASSWORD_LENGTH = 6


def hash_token(token: str) -> str:
    """SHA-256 hex. See the module docstring for why this is not bcrypt."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create(db: Session, user: User, *, requested_from: Optional[str] = None,
           now: Optional[datetime] = None) -> str:
    """
    Mint a token, store only its hash, and return the token itself.

    The plain token is returned rather than stored because this is the single
    moment it can be known. If the caller loses it, it is gone - which is the
    property that makes a leaked database useless for resets.
    """
    now = now or datetime.utcnow()

    # Retire anything already outstanding beyond the cap, oldest first. Not a
    # security control so much as hygiene: several live links for one account
    # is confusing for the user and pointless for us.
    live = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now)
        .order_by(PasswordResetToken.created_at.asc())
        .all()
    )
    for stale in live[max(0, MAX_LIVE_TOKENS - 1):]:
        stale.used_at = now

    token = secrets.token_urlsafe(TOKEN_BYTES)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(token),
        created_at=now,
        expires_at=now + TOKEN_LIFETIME,
        requested_from=requested_from,
    ))
    db.commit()
    logger.info("Password reset requested for user %s", user.id)
    return token


def look_up(db: Session, token: str,
            now: Optional[datetime] = None) -> Tuple[Optional[PasswordResetToken], str]:
    """
    Find a token and say plainly what is wrong with it.

    Returns (row, reason). `reason` is empty when the token is good. The
    distinction between expired, already used, and never existed is surfaced to
    the user on purpose: all three send someone to the same place - request a
    new link - but only one of them suggests their account may be under attack.
    """
    now = now or datetime.utcnow()
    if not token or not token.strip():
        return None, "No reset token was supplied."

    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_token(token.strip()))
        .first()
    )
    if row is None:
        return None, "That reset link is not valid. Request a new one."
    if row.is_spent:
        return None, "That reset link has already been used. Request a new one."
    if row.is_expired(now):
        minutes = int(TOKEN_LIFETIME.total_seconds() // 60)
        return None, f"That reset link has expired - they last {minutes} minutes. Request a new one."
    return row, ""


def consume(db: Session, token: str, new_password: str,
            now: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Set the password, spend the token, and revoke every other one.

    The order matters. The token is marked used in the SAME transaction as the
    password change, so a crash between the two cannot leave a spent token with
    an unchanged password, or a changed password with a still-live token.
    """
    from app.auth import get_password_hash

    now = now or datetime.utcnow()

    if len(new_password or "") < MIN_PASSWORD_LENGTH:
        return False, f"Choose a password of at least {MIN_PASSWORD_LENGTH} characters."

    row, problem = look_up(db, token, now)
    if row is None:
        return False, problem

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        # The account was deleted between request and reset.
        row.used_at = now
        db.commit()
        return False, "That account no longer exists."

    user.hashed_password = get_password_hash(new_password)
    row.used_at = now

    # Every other outstanding link for this user dies too. Someone who clicked
    # "forgot password" three times has three emails; using one must not leave
    # the other two live in an inbox that may not be theirs any more.
    (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None))
        .update({PasswordResetToken.used_at: now}, synchronize_session=False)
    )

    db.commit()
    logger.info("Password reset completed for user %s", user.id)
    return True, "Your password has been changed. You can sign in with it now."


def purge_expired(db: Session, now: Optional[datetime] = None) -> int:
    """Housekeeping. Nothing depends on it; the table just need not grow forever."""
    now = now or datetime.utcnow()
    removed = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.expires_at < now - timedelta(days=7))
        .delete(synchronize_session=False)
    )
    db.commit()
    return removed


def email_body(*, name: str, link: str, minutes: int) -> Tuple[str, str]:
    """
    The message. Plain text and HTML.

    Deliberately boring. A reset email that shouts, uses urgency, or hides the
    destination behind a decorated button is indistinguishable from the
    phishing it will be mistaken for. The URL is shown in full so the reader
    can see where it goes before clicking.
    """
    import html as html_mod

    greeting = f"Hi {name}," if name else "Hi,"
    safe_name = html_mod.escape(name or "")
    safe_link = html_mod.escape(link)

    text = f"""{greeting}

Someone asked to reset the password on your Kayosha account.

Open this link to choose a new one:

{link}

The link works once and expires in {minutes} minutes.

If you did not ask for this, you can ignore this email - your password has
not changed, and nobody can use the link without opening it from your inbox.

- Kayosha
"""

    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;line-height:1.6;color:#1a1a1a;max-width:520px">
  <p>{'Hi ' + safe_name + ',' if safe_name else 'Hi,'}</p>
  <p>Someone asked to reset the password on your Kayosha account.</p>
  <p><a href="{safe_link}" style="color:#7c3aed">Choose a new password</a></p>
  <p style="font-size:13px;color:#555">
    Or paste this into your browser:<br>
    <span style="word-break:break-all">{safe_link}</span>
  </p>
  <p style="font-size:13px;color:#555">
    The link works once and expires in {minutes} minutes.
  </p>
  <p style="font-size:13px;color:#555">
    If you did not ask for this you can ignore this email. Your password has
    not changed.
  </p>
  <p style="font-size:13px;color:#888">- Kayosha</p>
</div>"""

    return text, html
