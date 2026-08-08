# NutriCoach chatbot — audit, scenario matrix and personalisation plan

Written against the code as it stands, not against intent. Every claim below was
checked in the source; line references are given where it helps.

---

## 1. How a message actually flows today

```
POST /chatbot/chat/simple
  └─ conversation_manager.handle_query(user_id, query, db)      ← 3 args only
       ├─ get_user_context()        profile row + active Goal row
       ├─ get_history()             last 6 turns, assistant msgs cut to 500 chars
       ├─ system = SYSTEM_PROMPT + profile block
       │            + INJURY_GUIDANCE   (only if a trigger word appears)
       │            + extra_context     ← NEVER SET on this path
       ├─ is_smalltalk(query)?
       │      yes → replace the whole message list with a minimal greeting prompt,
       │            withhold tool schemas
       │      no  → send history + tools
       ├─ Groq call (max_tokens 700, temperature 0.7, no timeout)
       ├─ tool_calls[0] only → _dispatch_tool → specialist service
       └─ save_turn() → ChatMessage rows
```

## 2. What the assistant can and cannot see

| Data | In the prompt? | Source |
|---|---|---|
| Name, age, weight, height, activity level | ✅ | `User` row |
| Dietary preferences, cuisine preference | ✅ | `User` row |
| Health conditions | ⚠️ field exists, **nothing ever writes to it** | `User.health_conditions` |
| Active goal targets (kcal, protein, target weight) | ✅ | `Goal` row |
| **Meals actually logged** | ❌ | `MealLog` — never queried |
| **Calories eaten today / remaining** | ❌ | computable, not computed |
| **Weight check-in history and trend** | ❌ | `WeightLog` — never queried |
| **Goal progress** (on track? stalled?) | ❌ | derivable, not derived |
| **Saved plans** (workouts, meal plans generated) | ❌ | `SavedPlan` — never queried |
| **Typical budget** | ❌ | BudgetChef params never stored to profile |
| **Cuisine affinity from real logs** | ❌ | `personalization.build_profile()` computes it, chat never calls it |
| Time of day / day of week | ❌ | not injected |

**The single most important finding:** `personalization.build_profile()` already
computes almost everything in the ❌ rows, and `handle_query()` already accepts an
`extra_context` parameter designed to receive it. The two are simply not
connected. `SmartChatbotIntegration` — the class that *does* wire them — is only
reachable from `enhanced_ml_router`, which the frontend never calls.

---

## 3. Scenario matrix

Severity: **P1** breaks trust or safety · **P2** feels impersonal or wrong ·
**P3** polish.

### 3.1 Conversation flow

| # | Scenario | Expected | Actual | Sev |
|---|---|---|---|---|
| C1 | Bot asks "do you have gym access?" → user replies **"no"** | Treated as the answer; plan uses bodyweight | `"no"` is in `_SMALLTALK`, so tools are withheld **and history is collapsed to a one-line topic hint** — the answer is thrown away and the user gets a cheery greeting | **P1** |
| C2 | Same with "yes", "yeah", "sure", "nope", "ok" after a question | Answer consumed | Same failure — six of the most common answers to a yes/no question are classified as filler | **P1** |
| C3 | User types **"help"** | Explains what it can do | `"help"` is in `_SMALLTALK` → minimal greeting prompt whose instructions say *"Do NOT list what you can do"* | P2 |
| C4 | User sends "hi" as their very first message ever | Warm greeting, maybe an offer | Works | ✅ |
| C5 | User says "thanks" right after a 7-day plan | Short acknowledgement | Works — this was fixed earlier | ✅ |
| C6 | Model returns two tool calls in one turn | Both run, or one runs deliberately | `tool_calls[0]` only; the rest are dropped silently | P3 |
| C7 | User pastes a 4,000-word article and asks about it | Handled or truncated politely | User messages are **never** truncated (only assistant ones are). Blows the token budget and can 413 | P2 |
| C8 | Conversation runs past 6 turns, user refers to something from turn 2 | Remembered | Falls out of the window. No summarisation of older turns | P2 |
| C9 | Two messages sent in quick succession | Serialised | Both read the same history; the second doesn't see the first | P3 |
| C10 | User writes in Hinglish ("bhai mujhe protein wala breakfast chahiye") | Understood, replies in kind | Model usually copes, but nothing in the prompt acknowledges it | P3 |

### 3.2 Injuries and safety

