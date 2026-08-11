import React, { useState, useEffect, useCallback } from 'react';
import {
  Trophy, Flame, Target, Utensils, CalendarCheck, Sparkles,
  Plus, X, Check, RefreshCw, AlertCircle, Activity,
} from 'lucide-react';
import { PageHero } from './SpecialistUI';
import { solid, tint } from '../theme';

/**
 * Challenges.
 *
 * The old screen showed a list of challenges with a title, a difficulty word
 * and a percentage, and no indication of where any of it came from. That is
 * what made them feel arbitrary: nothing on screen connected "eat more
 * protein" to the fact that this user averages 62g against a 150g target.
 * So every card here states its reason in the user's own numbers.
 *
 * Injury tracking used to live here and has moved to the dashboard. This page
 * is about what you are trying to achieve; an injury is a constraint on all of
 * it, and belongs where you look first rather than behind a tab.
 */

const TYPE_STYLE = {
  nutrition:     { icon: Utensils,      colour: '--success-rgb', label: 'Nutrition' },
  consistency:   { icon: CalendarCheck, colour: '--cyan-rgb', label: 'Consistency' },
  workout:       { icon: Activity,      colour: '--accent-soft-rgb', label: 'Training' },
  goal_oriented: { icon: Target,        colour: '--warning-rgb', label: 'Goal' },
  variety:       { icon: Sparkles,      colour: '--brand-pink-rgb', label: 'Variety' },
  hybrid:        { icon: Trophy,        colour: '--accent-soft-rgb', label: 'Mixed' },
};

