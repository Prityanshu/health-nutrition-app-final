import React, { useState, useEffect, useMemo } from 'react';
import {
  TrendingDown, TrendingUp, Minus, Target, Flame, Scale, Award,
} from 'lucide-react';
import useCountUp from './useCountUp';

/**
 * Progress - how the last N days compare to the active goal.
 *
 * The previous version listed raw logs. This one answers the question people
 * actually have: am I on track? Everything is measured against the targets
 * stored on the active goal, so it stays consistent with the dashboard.
 */

const clamp = (n, min = 0, max = 100) => Math.min(max, Math.max(min, n));
const num = (v) => (typeof v === 'number' && !Number.isNaN(v) ? v : 0);

const RANGES = [
  { key: 7, label: '7D' },
  { key: 30, label: '30D' },
  { key: 90, label: '90D' },
];

/** Weight line chart with a target reference line. */
function WeightChart({ entries, targetWeight }) {
  const { path, area, min, max, points } = useMemo(() => {
    if (!entries || entries.length < 2) return {};
    const values = entries.map((e) => e.weight_kg);
    const lo = Math.min(...values, targetWeight || Infinity);
    const hi = Math.max(...values, targetWeight || -Infinity);
    const pad = (hi - lo) * 0.15 || 1;
    const minV = lo - pad;
    const maxV = hi + pad;
    const span = maxV - minV || 1;
    const W = 100;
    const H = 40;

    const pts = values.map((v, i) => ({
      x: (i / (values.length - 1)) * W,
      y: H - ((v - minV) / span) * H,
      v,
    }));
    const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
    return {
      path: d,
      area: `${d} L${W},${H} L0,${H} Z`,
      min: minV,
      max: maxV,
      points: pts,
    };
  }, [entries, targetWeight]);

  if (!path) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#667085', fontSize: '0.875rem' }}>
        Log at least two weigh-ins to see a trend.
      </div>
    );
  }

  const targetY = targetWeight
    ? 40 - ((targetWeight - min) / (max - min)) * 40
    : null;

  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" style={{ width: '100%', height: 150, overflow: 'visible' }}>
        <defs>
          <linearGradient id="wArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0" />
          </linearGradient>
        </defs>

        {targetY != null && (
          <line
            x1="0" y1={targetY} x2="100" y2={targetY}
            stroke="#34D399" strokeWidth="0.4" strokeDasharray="1.5 1.5"
            vectorEffect="non-scaling-stroke" opacity="0.8"
          />
        )}

        <path d={area} fill="url(#wArea)" />
        <path
          d={path} fill="none" stroke="#A78BFA" strokeWidth="2"
          vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round"
        />
        {points.length <= 30 && points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="1.6" fill="#0B0D11" stroke="#A78BFA"
            strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
        ))}
      </svg>

      <div className="flex items-center justify-between" style={{ fontSize: '0.6875rem', color: '#667085', marginTop: 6 }}>
        <span>{entries.length} entries</span>
        {targetWeight && (
          <span style={{ color: '#34D399' }}>— — target {targetWeight} kg</span>
        )}
        <span>{entries[entries.length - 1].weight_kg} kg now</span>
      </div>
    </div>
  );
}

