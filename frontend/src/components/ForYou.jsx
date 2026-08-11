import React, { useState, useEffect } from 'react';
import {
  Sparkles, TrendingUp, AlertTriangle, CheckCircle2, Info,
  Wallet, Utensils, Leaf, Clock, Plus, ChevronRight, Target,
} from 'lucide-react';
import useCountUp from './useCountUp';

/**
 * For You - recommendations derived from the user's own activity.
 *
 * Every number and reason on this page comes from real rows: meals they
 * logged, what those foods cost, their goal targets, their weight trend.
 * Nothing here is generic advice dressed up as personalisation, and where
 * there isn't enough history to be confident, the page says so instead of
 * pretending.
 */

const KIND_STYLE = {
  good: { icon: CheckCircle2, color: 'var(--success)', bg: 'rgba(var(--success-rgb),0.09)', border: 'rgba(var(--success-rgb),0.28)' },
  warn: { icon: AlertTriangle, color: 'var(--warning)', bg: 'rgba(var(--warning-rgb),0.09)', border: 'rgba(var(--warning-rgb),0.28)' },
  info: { icon: Info, color: 'var(--accent-soft)', bg: 'rgba(var(--accent-rgb),0.09)', border: 'rgba(var(--accent-rgb),0.28)' },
};

const CONFIDENCE = {
  high: { label: 'Tailored to you', cls: 'pill-good' },
  medium: { label: 'Getting to know you', cls: 'pill-brand' },
  low: { label: 'Log meals to improve this', cls: 'pill-warn' },
};

