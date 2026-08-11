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

const STORAGE_KEY = 'kayosha.apiBase';

const BUILD_TIME = process.env.REACT_APP_API_URL || '';
const WEB_DEFAULT = 'http://localhost:8001/api';

/** True when running inside the Capacitor shell rather than a browser tab. */
export const isNativeApp = () =>
  typeof window !== 'undefined' &&
  Boolean(window.Capacitor?.isNativePlatform?.());

/** A dotted quad, i.e. something on the local network rather than a domain. */
const looksLikeIp = (host) => /^\d{1,3}(\.\d{1,3}){3}$/.test(host);

/**
 * Is this address on this network, as opposed to out on the internet?
 *
 * The distinction decides two defaults - scheme and port - and getting it
 * wrong produces a connection error that looks exactly like a dead server.
 */
const isLocalHost = (host) => {
  const name = host.toLowerCase();
  return name === 'localhost'
      || name.endsWith('.local')          // Bonjour, e.g. macbook.local
      || looksLikeIp(name);
};

/**
 * Normalise whatever the user typed into something fetchable.
 *
 * People type "192.168.1.5", "192.168.1.5:8001", or paste a URL with a
 * trailing slash. All three should work rather than failing with a network
 * error that looks like the server is down.
 *
 * THE TUNNEL BUG
 * --------------
 * This used to append :8001 to any bare hostname, because a bare hostname
 * meant a laptop on the WiFi. Once the backend moved behind a tunnel that
 * stopped being true: pasting
 *
 *     laptop.tail1234.ts.net
 *
 * became `http://laptop.tail1234.ts.net:8001`, which is wrong three times
 * over - the tunnel is HTTPS, it listens on 443, and port 8001 is not open to
 * the internet at all. The request just hung until it timed out, and the app
 * reported that the server could not be reached.
 *
 * So the two defaults now follow from what kind of address it is. A LAN
 * address keeps http and :8001. A public hostname gets https and no port,
 * because that is what every tunnel and every host serves.
 */
export const normaliseBase = (raw) => {
  let value = String(raw || '').trim();
  if (!value) return '';

  const hadScheme = /^https?:\/\//i.test(value);
  // Everything up to the first slash, minus any scheme: host and maybe :port.
  const authority = value.replace(/^https?:\/\//i, '').split('/')[0];
  const host = authority.split(':')[0];
  const hasPort = /:\d+$/.test(authority);

  if (!hadScheme) {
    // A bare LAN address is a development server and speaks http. A bare
    // domain is on the internet and speaks https - assuming otherwise means
    // the request is refused or silently downgraded.
    value = `${isLocalHost(host) ? 'http' : 'https'}://${value}`;
  }

  value = value.replace(/\/+$/, '');

  // The port default applies only where 8001 is plausible: an http LAN
  // address with no port of its own. A public host is on 443.
  if (!hasPort && /^http:\/\//i.test(value) && isLocalHost(host)) {
    value = value.replace(/^(http:\/\/[^/]+)/i, `$1:8001`);
  }

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

/**
 * The address baked in at build time, if there is one.
 *
 * With a permanent tunnel URL this is finally worth setting: it is what makes
 * the APK work the moment a friend opens it, with nothing to type. Put it in
 * frontend/.env.production.local (which is gitignored) as
 *
 *     REACT_APP_API_URL=https://your-laptop.tailXXXX.ts.net/api
 *
 * See TUNNEL.md.
 */
export const builtInBase = () => (BUILD_TIME ? normaliseBase(BUILD_TIME) : '');

/** Is the app pointed somewhere other than the address it shipped with? */
export const isOverridden = () => {
  const stored = getStoredBase();
  return Boolean(stored) && stored !== builtInBase();
};

/**
 * Forget a manual override and go back to the built-in address.
 *
 * Needed because localStorage wins over the build-time default, permanently.
 * Someone who typed a laptop's LAN IP once would keep pointing at it after a
 * rebuild moved everyone to the tunnel, and would have no idea why the app
 * only worked at home.
 */
export const resetToBuiltIn = () => {
  setStoredBase('');
  return builtInBase() || WEB_DEFAULT;
};

/** The address to use right now. */
export const apiBase = () => getStoredBase() || builtInBase() || WEB_DEFAULT;

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
