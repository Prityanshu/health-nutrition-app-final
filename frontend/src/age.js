/**
 * Age from a birth date.
 *
 * WHY A BIRTH DATE AND NOT AN AGE
 * -------------------------------
 * Age is an input to the Mifflin-St Jeor BMR equation, which is where every
 * calorie and macro target in this app comes from. A number typed once is
 * correct on the day it was typed and wrong from the next birthday onwards -
 * so a stored age quietly biases those targets for as long as the account
 * exists. A date does not go stale.
 *
 * This mirrors `age_on` in app/database.py. The server is the authority; these
 * exist so the form can refuse an impossible date before a round trip, rather
 * than surfacing a Pydantic validation error nobody wants to read.
 */

/**
 * Parse "YYYY-MM-DD" into plain numbers.
 *
 * Deliberately NOT `new Date(iso)`. That parses a date-only string as UTC
 * midnight and then reads it back in local time, so anywhere west of UTC the
 * date comes out a day early - which would make someone a year older than
 * they are for one day around their birthday.
 */
function parts(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || '').trim());
  if (!match) return null;
  const [, y, m, d] = match.map(Number);
  if (m < 1 || m > 12 || d < 1 || d > 31) return null;
  // Round-trip through Date to reject the likes of 2025-02-30, which passes
  // the range check above but is not a day that exists.
  const probe = new Date(Date.UTC(y, m - 1, d));
  if (probe.getUTCFullYear() !== y || probe.getUTCMonth() !== m - 1
      || probe.getUTCDate() !== d) {
    return null;
  }
  return { y, m, d };
}

/**
 * Completed years between a birth date and today, or null if unparseable.
 *
 * Comparing (month, day) pairs handles the "has the birthday happened yet"
 * question in one step, and gets 29 February right for free: on 28 February of
 * a non-leap year, [2, 28] < [2, 29], so a leap-day birthday correctly has not
 * occurred yet.
 */
export function ageFrom(iso, today = new Date()) {
  const dob = parts(iso);
  if (!dob) return null;

  const ty = today.getFullYear();
  const tm = today.getMonth() + 1;
  const td = today.getDate();

  const hadBirthday = tm > dob.m || (tm === dob.m && td >= dob.d);
  const years = ty - dob.y - (hadBirthday ? 0 : 1);

  // A future date gives a negative age; the caller treats that as invalid.
  return years;
}

/** "YYYY-MM-DD" for exactly N years ago, for min/max on a date input. */
export function isoYearsAgo(years, today = new Date()) {
  const d = new Date(today.getFullYear() - years, today.getMonth(), today.getDate());
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
