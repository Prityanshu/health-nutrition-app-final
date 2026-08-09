/**
 * The user's day, on the client.
 *
 * `new Date().toISOString().split('T')[0]` looks like "today" and is not. It
 * is the UTC date. For anyone east of Greenwich it flips early and for anyone
 * west it flips late - in IST the dashboard asked for yesterday's totals until
 * 05:30 in the morning, which is exactly the "day doesn't reset at midnight"
 * symptom.
 *
 * Everything here works off the browser's own clock, which is the user's.
 */

/** Today as YYYY-MM-DD in the user's timezone. Never toISOString(). */
export const localDateString = (date = new Date()) => {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

/** The browser's IANA timezone, e.g. "Asia/Kolkata". */
export const browserTimezone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
};

/** Milliseconds until the next local midnight. */
export const msUntilLocalMidnight = (now = new Date()) => {
  const midnight = new Date(now);
  midnight.setHours(24, 0, 0, 0);
  return Math.max(0, midnight - now);
};

/**
 * Run `onRollover` the moment the local day changes, and every day after.
 *
 * A single setTimeout for 24h would drift and, more importantly, would not
 * fire at all if the machine slept through midnight - which is the common
 * case for a laptop. So this re-arms after each fire, and also checks on wake
 * and on tab focus, when the timer may have been throttled or skipped
 * entirely. Returns a cleanup function.
 */
export const onLocalDayChange = (onRollover) => {
  let currentDay = localDateString();
  let timer = null;

  const fireIfChanged = () => {
    const today = localDateString();
    if (today !== currentDay) {
      currentDay = today;
      onRollover(today);
    }
  };

  const arm = () => {
    clearTimeout(timer);
    // One extra second so we land just past the boundary rather than on it,
    // where rounding can leave the date still reading as yesterday.
    timer = setTimeout(() => {
      fireIfChanged();
      arm();
    }, msUntilLocalMidnight() + 1000);
  };

  const onVisible = () => {
    if (document.visibilityState === 'visible') {
      fireIfChanged();
      arm();
    }
  };

  arm();
  document.addEventListener('visibilitychange', onVisible);
  window.addEventListener('focus', fireIfChanged);

  return () => {
    clearTimeout(timer);
    document.removeEventListener('visibilitychange', onVisible);
    window.removeEventListener('focus', fireIfChanged);
  };
};

/**
 * Tell the backend which timezone we are in.
 *
 * Called on load rather than only at login: existing accounts predate the
 * field, and people travel. Best-effort - a failure here just means the
 * server falls back to APP_TIMEZONE.
 */
export const syncTimezone = async (apiBase) => {
  const timezone = browserTimezone();
  const token = localStorage.getItem('token');
  if (!timezone || !token) return null;
  try {
    const res = await fetch(`${apiBase}/auth/timezone`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ timezone }),
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
};
