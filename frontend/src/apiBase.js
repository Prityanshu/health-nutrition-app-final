/**
 * Where the backend lives.
 *
 * WHY THIS IS NOT JUST AN ENV VAR
 * -------------------------------
 * On the web the API is on the same machine, so a build-time constant is fine.
 * In an APK it is not: the address is baked in at build time, and it changes
 * constantly during testing -
 *
 *   - a laptop's LAN IP changes with every network and every DHCP lease
 *   - a free tunnel gives a new URL on each restart
 *   - a friend testing from their house needs a different address entirely
 *
 * With a baked-in URL, every one of those means a rebuild, a re-install, and
 * re-sending the APK to whoever is testing. So the address is resolved at
 * runtime and can be changed from inside the app.
 *
 * Resolution order, first hit wins:
 *   1. what the user set in the app (localStorage)
 *   2. REACT_APP_API_URL at build time
 *   3. localhost, for running in a desktop browser
 */

const STORAGE_KEY = 'nutriplan.apiBase';

const BUILD_TIME = process.env.REACT_APP_API_URL || '';
const WEB_DEFAULT = 'http://localhost:8001/api';

/** True when running inside the Capacitor shell rather than a browser tab. */
export const isNativeApp = () =>
  typeof window !== 'undefined' &&
  Boolean(window.Capacitor?.isNativePlatform?.());

/**
 * Normalise whatever the user typed into something fetchable.
 *
 * People type "192.168.1.5", "192.168.1.5:8001", or paste a URL with a
 * trailing slash. All three should work rather than failing with a network
 * error that looks like the server is down.
 */
export const normaliseBase = (raw) => {
  let value = String(raw || '').trim();
  if (!value) return '';

  if (!/^https?:\/\//i.test(value)) value = `http://${value}`;
  value = value.replace(/\/+$/, '');

  // A bare host with no port almost certainly means the dev server. A hosted
  // URL will have a port or be on 443 via https, so only assume for http.
  if (/^http:\/\/[^/:]+$/i.test(value)) value = `${value}:8001`;
  // The API is mounted under /api; forgetting it is the most common mistake
  // and produces 404s on every call.
  if (!/\/api$/i.test(value)) value = `${value}/api`;

  return value;
};

export const getStoredBase = () => {
  try {
    return localStorage.getItem(STORAGE_KEY) || '';
  } catch {
    return '';
  }
};

export const setStoredBase = (raw) => {
  const value = raw ? normaliseBase(raw) : '';
  try {
    if (value) localStorage.setItem(STORAGE_KEY, value);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* private mode or storage disabled - the session default still applies */
  }
  return value;
};

/** The address to use right now. */
export const apiBase = () => getStoredBase() || BUILD_TIME || WEB_DEFAULT;

/**
 * Is this address actually reachable?
 *
 * Checked before saving, because a typo otherwise produces an app that looks
 * broken on every screen with no clue why. `/health` is unauthenticated, so
 * this works before login.
 */
export const testBase = async (raw) => {
  const base = normaliseBase(raw);
  if (!base) return { ok: false, message: 'Enter an address first.' };

  const url = base.replace(/\/api$/, '') + '/health';
  try {
    const controller = new AbortController();
    // A wrong IP on a LAN does not refuse the connection, it hangs until the
    // OS gives up - which can be 30 seconds of the user staring at nothing.
    const timer = setTimeout(() => controller.abort(), 6000);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);

    if (res.ok) return { ok: true, base, message: 'Connected.' };
    return { ok: false, base, message: `Server answered ${res.status}.` };
  } catch (e) {
    if (e.name === 'AbortError') {
      return {
        ok: false, base,
        message: 'No answer. Check the laptop and phone are on the same WiFi '
               + 'and the server was started with --host 0.0.0.0.',
      };
    }
    return { ok: false, base, message: 'Could not reach that address.' };
  }
};
