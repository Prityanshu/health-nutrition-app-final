import React, { useState } from 'react';
import {
  HeartPulse, Plus, Check, RefreshCw, AlertCircle,
  TrendingDown, TrendingUp, Minus, ChevronRight,
} from 'lucide-react';

/**
 * Injury tracking card.
 *
 * Lives on the dashboard rather than buried in Challenges. An injury shapes
 * every workout, meal and challenge the app produces, so it belongs where the
 * user looks first - not behind a tab they open once a week. Challenges was
 * the wrong home for it: that page is about what you are trying to achieve,
 * and an injury is a constraint on all of it.
 */

const SEVERITY_LABELS = [
  'Gone', 'Barely there', 'Mild', 'Noticeable', 'Nagging', 'Moderate',
  'Sore most days', 'Painful', 'Bad', 'Very bad', 'Severe',
];

export default function InjuryTracker({ data, apiBase, onChanged }) {
  const [checkingIn, setCheckingIn] = useState(null);   // injury id
  const [severity, setSeverity] = useState(5);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState('');
  const [adding, setAdding] = useState(false);
  const [newInjury, setNewInjury] = useState('');
  const [newSeverity, setNewSeverity] = useState(5);

  const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  });

  const openCheckIn = (injury) => {
    setCheckingIn(injury.id);
    setSeverity(injury.severity);
    setNote('');
    setResult('');
  };

  const submitCheckIn = async () => {
    setBusy(true);
    try {
      const res = await fetch(`${apiBase}/injuries/${checkingIn}/checkin`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ severity, note: note.trim() || null }),
      });
      const body = await res.json().catch(() => ({}));
      setResult(body.message || '');
      setCheckingIn(null);
      onChanged();
    } catch {
      setResult('Could not save that just now.');
    } finally {
      setBusy(false);
    }
  };

  const addInjury = async () => {
    if (!newInjury.trim()) return;
    setBusy(true);
    try {
      await fetch(`${apiBase}/injuries`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ description: newInjury.trim(), severity: newSeverity }),
      });
      setNewInjury('');
      setNewSeverity(5);
      setAdding(false);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const injuries = data?.injuries || [];

  return (
    <div className="surface" style={{ padding: '1.25rem', display: 'grid', gap: '1rem' }}>
      <div className="flex items-center justify-between" style={{ gap: '1rem' }}>
        <div className="flex items-center" style={{ gap: '0.6rem' }}>
          <HeartPulse size={17} color="#F472B6" />
          <span className="section-title">Injuries</span>
        </div>
        {!adding && (
          <button className="ghost-btn" onClick={() => setAdding(true)}>
            <Plus size={14} /> Add
          </button>
        )}
      </div>

      {injuries.length === 0 && !adding && (
        <div className="section-sub">
          Nothing recorded. If you pick something up, add it here and your workouts,
          meals and challenges will work around it.
        </div>
      )}

      {result && (
        <div className="auth-notice">
          <Check size={15} /> <span>{result}</span>
        </div>
      )}

      {adding && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          <input
            className="form-input"
            autoFocus
            placeholder="e.g. upper hamstring strain, left leg"
            value={newInjury}
            onChange={(e) => setNewInjury(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addInjury()}
          />
          <SeveritySlider value={newSeverity} onChange={setNewSeverity} />
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="generate-btn" style={{ flex: 1 }} onClick={addInjury} disabled={busy || !newInjury.trim()}>
              {busy ? <><RefreshCw size={15} className="spin" /> Saving…</> : 'Track this'}
            </button>
            <button className="ghost-btn" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </div>
      )}

      {injuries.map((injury) => {
        const improving = (injury.improvement ?? 0) > 0;
        const worsening = (injury.improvement ?? 0) < 0;
        const Trend = improving ? TrendingDown : worsening ? TrendingUp : Minus;
        const trendColour = improving ? '#34D399' : worsening ? '#F87171' : '#667085';

        return (
          <div
            key={injury.id}
            style={{
              padding: '0.9rem',
              borderRadius: '0.75rem',
              background: '#12151B',
              border: `1px solid ${injury.needs_attention ? 'rgba(248,113,113,0.4)' : '#2A3240'}`,
              display: 'grid',
              gap: '0.7rem',
            }}
          >
            <div className="flex items-center justify-between" style={{ gap: '0.75rem' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{injury.label}</div>
                <div className="section-sub" style={{ marginTop: 2 }}>
                  {SEVERITY_LABELS[injury.severity]} · {injury.severity}/10
                  {injury.days_since_start > 0 && ` · day ${injury.days_since_start}`}
                </div>
              </div>
              <Trend size={16} color={trendColour} style={{ flexShrink: 0 }} />
            </div>

            {/* Severity over time. A single number says little; the shape of
                the last few check-ins is the useful part. */}
            {injury.history?.length > 1 && (
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 28 }}>
                {injury.history.map((h, i) => (
                  <div
                    key={i}
                    title={`${h.severity}/10`}
                    style={{
                      flex: 1,
                      height: `${Math.max(8, (h.severity / 10) * 100)}%`,
                      borderRadius: 2,
                      background: h.severity >= 7 ? '#F87171'
                        : h.severity >= 4 ? '#FBBF24' : '#34D399',
                      opacity: 0.4 + (i / injury.history.length) * 0.6,
                    }}
                  />
                ))}
              </div>
            )}

            {injury.needs_attention && (
              <div className="auth-error" style={{ fontSize: '0.75rem' }}>
                <AlertCircle size={14} />
                <span>This is worth getting looked at rather than training around.</span>
              </div>
            )}

            {checkingIn === injury.id ? (
              <div style={{ display: 'grid', gap: '0.7rem' }}>
                <SeveritySlider value={severity} onChange={setSeverity} />
                <input
                  className="form-input"
                  placeholder="Anything else? (optional)"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="generate-btn" style={{ flex: 1 }} onClick={submitCheckIn} disabled={busy}>
                    {busy ? <><RefreshCw size={15} className="spin" /> Saving…</> : 'Save check-in'}
                  </button>
                  <button className="ghost-btn" onClick={() => setCheckingIn(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <button
                className={injury.checkin_due ? 'generate-btn' : 'ghost-btn'}
                style={{ width: '100%' }}
                onClick={() => openCheckIn(injury)}
              >
                {injury.checkin_due
                  ? <>How is it doing? <ChevronRight size={15} /></>
                  : <>Update{injury.last_checked_days_ago != null && injury.last_checked_days_ago > 0
                      ? ` · last checked ${injury.last_checked_days_ago}d ago` : ''}</>}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SeveritySlider({ value, onChange }) {
  return (
    <div style={{ display: 'grid', gap: '0.35rem' }}>
      <div className="flex items-center justify-between">
        <span className="section-sub">How bad is it right now?</span>
        <span
          className="tabular"
          style={{
            fontWeight: 700,
            color: value >= 7 ? '#F87171' : value >= 4 ? '#FBBF24' : '#34D399',
          }}
        >
          {value}/10 · {SEVERITY_LABELS[value]}
        </span>
      </div>
      <input
        type="range"
        className="range-slider"
        min={0}
        max={10}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className="flex items-center justify-between" style={{ fontSize: '0.6875rem', color: '#556070' }}>
        <span>Gone</span><span>Severe</span>
      </div>
    </div>
  );
}
