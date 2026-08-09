import React from 'react';
import {
  Flame, UtensilsCrossed, MessageSquare, Trophy, Target,
  ChevronRight, Plus, Sparkles, TrendingDown, TrendingUp, Minus, Scale, Check,
} from 'lucide-react';
import useCountUp from './useCountUp';
import InjuryTracker from './InjuryTracker';
import WorkoutCheckIn from './WorkoutCheckIn';
import useIsPhone from '../useIsPhone';

/**
 * Dashboard - today at a glance, measured against the active goal.
 *
 * Everything here compares intake to the targets calculated when the goal was
 * set. Where there is no active goal the numbers are shown without comparison
 * and the user is prompted to set one, rather than being silently measured
 * against invented defaults.
 */

const clamp = (n, min = 0, max = 100) => Math.min(max, Math.max(min, n));
const num = (v) => (typeof v === 'number' && !Number.isNaN(v) ? v : 0);

/** "1.5" but "2" - trailing zeros on a serving count are noise. */
const formatQty = (q) => {
  const n = num(q);
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(/\.0$/, '');
};

/** Local time of a log entry, or '' if the timestamp is missing or unparseable. */
const mealTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

/* ------------------------------------------------------- goal adherence -- */

const DAY_COLOURS = {
  hit: '#34D399',
  missed: '#F87171',
  partial: '#FBBF24',
  unlogged: '#2A3240',
  no_goal: '#2A3240',
};

const DAY_LABELS = {
  hit: 'On target',
  missed: 'Missed',
  partial: 'Partly logged',
  unlogged: 'Nothing logged',
  no_goal: 'No target set',
};

/** Mon/Tue/… for a YYYY-MM-DD string, parsed as a LOCAL date. */
const weekdayOf = (iso) => {
  // new Date('2026-08-09') parses as UTC midnight, which renders as the
  // previous day for anyone west of Greenwich. Splitting the parts avoids it.
  const [y, m, d] = String(iso).split('-').map(Number);
  if (!y || !m || !d) return '';
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: 'short' });
};

/**
 * The last seven days as a row of marks.
 *
 * Intentionally not a streak counter alone. A single number hides the shape -
 * four hits then three misses and three misses then four hits are the same
 * "4/7", and they mean opposite things about where you are heading.
 */
function AdherenceStrip({ history, summary }) {
  const [open, setOpen] = React.useState(null);

  if (!history?.length) return null;

  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '0.6rem' }}>
        <span style={{ fontSize: '0.75rem', color: '#98A2B3' }}>
          Last {history.length} days
        </span>
        {summary?.current_streak > 0 && (
          <span className="pill" style={{
            fontSize: '0.6875rem', color: '#34D399',
            background: 'rgba(52,211,153,0.12)', border: '1px solid rgba(52,211,153,0.3)',
          }}>
            {summary.current_streak} day{summary.current_streak === 1 ? '' : 's'} on target
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: '0.375rem' }}>
        {history.map((day) => {
          const colour = DAY_COLOURS[day.status] || '#2A3240';
          const isOpen = open === day.date;
          return (
            <button
              key={day.date}
              type="button"
              onClick={() => setOpen(isOpen ? null : day.date)}
              title={`${day.date} — ${DAY_LABELS[day.status]}`}
              style={{
                flex: 1, background: 'none', border: 'none', padding: 0,
                cursor: 'pointer', display: 'grid', gap: '0.3rem', justifyItems: 'center',
              }}
            >
              <span style={{ fontSize: '0.625rem', color: '#667085' }}>
                {weekdayOf(day.date).slice(0, 1)}
              </span>
              <span style={{
                width: '100%', height: 6, borderRadius: 3, background: colour,
                opacity: day.status === 'unlogged' || day.status === 'no_goal' ? 1 : 0.9,
                outline: isOpen ? `2px solid ${colour}` : 'none',
                outlineOffset: 2,
              }} />
            </button>
          );
        })}
      </div>

      {/* Tapping a day says WHICH macro missed. "You missed" on its own is
          not information anybody can act on. */}
      {open && (() => {
        const day = history.find((d) => d.date === open);
        if (!day) return null;
        return (
          <div style={{
            marginTop: '0.6rem', padding: '0.625rem 0.75rem', borderRadius: '0.5rem',
            background: '#12151B', border: '1px solid #2A3240',
            fontSize: '0.75rem', color: '#98A2B3', lineHeight: 1.5,
          }}>
            <span style={{ color: DAY_COLOURS[day.status], fontWeight: 600 }}>
              {weekdayOf(day.date)}
            </span>
            {' — '}{day.summary}
            {day.meals > 0 && (
              <span style={{ color: '#667085' }}>
                {' '}· {day.meals} meal{day.meals === 1 ? '' : 's'}
              </span>
            )}
          </div>
        );
      })()}

      {summary?.headline && (
        <div style={{
          marginTop: '0.6rem', fontSize: '0.75rem', color: '#667085', lineHeight: 1.5,
        }}>
          {summary.headline}
        </div>
      )}
    </div>
  );
}

