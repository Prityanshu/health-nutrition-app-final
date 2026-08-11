import React, { useState, useEffect, useCallback } from 'react';
import {
  Target, TrendingDown, TrendingUp, Dumbbell, Heart, Activity,
  Scale, AlertTriangle, Check, ChevronRight, Info,
} from 'lucide-react';

/**
 * Goal setup.
 *
 * The user picks what they want to achieve; the app works out calories and
 * macros from their profile and latest weigh-in. Previously this screen asked
 * people to type in their own protein and carbohydrate targets, which is the
 * question the app exists to answer.
 *
 * Targets are computed server-side by a deterministic formula (Mifflin-St Jeor
 * BMR, activity multiplier, goal adjustment) - not by the language model - so
 * the same inputs always produce the same numbers and can be verified.
 */

const GOAL_ICONS = {
  weight_loss: TrendingDown,
  gentle_weight_loss: TrendingDown,
  muscle_gain: Dumbbell,
  lean_bulk: Dumbbell,
  body_recomposition: Activity,
  maintenance: Heart,
  general_health: Heart,
  athletic_performance: Activity,
  weight_gain: TrendingUp,
};

const MACROS = [
  { key: 'protein_g', label: 'Protein', color: 'var(--cyan)' },
  { key: 'carbs_g', label: 'Carbs', color: 'var(--accent-soft)' },
  { key: 'fat_g', label: 'Fat', color: 'var(--warning)' },
];

