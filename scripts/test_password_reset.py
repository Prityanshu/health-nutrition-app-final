#!/usr/bin/env python3
"""
Password reset: the security properties, not the happy path.

A reset flow is the softest part of most authentication systems, because it is
a deliberate, designed bypass of the password. The happy path is easy and not
very interesting. What matters is everything around it:

  * the database must not contain anything that can reset a password
  * a token must work once, briefly, and then never again
  * asking for a reset must not reveal whether an account exists
  * using one link must kill the others

Each of those is a way the feature could be quietly wrong while appearing to
work perfectly.

    python scripts/test_password_reset.py
"""

import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_DB = Path(tempfile.mkdtemp()) / "reset_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

GREEN, RED, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
)
passed = failed = 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        for line in str(detail).splitlines()[:8]:
            print(f"        {DIM}{line}{RESET}")


def fresh():
    from app.auth import get_password_hash
    from app.database import Base, PasswordResetToken, SessionLocal, User, engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(PasswordResetToken).delete()
    db.query(User).delete()
    db.commit()
    user = User(email="friend@example.com", username="friend",
                hashed_password=get_password_hash("original-password"),
                full_name="Test Friend", age=25, weight=75, height=178)
    db.add(user)
    db.commit()
    db.refresh(user)
    return db, user


# ---------------------------------------------------------------------------

def test_database_cannot_reset_anything():
    """The property that survives a stolen backup."""
    from app.database import PasswordResetToken
    from app.services import password_reset
    print(f"\n{BOLD}1. The stored row cannot be used to reset a password{RESET}")

    db, user = fresh()
    token = password_reset.create(db, user)
    row = db.query(PasswordResetToken).first()

    check("the plain token is nowhere in the row",
          token not in (row.token_hash or ""),
          f"token {token[:12]}... hash {row.token_hash[:12]}...")
    check("what is stored is a SHA-256 hex digest",
          re.fullmatch(r"[0-9a-f]{64}", row.token_hash) is not None, row.token_hash)
    check("...and it is the hash OF this token",
          row.token_hash == password_reset.hash_token(token))

    # The real test: can the stored value be used as a token?
    ok, _ = password_reset.consume(db, row.token_hash, "attacker-chosen")
    check("the stored hash is NOT accepted as a token", not ok,
          "a leaked table would otherwise be a master key")
    db.close()


def test_token_quality():
    from app.database import PasswordResetToken
    from app.services import password_reset
    print(f"\n{BOLD}2. Tokens are unguessable and unique{RESET}")

    db, user = fresh()
    tokens = {password_reset.create(db, user) for _ in range(25)}
    check("25 requests produce 25 distinct tokens", len(tokens) == 25, len(tokens))

    sample = next(iter(tokens))
    check(f"a token is long ({len(sample)} chars)", len(sample) >= 40, sample)
    check("...and url-safe", re.fullmatch(r"[A-Za-z0-9_-]+", sample) is not None, sample)
    check("no token contains the user id or email",
          not any(str(user.id) == t or user.email in t for t in tokens))

    stored = {r.token_hash for r in db.query(PasswordResetToken).all()}
    check("every stored hash is distinct too", len(stored) == 25, len(stored))
    db.close()


def test_single_use():
    from app.auth import verify_password
    from app.database import User
    from app.services import password_reset
    print(f"\n{BOLD}3. A link works exactly once{RESET}")

    db, user = fresh()
    token = password_reset.create(db, user)

    ok, message = password_reset.consume(db, token, "brand-new-password")
    check("the first use succeeds", ok, message)

    fresh_user = db.query(User).filter(User.id == user.id).first()
    check("the password actually changed",
          verify_password("brand-new-password", fresh_user.hashed_password))
    check("the old password no longer works",
          not verify_password("original-password", fresh_user.hashed_password))

    ok2, message2 = password_reset.consume(db, token, "third-password")
    check("the second use fails", not ok2, message2)
    check("...and says it was already used", "already been used" in message2, message2)

    fresh_user = db.query(User).filter(User.id == user.id).first()
    check("the replay did not change the password again",
          verify_password("brand-new-password", fresh_user.hashed_password))
    db.close()


