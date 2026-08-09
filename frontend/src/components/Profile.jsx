import React, { useState, useEffect, useCallback } from 'react';
import {
  Flame, Trophy, Pencil, Scale, Ruler, Cake, Activity, Loader2,
  ChevronRight, Info,
} from 'lucide-react';
import WorkoutCheckIn from './WorkoutCheckIn';
import ServerSetup from './ServerSetup';
import { isNativeApp } from '../apiBase';

/**
 * Profile - who you are, what you have done, and what it earned.
 *
 * The sidebar has said "View profile" since the first build and never gone
 * anywhere. Three things live here that had no home before:
 *
 *   1. Body stats you can actually edit. They were captured once at
 *      registration and then silently went stale, quietly degrading every
 *      calorie target derived from them.
 *   2. Points, with the ledger visible. A score you cannot explain is a score
 *      nobody trusts, so every point is traceable to the day and rule that
 *      produced it.
 *   3. The daily question the app has never asked: did you train today? It
 *      produced workout plans for months and never once checked.
 */

const authHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${localStorage.getItem('token')}`,
});

const ACTIVITY_LEVELS = [
  { key: 'sedentary', label: 'Sedentary' },
  { key: 'lightly_active', label: 'Light' },
  { key: 'moderately_active', label: 'Moderate' },
  { key: 'very_active', label: 'Very active' },
  { key: 'extra_active', label: 'Athlete' },
];

const num = (v) => (typeof v === 'number' && !Number.isNaN(v) ? v : 0);

/* ------------------------------------------------------------- points -- */

function PointsCard({ points, onExplain }) {
  const pct = Math.round((points?.progress || 0) * 100);
  const series = points?.last_30_days || [];
  const peak = Math.max(1, ...series.map((d) => d.points));

  return (
    <div className="surface" style={{ padding: '1.25rem' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
        <div>
          <div className="section-title">{points?.title || 'Getting started'}</div>
          <div className="section-sub">Level {points?.level || 1}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="tabular" style={{ fontSize: '1.875rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
            {(points?.total || 0).toLocaleString()}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#667085' }}>points</div>
        </div>
      </div>

      <div className="macro-track" style={{ height: '0.5rem' }}>
        <div
          className="macro-fill macro-fill-animate"
          style={{ width: `${pct}%`, background: 'linear-gradient(90deg,#8B5CF6,#22D3EE)' }}
        />
      </div>
      <div className="flex items-center justify-between" style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#667085' }}>
        <span>{pct}% to level {(points?.level || 1) + 1}</span>
        {points?.to_next != null && (
          <span>{points.to_next} points to “{points.next_title}”</span>
        )}
      </div>

      {/* 30 days as bars. A single total says nothing about direction, and
          direction is the only part you can still do anything about. */}
      {series.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 44, marginTop: '1.125rem' }}>
          {series.map((d) => (
            <span
              key={d.date}
              title={`${d.date} — ${d.points} points`}
              style={{
                flex: 1,
                height: `${Math.max(2, (d.points / peak) * 100)}%`,
                borderRadius: 2,
                background: d.points ? '#8B5CF6' : '#232A35',
                opacity: d.points ? 0.55 + (d.points / peak) * 0.45 : 1,
              }}
            />
          ))}
        </div>
      )}

      {points?.breakdown?.length > 0 && (
        <div style={{ marginTop: '1.125rem', display: 'grid', gap: '0.5rem' }}>
          {points.breakdown.slice(0, 5).map((b) => (
            <div key={b.reason} className="flex items-center justify-between" style={{ fontSize: '0.8125rem' }}>
              <span style={{ color: '#98A2B3' }}>
                {b.label}
                <span style={{ color: '#667085' }}> ×{b.times}</span>
              </span>
              <span className="tabular" style={{ fontWeight: 600 }}>+{b.points}</span>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onExplain}
        style={{
          background: 'none', border: 'none', padding: 0, marginTop: '0.875rem',
          color: '#A78BFA', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 4,
        }}
      >
        <Info size={13} /> How points work
      </button>
    </div>
  );
}

/* ------------------------------------------------------------- stats --- */

function BodyStats({ user, bmi, apiBase, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setForm({
      full_name: user?.full_name || '', age: user?.age || '',
      height: user?.height || '', weight: user?.weight || '',
      activity_level: user?.activity_level || 'moderately_active',
    });
  }, [user]);

  const save = async () => {
    setBusy(true);
    try {
      const body = {
        full_name: form.full_name || null,
        age: form.age ? Number(form.age) : null,
        height: form.height ? Number(form.height) : null,
        weight: form.weight ? Number(form.weight) : null,
        activity_level: form.activity_level || null,
      };
      const res = await fetch(`${apiBase}/profile`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(body),
      });
      if (res.ok) { setEditing(false); onSaved?.(); }
    } finally {
      setBusy(false);
    }
  };

  const rows = [
    { icon: Cake, label: 'Age', value: user?.age ? `${user.age}` : '—' },
    { icon: Ruler, label: 'Height', value: user?.height ? `${user.height} cm` : '—' },
    { icon: Scale, label: 'Weight', value: user?.weight ? `${user.weight} kg` : '—' },
    {
      icon: Activity, label: 'Activity',
      value: ACTIVITY_LEVELS.find((a) => a.key === user?.activity_level)?.label || '—',
    },
  ];

  return (
    <div className="surface" style={{ padding: '1.25rem' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
        <span className="section-title">Your details</span>
        <button
          onClick={() => setEditing(!editing)}
          style={{
            background: 'none', border: 'none', color: '#A78BFA', cursor: 'pointer',
            fontSize: '0.75rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          <Pencil size={13} /> {editing ? 'Cancel' : 'Edit'}
        </button>
      </div>

      {editing ? (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          <input
            className="form-input" placeholder="Full name" value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '0.5rem' }}>
            <input className="form-input" type="number" placeholder="Age" value={form.age}
                   onChange={(e) => setForm({ ...form, age: e.target.value })} />
            <input className="form-input" type="number" placeholder="Height cm" value={form.height}
                   onChange={(e) => setForm({ ...form, height: e.target.value })} />
            <input className="form-input" type="number" placeholder="Weight kg" value={form.weight}
                   onChange={(e) => setForm({ ...form, weight: e.target.value })} />
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            {ACTIVITY_LEVELS.map((a) => (
              <button
                key={a.key}
                className={`suggest-chip ${form.activity_level === a.key ? 'is-active' : ''}`}
                onClick={() => setForm({ ...form, activity_level: a.key })}
              >
                {a.label}
              </button>
            ))}
          </div>
          {/* Changing weight here also files a check-in, so the trend chart
              keeps its history instead of the old value being overwritten. */}
          <div style={{ fontSize: '0.6875rem', color: '#667085', lineHeight: 1.5 }}>
            Updating your weight also records a check-in, so your progress chart keeps the history.
          </div>
          <button className="btn btn-primary" style={{ justifyContent: 'center' }}
                  onClick={save} disabled={busy}>
            {busy ? <Loader2 size={15} className="spin" /> : 'Save'}
          </button>
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(110px,1fr))', gap: '0.875rem' }}>
            {rows.map(({ icon: Icon, label, value }) => (
              <div key={label}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
                  <Icon size={13} color="#667085" />
                  <span style={{ fontSize: '0.6875rem', color: '#667085', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {label}
                  </span>
                </div>
                <div className="tabular" style={{ fontSize: '1.0625rem', fontWeight: 600 }}>{value}</div>
              </div>
            ))}
          </div>

          {bmi && (
            <div style={{
              marginTop: '1rem', paddingTop: '0.875rem', borderTop: '1px solid #2A3240',
              fontSize: '0.75rem', color: '#98A2B3', lineHeight: 1.5,
            }}>
              BMI <span className="tabular" style={{ color: '#EEF2F7', fontWeight: 600 }}>{bmi.value}</span>
              {' — '}{bmi.band}. <span style={{ color: '#667085' }}>{bmi.note}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- main -- */

export default function Profile({ apiBase, user: authUser, onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [explain, setExplain] = useState(false);
  const [board, setBoard] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/profile`, { headers: authHeaders() });
      if (res.ok) setData(await res.json());
    } catch {
      /* leave whatever we had rather than blanking the screen */
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    fetch(`${apiBase}/profile/leaderboard?days=30&limit=5`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.success && setBoard(d))
      .catch(() => {});
  }, [apiBase]);

  const u = data?.user || authUser || {};
  const initials = (u.full_name || u.username || 'A')
    .split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();

  if (loading && !data) {
    return (
      <div className="surface" style={{ padding: '3rem', textAlign: 'center' }}>
        <Loader2 size={22} className="spin" color="#667085" />
      </div>
    );
  }

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      {/* identity */}
      <div className="surface" style={{
        padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.125rem',
        background: 'linear-gradient(100deg, rgba(139,92,246,0.14), rgba(34,211,238,0.05))',
      }}>
        <div style={{
          width: 62, height: 62, borderRadius: 999, flexShrink: 0,
          background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.25rem', fontWeight: 700, color: '#0B0E14',
        }}>
          {initials}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em' }}>
            {u.full_name || u.username}
          </div>
          <div style={{ fontSize: '0.8125rem', color: '#98A2B3', marginTop: 2 }}>
            {u.email}
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.6rem', flexWrap: 'wrap' }}>
            <span className="pill pill-brand" style={{ fontSize: '0.6875rem' }}>
              <Trophy size={11} /> Level {data?.points?.level || 1}
            </span>
            {num(data?.points?.this_week) > 0 && (
              <span className="pill pill-good" style={{ fontSize: '0.6875rem' }}>
                +{data.points.this_week} this week
              </span>
            )}
            {board?.your_rank && (
              <span className="pill pill-muted" style={{ fontSize: '0.6875rem' }}>
                #{board.your_rank} in the last 30 days
              </span>
            )}
          </div>
        </div>
      </div>

      <WorkoutCheckIn apiBase={apiBase} workout={data?.workout} onLogged={load} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: '1.25rem' }}>
        <PointsCard points={data?.points} onExplain={() => setExplain(!explain)} />
        <BodyStats user={u} bmi={data?.bmi} apiBase={apiBase} onSaved={load} />
      </div>

      {explain && (
        <div className="surface" style={{ padding: '1.25rem' }}>
          <div className="section-title" style={{ marginBottom: '0.75rem' }}>How points work</div>
          <div style={{ fontSize: '0.8125rem', color: '#98A2B3', lineHeight: 1.6 }}>
            <p style={{ marginTop: 0 }}>
              Logging earns the base, hitting your targets earns a bonus. Effort is
              weighted heavily on purpose — a day where you logged everything honestly
              and went over still scores, because hiding a bad day is the habit worth
              avoiding.
            </p>
            <div style={{ display: 'grid', gap: '0.4rem', marginTop: '0.875rem' }}>
              {[
                ['Each meal logged', '4 pts', 'up to 4 meals'],
                ['Full day logged', '12 pts', '3 or more meals'],
                ['All macros on target', '25 pts', 'the big one'],
                ['Each macro in band', '4 pts', 'when the day missed'],
                ['Workout completed', '30 pts', 'plus up to 15 for effort'],
                ['Rest day', '8 pts', 'recovery counts'],
                ['Weight check-in', '6 pts', ''],
                ['Streak bonus', '3 pts × days', 'capped at 30'],
              ].map(([what, worth, note]) => (
                <div key={what} className="flex items-center justify-between" style={{ fontSize: '0.8125rem' }}>
                  <span>{what} {note && <span style={{ color: '#667085' }}>· {note}</span>}</span>
                  <span className="tabular" style={{ fontWeight: 600, color: '#A78BFA' }}>{worth}</span>
                </div>
              ))}
            </div>
            <p style={{ marginBottom: 0, color: '#667085', fontSize: '0.75rem' }}>
              Points are never taken away.
            </p>
          </div>
        </div>
      )}

      {/* records */}
      {data?.records?.length > 0 && (
        <div className="surface" style={{ padding: '1.25rem' }}>
          <div className="section-title" style={{ marginBottom: '1rem' }}>Your records</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '1rem' }}>
            {data.records.map((r) => (
              <div key={r.label}>
                <div style={{ fontSize: '0.6875rem', color: '#667085', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {r.label}
                </div>
                <div className="tabular" style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: 3 }}>
                  {r.value}
                </div>
                <div style={{ fontSize: '0.6875rem', color: '#667085', marginTop: 2 }}>{r.sub}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* leaderboard preview */}
      {board?.entries?.length > 1 && (
        <div className="surface" style={{ padding: '1.25rem' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
            <span className="section-title">Last 30 days</span>
            <span style={{ fontSize: '0.6875rem', color: '#667085' }}>rolling window</span>
          </div>
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {board.entries.map((e) => (
              <div
                key={e.user_id}
                className="flex items-center justify-between"
                style={{
                  padding: '0.625rem 0.75rem', borderRadius: '0.5rem',
                  background: e.is_you ? 'rgba(139,92,246,0.12)' : '#12151B',
                  border: `1px solid ${e.is_you ? 'rgba(139,92,246,0.35)' : '#2A3240'}`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', minWidth: 0 }}>
                  <span className="tabular" style={{ width: 20, color: '#667085', fontSize: '0.8125rem' }}>
                    {e.rank}
                  </span>
                  <span style={{
                    fontSize: '0.8125rem', fontWeight: e.is_you ? 700 : 500,
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {e.is_you ? 'You' : e.name}
                  </span>
                </div>
                <span className="tabular" style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#A78BFA' }}>
                  {e.points.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Only in the app. On the web the API is on the same origin, so a
          server picker would be a setting with exactly one correct value. */}
      {isNativeApp() && <ServerSetup embedded />}

      <button
        onClick={() => onNavigate?.('view-progress')}
        className="surface lift"
        style={{
          padding: '1.125rem', display: 'flex', alignItems: 'center', gap: '0.875rem',
          textAlign: 'left', cursor: 'pointer', width: '100%',
        }}
      >
        <Flame size={18} color="#FBBF24" />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Full progress</div>
          <div style={{ fontSize: '0.75rem', color: '#98A2B3' }}>Charts, weight trend and history</div>
        </div>
        <ChevronRight size={17} color="#667085" />
      </button>
    </div>
  );
}
