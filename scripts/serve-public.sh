#!/usr/bin/env bash
#
# Start the backend and put it on the internet at a permanent address.
#
# WHY THIS EXISTS
# ---------------
# A Cloudflare quick tunnel gives out a new random hostname on every restart,
# so every time the laptop was turned on, everyone testing the app had to be
# sent a new URL and type it into the phone again. A Tailscale Funnel hostname
# is derived from the machine name and the tailnet name, so it is the same
# address today, tomorrow, and after a reboot. That is the whole difference.
#
# The address is therefore worth compiling into the APK - see TUNNEL.md - which
# is what lets someone install it and have it work with nothing to type.
#
#   ./scripts/serve-public.sh
#
# Ctrl-C stops both the server and the tunnel.

set -euo pipefail

PORT="${PORT:-8001}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

red()   { printf '\033[91m%s\033[0m\n' "$*"; }
green() { printf '\033[92m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

# --- the virtualenv ---------------------------------------------------------
# After a reboot you open a fresh terminal, and a fresh terminal has no venv
# active. Without this the script dies on `uvicorn: command not found`, which
# reads as a broken script rather than an unactivated environment - and it
# happens precisely when you are least likely to remember why.

if ! command -v uvicorn >/dev/null 2>&1 && [ -f "$ROOT/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/venv/bin/activate"
  dim "Activated venv/"
fi

if ! command -v uvicorn >/dev/null 2>&1; then
  red "uvicorn is not available."
  echo
  echo "  source venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

# --- checks, before anything is started -------------------------------------
# Each of these fails in a way that looks like "the app is broken" rather than
# "this tool is not set up", so they are worth catching by name.

if ! command -v tailscale >/dev/null 2>&1; then
  red "tailscale is not installed."
  echo
  echo "  brew install --cask tailscale"
  echo
  echo "On macOS, Funnel can only share ports if you have the App Store or"
  echo "Standalone build - the sandboxed variants cannot do it."
  exit 1
fi

if ! tailscale status >/dev/null 2>&1; then
  red "tailscale is installed but not logged in."
  echo
  echo "  tailscale up"
  exit 1
fi

# --- the permanent address --------------------------------------------------
# `tailscale status --json` carries the machine's full DNS name. Reading it
# here means the script can print the exact URL to paste, rather than telling
# the user to go and find it.

DNS_NAME="$(tailscale status --json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' \
  2>/dev/null || true)"

if [ -z "$DNS_NAME" ]; then
  red "Could not read this machine's tailnet name."
  echo "Check 'tailscale status' and that MagicDNS is enabled."
  exit 1
fi

API_URL="https://${DNS_NAME}/api"

# --- run --------------------------------------------------------------------

cleanup() {
  # Stop the server, and DELIBERATELY leave the funnel configured.
  #
  # An earlier version tore the funnel down here, on the theory that a hostname
  # resolving to a machine with nothing behind it fails slowly. That was wrong,
  # and it was actively harmful: the public DNS record for the machine only
  # exists while a funnel is configured. Removing it on every exit meant the
  # name stopped resolving, the certificate could not be validated, and every
  # debugging session started from zero.
  #
  # Configured once with --bg, the funnel survives reboots and `tailscale
  # down`/`up`, so the address stays published and only the backend comes and
  # goes. To take it down on purpose: tailscale funnel reset
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

bold "Starting the backend on port $PORT"
# 127.0.0.1 is deliberate and is NOT the same mistake as before. The funnel
# connects from this machine, so the server does not need to accept connections
# from the network - and not listening on 0.0.0.0 means the LAN cannot reach it
# directly. Set HOST=0.0.0.0 if you also want phones on the same WiFi to
# connect without the tunnel.
# Wrapped in caffeinate where available. The funnel proxies to THIS machine, so
# a sleeping laptop is an app that is down for everyone using it - and closing
# the lid is the normal way to walk away from a laptop. `-i` blocks idle sleep
# and `-s` blocks system sleep on AC power, both only for as long as this
# command runs. Ctrl-C and the machine sleeps normally again.
#
# It cannot defeat clamshell sleep on battery; nothing in userspace can. Keep
# it plugged in if people are relying on it.
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -is uvicorn main:app --host "${HOST:-127.0.0.1}" --port "$PORT" --reload &
else
  uvicorn main:app --host "${HOST:-127.0.0.1}" --port "$PORT" --reload &
fi
SERVER_PID=$!

# Wait for it to answer before opening the funnel, so the first request from a
# phone does not arrive at a port with nothing on it.
printf 'Waiting for the server'
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo
    green "Server is up."
    break
  fi
  printf '.'
  sleep 0.5
done
echo

# --- the funnel -------------------------------------------------------------
# Configured once, persistently. Two reasons it is --bg and not foreground:
#
#   * Foreground prints "Available on the internet" and blocks. That message is
#     optimistic - it appears even when the certificate was never issued - so
#     there is nowhere to stand to check whether it actually worked.
#   * Foreground tears the config down on Ctrl-C, and the machine's PUBLIC DNS
#     record only exists while a funnel is configured. So stopping the script
#     un-published the hostname, which is why `dig` came back empty and why the
#     certificate could not be validated.

if tailscale funnel status 2>/dev/null | grep -q "127.0.0.1:${PORT}"; then
  dim "Funnel already configured for port ${PORT}."
else
  bold "Configuring the funnel (once - it persists across reboots)"
  tailscale funnel --bg "$PORT" >/dev/null 2>&1 || true
fi

# Is the hostname published in PUBLIC DNS?
#
# This has to be asked over DNS-over-HTTPS, not with dig. Tailscale split-routes
# `ts.net` on this machine to its own resolver (see `tailscale dns status`), so
# a local lookup answers from inside the tailnet and says yes regardless of
# what the rest of the world can see. Asking Google over HTTPS is the only way
# to get an outside answer from inside the tunnel's own machine.
#
# `Status: 0` with no `Answer` means the zone exists but the record does not -
# which is Tailscale not having published it, and is not something any amount
# of local configuration will fix.
# Three outcomes, not two:
#
#   0  published
#   1  definitively not published (the query was answered, with no Answer)
#   2  could not check (no route to dns.google, captive portal, proxy)
#
# The third one matters. Folding it into "not published" would make this
# announce a Tailscale fault whenever the machine simply could not reach
# Google - which is exactly what it did on the first version, confidently
# reporting a known-good hostname as missing.
dns_published() {
  local body
  body="$(curl -fsS --max-time 8 \
    "https://dns.google/resolve?name=${DNS_NAME}&type=A" 2>/dev/null)" || return 2
  [ -n "$body" ] || return 2
  printf '%s' "$body" | python3 -c 'import json, sys
try:
    answer = json.load(sys.stdin).get("Answer")
except Exception:
    sys.exit(2)          # not JSON - something intercepted the request
sys.exit(0 if answer else 1)'
}

# The real test: fetch the public URL from the public internet.
printf 'Checking it answers from outside'
REACHABLE=""
for _ in $(seq 1 10); do
  if curl -fsS --max-time 6 "https://${DNS_NAME}/health" >/dev/null 2>&1; then
    REACHABLE="yes"
    break
  fi
  printf '.'
  sleep 2
done
echo

if [ -n "$REACHABLE" ]; then
  green "Reachable from the internet."
  echo
  bold "  Website   https://${DNS_NAME}"
  dim  "            Send this to anyone. No install, works on iPhone too."
  echo
  bold "  API       $API_URL"
  dim  "            What the installed app talks to. Same origin as the site,"
  dim  "            which is why there is no CORS to configure."
  echo
  if [ ! -f "$ROOT/frontend/build/index.html" ]; then
    red "  No frontend build - the website will 404."
    red "  Fix: cd frontend && npm run build"
    echo
  fi
  dim "Neither address changes. Nothing to resend, ever."
else
  red "https://${DNS_NAME}/health did not answer."
  echo
  echo "The server is running and answers locally, so the problem is between"
  echo "the internet and Tailscale rather than in your code. Which of the two"
  echo "it is depends entirely on the next line."
  echo

  DNS_STATE=0
  dns_published || DNS_STATE=$?

  if [ "$DNS_STATE" -eq 2 ]; then
    bold "Public DNS: could not check."
    echo
    echo "dns.google was not reachable, so this cannot tell you whether the"
    echo "hostname is published. That is a network problem here, not a verdict"
    echo "on Tailscale. Check connectivity and run this again."
  elif [ "$DNS_STATE" -eq 0 ]; then
    bold "Public DNS: the hostname resolves."
    echo
    echo "So the name is published and the failure is the TLS certificate."
    echo
    echo "  1. Check HTTPS certificates are enabled for the tailnet:"
    echo "     https://login.tailscale.com/admin/dns  ->  HTTPS Certificates"
    echo "     Enabling Funnel usually turns this on for you."
    echo
    echo "  2. Then request the certificate ONCE:"
    echo "     tailscale cert ${DNS_NAME}"
    echo
    red "  Not in a loop. Let's Encrypt allows about five failed validations"
    red "  per hostname per hour, and past that every attempt fails the same"
    red "  way whatever you change - which reads as a broken setup and is not"
    red "  one. After a few failures, waiting an hour beats trying again."
  else
    bold "Public DNS: the hostname is NOT published."
    echo
    echo "Tailscale has not created the public record for this machine, even"
    echo "though the funnel is configured. Nothing local can fix that, and"
    echo "requesting a certificate cannot work either - Let's Encrypt has no"
    echo "name to validate. Do NOT run 'tailscale cert' in this state; it will"
    echo "fail with 'acme: order ... status: invalid' and spend one of your"
    echo "five attempts an hour."
    echo
    echo "  1. Give it time. A new tailnet is documented at up to 10 minutes"
    echo "     and can take longer."
    echo
    echo "  2. Force the node to re-register:"
    echo "       tailscale funnel reset"
    echo "       tailscale funnel --bg ${PORT}"
    echo "     and if that does not do it:"
    echo "       tailscale down && tailscale up"
    echo "       tailscale funnel --bg ${PORT}"
    echo
    echo "  3. Check for an incident: https://status.tailscale.com"
    echo
    echo "  4. Watch it from outside, without trusting local DNS:"
    echo "     curl -s 'https://dns.google/resolve?name=${DNS_NAME}&type=A'"
    echo "     You want an \"Answer\" key. Only \"Authority\" means not yet."
  fi
  echo
  dim "None of this blocks the APK: ${DNS_NAME} is already your permanent"
  dim "hostname and will not change, so you can build against it meanwhile."
fi
echo

# Hold here so Ctrl-C reaches the trap and takes both down together.
wait "$SERVER_PID"
