# 🥗 Kayosha — AI Health & Nutrition

A nutrition and fitness app that plans around *you*: your goals, your budget,
your kitchen, your injuries, and what you actually ate today.

Runs as a **website** and as an **Android app**, both talking to the same
backend.

---

## What it does

### Track what you eat

- **Log a meal** by describing it — the nutrition is worked out for you
- **Scan a barcode** for packaged food, which reads the real values off the
  product label instead of estimating them
- Every figure is labelled with where it came from: **verified** (a product
  label or a government food table) or **AI estimate**. A guess is never
  displayed as a fact
- Today's meals appear on the dashboard as a timeline — what you ate and when

### Goals that mean something

- Pick an objective (lose fat, gain muscle, maintain) and your calorie and
  macro targets are **derived** from your profile rather than typed in
- Daily adherence is judged per macro, with tolerance bands — a day you didn't
  log is not counted as a day you failed
- Weekly view of which days hit target and, when they missed, **which macro was
  the problem**

### AI specialists

| | |
| --- | --- |
| **ChefGenius** | Recipes from what you have in the kitchen |
| **FitMentor** | Workout plans that respect your injuries |
| **BudgetChef** | Meal plans to a weekly budget |
| **Explorer** | Regional cuisines, optionally built to your macro targets |
| **Meal Planner** | Multi-day plans held to calories, protein, carbs and fat |
| **Assistant** | A chatbot with context on your goals and history |

Generated plans can be **downloaded as PDF**, **shared**, or **emailed**.

### Injury-aware training

FitMentor doesn't work from a blacklist of exercise names — it reasons about
**movement patterns**. An injury is mapped to the patterns it rules out, so an
exercise nobody anticipated is still filtered correctly.

- Severity grading, from "train around it" to "see a professional first"
- Red-flag symptoms stop plan generation and say why
- Plans are checked after generation and repaired if something unsafe slipped in

### Points, streaks and a leaderboard

Points for meals logged, days completed, days on target, workouts done, rest
days taken, weight check-ins and streaks. Nine levels. The ledger is
**idempotent** — the same day can never be scored twice, and points never go
down.

### Details that are easy to get wrong

- **Your day, your timezone.** Days roll over at *your* midnight, not the
  server's, and DST is handled properly
- Everything is stored in UTC and interpreted in your local day

---

## Running it

### Prerequisites

- Python 3.8+
- Node.js 16+

### Backend

```bash
git clone https://github.com/Prityanshu/health-nutrition-app-final.git
cd health-nutrition-app-final
```

```bash
python -m venv venv
source venv/bin/activate
```

On Windows the activate step is `venv\Scripts\activate` instead.

```bash
pip install -r requirements.txt
```

Create a `.env` with your API keys (see `.env.example` if present). It is
gitignored and must stay that way.

```bash
uvicorn main:app --port 8001 --reload
```

API docs: http://localhost:8001/docs

### Frontend

```bash
cd frontend
npm install
npm start
```

Opens http://localhost:3000 with hot reload, talking to the backend on 8001.

### Serving the built site

`main.py` serves `frontend/build` at `/`, so once you have a production build
the backend serves the website too — one origin for both, which is why there is
no CORS to configure:

```bash
cd frontend
npm run build
```

Then http://localhost:8001 is the app.

---

## Sharing it with other people

`scripts/serve-public.sh` starts the backend and puts it on the internet at a
permanent HTTPS address using **Tailscale Funnel** — free, no domain, no port
forwarding:

```bash
./scripts/serve-public.sh
```

It prints one URL that serves the website and the API. Send the link and people
can use the app in any browser, including on iPhone.

Full setup, and the failure modes worth knowing about, are in
**[TUNNEL.md](TUNNEL.md)**.

> The laptop has to be awake and running the script. Funnel proxies to your
> machine — it does not host anything.

---

## Android app

Built with Capacitor from the same React frontend.

```bash
cd frontend
npm run build
npx cap sync android
cd android && ./gradlew assembleDebug
```

The APK lands at
`frontend/android/app/build/outputs/apk/debug/app-debug.apk`.

The backend address is compiled in from `frontend/.env.production.local`, so
the app works the moment it is installed. It can still be pointed elsewhere at
runtime from **Profile → Server**, which is also how you get back to the
built-in address.

Details in **[ANDROID.md](ANDROID.md)**.

---

## Tech stack

### Backend

| | |
| --- | --- |
| FastAPI 0.104 + Uvicorn | API and web server |
| SQLAlchemy 2.0 + SQLite | Data, in WAL mode for concurrent reads |
| Pydantic 2.5 | Validation |
| python-jose + passlib/bcrypt | JWT auth, password hashing |
| agno + Groq (`llama-3.3-70b-versatile`) | The AI agents, with key rotation |
| ReportLab | Plan PDFs |
| Open Food Facts, USDA FoodData Central | Sourced nutrition data |

### Frontend

| | |
| --- | --- |
| React 18 + Create React App | UI |
| Tailwind 3.4 | Styling |
| lucide-react | Icons |
| html5-qrcode | Barcode scanning |
| Capacitor 8 | Android packaging |

---

## Project layout

```
app/
  routers/          API endpoints
  services/         Business logic - the interesting parts live here
  middleware/       Performance tracking
  database.py       Models and engine configuration
frontend/
  src/              React app
  android/          Capacitor Android project
scripts/            Migrations, tests, and the public-serving script
main.py             App entry point; serves the API and the built site
```

Some services worth a look:

| File | What it solves |
| --- | --- |
| `movement_ontology.py` | Injuries to movement patterns, not exercise names |
| `daytime.py` | What day it is *for this user*, in their timezone |
| `adherence.py` | Whether a day hit its macro targets, honestly |
| `points_engine.py` | The scoring tariff and leaderboard |
| `food_lookup.py` | Real nutrition data with stated provenance |
| `macro_targets.py` | Holding generated plans to actual numbers |
| `plan_repair.py` | Fixing a plan rather than discarding it |

---

## Tests

Hand-rolled scripts, no pytest required. Each is runnable on its own:

```bash
python scripts/test_daytime.py
python scripts/test_barcode.py
python scripts/test_web_serving.py
```

Around **850 assertions** across 13 suites, covering timezone handling,
adherence, points, macro targeting, injury safety, barcode validation, mobile
layout, and the web/API routing. Plus `scripts/audit_safety_system.py` for the
injury-safety ontology.

---

## Notes

- `.env` holds live credentials and is gitignored — keep it that way
- SQLite is right for this scale; a real deployment would want Postgres
- Funnel bandwidth is limited, so this is for testing rather than production