/** Concentric progress rings: calories outer, protein inner. */
function GoalRings({ calories, calorieTarget, protein, proteinTarget, hasGoal }) {
  const size = 224;
  const animatedCals = useCountUp(calories);

  const rings = [
    {
      r: 96, stroke: 15, value: calories, target: calorieTarget,
      from: '#8B5CF6', to: '#22D3EE', label: 'calories',
    },
    {
      r: 74, stroke: 11, value: protein, target: proteinTarget,
      from: '#22D3EE', to: '#34D399', label: 'protein',
    },
  ];

  const over = hasGoal && calorieTarget > 0 && calories > calorieTarget * 1.05;
  const remaining = Math.max(0, calorieTarget - calories);

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <defs>
          {rings.map((ring, i) => (
            <linearGradient key={i} id={`ring${i}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={over && i === 0 ? '#FBBF24' : ring.from} />
              <stop offset="100%" stopColor={over && i === 0 ? '#F87171' : ring.to} />
            </linearGradient>
          ))}
        </defs>
        {rings.map((ring, i) => {
          const c = 2 * Math.PI * ring.r;
          const pct = ring.target > 0 ? clamp((ring.value / ring.target) * 100) : 0;
          const offset = c - (pct / 100) * c;
          return (
            <g key={i}>
              <circle
                cx={size / 2} cy={size / 2} r={ring.r}
                fill="none" stroke="#232A35" strokeWidth={ring.stroke}
              />
              <circle
                cx={size / 2} cy={size / 2} r={ring.r}
                fill="none"
                stroke={`url(#ring${i})`}
                strokeWidth={ring.stroke}
                strokeLinecap="round"
                strokeDasharray={c}
                strokeDashoffset={offset}
                className="ring-animate"
                style={{
                  '--dash-from': `${c}px`,
                  '--dash-to': `${offset}px`,
                  animationDelay: `${i * 0.12}s`,
                  filter: `drop-shadow(0 0 7px ${ring.from}66)`,
                }}
              />
            </g>
          );
        })}
      </svg>

      <div style={{
        position: 'absolute', inset: 0, display: 'flex',
        flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <div className="metric-value tabular" style={{ fontSize: '3rem' }}>
          {Math.round(animatedCals).toLocaleString()}
        </div>
        <div className="metric-label" style={{ marginTop: 5 }}>
          {hasGoal ? `of ${calorieTarget.toLocaleString()} kcal` : 'kcal today'}
        </div>
        {hasGoal && (
          <div style={{
            marginTop: 9, fontSize: '0.75rem', fontWeight: 700,
            color: over ? '#FBBF24' : '#34D399',
          }}>
            {over
              ? `${(calories - calorieTarget).toLocaleString()} over`
              : `${remaining.toLocaleString()} to go`}
          </div>
        )}
      </div>
    </div>
  );
}

function MacroBar({ label, grams, target, color, hasGoal, delay = 0 }) {
  const pct = target > 0 ? clamp((grams / target) * 100) : 0;
  const animated = useCountUp(grams);
  const hit = hasGoal && pct >= 95;

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 6 }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{label}</span>
        <span className="tabular" style={{ fontSize: '0.75rem', color: hit ? '#34D399' : '#98A2B3' }}>
          {Math.round(animated)}g
          {hasGoal && <span style={{ color: '#667085' }}> / {Math.round(target)}g</span>}
        </span>
      </div>
      <div className="macro-track">
        <div
          className="macro-fill macro-fill-animate"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${color}, ${color}CC)`,
            animationDelay: `${delay}s`,
            boxShadow: pct > 0 ? `0 0 10px ${color}55` : 'none',
          }}
        />
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, label, value, sub, accent, onClick }) {
  return (
    <div
      className="surface lift"
      onClick={onClick}
      style={{ padding: '1.125rem', cursor: onClick ? 'pointer' : 'default' }}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
        <span className="metric-label">{label}</span>
        <Icon size={16} color={accent} />
      </div>
      <div className="tabular" style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

/* ----------------------------------------------------------- this week -- */

const MACRO_UNIT = (m) => (m === 'calories' ? 'kcal' : 'g');

/** A compact labelled figure for the right-hand side of the week band. */
function WeekMetric({ icon: Icon, label, value, sub, accent = '#A78BFA', stacked = false }) {
  // Side by side on a wide screen; stacked into a narrow column on a phone,
  // where an icon beside two lines of text leaves no room for either.
  return (
    <div style={{
      display: 'flex',
      flexDirection: stacked ? 'column' : 'row',
      gap: stacked ? '0.2rem' : '0.625rem',
      alignItems: stacked ? 'flex-start' : 'flex-start',
      minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', minWidth: 0 }}>
        <Icon size={stacked ? 13 : 15} color={accent} style={{ flexShrink: 0 }} />
        <span style={{
          fontSize: stacked ? '0.625rem' : '0.6875rem', color: '#667085',
          letterSpacing: '0.04em', textTransform: 'uppercase',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {label}
        </span>
      </div>
      <div style={{ minWidth: 0, width: '100%' }}>
        <div className="tabular" style={{
          fontSize: stacked ? '0.9375rem' : '1.0625rem', fontWeight: 700, marginTop: 1,
        }}>
          {value}
        </div>
        {sub && (
          <div style={{
            fontSize: stacked ? '0.625rem' : '0.6875rem', color: '#667085',
            marginTop: 1, lineHeight: 1.35,
          }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * The wide row: what you are working on, and how the week is going.
 *
 * This space used to hold the weight goal - one number that moves a few times
 * a month, given the most prominent horizontal band on the screen. Challenges
 * were meanwhile reduced to a count in a small tile, which told you there were
 * three of them and nothing about whether you were close to finishing any.
 *
 * Everything here is already computed server-side by the adherence service, so
 * this costs no extra requests.
 */
/**
 * A slice of the leaderboard centred on you.
 *
 * Showing only the top five is demotivating for everyone outside it and
 * uninformative for everyone in it - the useful question is "who is just
 * ahead of me", which is the only gap you can actually close.
 */
function MiniBoard({ board, onNavigate, isPhone = false }) {
  const entries = board?.entries || [];
  if (entries.length < 2) return null;

  const myIndex = entries.findIndex((e) => e.is_you);
  // Centre on you when you are outside the visible top, otherwise just show
  // the top - being 1st should look like being 1st.
  const window = myIndex > 2
    ? entries.slice(Math.max(0, myIndex - 1), myIndex + 2)
    : entries.slice(0, 3);

  return (
    <div style={{
      display: 'grid', gap: '0.45rem', minWidth: 0,
      ...(isPhone ? { paddingTop: '1rem', borderTop: '1px solid #2A3240' } : {}),
    }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '0.15rem' }}>
        <span style={{ fontSize: '0.6875rem', color: '#667085', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
          Leaderboard
        </span>
        <button
          onClick={() => onNavigate('profile')}
          style={{
            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            color: '#A78BFA', fontSize: '0.6875rem', fontWeight: 600,
          }}
        >
          All
        </button>
      </div>

      {window.map((e) => (
        <button
          key={e.user_id}
          onClick={() => onNavigate('profile')}
          className="flex items-center justify-between"
          style={{
            padding: '0.4rem 0.55rem', borderRadius: '0.4rem', cursor: 'pointer',
            background: e.is_you ? 'rgba(139,92,246,0.14)' : '#12151B',
            border: `1px solid ${e.is_you ? 'rgba(139,92,246,0.35)' : '#2A3240'}`,
            gap: '0.5rem', width: '100%', textAlign: 'left',
          }}
        >
          <span className="tabular" style={{ color: '#667085', fontSize: '0.75rem', width: 16, flexShrink: 0 }}>
            {e.rank}
          </span>
          <span style={{
            flex: 1, minWidth: 0, fontSize: '0.75rem',
            fontWeight: e.is_you ? 700 : 500,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {e.is_you ? 'You' : e.name}
          </span>
          <span className="tabular" style={{ fontSize: '0.75rem', fontWeight: 600, color: '#A78BFA', flexShrink: 0 }}>
            {e.points.toLocaleString()}
          </span>
        </button>
      ))}

      {/* The gap to the person above - the only number here you can act on. */}
      {myIndex > 0 && (
        <div style={{ fontSize: '0.6875rem', color: '#667085', paddingLeft: '0.15rem' }}>
          {entries[myIndex - 1].points - entries[myIndex].points} points behind {entries[myIndex - 1].name.split(' ')[0]}
        </div>
      )}
    </div>
  );
}

function WeekBand({ challenges, summary, history, board, onNavigate }) {
  const isPhone = useIsPhone();
  // Unfinished first - a completed challenge is nice to see but it is not
  // what you can still act on today.
  const active = [...(challenges || [])]
    .sort((a, b) => (a.completed === b.completed ? 0 : a.completed ? 1 : -1))
    .slice(0, 3);

  const assessable = summary?.assessable_days || 0;
  const hits = summary?.hits || 0;
  const streak = summary?.current_streak || 0;
  const logged = history?.length
    ? history.filter((d) => d.status !== 'unlogged').length
    : 0;
  const worst = summary?.weak_points?.[0] || null;

  // With no goal and no challenges there is nothing honest to show, and an
  // empty band is worse than no band.
  if (!active.length && !assessable && !logged) {
    return (
      <button
        onClick={() => onNavigate('enhanced-challenges')}
        className="surface lift"
        style={{
          padding: '1.25rem', width: '100%', textAlign: 'left', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '0.875rem',
          background: 'linear-gradient(100deg, rgba(167,139,250,0.10), rgba(34,211,238,0.04))',
        }}
      >
        <Trophy size={20} color="#A78BFA" />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: '0.9375rem' }}>Pick up a challenge</div>
          <div style={{ fontSize: '0.8125rem', color: '#98A2B3', marginTop: 2 }}>
            A few days of logging is enough for the app to build ones that fit you.
          </div>
        </div>
        <ChevronRight size={18} color="#667085" />
      </button>
    );
  }

  return (
    <div className="surface" style={{ padding: '1.25rem' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
        <span className="section-title">This week</span>
        {assessable > 0 && (
          <span
            className={`pill ${hits === assessable ? 'pill-good' : hits ? 'pill-brand' : 'pill-warn'}`}
            style={{ fontSize: '0.6875rem' }}
          >
            {hits} of {assessable} day{assessable === 1 ? '' : 's'} on target
          </span>
        )}
      </div>

      <div style={{
        display: 'grid',
        // On a phone everything stacks. Three columns at 360px is not a tight
        // layout, it is overlapping text - which is exactly what shipped.
        gridTemplateColumns: isPhone
          ? '1fr'
          : board?.entries?.length > 1
            ? 'minmax(0,1.3fr) minmax(0,1fr) minmax(0,0.9fr)'
            : 'minmax(0,1.4fr) minmax(0,1fr)',
        gap: isPhone ? '1.25rem' : '1.5rem',
        alignItems: 'start',
      }}>
        {/* --- challenges, with progress rather than just a count --------- */}
        <div style={{ display: 'grid', gap: '0.7rem', minWidth: 0 }}>
          {active.length === 0 ? (
            <button
              onClick={() => onNavigate('enhanced-challenges')}
              style={{
                background: 'none', border: '1px dashed #2A3240', borderRadius: '0.625rem',
                padding: '0.875rem', cursor: 'pointer', color: '#98A2B3',
                fontSize: '0.8125rem', textAlign: 'left', display: 'flex',
                alignItems: 'center', gap: '0.5rem',
              }}
            >
              <Plus size={14} color="#A78BFA" />
              No challenge running — pick one built from how you actually eat
            </button>
          ) : active.map((c, i) => {
            const pct = clamp(num(c.progress_percentage));
            const done = pct >= 100 || c.completed;
            const left = num(c.days_remaining);
            return (
              <button
                key={c.challenge_id ?? i}
                onClick={() => onNavigate('enhanced-challenges')}
                style={{
                  background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                  textAlign: 'left', display: 'grid', gap: '0.3rem', minWidth: 0,
                }}
              >
                <div className="flex items-center justify-between" style={{ gap: '0.5rem' }}>
                  <span style={{
                    fontSize: '0.8125rem', fontWeight: 600, whiteSpace: 'nowrap',
                    overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0,
                  }}>
                    {done && <Check size={12} color="#34D399" style={{ marginRight: 4 }} />}
                    {c.title || 'Challenge'}
                  </span>
                  <span className="tabular" style={{
                    fontSize: '0.75rem', color: done ? '#34D399' : '#98A2B3', flexShrink: 0,
                  }}>
                    {Math.round(num(c.current_value))}/{Math.round(num(c.target_value))}
                    {c.unit ? ` ${c.unit}` : ''}
                  </span>
                </div>
                <div className="macro-track" style={{ height: '0.3125rem' }}>
                  <div
                    className="macro-fill macro-fill-animate"
                    style={{
                      width: `${pct}%`,
                      background: done
                        ? '#34D399'
                        : 'linear-gradient(90deg,#8B5CF6,#22D3EE)',
                    }}
                  />
                </div>
                {/* Days left is the bit that makes a challenge feel live. A
                    percentage alone gives no sense of whether it is winnable. */}
                <div style={{ fontSize: '0.6875rem', color: '#667085' }}>
                  {done ? 'complete' : left > 0 ? `${left} day${left === 1 ? '' : 's'} left` : 'last day'}
                </div>
              </button>
            );
          })}

          {(challenges || []).length > 3 && (
            <button
              onClick={() => onNavigate('enhanced-challenges')}
              style={{
                background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                color: '#A78BFA', fontSize: '0.75rem', fontWeight: 600, textAlign: 'left',
              }}
            >
              +{challenges.length - 3} more
            </button>
          )}
        </div>

        {/* --- the week in three figures ---------------------------------- */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: isPhone ? 'repeat(3, minmax(0,1fr))' : '1fr',
          gap: isPhone ? '0.75rem' : '0.875rem',
          minWidth: 0,
          ...(isPhone ? {
            paddingTop: '1rem', borderTop: '1px solid #2A3240',
          } : {}),
        }}>
          <WeekMetric
            icon={Flame} accent="#FBBF24" label="Streak"
            stacked={isPhone}
            value={streak ? `${streak} day${streak === 1 ? '' : 's'}` : '—'}
            sub={streak ? 'on target in a row' : 'no run going yet'}
          />
          <WeekMetric
            icon={UtensilsCrossed} accent="#22D3EE" label="Logged"
            stacked={isPhone}
            value={history?.length ? `${logged}/${history.length}` : '—'}
            sub="days with meals recorded"
          />
          {/* The single most actionable line on the dashboard: not "you
              missed", but which macro, how often, and by how much. */}
          <WeekMetric
            icon={Target} accent={worst ? '#F87171' : '#34D399'} label="To fix"
            stacked={isPhone}
            value={worst
              ? `${worst.direction === 'short' ? '−' : '+'}${Math.abs(worst.average_delta).toFixed(0)}${MACRO_UNIT(worst.macro)}`
              : 'nothing'}
            sub={worst
              ? `${worst.macro} on ${worst.days} of ${worst.of} days`
              : assessable ? 'every macro in band' : 'not enough logged yet'}
          />
        </div>

        <MiniBoard board={board} onNavigate={onNavigate} isPhone={isPhone} />
      </div>

      {summary?.headline && (
        <div style={{
          marginTop: '1rem', paddingTop: '0.875rem', borderTop: '1px solid #2A3240',
          fontSize: '0.75rem', color: '#98A2B3', lineHeight: 1.5,
        }}>
          {summary.headline}
        </div>
      )}
    </div>
  );
}

/**
 * Weight goal, as a tile rather than a full-width bar.
 *
 * It had an entire row to itself for one number that moves a few times a
 * month. The tile keeps everything that was on the bar - start, target,
 * current, percentage, direction - and gives the row back to things that
 * change daily.
 */
function WeightTile({ weight, goal, onNavigate }) {
  const entries = weight?.entries || [];
  const target = goal?.target_weight;
  const current = entries.length ? entries[entries.length - 1].weight_kg : weight?.latest;

  // No goal or no weigh-in: fall back to a plain reading rather than
  // rendering an empty progress bar that implies zero progress.
  if (!target || !entries.length) {
    return (
      <StatTile
        icon={Scale} accent="#34D399" label="Weight"
        value={current ? `${current} kg` : '—'}
        sub={target ? `target ${target} kg` : 'log your first'}
        onClick={() => onNavigate('set-goals')}
      />
    );
  }

  const start = entries[0].weight_kg;
  const total = Math.abs(target - start);
  const done = Math.abs(current - start);
  const pct = total > 0 ? clamp((done / total) * 100) : 0;
  const movedRight =
    Math.sign(target - start) === Math.sign(current - start) || current === start;

  const change = current - start;
  const remaining = Math.abs(target - current);
  const Trend = change < -0.05 ? TrendingDown : change > 0.05 ? TrendingUp : Minus;

  return (
    <div
      className="surface lift"
      onClick={() => onNavigate('view-progress')}
      style={{ padding: '1.125rem', cursor: 'pointer' }}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
        <span className="metric-label">Weight goal</span>
        <Scale size={16} color="#34D399" />
      </div>

      <div className="flex items-center justify-between" style={{ gap: '0.5rem' }}>
        <span className="tabular" style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
          {current} kg
        </span>
        <span
          className={`pill ${movedRight ? 'pill-good' : 'pill-warn'}`}
          style={{ fontSize: '0.6875rem' }}
        >
          <Trend size={12} />
          {change > 0 ? '+' : ''}{change.toFixed(1)}
        </span>
      </div>

      <div className="macro-track" style={{ height: '0.3125rem', marginTop: '0.6rem' }}>
        <div
          className="macro-fill macro-fill-animate"
          style={{
            width: `${pct}%`,
            background: 'linear-gradient(90deg,#8B5CF6,#22D3EE)',
          }}
        />
      </div>

      <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 6 }}>
        {remaining < 0.05
          ? `target reached · ${target} kg`
          : `${remaining.toFixed(1)} kg to ${target} · ${Math.round(pct)}% there`}
      </div>
    </div>
  );
}

export default function Dashboard({
  user, dashboardData, onNavigate, isLoading, injuries, apiBase, onInjuryChanged,
  workout, board, onWorkoutLogged,
}) {
  const stats = dashboardData?.dailyStats || {};
  // Today's meals in time order, plus how the completed days went. The old
  // `recentMeals` was the last N logs whenever they happened, which is a
  // different question - and one nobody was asking.
  const timeline = dashboardData?.timeline || [];
  const history = dashboardData?.adherenceHistory || [];
  const summary = dashboardData?.adherenceSummary || null;
  const challenges = dashboardData?.challenges || [];
  const goals = dashboardData?.goals || [];
  const weight = dashboardData?.weight;

  const goal = goals.find((g) => g.is_active) || goals[0] || null;
  const hasGoal = Boolean(goal?.target_calories);

  const calorieTarget = num(goal?.target_calories);
  const proteinTarget = num(goal?.target_protein);
  const carbTarget = num(goal?.target_carbs);
  const fatTarget = num(goal?.target_fat);

  const consumed = num(stats.total_calories);
  const protein = num(stats.total_protein);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = (user?.full_name || user?.username || '').split(' ')[0] || 'there';

  const goalLabel = goal?.goal_type
    ? goal.goal_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : null;

  if (isLoading) {
    return (
      <div style={{ display: 'grid', gap: '1rem' }}>
        <div className="skeleton" style={{ height: 40, width: 260 }} />
        <div className="skeleton" style={{ height: 300 }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '1rem' }}>
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 110 }} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div className="metric-label">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', marginTop: 4 }}>
            {greeting}, {firstName}
          </h1>
          {goalLabel && (
            <span className="pill pill-brand" style={{ marginTop: 8 }}>
              <Target size={12} /> {goalLabel}
            </span>
          )}
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('log-meal')}>
          <Plus size={16} style={{ marginRight: 6 }} /> Log a meal
        </button>
      </div>

      {/* No goal yet */}
      {!hasGoal && (
        <button
          onClick={() => onNavigate('set-goals')}
          className="surface-hero lift"
          style={{
            padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem',
            textAlign: 'left', cursor: 'pointer', width: '100%',
            borderColor: 'rgba(139,92,246,0.35)',
          }}
        >
          <div className="flex items-center justify-center" style={{
            width: 44, height: 44, borderRadius: 12, flexShrink: 0,
            background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
          }}>
            <Target size={20} color="#fff" />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>Set a goal to unlock targets</div>
            <div style={{ fontSize: '0.8125rem', color: '#98A2B3', marginTop: 2 }}>
              Pick what you're aiming for and we'll work out your calories and macros.
            </div>
          </div>
          <ChevronRight size={18} color="#667085" />
        </button>
      )}

      {/* Rings + macros */}
      <div className="surface-hero dash-hero" style={{ padding: '1.75rem', display: 'flex', gap: '2rem', alignItems: 'center' }}>
        <GoalRings
          calories={consumed} calorieTarget={calorieTarget}
          protein={protein} proteinTarget={proteinTarget}
          hasGoal={hasGoal}
        />
        <div style={{ flex: 1, minWidth: 220, display: 'grid', gap: '1.125rem' }}>
          <div className="flex items-center justify-between">
            <span className="metric-label">Macronutrients</span>
            <span className="pill pill-brand">
              {num(stats.meal_count)} {num(stats.meal_count) === 1 ? 'meal' : 'meals'} today
            </span>
          </div>
          <MacroBar label="Protein" grams={protein} target={proteinTarget} color="#22D3EE" hasGoal={hasGoal} delay={0.05} />
          <MacroBar label="Carbs" grams={num(stats.total_carbs)} target={carbTarget} color="#A78BFA" hasGoal={hasGoal} delay={0.12} />
          <MacroBar label="Fat" grams={num(stats.total_fat)} target={fatTarget} color="#FBBF24" hasGoal={hasGoal} delay={0.19} />
        </div>
      </div>

      {/* The wide row now carries what changes daily - challenges in
          progress, the streak, logging consistency and the macro to fix -
          instead of a weight bar that moves a few times a month. */}
      <WeekBand
        challenges={challenges}
        summary={summary}
        history={history}
        board={board}
        onNavigate={onNavigate}
      />

      {/* Training, answerable from the first screen. The app produced workout
          plans for months and never asked whether any of them happened -
          putting the question behind a profile tab would keep it unanswered. */}
      <WorkoutCheckIn
        apiBase={apiBase}
        workout={workout}
        onLogged={onWorkoutLogged}
        compact
      />

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '1rem' }}>
        <StatTile
          icon={Flame} accent="#FBBF24" label="Calories"
          value={consumed.toLocaleString()}
          sub={hasGoal ? `${Math.round((consumed / calorieTarget) * 100)}% of target` : 'no target set'}
        />
        <StatTile
          icon={UtensilsCrossed} accent="#22D3EE" label="Meals"
          value={num(stats.meal_count)} sub="logged today"
          onClick={() => onNavigate('log-meal')}
        />
        {/* Weight goal moved down here, keeping its progress track. */}
        <WeightTile weight={weight} goal={goal} onNavigate={onNavigate} />
        {/* Protein replaces the challenge count, which said "3" and nothing
            about whether any of them were close to done - that now lives in
            the band above with actual progress. Protein is the macro most
            often missed, and the one worth watching mid-day. */}
        <StatTile
          icon={Target} accent="#22D3EE" label="Protein"
          value={`${Math.round(protein)}g`}
          sub={hasGoal && proteinTarget
            ? (protein >= proteinTarget
                ? 'target met'
                : `${Math.round(proteinTarget - protein)}g to go`)
            : 'no target set'}
          onClick={() => onNavigate('log-meal')}
        />
      </div>

      {/* Injuries, in full, right here.
          An injury changes every workout, meal and challenge the app produces,
          so checking in on it should take one tap from the screen you open
          first - not a trip to another tab. The card collapses to nothing when
          there is no injury to report. */}
      {injuries?.injuries?.length > 0 && (
        <InjuryTracker data={injuries} apiBase={apiBase} onChanged={onInjuryChanged} />
      )}

      {/* Assistant */}
      <button
        onClick={() => onNavigate('chatbot')}
        className="surface lift"
        style={{
          padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem',
          textAlign: 'left', cursor: 'pointer', width: '100%',
          background: 'linear-gradient(100deg, rgba(139,92,246,0.14), rgba(34,211,238,0.05))',
          borderColor: 'rgba(139,92,246,0.3)',
        }}
      >
        <div className="flex items-center justify-center" style={{
          width: 44, height: 44, borderRadius: 12, flexShrink: 0,
          background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
        }}>
          <MessageSquare size={20} color="#fff" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>Ask your AI coach</div>
          <div style={{ fontSize: '0.8125rem', color: '#98A2B3', marginTop: 2 }}>
            {hasGoal
              ? `Plan meals that fit ${calorieTarget.toLocaleString()} kcal`
              : 'Plan meals, adapt workouts, or check what to eat next'}
          </div>
        </div>
        <ChevronRight size={18} color="#667085" />
      </button>

      {/* Today, and how the week has gone.
          This replaced "Recent meals", which showed the last five logs
          regardless of when - so at 9am it was mostly yesterday's dinner, and
          there was no way to see what you had actually eaten today or whether
          any recent day had hit its targets. */}
      <div className="surface" style={{ padding: '1.25rem' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
          <span className="section-title">Today</span>
          <button
            onClick={() => onNavigate('view-progress')}
            style={{ background: 'none', border: 'none', color: '#A78BFA', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}
          >
            View all
          </button>
        </div>

        <AdherenceStrip history={history} summary={summary} />

        {timeline.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem 1rem' }}>
            <Sparkles size={26} color="#3A4453" style={{ marginBottom: 10 }} />
            <div style={{ color: '#98A2B3', fontSize: '0.875rem' }}>Nothing logged yet today</div>
            <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => onNavigate('log-meal')}>
              Log your first meal
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {timeline.map((meal, i) => {
              // Gap since the previous meal. Worth showing because a seven
              // hour hole between lunch and dinner explains an evening binge
              // far better than the calorie total does.
              const previous = timeline[i - 1];
              const gapHours = previous && meal.local_hour != null && previous.local_hour != null
                ? meal.local_hour - previous.local_hour
                : null;

              return (
                <React.Fragment key={meal.id ?? i}>
                  {gapHours != null && gapHours >= 5 && (
                    <div style={{
                      fontSize: '0.6875rem', color: '#667085',
                      paddingLeft: '0.75rem', display: 'flex',
                      alignItems: 'center', gap: '0.4rem',
                    }}>
                      <span style={{ width: 1, height: 12, background: '#2A3240' }} />
                      {gapHours} hours
                    </div>
                  )}
                  <div
                    className="flex items-center justify-between lift"
                    style={{
                      padding: '0.75rem', borderRadius: '0.625rem',
                      background: '#12151B', border: '1px solid #2A3240',
                    }}
                  >
                    <div style={{
                      fontSize: '0.75rem', color: '#98A2B3', fontVariantNumeric: 'tabular-nums',
                      width: 44, flexShrink: 0,
                    }}>
                      {meal.local_time || mealTime(meal.logged_at)}
                    </div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: '0.875rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {meal.name || 'Meal'}
                        {num(meal.quantity) > 1 && (
                          <span style={{ color: '#667085', fontWeight: 500 }}>
                            {' '}&times;{formatQty(meal.quantity)}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 2 }}>
                        <span style={{ textTransform: 'capitalize' }}>{meal.meal_type || 'meal'}</span>
                        {num(meal.protein) > 0 && <> · {Math.round(num(meal.protein))}g protein</>}
                      </div>
                    </div>
                    <div className="tabular" style={{ fontSize: '0.875rem', fontWeight: 700, color: '#FBBF24', flexShrink: 0 }}>
                      {Math.round(num(meal.calories))} kcal
                    </div>
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
