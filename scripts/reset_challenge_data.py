#!/usr/bin/env python3
"""
Clear challenge and injury data left behind by testing.

The test suite creates injuries, check-ins and challenge outcomes against your
real account. Those rows are indistinguishable from genuine ones afterwards -
they award points, build streaks, and can complete a challenge you never
touched. This removes them so the screen reflects reality again.

    python scripts/reset_challenge_data.py --user you@example.com
    python scripts/reset_challenge_data.py --user you@example.com --injuries-too
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, YELLOW, DIM, RESET = "\033[92m", "\033[93m", "\033[2m", "\033[0m"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="email or username")
    ap.add_argument("--injuries-too", action="store_true",
                    help="also remove recorded injuries, not just challenge state")
    args = ap.parse_args()

    from app.database import (
        ChallengeOutcome, Injury, InjuryCheckIn, SessionLocal, User,
    )
    from app.models.enhanced_challenge_models import (
        PersonalizedChallenge, UserChallengeProgress,
    )

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter((User.email == args.user) | (User.username == args.user))
            .first()
        )
        if not user:
            print(f"{YELLOW}No user matching {args.user!r}.{RESET}")
            return 1

        print(f"\nClearing challenge data for {user.email}…")

        challenge_ids = [
            c.id for c in db.query(PersonalizedChallenge)
            .filter(PersonalizedChallenge.user_id == user.id).all()
        ]
        if challenge_ids:
            db.query(UserChallengeProgress).filter(
                UserChallengeProgress.challenge_id.in_(challenge_ids)
            ).delete(synchronize_session=False)

        counts = {
            "challenges": db.query(PersonalizedChallenge)
                .filter(PersonalizedChallenge.user_id == user.id)
                .delete(synchronize_session=False),
            "outcomes (points and streaks)": db.query(ChallengeOutcome)
                .filter(ChallengeOutcome.user_id == user.id)
                .delete(synchronize_session=False),
            "injury check-ins": db.query(InjuryCheckIn)
                .filter(InjuryCheckIn.user_id == user.id)
                .delete(synchronize_session=False),
        }

        if args.injuries_too:
            counts["injuries"] = (
                db.query(Injury).filter(Injury.user_id == user.id)
                .delete(synchronize_session=False)
            )
        else:
            print(f"{DIM}  Keeping recorded injuries. Pass --injuries-too to remove them.{RESET}")

        db.commit()

        for label, n in counts.items():
            print(f"  removed {n:>3}  {label}")

        print(f"\n{GREEN}Done.{RESET} Fresh challenges will be generated on your next visit.\n")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
