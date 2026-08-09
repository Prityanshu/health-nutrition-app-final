import React, { useState } from 'react';
import {
  Dumbbell, Moon, Check, Activity, Trophy, TrendingUp, Loader2,
} from 'lucide-react';

/**
 * Did you train today?
 *
 * One component, two sizes. It lives on the dashboard because that is the
 * screen people actually open, and on the profile because that is where the
 * history and points live - and a second implementation would be a second
 * thing to keep in step.
 *
 * Three answers, not two. "Rest" and "no answer" are different facts: one is
 * a deliberate part of a programme and earns points, the other is silence.
 * Collapsing them would mean the only way to keep a streak is to train every
 * single day, which is bad training advice dressed up as gamification.
 */

const authHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${localStorage.getItem('token')}`,
});

const WORKOUT_TYPES = [
  { key: 'strength', label: 'Strength', icon: Dumbbell },
  { key: 'cardio', label: 'Cardio', icon: Activity },
  { key: 'sport', label: 'Sport', icon: Trophy },
  { key: 'mobility', label: 'Mobility', icon: TrendingUp },
];

const STATUS_COLOUR = { done: '#F87171', rest: '#A78BFA', skipped: '#2A3240' };

/** Mon…Sun initial for a YYYY-MM-DD string, parsed as a local date. */
const dayInitial = (iso) => {
  const [y, m, d] = String(iso).split('-').map(Number);
  if (!y) return '';
  return new Date(y, m - 1, d)
    .toLocaleDateString(undefined, { weekday: 'short' })
    .slice(0, 1);
};

export default function WorkoutCheckIn({ apiBase, workout, onLogged, compact = false }) {
  const [expanded, setExpanded] = useState(false);
  const [type, setType] = useState(null);
  const [minutes, setMinutes] = useState(45);
  const [intensity, setIntensity] = useState(7);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState('');

  const already = workout?.today;

  const send = async (status, detail = {}) => {
    setBusy(true);
    setResult('');
    try {
      const res = await fetch(`${apiBase}/profile/workout`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ status, ...detail }),
      });
      const data = await res.json();
      if (data.success) {
        setResult(data.message);
        setExpanded(false);
        onLogged?.(data);
      } else {
        setResult('Could not save that.');
      }
    } catch {
      setResult('Could not reach the server.');
    } finally {
      setBusy(false);
    }
  };

  const strip = workout?.recent?.length > 0 && (
    <div style={{ display: 'flex', gap: '0.3rem', marginTop: compact ? '0.75rem' : '1rem' }}>
      {workout.recent.map((w) => (
        <div key={w.date} style={{ flex: 1, display: 'grid', gap: 3, justifyItems: 'center' }}>
          <span
            title={`${w.date} — ${w.status}${w.minutes ? `, ${w.minutes} min` : ''}`}
            style={{
              width: '100%', height: 5, borderRadius: 3,
              background: STATUS_COLOUR[w.status] || '#2A3240',
            }}
          />
          <span style={{ fontSize: '0.5625rem', color: '#667085' }}>
            {dayInitial(w.date)}
          </span>
        </div>
      ))}
    </div>
  );

  return (
    <div className="surface" style={{ padding: compact ? '1.125rem' : '1.25rem' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '0.875rem' }}>
        <span className={compact ? 'metric-label' : 'section-title'}>
          {compact ? 'Training today' : 'Did you train today?'}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {workout?.done_this_week > 0 && (
            <span className="pill pill-muted" style={{ fontSize: '0.625rem' }}>
              {workout.done_this_week} this week
            </span>
          )}
          <Dumbbell size={15} color="#F87171" />
        </div>
      </div>

      {already && !expanded ? (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.625rem',
          padding: '0.75rem', borderRadius: '0.625rem',
          background: already.status === 'done'
            ? 'rgba(248,113,113,0.09)' : 'rgba(167,139,250,0.09)',
          border: `1px solid ${already.status === 'done'
            ? 'rgba(248,113,113,0.28)' : 'rgba(167,139,250,0.28)'}`,
        }}>
          {already.status === 'done'
            ? <Check size={15} color="#F87171" />
            : <Moon size={15} color="#A78BFA" />}
          <div style={{ flex: 1, fontSize: '0.8125rem', minWidth: 0 }}>
            {already.status === 'done' ? (
              <>
                Trained{already.workout_type ? ` — ${already.workout_type}` : ''}
                {already.minutes ? `, ${already.minutes} min` : ''}
                {already.intensity ? ` at ${already.intensity}/10` : ''}
              </>
            ) : already.status === 'rest' ? 'Rest day' : 'Marked as skipped'}
          </div>
          <button
            onClick={() => setExpanded(true)}
            style={{
              background: 'none', border: 'none', color: '#A78BFA',
              fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', flexShrink: 0,
            }}
          >
            Change
          </button>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              className={`toggle-chip ${expanded ? 'is-active' : ''}`}
              onClick={() => setExpanded(true)}
              disabled={busy}
            >
              <Check size={14} /> {compact ? 'Trained' : 'Yes, I trained'}
            </button>
            <button className="toggle-chip" onClick={() => send('rest')} disabled={busy}>
              <Moon size={14} /> Rest day
            </button>
            <button className="toggle-chip" onClick={() => send('skipped')} disabled={busy}>
              Not today
            </button>
          </div>

          {expanded && (
            <div style={{ display: 'grid', gap: '0.875rem', marginTop: '1rem' }}>
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                {WORKOUT_TYPES.map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    className={`suggest-chip ${type === key ? 'is-active' : ''}`}
                    onClick={() => setType(type === key ? null : key)}
                  >
                    <Icon size={12} /> {label}
                  </button>
                ))}
              </div>

              <div style={{ display: 'grid', gap: '0.75rem' }}>
                <div>
                  <div className="flex items-center justify-between" style={{ marginBottom: '0.4rem' }}>
                    <span style={{ fontSize: '0.75rem', color: '#98A2B3' }}>How long</span>
                    <span className="pill pill-muted tabular" style={{ fontSize: '0.6875rem' }}>
                      {minutes} min
                    </span>
                  </div>
                  <input
                    type="range" min={5} max={180} step={5} value={minutes}
                    onChange={(e) => setMinutes(Number(e.target.value))}
                    className="range-slider"
                    style={{ '--pct': `${((minutes - 5) / 175) * 100}%` }}
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between" style={{ marginBottom: '0.4rem' }}>
                    <span style={{ fontSize: '0.75rem', color: '#98A2B3' }}>How hard it felt</span>
                    <span className="pill pill-muted tabular" style={{ fontSize: '0.6875rem' }}>
                      {intensity}/10
                    </span>
                  </div>
                  <input
                    type="range" min={1} max={10} value={intensity}
                    onChange={(e) => setIntensity(Number(e.target.value))}
                    className="range-slider"
                    style={{ '--pct': `${intensity * 10}%` }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, justifyContent: 'center' }}
                  disabled={busy}
                  onClick={() => send('done', { workout_type: type, minutes, intensity })}
                >
                  {busy ? <Loader2 size={15} className="spin" /> : 'Log it'}
                </button>
                <button
                  className="btn"
                  onClick={() => setExpanded(false)}
                  style={{ border: '1px solid #2A3240' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {result && (
        <div style={{ fontSize: '0.8125rem', color: '#34D399', marginTop: '0.75rem' }}>
          {result}
        </div>
      )}

      {strip}
    </div>
  );
}