| # | Scenario | Expected | Actual | Sev |
|---|---|---|---|---|
| S1 | "I have a hamstring injury" **in the same message** as a plan request | Plan excludes hinges, states what it removed | Observed failure: returned a generic bodybuilding split, never mentioned the hamstring | **P1** |
| S2 | "I'm a footballer" | Sport-appropriate training | `fitness_goal` enum is `muscle_gain / weight_loss / endurance / flexibility / general_fitness`. No sport concept → falls to `general_fitness` | **P1** |
| S3 | Injury mentioned, then a new session tomorrow | Still remembered | `health_conditions` is never written by any screen — the injury lives only in chat history and falls out after 6 turns | **P1** |
| S4 | "I want to get **back** into running" | Normal reply | `"back"` is an injury trigger → 700 tokens of injury guidance loaded for nothing | P2 |
| S5 | "I have a head**ache**" / "my **hip** hop class" | — | `"ache"` and `"hip"` are substring triggers → same false positive | P2 |
| S6 | "I have **sciatica**" / shin splints / plantar fasciitis / tennis elbow / IT band / groin strain / **asthma** / arthritis | Guidance loads | None of these are in `INJURY_TRIGGERS`. Only `strain` catches groin strain; asthma and arthritis are missed entirely | **P1** |
| S7 | "my knee gave way and it's swollen" | Told to get it looked at before training | Guidance covers this **if** it loads — `swollen`/`gave way` are not triggers, but `knee` is, so it happens to work | P3 |
| S8 | Injury mentioned after a plan exists, but the plan is >6 turns back | `refine_previous_output` adapts it | `get_last_artifact` looks at the last 6 **bot** rows regardless of window, so usually fine; if none found it silently falls to the recovery path and answers *without* the plan | P2 |
| S9 | `refine_previous_output` on a recipe, model guesses `artifact_type: workout_plan` | Right adapter | Wrong adapter called; nothing validates the type against what the artifact actually is | P2 |
| S10 | User asks for a 900 kcal/day plan | Refused kindly, safer version offered | Prompt covers it; `nutrition_targets` clamps the goal path, but the **chat** path has no hard floor | P2 |

### 3.3 Personalisation

| # | Scenario | Expected | Actual | Sev |
|---|---|---|---|---|
| P1 | "What should I eat for dinner?" after logging 3 meals today | Knows what's left and what they've eaten | No meal data at all → generic suggestion | **P1** |
| P2 | Vegetarian user who has logged paneer 12 times | Suggests around real habits | Only the `dietary_preferences` string; never the actual foods | **P1** |
| P3 | "Am I on track?" | Reads weight trend and goal progress | Cannot answer — no weight or progress data | **P1** |
| P4 | "Give me another workout" a day after one was generated | Knows what it already gave | `SavedPlan` not visible; may repeat the same plan | P2 |
| P5 | "Something cheap" | Uses their typical spend | No budget signal | P2 |
| P6 | User logs nothing for 5 days, then opens chat | Notices, gently | No awareness of logging gaps | P2 |
| P7 | 9pm, no dinner logged, 900 kcal remaining | "You've got room for a proper dinner" | No time-of-day awareness | P2 |
| P8 | User's protein has been low all week | Nudges protein | Not computed for chat | P2 |

### 3.4 Generation and failure

| # | Scenario | Expected | Actual | Sev |
|---|---|---|---|---|
| F1 | All Groq keys exhausted | Plain "come back later" | `_complete` raises → caught → generic "having trouble right now" (acceptable, but no retry-after hint) | P2 |
| F2 | A service returns a dict with no string field | Readable message | `_unwrap` falls through to `str(result)` → **raw Python dict rendered into the chat** | **P1** |
| F3 | Specialist times out | Graceful | No timeout is set on the Groq client at all; a hung call blocks the request | P2 |
| F4 | Tool returns success but empty text | Recovery | Handled — `not text.strip()` routes to recovery | ✅ |
| F5 | Model emits malformed tool JSON | Recovery | Handled — `json.JSONDecodeError` → `{}` | ✅ |
| F6 | DB write fails while saving the turn | Reply still delivered | Handled — rollback, response returned | ✅ |

### 3.5 Immersion

| # | Scenario | Expected | Actual | Sev |
|---|---|---|---|---|
| I1 | Any generation request | Text appears progressively | 20–40 s of nothing, then a wall of text | **P1** |
| I2 | Opening the Assistant tab | Something grounded in their day | Empty box | P2 |
| I3 | After a reply | Tappable next steps | Nothing; user must think of what to type | P2 |
| I4 | Greeting vs. normal message | Same coach, same voice | Two different system prompts define the persona differently — tone shifts between paths | P2 |
| I5 | Returning after a week | "How did that plan go?" | No concept of elapsed time | P2 |

---

## 4. Fix plan, in order

**Round 1 — make it know the user** (fixes P1–P8, C1–C3)
1. Build a `chat_context` module: today's intake and gap, recent foods, protein
   trend, weight trend, goal progress, last saved plan, typical budget, local time.
2. Pass it into `handle_query` from the chat router.
3. Fix `is_smalltalk` so bare answers ("no", "yes", "sure") are only filler when
   the assistant did **not** just ask a question.

**Round 2 — make it safe** (S1–S9)
4. Persist injuries to `User.health_conditions` and surface a field for them.
5. Replace substring triggers with word-boundary matching plus a proper synonym
   list; drop the ones that fire on ordinary words.
6. Add sport/activity to the workout tool and let the plan state its adaptations.

**Round 3 — make it feel alive** (I1–I5)
7. Streaming endpoint and frontend consumption.
8. Grounded opener and suggested follow-up chips.
9. One persona definition shared by both prompt paths.

**Round 4 — hardening** (F2, F3, C6, C7)
10. `_unwrap` must never return a stringified dict.
11. Request timeout on the Groq client.
12. Cap user message length before it reaches the prompt.