function RemainingBar({ label, remaining, target, color }) {
  const eaten = Math.max(0, target - remaining);
  const pct = target > 0 ? Math.min(100, (eaten / target) * 100) : 0;
  const animated = useCountUp(remaining);
  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 5 }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{label}</span>
        <span className="tabular" style={{ fontSize: '0.75rem', fontWeight: 700, color }}>
          {Math.round(animated)} left
        </span>
      </div>
      <div className="macro-track" style={{ height: '0.375rem' }}>
        <div className="macro-fill macro-fill-animate" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function FoodCard({ food, onLog, rank }) {
  return (
    <div className="surface lift" style={{ padding: '1.125rem', display: 'grid', gap: '0.75rem' }}>
      <div className="flex items-start justify-between" style={{ gap: '0.75rem' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: '0.9375rem', textTransform: 'capitalize' }}>
            {food.name}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', marginTop: 3, textTransform: 'capitalize' }}>
            {food.cuisine && food.cuisine !== 'mixed' ? `${food.cuisine} · ` : ''}
            {food.prep_complexity ? `${food.prep_complexity.toLowerCase()} effort` : ''}
          </div>
        </div>
        {rank <= 3 && (
          <span className="pill pill-brand" style={{ fontSize: '0.625rem', flexShrink: 0 }}>
            Top pick
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        {[
          { v: food.calories, u: 'kcal', c: 'var(--warning)' },
          { v: food.protein_g, u: 'g protein', c: 'var(--cyan)' },
          { v: food.carbs_g, u: 'g carbs', c: 'var(--accent-soft)' },
        ].map((m, i) => (
          <div key={i}>
            <span className="tabular" style={{ fontSize: '1rem', fontWeight: 700, color: m.c }}>{m.v}</span>
            <span style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', marginLeft: 3 }}>{m.u}</span>
          </div>
        ))}
        {food.cost != null && (
          <div style={{ marginLeft: 'auto' }}>
            <span className="tabular" style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--success)' }}>₹{food.cost}</span>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gap: '0.3125rem' }}>
        {food.reasons.map((r, i) => (
          <div key={i} style={{ display: 'flex', gap: '0.4rem', alignItems: 'flex-start', fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
            <span style={{ color: 'var(--accent)', flexShrink: 0 }}>·</span>
            <span>{r}</span>
          </div>
        ))}
      </div>

      {onLog && (
        <button
          onClick={() => onLog(food)}
          className="btn btn-secondary"
          style={{ justifyContent: 'center', padding: '0.5rem', fontSize: '0.8125rem' }}
        >
          <Plus size={14} style={{ marginRight: 5 }} /> Log this
        </button>
      )}
    </div>
  );
}

export default function ForYou({ apiBase, onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    fetch(`${apiBase}/ml/for-you`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch(() => setError('Could not load your recommendations.'))
      .finally(() => setLoading(false));
  }, [apiBase]);

  if (loading) {
    return (
      <div style={{ display: 'grid', gap: '1rem' }}>
        <div className="skeleton" style={{ height: 40, width: 200 }} />
        <div className="skeleton" style={{ height: 140 }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: '1rem' }}>
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 190 }} />)}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface" style={{ padding: '1.5rem', color: 'var(--danger)' }}>
        {error || 'No data.'}
      </div>
    );
  }

  const { profile, today, goal, recommendations, insights, confidence } = data;
  const remaining = today?.remaining;
  const conf = CONFIDENCE[confidence] || CONFIDENCE.low;

  // Chips describing what the page is actually using about this person.
  const chips = [];
  if (profile.vegetarian) chips.push({ icon: Leaf, text: 'Vegetarian', title: profile.vegetarian_source });
  if (profile.top_cuisine) chips.push({ icon: Utensils, text: `${profile.top_cuisine} favourite` });
  if (profile.budget) chips.push({ icon: Wallet, text: `~₹${profile.budget.median_per_item}/item` });
  if (profile.prep_preference) chips.push({ icon: Clock, text: `${profile.prep_preference.toLowerCase()} effort` });

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>For you</h1>
          <p className="section-sub" style={{ fontSize: '0.875rem' }}>
            Built from {profile.log_count} logged meal{profile.log_count === 1 ? '' : 's'} across{' '}
            {profile.days_active} day{profile.days_active === 1 ? '' : 's'}.
          </p>
        </div>
        <span className={`pill ${conf.cls}`}><Sparkles size={13} /> {conf.label}</span>
      </div>

      {/* What we know about you */}
      {chips.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {chips.map((c, i) => (
            <span key={i} className="pill pill-muted" title={c.title || ''} style={{ fontSize: '0.75rem' }}>
              <c.icon size={13} /> {c.text}
            </span>
          ))}
        </div>
      )}

      {/* Cold start */}
      {confidence === 'low' && (
        <div className="surface-hero" style={{ padding: '1.25rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Target size={20} color="var(--warning)" style={{ flexShrink: 0 }} />
          <div style={{ flex: 1, fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
            These are reasonable general picks, not personal ones yet. Log a handful of meals and
            this page starts matching your cuisines, budget and macro gaps.
          </div>
          <button className="btn btn-primary" onClick={() => onNavigate('log-meal')}>Log a meal</button>
        </div>
      )}

      {/* Today's remaining */}
      {remaining && goal && (
        <div className="surface-hero" style={{ padding: '1.5rem' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: '1.125rem' }}>
            <div>
              <div className="section-title">Left today</div>
              <div className="section-sub">Suggestions below are chosen to fit this</div>
            </div>
            <span className="pill pill-muted">{today.meals_today} logged</span>
          </div>
          <div style={{ display: 'grid', gap: '0.875rem' }}>
            <RemainingBar label="Calories" remaining={remaining.calories} target={goal.target_calories} color="var(--accent)" />
            <RemainingBar label="Protein (g)" remaining={remaining.protein} target={goal.target_protein} color="var(--cyan)" />
          </div>
        </div>
      )}

      {/* Insights */}
      {insights.length > 0 && (
        <div style={{ display: 'grid', gap: '0.625rem' }}>
          <div className="section-title">What we're noticing</div>
          {insights.map((ins, i) => {
            const s = KIND_STYLE[ins.kind] || KIND_STYLE.info;
            const Icon = s.icon;
            return (
              <div key={i} className="lift" style={{
                display: 'flex', gap: '0.75rem', alignItems: 'flex-start',
                background: s.bg, border: `1px solid ${s.border}`,
                borderRadius: '0.75rem', padding: '0.9375rem',
              }}>
                <Icon size={17} color={s.color} style={{ flexShrink: 0, marginTop: 1 }} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem', color: s.color }}>{ins.title}</div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.55 }}>
                    {ins.body}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Recommendations */}
      <div>
        <div className="flex items-center justify-between" style={{ marginBottom: '0.875rem' }}>
          <div>
            <div className="section-title">Suggested for you</div>
            <div className="section-sub">
              {remaining
                ? `Picked to fit your remaining ${Math.round(remaining.protein)}g protein`
                : 'Balanced picks for your profile'}
            </div>
          </div>
          <button
            onClick={() => onNavigate('chatbot')}
            style={{ background: 'none', border: 'none', color: 'var(--accent-soft)', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3 }}
          >
            Ask the coach <ChevronRight size={13} />
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(265px,1fr))', gap: '1rem' }}>
          {recommendations.map((f, i) => (
            <FoodCard key={f.id} food={f} rank={i + 1} onLog={() => onNavigate('log-meal')} />
          ))}
        </div>
      </div>

      {/* Your regulars */}
      {profile.favourites?.length > 0 && (
        <div className="surface" style={{ padding: '1.25rem' }}>
          <div className="section-title" style={{ marginBottom: '0.875rem' }}>Your regulars</div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {profile.favourites.map((f, i) => (
              <span key={i} className="pill pill-muted" style={{ textTransform: 'capitalize' }}>
                {f.name} <span style={{ color: 'var(--text-faint)' }}>×{f.times}</span>
              </span>
            ))}
          </div>
          {profile.variety?.in_a_rut && (
            <div style={{ fontSize: '0.75rem', color: 'var(--warning)', marginTop: '0.75rem' }}>
              You've been repeating these a lot — the suggestions above lean toward variety.
            </div>
          )}
        </div>
      )}

      <p style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', textAlign: 'center', lineHeight: 1.55 }}>
        Recommendations are calculated from your logged meals, goal targets and stated preferences.
        No two accounts get the same list.
      </p>
    </div>
  );
}
