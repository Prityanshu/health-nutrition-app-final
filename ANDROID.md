# NutriPlan on Android

The React app runs inside a Capacitor shell, so the APK is the same frontend
you already have — no rewrite, and every fix to the web app is one rebuild away
from being in the app.

---

## One-time setup

**1. Install Android Studio** — <https://developer.android.com/studio> (free).
On first launch let it install the SDK and an emulator image.

**2. Point the shell at your machine.** In `frontend/.env`:

```
REACT_APP_API_URL=http://192.168.1.5:8001/api
```

Find your laptop's address with:

```bash
ipconfig getifaddr en0        # WiFi on macOS
```

This is only the *default*. The address can be changed from inside the app
later without rebuilding — see "When the address changes" below.

---

## Building the APK

Run these from the repo root every time you want a new build:

```bash
cd frontend
npm run build
npx cap sync android
npx cap open android
```

`cap sync` copies the fresh web build into the Android project and updates
native plugins. `cap open` launches Android Studio on the project.

In Android Studio: **Build → Build Bundle(s) / APK(s) → Build APK(s)**.

The APK lands at:

```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

To skip Android Studio once it is set up:

```bash
cd frontend/android && ./gradlew assembleDebug
```

---

## Running the backend so the phone can see it

The default `uvicorn main:app --reload` binds to `127.0.0.1`, which accepts
connections **only from the laptop itself**. The phone will time out. Use:

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Both devices must be on the same WiFi. Some networks — university WiFi and
most public hotspots — block device-to-device traffic entirely; if the phone
cannot reach the laptop on a network you don't control, that is usually why.
A phone hotspot shared to the laptop is the quickest workaround.

---

## Getting it onto a phone

**Plugged in (easiest):** enable Developer Options (tap Build Number seven
times in Settings → About), turn on USB debugging, connect, then press Run in
Android Studio.

**By file:** send `app-debug.apk` to the phone however you like. Android will
warn about installing from an unknown source; allow it for whichever app is
doing the sending.

---

## When the address changes

It will — a new WiFi network, a new DHCP lease, a friend on the other side of
the city. The app does not need rebuilding for any of them:

- If the backend is unreachable at startup, the app shows a **connect screen**
  and asks for the address.
- It can also be changed any time from **Profile → Server**.

Typing `192.168.1.5` is enough; `http://` and `/api` are filled in. The address
is checked against `/health` before it is saved, so a typo says so immediately
instead of producing an app that silently fails on every screen.

---

## Letting friends test it, for free

The LAN approach needs them on your WiFi. For remote testers, in rough order
of effort:

**A tunnel** — `cloudflared tunnel --url http://localhost:8001` prints a public
HTTPS URL. Zero setup, no account needed. The URL changes every restart and it
dies when your laptop sleeps, so it suits a scheduled test session rather than
casual use. Give testers the URL and they paste it into the connect screen.

**A free host** — Render or Fly.io give a permanent HTTPS URL that works
without your laptop on. Free tiers sleep when idle, so the first request after
a quiet spell takes ~50 seconds. Two things to sort out first:

- SQLite does not survive a redeploy on those platforms; you would move to
  their free Postgres.
- `allow_origin_regex` in `main.py` is a development convenience. Replace it
  with the specific deployed origin before anything is public.

Either way the APK stays the same — testers change the address in the app.

---

## Notes

**Cleartext HTTP is enabled** in `android/app/src/main/res/xml/network_security_config.xml`
because Android blocks plain `http://` by default and a LAN IP has no
certificate. This is a debug build. Once the backend is on HTTPS, delete that
file and the two attributes referencing it in `AndroidManifest.xml`.

**The debug APK is signed with a throwaway debug key.** Fine for testing and
for sharing with friends. Publishing to Play would need a release key — not
needed for anything here.

**`frontend/android/` is generated.** It is safe to delete and recreate with
`npx cap add android`, but you would lose the manifest and network-config edits
listed above, so prefer not to.

**Every web change needs `npm run build && npx cap sync android`** before it
appears in the app. The APK bundles a snapshot of the build; it does not read
your source at runtime.