function AdherenceRow({ label, actual, target, color }) {
  const pct = target > 0 ? clamp((actual / target) * 100) : 0;
  const animated = useCountUp(actual);
  // Within 10% either way counts as on target.
  const state = !target ? 'muted' : pct >= 90 && pct <= 110 ? 'good' : pct < 90 ? 'warn' : 'bad';
  const stateLabel = { good: 'On target', warn: 'Under', bad: 'Over', muted: '—' }[state];

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 6 }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{label}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="tabular" style={{ fontSize: '0.75rem', color: '#98A2B3' }}>
            {Math.round(animated)} <span style={{ color: '#667085' }}>/ {Math.round(target)}</span>
          </span>
          <span className={`pill pill-${state}`} style={{ fontSize: '0.625rem' }}>{stateLabel}</span>
        </div>
      </div>
      <div className="macro-track">
        <div
          className="macro-fill macro-fill-animate"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 10px ${color}44` }}
        />
      </div>
    </div>
  );
}

export default function Progress({ apiBase, dashboardData, onNavigate }) {
  const [range, setRange] = useState(30);
  const [weight, setWeight] = useState(null);
  const [loading, setLoading] = useState(true);

  const goals = dashboardData?.goals || [];
  const goal = goals.find((g) => g.is_active) || goals[0] || null;
  const stats = dashboardData?.dailyStats || {};

  useEffect(() => {
    setLoading(true);
    fetch(`${apiBase}/goals/weight/history?days=${range}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
      .then((r) => r.json())
      .then(setWeight)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [apiBase, range]);

  const entries = weight?.entries || [];
  const change = num(weight?.change_kg);
  const Trend = change < -0.05 ? TrendingDown : change > 0.05 ? TrendingUp : Minus;

  const target = goal?.target_weight;
  const start = entries[0]?.weight_kg;
  const current = entries[entries.length - 1]?.weight_kg;
  const totalNeeded = target && start ? Math.abs(target - start) : 0;
  const achieved = target && start && current ? Math.abs(current - start) : 0;
  const goalPct = totalNeeded > 0 ? clamp((achieved / totalNeeded) * 100) : 0;

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>Progress</h1>
          <p className="section-sub" style={{ fontSize: '0.875rem' }}>
            {goal ? 'Measured against your active goal.' : 'Set a goal to track against targets.'}
          </p>
        </div>
        <div className="segmented">
          {RANGES.map((r) => (
            <button
              key={r.key}
              className={range === r.key ? 'is-active' : ''}
              onClick={() => setRange(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {!goal && (
        <button onClick={() => onNavigate('set-goals')} className="surface-hero lift"
          style={{ padding: '1.25rem', width: '100%', textAlign: 'left', cursor: 'pointer', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Target size={20} color="#A78BFA" />
          <span style={{ fontSize: '0.875rem' }}>No active goal — set one to see how you're tracking.</span>
        </button>
      )}

      {/* Weight trend */}
      <div className="surface-hero" style={{ padding: '1.5rem' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div className="metric-label">Weight trend</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem', marginTop: 6 }}>
              <span className="metric-value tabular" style={{ fontSize: '2.5rem' }}>
                {current ?? '—'}
                {current && <span style={{ fontSize: '0.9rem', color: '#667085', fontWeight: 500, marginLeft: 5 }}>kg</span>}
              </span>
              {entries.length > 1 && (
                <span className={`pill ${change < 0 ? 'pill-good' : change > 0 ? 'pill-warn' : 'pill-muted'}`}>
                  <Trend size={13} />{change > 0 ? '+' : ''}{change} kg
                </span>
              )}
            </div>
          </div>
          {target && (
            <div style={{ textAlign: 'right' }}>
              <div className="metric-label">Goal</div>
              <div className="tabular" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34D399', marginTop: 4 }}>
                {target} kg
              </div>
            </div>
          )}
        </div>

        {loading ? <div className="skeleton" style={{ height: 150 }} /> :
          <WeightChart entries={entries} targetWeight={target} />}

        {target && totalNeeded > 0 && (
          <>
            <hr className="hairline" style={{ margin: '1.25rem 0 1rem' }} />
            <div className="flex items-center justify-between" style={{ marginBottom: 8 }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Toward your target</span>
              <span className="tabular" style={{ fontSize: '0.8125rem', color: '#A78BFA', fontWeight: 700 }}>
                {Math.round(goalPct)}%
              </span>
            </div>
            <div className="macro-track" style={{ height: '0.625rem' }}>
              <div className="macro-fill macro-fill-animate"
                style={{ width: `${goalPct}%`, background: 'linear-gradient(90deg,#8B5CF6,#34D399)', boxShadow: '0 0 12px rgba(139,92,246,0.5)' }} />
            </div>
            <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 8 }}>
              {Math.abs(target - current).toFixed(1)} kg to go
            </div>
          </>
        )}
      </div>

      {/* Today vs targets */}
      {goal && (
        <div className="surface" style={{ padding: '1.5rem', display: 'grid', gap: '1.125rem' }}>
          <div className="flex items-center justify-between">
            <div>
              <div className="section-title">Today against target</div>
              <div className="section-sub">Within 10% counts as on target</div>
            </div>
            <Flame size={16} color="#FBBF24" />
          </div>
          <AdherenceRow label="Calories" actual={num(stats.total_calories)} target={num(goal.target_calories)} color="#8B5CF6" />
          <AdherenceRow label="Protein (g)" actual={num(stats.total_protein)} target={num(goal.target_protein)} color="#22D3EE" />
          <AdherenceRow label="Carbs (g)" actual={num(stats.total_carbs)} target={num(goal.target_carbs)} color="#A78BFA" />
          <AdherenceRow label="Fat (g)" actual={num(stats.total_fat)} target={num(goal.target_fat)} color="#FBBF24" />
        </div>
      )}

      {/* Summary tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: '1rem' }}>
        <div className="surface lift" style={{ padding: '1.125rem' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
            <span className="metric-label">Check-ins</span><Scale size={15} color="#22D3EE" />
          </div>
          <div className="tabular" style={{ fontSize: '1.75rem', fontWeight: 700 }}>{entries.length}</div>
          <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 4 }}>last {range} days</div>
        </div>

        <div className="surface lift" style={{ padding: '1.125rem' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
            <span className="metric-label">Net change</span><Trend size={15} color={change < 0 ? '#34D399' : '#FBBF24'} />
          </div>
          <div className="tabular" style={{ fontSize: '1.75rem', fontWeight: 700, color: change < 0 ? '#34D399' : change > 0 ? '#FBBF24' : '#EEF2F7' }}>
            {change > 0 ? '+' : ''}{change}<span style={{ fontSize: '0.875rem' }}> kg</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 4 }}>over the period</div>
        </div>

        <div className="surface lift" style={{ padding: '1.125rem' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
            <span className="metric-label">Daily target</span><Target size={15} color="#A78BFA" />
          </div>
          <div className="tabular" style={{ fontSize: '1.75rem', fontWeight: 700 }}>
            {goal?.target_calories ? Math.round(goal.target_calories).toLocaleString() : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 4 }}>kcal</div>
        </div>

        <div className="surface lift" style={{ padding: '1.125rem' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
            <span className="metric-label">Goal</span><Award size={15} color="#34D399" />
          </div>
          <div style={{ fontSize: '1rem', fontWeight: 700, lineHeight: 1.3 }}>
            {goal ? goal.goal_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'None set'}
          </div>
          <button
            onClick={() => onNavigate('set-goals')}
            style={{ background: 'none', border: 'none', color: '#A78BFA', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', padding: 0, marginTop: 6 }}
          >
            {goal ? 'Change' : 'Set one'}
          </button>
        </div>
      </div>
    </div>
  );
}
