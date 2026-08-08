import React, { useState, useEffect, useRef } from 'react';
import {
  Utensils, Sunrise, Sun, Moon, Cookie, Sparkles, Check, X,
  RefreshCw, AlertCircle, Flame, Zap, ScanLine, BadgeCheck, ExternalLink,
} from 'lucide-react';
import { PageHero } from './SpecialistUI';
import BarcodeScanner from './BarcodeScanner';

/**
 * Log a meal.
 *
 * You type what you ate, the model works out the nutrition, you confirm, it
 * gets logged. The previous screen had that flow but wrapped in a white header
 * with its own Back and Logout buttons duplicating the sidebar, light-theme
 * cards that rendered white-on-white inside the dark shell, and two alert()
 * dialogs.
 *
 * Three functional changes beyond the styling:
 *
 *  - The "Sample Foods to Try" list was plain text. Every suggestion is now a
 *    button that fills the form, and the list leads with foods this user has
 *    actually logged before rather than salmon fillet and quinoa.
 *  - Meal type defaults to the current time of day instead of always Lunch.
 *  - Confirming a meal no longer re-runs the analysis. The numbers on screen
 *    are sent with the log request, so it saves in about a second rather than
 *    waiting on the model twice.
 */

const MEAL_TYPES = [
  { key: 'breakfast', label: 'Breakfast', icon: Sunrise },
  { key: 'lunch', label: 'Lunch', icon: Sun },
  { key: 'dinner', label: 'Dinner', icon: Moon },
  { key: 'snack', label: 'Snack', icon: Cookie },
];

/** Whatever they are most likely eating right now. */
function defaultMealType(date = new Date()) {
  const h = date.getHours();
  if (h < 11) return 'breakfast';
  if (h < 16) return 'lunch';
  if (h < 22) return 'dinner';
  return 'snack';
}

// Fallback suggestions for a brand-new account with nothing logged yet. Kept
// short and recognisable rather than a nutritionist's shopping list.
const STARTERS = [
  { name: 'Roti', serving: '2 pieces' },
  { name: 'Dal', serving: '1 bowl' },
  { name: 'Paneer curry', serving: '1 cup' },
  { name: 'Curd', serving: '1 cup' },
  { name: 'Boiled eggs', serving: '2 large' },
  { name: 'Poha', serving: '1 plate' },
  { name: 'Banana', serving: '1 medium' },
  { name: 'Chicken breast', serving: '150g' },
];

const MACROS = [
  { key: 'protein', label: 'Protein', colour: '#22D3EE' },
  { key: 'carbohydrates', label: 'Carbs', colour: '#FBBF24' },
  { key: 'fat', label: 'Fat', colour: '#F472B6' },
];

const num = (v) => {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return typeof n === 'number' && !Number.isNaN(n) ? n : 0;
};