def test_expiry():
    from app.services import password_reset
    print(f"\n{BOLD}4. A link expires{RESET}")

    db, user = fresh()
    token = password_reset.create(db, user)
    lifetime = password_reset.TOKEN_LIFETIME

    just_before = datetime.utcnow() + lifetime - timedelta(minutes=1)
    row, problem = password_reset.look_up(db, token, now=just_before)
    check("valid a minute before expiry", row is not None, problem)

    just_after = datetime.utcnow() + lifetime + timedelta(seconds=1)
    row, problem = password_reset.look_up(db, token, now=just_after)
    check("invalid a second after expiry", row is None, "still accepted")
    check("...and says so, with the lifetime", "expired" in problem, problem)

    ok, message = password_reset.consume(db, token, "too-late-password", now=just_after)
    check("an expired token cannot set a password", not ok, message)
    db.close()


def test_using_one_link_kills_the_others():
    from app.database import PasswordResetToken
    from app.services import password_reset
    print(f"\n{BOLD}5. Resetting invalidates every other outstanding link{RESET}")

    db, user = fresh()
    first = password_reset.create(db, user)
    second = password_reset.create(db, user)

    ok, _ = password_reset.consume(db, second, "chosen-password")
    check("the newest link works", ok)

    row, problem = password_reset.look_up(db, first)
    check("the earlier link is now dead", row is None, "an old email stayed live")
    check("...reported as used, not expired", "already been used" in problem, problem)

    live = db.query(PasswordResetToken).filter(
        PasswordResetToken.used_at.is_(None)).count()
    check("no live tokens remain for the account", live == 0, live)
    db.close()


def test_live_token_cap():
    from app.database import PasswordResetToken
    from app.services import password_reset
    print(f"\n{BOLD}6. Repeated requests do not pile up{RESET}")

    db, user = fresh()
    for _ in range(10):
        password_reset.create(db, user)

    live = db.query(PasswordResetToken).filter(
        PasswordResetToken.used_at.is_(None)).count()
    check(f"live tokens capped at {password_reset.MAX_LIVE_TOKENS}",
          live <= password_reset.MAX_LIVE_TOKENS, live)
    db.close()


def test_weak_passwords_refused():
    from app.services import password_reset
    print(f"\n{BOLD}7. A reset cannot set a trivial password{RESET}")

    db, user = fresh()
    token = password_reset.create(db, user)

    ok, message = password_reset.consume(db, token, "abc")
    check("a 3-character password is refused", not ok, message)
    check("...with the requirement stated", "at least" in message, message)

    row, _ = password_reset.look_up(db, token)
    check("the token survives a rejected attempt", row is not None,
          "otherwise a typo burns the link")
    db.close()


def test_garbage_tokens():
    from app.services import password_reset
    print(f"\n{BOLD}8. Nonsense is rejected cleanly{RESET}")

    db, user = fresh()
    for label, value in [("empty", ""), ("whitespace", "   "),
                         ("random", "not-a-real-token"),
                         ("sql-ish", "' OR 1=1 --"),
                         ("very long", "x" * 5000)]:
        ok, message = password_reset.consume(db, value, "some-password-123")
        check(f"{label} token refused", not ok, message)
    db.close()