function ChallengeCard({ challenge, onDrop }) {
  const style = TYPE_STYLE[challenge.type] || TYPE_STYLE.nutrition;
  const Icon = style.icon;
  const done = challenge.completed;

  return (
    <div
      className="surface lift"
      style={{
        padding: '1.15rem',
        display: 'grid',
        gap: '0.85rem',
        borderColor: done ? 'rgba(var(--success-rgb),0.35)' : undefined,
        background: done
          ? 'linear-gradient(120deg, rgba(var(--success-rgb),0.08), transparent 60%)'
          : undefined,
      }}
    >
      <div className="flex items-start justify-between" style={{ gap: '0.75rem' }}>
        <div className="flex items-start" style={{ gap: '0.7rem', minWidth: 0 }}>
          <div
            className="flex items-center justify-center"
            style={{
              width: 34, height: 34, borderRadius: 10, flexShrink: 0,
              color: solid(done ? '--success-rgb' : style.colour),
              background: tint(done ? '--success-rgb' : style.colour, 0.12),
              border: `1px solid ${tint(done ? '--success-rgb' : style.colour, 0.27)}`,
            }}
          >
            {done ? <Check size={16} /> : <Icon size={16} />}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: '0.9375rem', lineHeight: 1.35 }}>
              {challenge.title}
            </div>
            <div className="section-sub" style={{ marginTop: 2 }}>
              {challenge.description}
            </div>
          </div>
        </div>
        {!done && (
          <button
            className="ghost-btn"
            style={{ padding: '0.3rem 0.45rem', flexShrink: 0 }}
            onClick={() => onDrop(challenge.id)}
            title="Not for me"
            aria-label="Drop this challenge"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {/* Why this challenge exists, in the user's own numbers. */}
      {challenge.reason && (
        <div
          style={{
            fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--text-muted)',
            paddingLeft: '0.7rem', borderLeft: `2px solid ${tint(style.colour, 0.33)}`,
          }}
        >
          {challenge.reason}
        </div>
      )}

      <div style={{ display: 'grid', gap: '0.4rem' }}>
        <div className="macro-track">
          <div
            className="macro-fill macro-fill-animate"
            style={{
              width: `${challenge.percent}%`,
              background: done
                ? 'linear-gradient(90deg,var(--success),var(--cyan))'
                : `linear-gradient(90deg, ${solid(style.colour)}, var(--cyan))`,
              boxShadow: `0 0 12px ${tint(style.colour, 0.4)}`,
            }}
          />
        </div>
        <div className="flex items-center justify-between" style={{ fontSize: '0.75rem' }}>
          <span className="tabular" style={{ color: 'var(--text)', fontWeight: 600 }}>
            {Math.round(challenge.current)} / {Math.round(challenge.target)} {challenge.unit}
          </span>
          <span style={{ color: 'var(--text-faint)' }}>
            {done
              ? `+${challenge.points} points`
              : `${challenge.days_left}d left · ${challenge.points} pts`}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ main -- */

export default function Challenges({ apiBase }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  const headers = useCallback(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  }), []);

  const load = useCallback(async () => {
    try {
      const c = await fetch(`${apiBase}/challenges`, { headers: headers() })
        .then((r) => (r.ok ? r.json() : null));
      if (c) setData(c);
      else setError('Could not load your challenges.');
    } catch {
      setError('Could not reach the server.');
    } finally {
      setLoading(false);
    }
  }, [apiBase, headers]);

  useEffect(() => { load(); }, [load]);

  const addChallenge = async () => {
    setAdding(true);
    try {
      const res = await fetch(`${apiBase}/challenges/refresh`, { method: 'POST', headers: headers() });
      const body = await res.json().catch(() => ({}));
      if (!body.success && body.message) setError(body.message);
      await load();
    } finally {
      setAdding(false);
    }
  };

  const drop = async (id) => {
    await fetch(`${apiBase}/challenges/${id}`, { method: 'DELETE', headers: headers() });
    load();
  };

  if (loading) {
    return (
      <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
        <div className="skeleton" style={{ height: 90, borderRadius: 16 }} />
        <div className="skeleton" style={{ height: 150, borderRadius: 16 }} />
        <div className="skeleton" style={{ height: 150, borderRadius: 16 }} />
      </div>
    );
  }

  const challenges = data?.challenges || [];
  const context = data?.context || {};
  const done = challenges.filter((c) => c.completed).length;

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <PageHero
        icon={Trophy}
        title="Challenges"
        subtitle="Built from what you've actually been doing — not a generic list."
        from="--warning-rgb" to="--brand-pink-rgb"
      />

      {/* Standing, so completing things means something. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '0.75rem' }}>
        <Stat icon={Trophy} label="Points earned" value={context.total_points ?? 0} colour="var(--warning)" />
        <Stat icon={Flame} label="Streak" value={context.streak ?? 0}
              suffix={context.streak === 1 ? 'challenge' : 'challenges'} colour="var(--brand-pink)" />
        <Stat icon={Check} label="Done this round" value={done} colour="var(--success)" />
        <Stat icon={Target} label="Up for grabs" value={data?.points_available ?? 0}
              suffix="pts" colour="var(--accent-soft)" />
      </div>


      {error && (
        <div className="auth-error"><AlertCircle size={15} /> <span>{error}</span></div>
      )}

      {challenges.length === 0 ? (
        <div className="surface" style={{ padding: '2.5rem 1.5rem', textAlign: 'center' }}>
          <Trophy size={30} color="var(--border-strong)" style={{ marginBottom: 12 }} />
          <div style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', marginBottom: 4 }}>
            No challenges right now
          </div>
          <div className="section-sub" style={{ maxWidth: 380, margin: '0 auto 1.25rem' }}>
            Log a few days of meals and these will be built around what your data
            actually shows.
          </div>
          <button className="generate-btn" onClick={addChallenge} disabled={adding}>
            {adding ? <><RefreshCw size={15} className="spin" /> Building…</> : 'Give me one'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.875rem' }}>
          {challenges.map((c) => (
            <ChallengeCard key={c.id} challenge={c} onDrop={drop} />
          ))}
          <button className="ghost-btn" style={{ justifyContent: 'center' }} onClick={addChallenge} disabled={adding}>
            {adding ? <><RefreshCw size={14} className="spin" /> Finding one…</> : <><Plus size={14} /> Another challenge</>}
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, suffix, colour }) {
  return (
    <div className="surface" style={{ padding: '0.9rem 1rem' }}>
      <div className="flex items-center justify-between">
        <span className="metric-label">{label}</span>
        <Icon size={14} color={colour} />
      </div>
      <div className="tabular" style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: 4, lineHeight: 1 }}>
        {value}
        {suffix && <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)', fontWeight: 500 }}> {suffix}</span>}
      </div>
    </div>
  );
}