export default function GoalSetup({ apiBase, onGoalSaved }) {
  const [presets, setPresets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [targetWeight, setTargetWeight] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [sex, setSex] = useState('');
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [freeText, setFreeText] = useState('');

  const token = () => localStorage.getItem('token');
  const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token()}`,
  });

  useEffect(() => {
    fetch(`${apiBase}/goals/presets`, { headers: headers() })
      .then((r) => r.json())
      .then((d) => setPresets(d.presets || []))
      .catch(() => setError('Could not load goal options.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  // Ask the server to compute targets whenever the inputs change.
  const runPreview = useCallback(async () => {
    if (!selected) return;
    setLoading(true);
    setError('');
    try {
      const body = { goal_key: selected.key };
      if (targetWeight) body.target_weight = parseFloat(targetWeight);
      if (targetDate) body.target_date = targetDate;
      if (sex) body.sex = sex;

      const res = await fetch(`${apiBase}/goals/preview-targets`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setPreview(await res.json());
    } catch (e) {
      setError('Could not calculate targets. Is the backend running?');
      setPreview(null);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, targetWeight, targetDate, sex, apiBase]);

  useEffect(() => {
    if (!selected) return;
    const t = setTimeout(runPreview, 350); // debounce typing
    return () => clearTimeout(t);
  }, [selected, targetWeight, targetDate, sex, runPreview]);

  const matchFreeText = async () => {
    if (!freeText.trim()) return;
    try {
      const res = await fetch(
        `${apiBase}/goals/suggest?q=${encodeURIComponent(freeText)}`,
        { headers: headers() }
      );
      const data = await res.json();
      if (data.matched) {
        const found = presets.find((p) => p.key === data.suggestion.key);
        if (found) {
          setSelected(found);
          setSaved(false);
        }
      } else {
        setError("Couldn't match that to a goal — try picking one below.");
      }
    } catch {
      setError('Suggestion lookup failed.');
    }
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setError('');
    try {
      const body = { goal_key: selected.key };
      if (targetWeight) body.target_weight = parseFloat(targetWeight);
      if (targetDate) body.target_date = targetDate;
      if (sex) body.sex = sex;

      const res = await fetch(`${apiBase}/goals/from-preset`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(true);
      if (onGoalSaved) onGoalSaved(await res.json());
    } catch {
      setError('Could not save the goal.');
    } finally {
      setSaving(false);
    }
  };

  const needsSex = preview?.profile_used?.sex_missing && !sex;

  return (
    <div style={{ display: 'grid', gap: '1.25rem' }}>
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
          Set your goal
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: 4 }}>
          Tell us what you're aiming for. We'll work out the calories and macros.
        </p>
      </div>

      {/* Free-text shortcut */}
      <div className="surface" style={{ padding: '1rem' }}>
        <div className="metric-label" style={{ marginBottom: '0.625rem' }}>
          Describe it in your own words
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <input
            className="form-input"
            style={{ flex: 1, minWidth: 220 }}
            placeholder='e.g. "I want to slim down" or "training for a marathon"'
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && matchFreeText()}
          />
          <button className="btn btn-secondary" onClick={matchFreeText}>Match</button>
        </div>
      </div>

      {/* Preset grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: '0.75rem' }}>
        {presets.map((p) => {
          const Icon = GOAL_ICONS[p.key] || Target;
          const active = selected?.key === p.key;
          return (
            <button
              key={p.key}
              onClick={() => { setSelected(p); setSaved(false); }}
              className="surface surface-hover"
              style={{
                padding: '1rem', textAlign: 'left', cursor: 'pointer',
                borderColor: active ? 'var(--accent)' : undefined,
                background: active
                  ? 'linear-gradient(135deg, rgba(var(--accent-rgb),0.16), rgba(var(--cyan-rgb),0.05))'
                  : undefined,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <Icon size={17} color={active ? 'var(--accent-soft)' : 'var(--text-faint)'} />
                <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{p.label}</span>
                {active && <Check size={15} color="var(--success)" style={{ marginLeft: 'auto' }} />}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                {p.description}
              </div>
            </button>
          );
        })}
      </div>

      {/* Follow-up inputs */}
      {selected && (
        <div className="surface" style={{ padding: '1.25rem', display: 'grid', gap: '1rem' }}>
          <div className="metric-label">A couple of details</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '1rem' }}>
            {selected.needs_target_weight && (
              <div>
                <label style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Target weight (kg)
                </label>
                <input
                  type="number" className="form-input" placeholder="e.g. 68"
                  value={targetWeight} onChange={(e) => setTargetWeight(e.target.value)}
                />
              </div>
            )}
            <div>
              <label style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                By when? <span style={{ color: 'var(--text-faint)' }}>(optional)</span>
              </label>
              <input
                type="date" className="form-input"
                value={targetDate} onChange={(e) => setTargetDate(e.target.value)}
              />
            </div>
            {needsSex && (
              <div>
                <label style={{ fontSize: '0.8125rem', color: 'var(--warning)', display: 'block', marginBottom: 6 }}>
                  Sex — needed for an accurate estimate
                </label>
                <select className="form-input" value={sex} onChange={(e) => setSex(e.target.value)}>
                  <option value="">Select…</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Prefer not to say</option>
                </select>
              </div>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="surface" style={{ padding: '0.875rem', borderColor: 'var(--danger)', color: 'var(--danger)', fontSize: '0.875rem' }}>
          {error}
        </div>
      )}

      {/* Computed targets */}
      {loading && <div className="skeleton" style={{ height: 220 }} />}

      {!loading && preview && (
        <div className="surface" style={{ padding: '1.5rem', display: 'grid', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <div className="metric-label">Your daily target</div>
              <div className="metric-value" style={{ marginTop: 6 }}>
                {preview.target_calories.toLocaleString()}
                <span style={{ fontSize: '1rem', color: 'var(--text-faint)', fontWeight: 500, marginLeft: 8 }}>kcal</span>
              </div>
            </div>
            <div style={{ textAlign: 'right', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              <div>BMR {preview.bmr.toLocaleString()} kcal</div>
              <div>Maintenance {preview.tdee.toLocaleString()} kcal</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '0.75rem' }}>
            {MACROS.map((m) => (
              <div key={m.key} style={{ background: 'var(--surface-inset)', border: '1px solid var(--border)', borderRadius: '0.75rem', padding: '0.875rem' }}>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
                  {m.label}
                </div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: m.color, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
                  {preview[m.key]}<span style={{ fontSize: '0.875rem' }}>g</span>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            <Info size={15} style={{ flexShrink: 0, marginTop: 2 }} />
            <span>{preview.rationale}</span>
          </div>

          {preview.estimated_weeks && (
            <div className="pill" style={{ background: 'rgba(var(--success-rgb),0.14)', color: 'var(--success)', width: 'fit-content' }}>
              <Scale size={13} />
              About {preview.estimated_weeks} weeks at {preview.weekly_change_kg} kg/week
            </div>
          )}

          {preview.warnings?.length > 0 && (
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              {preview.warnings.map((w, i) => (
                <div key={i} style={{
                  display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
                  background: 'rgba(var(--warning-rgb),0.09)', border: '1px solid rgba(var(--warning-rgb),0.28)',
                  borderRadius: '0.625rem', padding: '0.75rem', fontSize: '0.8125rem', color: 'var(--warning)',
                  lineHeight: 1.55,
                }}>
                  <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          <button
            className="btn btn-primary"
            onClick={save}
            disabled={saving || saved}
            style={{ justifyContent: 'center' }}
          >
            {saved ? <><Check size={16} style={{ marginRight: 6 }} /> Goal saved</>
              : saving ? 'Saving…'
              : <>Set this as my goal <ChevronRight size={16} style={{ marginLeft: 6 }} /></>}
          </button>

          <p style={{ fontSize: '0.75rem', color: 'var(--text-faint)', textAlign: 'center', lineHeight: 1.5 }}>
            These are estimates from a standard formula, not medical advice. If you have a health
            condition or are unsure, check with a doctor or dietitian.
          </p>
        </div>
      )}
    </div>
  );
}