export default function LogMeal({ apiBase, onLogged, calorieTarget = 0, consumedToday = 0 }) {
  const [foodName, setFoodName] = useState('');
  const [serving, setServing] = useState('');
  const [mealType, setMealType] = useState(defaultMealType);
  const [analysis, setAnalysis] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [logged, setLogged] = useState(null);
  const [regulars, setRegulars] = useState([]);
  const [scanning, setScanning] = useState(false);
  const nameRef = useRef(null);

  const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  });

  // Foods this user logs often make far better suggestions than a generic
  // list. Same endpoint the other screens use, so no new API surface.
  useEffect(() => {
    fetch(`${apiBase}/ml/for-you`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const favs = d?.profile?.favourites || [];
        setRegulars(favs.slice(0, 6).map((f) => ({ name: f.name, serving: '1 serving' })));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  const reset = () => {
    setAnalysis(null);
    setError('');
  };

  // Errors from this API arrive as a string, or as an object carrying an
  // error_type. Rate limiting is common enough to deserve its own wording.
  const readError = (detail, fallback) => {
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object') {
      if (detail.error_type === 'rate_limit') {
        return 'The AI service is busy right now. Try again in a minute or two.';
      }
      return detail.error || fallback;
    }
    return fallback;
  };

  const analyse = async () => {
    if (!foodName.trim() || !serving.trim()) {
      setError('Add both what you ate and how much.');
      return;
    }
    setAnalysing(true);
    setError('');
    setAnalysis(null);
    setLogged(null);
    try {
      const res = await fetch(`${apiBase}/nutrient/analyze`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ food_name: foodName.trim(), serving_size: serving.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success && data.data) {
        setAnalysis(data.data);
      } else {
        setError(readError(data.detail, 'Could not analyse that. Try describing it differently.'));
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setAnalysing(false);
    }
  };

  // A scanned packet skips the model entirely: the barcode names exactly one
  // product, so the figures come off its label.
  const onBarcode = async (barcode) => {
    setScanning(false);
    setAnalysing(true);
    setError('');
    setAnalysis(null);
    setLogged(null);
    try {
      const res = await fetch(`${apiBase}/nutrient/barcode`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ barcode, serving_size: serving.trim() || '100g' }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success && data.data) {
        setAnalysis(data.data);
        // Fill the form from the product so logging and the history read well.
        setFoodName(data.data.food_name || '');
        if (!serving.trim()) setServing('100g');
      } else {
        setError(readError(data.detail, 'That barcode is not in the database yet.'));
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setAnalysing(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/nutrient/log-meal`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          food_name: foodName.trim(),
          serving_size: serving.trim(),
          meal_type: mealType,
          // Send what is already on screen so the server does not pay for a
          // second analysis of the same food.
          nutrients: analysis?.parsed_nutrients || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success) {
        setLogged({
          name: foodName.trim(),
          calories: num(analysis?.parsed_nutrients?.calories),
          mealType,
        });
        setAnalysis(null);
        setFoodName('');
        setServing('');
        onLogged?.();
        nameRef.current?.focus();
      } else {
        setError(readError(data.detail, 'Could not log that meal.'));
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setSaving(false);
    }
  };

  const pick = (item) => {
    setFoodName(item.name);
    setServing(item.serving);
    setLogged(null);
    reset();
    nameRef.current?.focus();
  };

  const suggestions = [...regulars, ...STARTERS]
    .filter((s, i, arr) => arr.findIndex((x) => x.name.toLowerCase() === s.name.toLowerCase()) === i)
    .slice(0, 8);

  const n = analysis?.parsed_nutrients;
  const kcal = num(n?.calories);
  const macroTotal = MACROS.reduce((sum, m) => sum + num(n?.[m.key]), 0) || 1;

  const remaining = calorieTarget > 0 ? calorieTarget - consumedToday : null;
  const remainingAfter = remaining !== null ? remaining - kcal : null;

  const canAnalyse = foodName.trim() && serving.trim() && !analysing;

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <PageHero
        icon={Utensils}
        title="Log a meal"
        subtitle="Describe what you ate — the nutrition is worked out for you."
      />

      {/* ------------------------------------------------------- the form -- */}
      <div className="surface-hero" style={{ padding: '1.5rem', display: 'grid', gap: '1.25rem' }}>
        <div style={{ display: 'grid', gap: '0.4rem' }}>
          <div className="flex items-center justify-between" style={{ gap: '0.75rem' }}>
            <label className="section-title" htmlFor="food-name">What did you eat?</label>
            {/* Packaged food has a barcode, and a barcode gives real label
                values instead of an approximation. Worth pointing at. */}
            <button type="button" className="ghost-btn" onClick={() => setScanning(true)}>
              <ScanLine size={14} /> Scan barcode
            </button>
          </div>
          <input
            id="food-name"
            ref={nameRef}
            className="form-input"
            placeholder="e.g. rajma chawal, two rotis with sabzi, protein shake"
            value={foodName}
            onChange={(e) => { setFoodName(e.target.value); reset(); }}
            onKeyDown={(e) => e.key === 'Enter' && canAnalyse && analyse()}
          />
          <div className="section-sub" style={{ fontSize: '0.75rem' }}>
            From a packet? Scanning the barcode gives the exact values off the label.
          </div>
        </div>

        <div style={{ display: 'grid', gap: '0.4rem' }}>
          <label className="section-title" htmlFor="serving">How much?</label>
          <input
            id="serving"
            className="form-input"
            placeholder="e.g. 1 plate, 150g, 2 pieces"
            value={serving}
            onChange={(e) => { setServing(e.target.value); reset(); }}
            onKeyDown={(e) => e.key === 'Enter' && canAnalyse && analyse()}
          />
        </div>

        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <div>
            <div className="section-title">Which meal?</div>
            <div className="section-sub">Set from the time of day — change it if that's wrong</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.5rem' }}>
            {MEAL_TYPES.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                className={`choice-tile ${mealType === key ? 'is-active' : ''}`}
                onClick={() => setMealType(key)}
              >
                <Icon size={17} />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Quick picks - these used to be static text nobody could use. */}
        {suggestions.length > 0 && (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <div className="section-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.6875rem' }}>
              {regulars.length ? 'You often log' : 'Quick picks'}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {suggestions.map((s) => (
                <button key={s.name} type="button" className="suggest-chip" onClick={() => pick(s)}>
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="auth-error">
            <AlertCircle size={15} /> <span>{error}</span>
          </div>
        )}

        <button className="generate-btn" onClick={analyse} disabled={!canAnalyse}>
          {analysing
            ? <><RefreshCw size={16} className="spin" /> Working out the nutrition…</>
            : <><Sparkles size={16} /> Analyse this meal</>}
        </button>
      </div>

      {/* --------------------------------------------------- just logged -- */}
      {logged && (
        <div className="surface" style={{
          padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.875rem',
          borderColor: 'rgba(52,211,153,0.35)',
          background: 'linear-gradient(100deg, rgba(52,211,153,0.10), transparent)',
        }}>
          <div className="flex items-center justify-center" style={{
            width: 38, height: 38, borderRadius: 11, flexShrink: 0,
            background: 'rgba(52,211,153,0.16)', color: '#34D399',
          }}>
            <Check size={19} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
              {logged.name} logged
            </div>
            <div className="section-sub">
              {Math.round(logged.calories)} kcal added to {logged.mealType}
              {remaining !== null && ` · ${Math.max(0, Math.round(remaining))} kcal left today`}
            </div>
          </div>
          <button className="ghost-btn" onClick={() => setLogged(null)}>Done</button>
        </div>
      )}

      {/* ----------------------------------------------------- the result -- */}
      {analysing && (
        <div className="surface" style={{ padding: '1.5rem', display: 'grid', gap: '0.75rem' }}>
          <div className="skeleton" style={{ height: 20, width: '45%', borderRadius: 6 }} />
          <div className="skeleton" style={{ height: 52, width: '30%', borderRadius: 8 }} />
          <div className="skeleton" style={{ height: 12, borderRadius: 6 }} />
          <div className="skeleton" style={{ height: 12, width: '80%', borderRadius: 6 }} />
        </div>
      )}

      {analysis && n && (
        <div className="surface-hero" style={{ padding: '1.5rem', display: 'grid', gap: '1.25rem' }}>
          <div className="flex items-center justify-between" style={{ gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ minWidth: 0 }}>
              <div className="section-title" style={{ fontSize: '1.0625rem' }}>
                {analysis.food_name || foodName}
              </div>
              <div className="section-sub">{analysis.serving_size || serving}</div>
              {/* Where these numbers came from. A guess and a label look
                  identical once they are in a table, so say which it is. */}
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                {analysis.source?.verified ? (
                  <>
                    <span className={`source-badge ${analysis.source.exact ? 'source-verified' : 'source-matched'}`}>
                      <BadgeCheck size={12} />
                      {analysis.source.exact ? 'Scanned — exact label' : 'Matched by name'}
                    </span>
                    {analysis.source.source_url && (
                      <a
                        href={analysis.source.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="section-sub"
                        style={{ fontSize: '0.6875rem', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                      >
                        {[analysis.source.brand, analysis.source.matched_name]
                          .filter(Boolean).join(' ') || 'source'} <ExternalLink size={10} />
                      </a>
                    )}
                  </>
                ) : (
                  <span className="source-badge source-estimate">
                    <Sparkles size={12} /> AI estimate
                  </span>
                )}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="metric-value tabular" style={{ color: '#FBBF24', fontSize: '2rem', lineHeight: 1 }}>
                {Math.round(kcal)}
              </div>
              <div className="metric-label">kcal</div>
            </div>
          </div>

          {/* Macro split. A single stacked bar reads faster than four numbers,
              and the numbers are still underneath it. */}
          <div style={{ display: 'grid', gap: '0.625rem' }}>
            <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: '#12151B' }}>
              {MACROS.map((m) => (
                <div
                  key={m.key}
                  style={{
                    width: `${(num(n[m.key]) / macroTotal) * 100}%`,
                    background: m.colour,
                    transition: 'width 0.5s cubic-bezier(0.22,1,0.36,1)',
                  }}
                />
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0.5rem' }}>
              {MACROS.map((m) => (
                <div key={m.key} style={{
                  padding: '0.625rem 0.75rem', borderRadius: '0.625rem',
                  background: '#12151B', border: '1px solid #2A3240',
                }}>
                  <div className="metric-label" style={{ color: m.colour }}>{m.label}</div>
                  <div className="tabular" style={{ fontSize: '1.0625rem', fontWeight: 700, marginTop: 2 }}>
                    {Math.round(num(n[m.key]))}g
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* A name match can find a real label for the wrong variant. Brands
              sell regular, low-fat and high-protein versions of the same
              product under nearly the same name, and they differ enough to
              matter. Offer the exact route rather than hoping it was right. */}
          {analysis.source?.verified && !analysis.source.exact && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap',
              padding: '0.7rem 0.85rem', borderRadius: '0.625rem',
              background: 'rgba(251,191,36,0.07)',
              border: '1px solid rgba(251,191,36,0.22)',
              fontSize: '0.8125rem', color: '#C6CEDA',
            }}>
              <AlertCircle size={15} style={{ flexShrink: 0, color: '#FBBF24' }} />
              <span style={{ flex: 1, minWidth: 180 }}>
                This is the label for <strong>{analysis.source.matched_name}</strong>. If your
                packet is a different variant, the numbers will differ.
              </span>
              <button className="ghost-btn" onClick={() => setScanning(true)}>
                <ScanLine size={14} /> Scan mine
              </button>
            </div>
          )}

          {/* What this does to the day's budget - the reason anyone logs at all. */}
          {remainingAfter !== null && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.6rem',
              padding: '0.7rem 0.85rem', borderRadius: '0.625rem',
              background: remainingAfter < 0 ? 'rgba(248,113,113,0.08)' : 'rgba(139,92,246,0.08)',
              border: `1px solid ${remainingAfter < 0 ? 'rgba(248,113,113,0.28)' : 'rgba(139,92,246,0.24)'}`,
              fontSize: '0.8125rem',
              color: remainingAfter < 0 ? '#FCA5A5' : '#C6CEDA',
            }}>
              <Flame size={15} style={{ flexShrink: 0 }} />
              <span>
                {remainingAfter < 0
                  ? `Puts you ${Math.abs(Math.round(remainingAfter))} kcal over today's target.`
                  : `Leaves ${Math.round(remainingAfter)} kcal for the rest of today.`}
              </span>
            </div>
          )}

          {Array.isArray(n.health_tags) && n.health_tags.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
              {n.health_tags.map((tag, i) => (
                <span key={i} className="pill pill-brand">{String(tag)}</span>
              ))}
            </div>
          )}

          {analysis.raw_analysis && (
            <details>
              <summary style={{
                cursor: 'pointer', fontSize: '0.8125rem', color: '#98A2B3',
                display: 'flex', alignItems: 'center', gap: '0.4rem',
              }}>
                <Zap size={13} /> Full breakdown
              </summary>
              {/* Plain text, escaped by React - the old screen pushed this
                  straight into dangerouslySetInnerHTML. */}
              <div style={{
                marginTop: '0.75rem', fontSize: '0.8125rem', lineHeight: 1.7,
                color: '#C6CEDA', whiteSpace: 'pre-wrap',
              }}>
                {analysis.raw_analysis}
              </div>
            </details>
          )}

          <div style={{ display: 'flex', gap: '0.625rem' }}>
            <button className="generate-btn" style={{ flex: 1 }} onClick={save} disabled={saving}>
              {saving
                ? <><RefreshCw size={16} className="spin" /> Logging…</>
                : <><Check size={16} /> Log this meal</>}
            </button>
            <button className="ghost-btn" onClick={reset} disabled={saving}>
              <X size={15} /> Discard
            </button>
          </div>
        </div>
      )}

      {scanning && (
        <BarcodeScanner onDetected={onBarcode} onClose={() => setScanning(false)} />
      )}
    </div>
  );
}
