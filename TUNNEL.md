# A permanent address for the backend

Your friends need one link that keeps working. This is how to get one, for
free, without buying a domain.

## The problem with what you had

`cloudflared tunnel --url http://localhost:8001` creates a **quick tunnel**. It
is genuinely free and needs no account, and in exchange the hostname is random
and thrown away when the process stops. Every restart meant a new URL, a new
message to everyone testing, and everyone re-typing it into the app.

Cloudflare can give you a permanent hostname — that is a **named tunnel** — but
a named tunnel routes through DNS, so it needs a domain you own and have added
to Cloudflare. That is about $1–11 a year. Worth it if you want
`api.yourproject.com` on a project report; not necessary just to make the link
stop moving.

ngrok is no longer an option: in February 2026 its free tier was cut to random
URLs and two-hour sessions.

## What to use instead

**Tailscale Funnel.** Free on every plan, no domain, no card. It gives your
laptop a permanent public HTTPS address derived from the machine name and your
account, something like:

```
https://your-machine.tailXXXXXX.ts.net
```

That name never changes. When your laptop is off, the address stops answering;
when you turn the server back on, the same address works again. Which is
exactly what you asked for.

## One-time setup

**1. Install and sign in**

```bash
brew install --cask tailscale
tailscale up
```

Sign in with Google or GitHub — that creates your free tailnet.

> On macOS, Funnel can only share ports on the **App Store** or **Standalone**
> builds of Tailscale. The sandboxed variants cannot. `brew install --cask
> tailscale` gives you the right one.

**2. Check HTTPS certificates are enabled**

At https://login.tailscale.com/admin/dns, **HTTPS Certificates** must be on.
Running `tailscale funnel` normally turns it on for you, so this is usually
already correct — it is worth a look, not a step to perform blindly.

It matters because Tailscale gets `.ts.net` certificates from Let's Encrypt
through a DNS-01 challenge, and it can only create the record that challenge
needs when this is enabled.

**3. Turn Funnel on**

```bash
tailscale funnel --bg 8001
```

`--bg` is not optional in spirit. It configures the funnel persistently, so it
survives reboots and `tailscale down`/`up`. Without it the funnel exists only
while that command is in the foreground, and Ctrl-C removes the configuration
— **including the machine's public DNS record**, which is what makes the
address stop resolving and the certificate stop validating.

The first run opens a browser page asking you to enable Funnel for your
network. Approve it. Tailscale then issues the HTTPS certificate and adds the
`funnel` attribute to your policy file for you.

The command prints your permanent address. Note it down.

> Public DNS for a brand-new tailnet can take up to 10 minutes to propagate. If
> the first attempt from a phone fails, wait and try again before assuming
> something is wrong.

**4. Put the address in the app**

Create `frontend/.env.production.local` — it is gitignored, so your address is
not published:

```
REACT_APP_API_URL=https://your-machine.tailXXXXXX.ts.net/api
```

**5. Build the APK**

```bash
cd frontend
npm run build
npx cap sync android
cd android && ./gradlew assembleDebug
```

The APK is at `frontend/android/app/build/outputs/apk/debug/app-debug.apk`.
Send that file to your friends. They install it and it works — there is
nothing for them to type, and you never have to send another link.

## The website

The same address serves the site, not just the API:

| | |
| --- | --- |
| `https://your-machine.tailXXXXXX.ts.net` | the app, in any browser |
| `https://your-machine.tailXXXXXX.ts.net/api/...` | what the installed APK calls |
| `https://your-machine.tailXXXXXX.ts.net/health` | what the serve script checks |

So friends have two options and neither involves you sending anything twice:
open the link, or install the APK. **The link is the one that works on an
iPhone**, which cannot take an Android APK at all.

`main.py` mounts `frontend/build` at `/`, which means the site needs a build
present:

```bash
cd frontend
npm run build
```

Rebuild that whenever you change the frontend. The APK needs `npx cap sync
android` on top; the website does not — refreshing the page is enough.

> **The mount has to be registered after every router.** A `StaticFiles` mount
> at `/` matches every path, so putting it earlier makes the entire API return
> 404 — which looks like the routes vanished rather than like an ordering
> mistake. `scripts/test_web_serving.py` asserts the ordering and then proves
> it by making real requests.

## Every day after that

```bash
./scripts/serve-public.sh
```

That starts the backend, waits until it answers, checks the address is
reachable from the public internet, and prints it.

Ctrl-C stops the backend and **deliberately leaves the funnel configured**. The
machine's public DNS record only exists while a funnel is configured, so taking
it down on every exit would un-publish the address and break the certificate.
To take it down on purpose: `tailscale funnel reset`.

## Things worth knowing

**The laptop has to be awake.** Funnel proxies to your machine; it is not
hosting anything. Sleep the laptop and the address stops answering. If you want
the app to work while your laptop is off, that is a different job — deploying
the backend to a host — and it means moving off SQLite, because free hosts wipe
the disk on every redeploy.

**Anyone with the URL can reach the API.** It is the public internet. Accounts
still need a password, but the sign-up endpoint is open, so treat the address
as semi-private and do not post it anywhere public.

**Bandwidth is limited** and not configurable. Fine for a handful of friends
testing; not a production host.

