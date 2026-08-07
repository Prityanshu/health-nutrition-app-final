import React, { useState, useEffect } from 'react';
import { Scale, TrendingDown, TrendingUp, Minus, Check } from 'lucide-react';

/**
 * Weekly weigh-in.
 *
 * Calorie targets are a function of bodyweight, so a target set from a
 * registration weight quietly drifts out of date as the user actually changes.
 * Logging a weight recalculates any active goal server-side, which is the
 * whole reason for prompting weekly.
 */
export default function WeightCheckIn({ apiBase, onLogged }) {
  const [history, setHistory] = useState(null);
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  });

  const load = () => {
    fetch(`${apiBase}/goals/weight/history`, { headers: headers() })
      .then((r) => r.json())
      .then(setHistory)
      .catch(() => {});
  };

  useEffect(load, [apiBase]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    const kg = parseFloat(value);
    if (!kg || kg < 20 || kg > 400) {
      setError('Enter a weight between 20 and 400 kg.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/goals/weight`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ weight_kg: kg }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setResult(data);
      setValue('');
      load();
      if (onLogged) onLogged(data);
    } catch {
      setError('Could not save that weigh-in.');
    } finally {
      setSaving(false);
    }
  };

  const change = history?.change_kg ?? 0;
  const Trend = change < -0.05 ? TrendingDown : change > 0.05 ? TrendingUp : Minus;
  const trendColor = change < -0.05 ? '#34D399' : change > 0.05 ? '#FBBF24' : '#667085';
  const stale = history?.days_since_last != null && history.days_since_last >= 7;

  return (
    <div className="surface" style={{ padding: '1.25rem', display: 'grid', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="metric-label">Weekly check-in</span>
        <Scale size={16} color="#667085" />
      </div>

      {history?.latest != null && (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ fontSize: '2rem', fontWeight: 700, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>
            {history.latest}
            <span style={{ fontSize: '0.875rem', color: '#667085', fontWeight: 500, marginLeft: 4 }}>kg</span>
          </div>
          {history.count > 1 && (
            <span className="pill" style={{ background: 'rgba(255,255,255,0.05)', color: trendColor }}>
              <Trend size={13} />
              {change > 0 ? '+' : ''}{change} kg
            </span>
          )}
        </div>
      )}

      {stale && (
        <div style={{ fontSize: '0.8125rem', color: '#FBBF24' }}>
          Last weighed {history.days_since_last} days ago — worth updating so your targets stay accurate.
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <input
          type="number" step="0.1" className="form-input"
          style={{ flex: 1, minWidth: 140 }}
          placeholder="Today's weight (kg)"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && submit()}
        />
        <button className="btn btn-primary" onClick={submit} disabled={saving}>
          {saving ? 'Saving…' : 'Log'}
        </button>
      </div>

      {error && <div style={{ fontSize: '0.8125rem', color: '#F87171' }}>{error}</div>}

      {result?.goal_recalculated && result.updated_targets && (
        <div style={{
          background: 'rgba(52,211,153,0.09)', border: '1px solid rgba(52,211,153,0.28)',
          borderRadius: '0.625rem', padding: '0.75rem', fontSize: '0.8125rem', color: '#34D399',
          display: 'flex', gap: '0.5rem', alignItems: 'flex-start', lineHeight: 1.55,
        }}>
          <Check size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Targets updated for your new weight — {result.updated_targets.target_calories} kcal,
            {' '}{result.updated_targets.protein_g}g protein.
          </span>
        </div>
      )}

      {history?.count > 1 && <Sparkline entries={history.entries} />}
    </div>
  );
}

/** Inline SVG trend line - no chart library needed for a single series. */
function Sparkline({ entries }) {
  const values = entries.map((e) => e.weight_kg);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 100;
  const h = 30;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: 44 }}>
        <polyline
          points={points}
          fill="none"
          stroke="#8B5CF6"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
        />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6875rem', color: '#667085' }}>
        <span>{min.toFixed(1)} kg</span>
        <span>{entries.length} entries</span>
        <span>{max.toFixed(1)} kg</span>
      </div>
    </div>
  );
}