def test_no_account_enumeration():
    """
    The endpoint must not reveal who has an account.

    Run through the real app, because this is a property of the ENDPOINT - the
    service layer legitimately knows the difference.
    """
    import asyncio
    import logging
    logging.disable(logging.CRITICAL)
    import httpx
    import main
    from app.database import SessionLocal, get_db

    print(f"\n{BOLD}9. Requesting a reset does not reveal who has an account{RESET}")

    db, user = fresh()

    # Stub the sender. Without this the suite reaches a real SMTP server with
    # real credentials, sends mail to an address invented for a test, and eats
    # the account's hourly quota. A test that has side effects outside itself
    # is not a test.
    from app.services import email_service
    sent = []
    real_send = email_service.send_email
    email_service.send_email = lambda **kw: (
        sent.append(kw), email_service.EmailResult(True, "stubbed"))[1]

    def _shared():
        yield db
    main.app.dependency_overrides[get_db] = _shared

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://t", timeout=30) as c:
            known = await c.post("/api/auth/forgot-password",
                                 json={"email": user.email})
            unknown = await c.post("/api/auth/forgot-password",
                                   json={"email": "nobody@example.com"})
            return known, unknown

    known, unknown = asyncio.run(run())

    check("both requests return the same status",
          known.status_code == unknown.status_code,
          f"{known.status_code} vs {unknown.status_code}")
    check("...and byte-identical bodies", known.text == unknown.text,
          f"{known.text}\n{unknown.text}")
    check("the reply does not confirm or deny an account",
          "if that address" in known.text.lower(), known.text)
    check("the reply never contains the token",
          "token" not in known.text.lower(), known.text)

    check("exactly one email was sent - to the real account only",
          len(sent) == 1, f"{len(sent)} sends")
    if sent:
        check("...addressed to the account owner",
              sent[0].get("to_email") == user.email, sent[0].get("to_email"))
        body = sent[0].get("body", "") + sent[0].get("html_body", "")
        check("...containing a reset link", "reset_token=" in body, body[:120])
        check("...and no password", "hashed" not in body.lower())

    email_service.send_email = real_send
    main.app.dependency_overrides.pop(get_db, None)
    logging.disable(logging.NOTSET)
    db.close()


def test_reset_endpoint_is_specific():
    """Unlike the request, the reset itself should say what went wrong."""
    import asyncio
    import logging
    logging.disable(logging.CRITICAL)
    import httpx
    import main
    from app.database import get_db
    from app.services import password_reset

    print(f"\n{BOLD}10. The reset endpoint explains failures{RESET}")

    db, user = fresh()
    token = password_reset.create(db, user)

    def _shared():
        yield db
    main.app.dependency_overrides[get_db] = _shared

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://t", timeout=30) as c:
            good_check = await c.get("/api/auth/reset-password/check",
                                     params={"token": token})
            bad_check = await c.get("/api/auth/reset-password/check",
                                    params={"token": "nope"})
            done = await c.post("/api/auth/reset-password",
                                json={"token": token, "new_password": "a-good-password"})
            replay = await c.post("/api/auth/reset-password",
                                  json={"token": token, "new_password": "another-one"})
            return good_check, bad_check, done, replay

    good_check, bad_check, done, replay = asyncio.run(run())

    check("a live token checks out", good_check.json().get("valid") is True, good_check.text)
    check("a bogus token does not", bad_check.json().get("valid") is False, bad_check.text)
    check("the reset succeeds", done.status_code == 200, done.text)
    check("the replay is rejected with 400", replay.status_code == 400, replay.status_code)
    check("...and names the reason",
          "already been used" in replay.text, replay.text)

    main.app.dependency_overrides.pop(get_db, None)
    logging.disable(logging.NOTSET)
    db.close()


def test_no_orphan_tests():
    print(f"\n{BOLD}11. No test is defined and then forgotten{RESET}")
    import inspect
    body = inspect.getsource(main_fn)
    defined = {n for n, o in globals().items()
               if n.startswith("test_") and inspect.isfunction(o)}
    missing = sorted(n for n in defined if f"{n}()" not in body)
    check(f"all {len(defined)} test functions are called", not missing, missing)


def main_fn():
    test_database_cannot_reset_anything()
    test_token_quality()
    test_single_use()
    test_expiry()
    test_using_one_link_kills_the_others()
    test_live_token_cap()
    test_weak_passwords_refused()
    test_garbage_tokens()
    test_no_account_enumeration()
    test_reset_endpoint_is_specific()
    test_no_orphan_tests()

    print(f"\n{BOLD}{'-' * 62}{RESET}")
    print(f"{GREEN}{passed} passed{RESET}, {RED if failed else DIM}{failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main_fn())