**Funnel is in beta.** It has been in beta for a long time and is widely used,
but that is what Tailscale calls it.

## If the address itself will not serve

The symptom is a TLS error rather than a timeout — from `curl`, something like:

```
error:1404B438:SSL routines:ST_CONNECT:tlsv1 alert internal error
```

and from `tailscale cert`, `acme: order ... status: invalid`. Both mean the
certificate was never issued.

If `tailscale funnel status` says `No serve config`, that is a *separate*
problem and not a consequence of the certificate: it means no funnel is
configured at all, usually because a foreground `tailscale funnel` was stopped
with Ctrl-C. Fix that first, with `--bg`, or everything below measures nothing.

Check in this order, and check each one **before** requesting another
certificate. The order matters more than it looks — checks 1 and 2 are
meaningless in the wrong sequence.

1. **Is a funnel configured right now?**

   ```bash
   tailscale funnel status
   ```

   It must list your port. `No serve config` means there is no funnel, and
   **the machine's public DNS record only exists while a funnel is
   configured** — so with it down, everything below will look broken no matter
   what state it is in.

   This is why `tailscale funnel --bg` matters. Run in the foreground, Ctrl-C
   removes the config and un-publishes the hostname.

2. **Has public DNS caught up?**

   ```bash
   curl -s 'https://dns.google/resolve?name=your-machine.tailXXXXXX.ts.net&type=A'
   ```

   You want an `"Answer"` key. `"Authority"` alone means the name exists but
   has no address yet; `"Status": 3` means it does not exist at all. A brand
   new name took about twenty minutes here, well past the documented ten.

   **Do not use `dig` for this.** On a machine running Tailscale it lies:
   `tailscale dns status` shows `ts.net` split-routed to Tailscale's own
   resolver, so a local lookup answers from *inside* the tailnet and returns
   your `100.x` address whether or not anything is published publicly. Asking
   Google over HTTPS is the only way to get an outside answer from the inside.

   Also do not check the NS record of your tailnet — a tailnet is not a
   delegated zone, its records are served straight from `ts.net`, so an empty
   NS answer is normal and tells you nothing.

3. **HTTPS Certificates**, as in step 2 above. Usually already on.

4. **Then, and only if all of the above are green**, let Funnel provision the
   certificate by making a request. Do not reach for `tailscale cert` — see
   below for why that made things worse, not better.

**The rate limit is the trap.** Let's Encrypt allows roughly five failed
validations per hostname per hour. Every attempt after that fails identically
regardless of what you change, which reads exactly like a broken setup and is
not one. If you have already had a few failures, stop and come back in an hour
— retrying is worse than waiting.

### The failure that actually happened here

`tailscale cert` was run by hand several times while the DNS record was still
propagating. Each run appended a challenge token to the same record and none
were ever cleaned up:

```bash
curl -s 'https://dns.google/resolve?name=_acme-challenge.YOUR-HOST.tailXXXXXX.ts.net&type=TXT'
```

```
"Answer": [ seven different tokens ]
```

Let's Encrypt then validated against a pile of dead tokens and marked every
order `invalid`, and every retry made it worse by adding another. It is
self-perpetuating and no amount of local configuration escapes it. This is
[tailscale#14402](https://github.com/tailscale/tailscale/issues/14402), open
and untriaged.

**The fix is to rename the machine.** A new hostname gets a fresh challenge
record and a fresh rate-limit bucket:

```bash
tailscale serve reset
tailscale funnel reset
tailscale down
tailscale up --hostname=kayosha
tailscale funnel --bg 8001
```

Then wait — the new name took about twenty minutes to publish, well past the
documented ten. **One token in that TXT record means healthy; several means the
bug has followed you.**

**Do not run `tailscale cert` by hand.** Funnel provisions the certificate on
its own, and the manual runs are what caused this. The single legitimate use is
diagnosing a genuine failure, once.

None of this blocks the rest of the work. The hostname is already permanent, so
the address can go into the APK and be built against while the certificate
sorts itself out.

## If someone's app cannot connect

The setup screen still exists — it is now the override rather than the only
way in. It appears by itself when nothing is reachable, and lives in **Profile
→ Server**.

If a friend typed an address in earlier, that stored value **outranks** the one
built into the APK, permanently. That is what the **Use the built-in address**
button on that screen is for: it clears the override and goes back to the
compiled-in tunnel URL.

Addresses are interpreted by kind, so both of these work as typed:

| You type | It becomes |
| --- | --- |
| `x.tailXXXXXX.ts.net` | `https://x.tailXXXXXX.ts.net/api` |
| `192.168.1.5` | `http://192.168.1.5:8001/api` |

A name gets HTTPS and no port; a LAN address gets HTTP and port 8001. Assuming
one rule for both is what made pasting a tunnel hostname fail silently before.

## Sources

- [Tailscale Funnel · Tailscale Docs](https://tailscale.com/docs/features/tailscale-funnel)
- [Cloudflare Tunnel changelog: hostname routing](https://developers.cloudflare.com/changelog/2025-09-18-tunnel-hostname-routing/)
- [Static domains for all ngrok users](https://webflow.ngrok.com/blog-post/free-static-domains-ngrok-users)
