import React, { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
  Plus, X, Sparkles, RefreshCw, Copy, Check, Download, Share2, History, Mail,
} from 'lucide-react';
import renderMarkdown from './markdown';
import useIsPhone from '../useIsPhone';
import { saveFile, shareFile } from '../nativeFiles';
import { toast, toastError } from '../Toast';

/**
 * Shared building blocks for the specialist pages (FitMentor, BudgetChef,
 * Explorer, Meal Planner).
 *
 * These four screens were all the same shape - a stack of labels, selects,
 * number inputs and checkboxes. Factoring the pieces out means each page is a
 * short declaration of its own fields rather than 300 lines of repeated
 * markup, and any future specialist gets the same look for free.
 */

/* ---------------------------------------------------------------- layout */

export function PageHero({ icon: Icon, title, subtitle, gradient = '#8B5CF6,#22D3EE' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
      <div
        className="flex items-center justify-center"
        style={{
          width: 52, height: 52, borderRadius: 15, flexShrink: 0,
          background: `linear-gradient(135deg,${gradient})`,
          boxShadow: `0 0 28px -6px ${gradient.split(',')[0]}b3`,
        }}
      >
        <Icon size={25} color="#fff" />
      </div>
      {/* min-width:0 is what lets the text wrap instead of pushing the flex
          row wider than the screen - a long subtitle was overflowing the
          viewport and making the whole page swipe sideways. */}
      <div style={{ minWidth: 0, flex: 1 }}>
        <h1 className="hero-title" style={{ fontWeight: 700, letterSpacing: '-0.02em' }}>{title}</h1>
        <p className="section-sub hero-sub">{subtitle}</p>
      </div>
    </div>
  );
}

export function Section({ title, hint, children, right, hero = false }) {
  return (
    <div className={hero ? 'surface-hero' : 'surface'} style={{ padding: '1.25rem', display: 'grid', gap: '0.875rem' }}>
      {(title || right) && (
        <div className="flex items-center justify-between" style={{ gap: '0.75rem' }}>
          <div>
            {title && <div className="section-title">{title}</div>}
            {hint && <div className="section-sub">{hint}</div>}
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------- inputs */

/** Icon tiles for a single choice - replaces a <select>. */
export function TileGroup({ options, value, onChange, columns }) {
  const isPhone = useIsPhone();
  // Four tiles across a 360px screen leaves ~75px each - not enough for
  // "Intermediate" or "Bodyweight" at a readable size. Two columns on a
  // phone, so the label has room and the tile is a comfortable tap target.
  const requested = columns || Math.min(options.length, 4);
  const cols = isPhone ? Math.min(requested, 2) : requested;
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
      gap: isPhone ? '0.5rem' : '0.4375rem',
    }}>
      {options.map(({ key, label, icon: Icon, sub }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`choice-tile ${value === key ? 'is-active' : ''}`}
          title={sub || label}
        >
          {Icon && <Icon size={17} />}
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}

/** Slider with a live readout and optional presets. */
export function SliderField({
  value, onChange, min, max, step = 1, presets, unit = '', format,
}) {
  const pct = ((value - min) / (max - min)) * 100;
  const shown = format ? format(value) : `${value}${unit}`;
  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: '0.625rem' }}>
        <span style={{ fontSize: '0.75rem', color: '#98A2B3' }}>Drag to adjust</span>
        <span className="pill pill-brand tabular">{shown}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="range-slider"
        style={{ '--pct': `${pct}%` }}
      />
      {presets && (
        <div style={{ display: 'flex', gap: '0.375rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
          {presets.map((p) => (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`suggest-chip ${value === p ? 'is-active' : ''}`}
            >
              {format ? format(p) : `${p}${unit}`}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Multi-select toggle chips. */
export function ChipToggles({ options, values, onChange }) {
  const toggle = (k) =>
    onChange(values.includes(k) ? values.filter((v) => v !== k) : [...values, k]);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
      {options.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          onClick={() => toggle(key)}
          className={`toggle-chip ${values.includes(key) ? 'is-active' : ''}`}
        >
          {Icon && <Icon size={14} />} {label}
          {values.includes(key) && <Check size={13} />}
        </button>
      ))}
    </div>
  );
}

/** Free-text chip list with suggestions. */
export function ChipInput({ values, onChange, placeholder, suggestions = [], suggestLabel }) {
  const [draft, setDraft] = useState('');
  const ref = useRef(null);

  const add = (v) => {
    const clean = (v || '').trim().toLowerCase();
    if (!clean || values.includes(clean)) return;
    onChange([...values, clean]);
    setDraft('');
    ref.current?.focus();
  };

  const remaining = suggestions
    .map((s) => s.toLowerCase())
    .filter((s, i, a) => a.indexOf(s) === i && !values.includes(s))
    .slice(0, 8);

  return (
    <div style={{ display: 'grid', gap: '0.75rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          ref={ref}
          className="form-input"
          style={{ flex: 1 }}
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); add(draft); }
            if (e.key === 'Backspace' && !draft && values.length) {
              onChange(values.slice(0, -1));
            }
          }}
        />
        <button
          className="btn btn-primary"
          onClick={() => add(draft)}
          disabled={!draft.trim()}
          style={{ opacity: draft.trim() ? 1 : 0.45 }}
        >
          <Plus size={16} />
        </button>
      </div>

      {values.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4375rem' }}>
          {values.map((v) => (
            <span key={v} className="ingredient-chip" onClick={() => onChange(values.filter((x) => x !== v))}>
              {v}<X size={13} />
            </span>
          ))}
        </div>
      )}

      {remaining.length > 0 && (
        <div>
          {suggestLabel && (
            <div style={{ fontSize: '0.6875rem', color: '#667085', marginBottom: '0.5rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {suggestLabel}
            </div>
          )}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4375rem' }}>
            {remaining.map((s) => (
              <button key={s} className="suggest-chip" onClick={() => add(s)}>
                <Plus size={12} /> {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ generation */

/**
 * Primary action with staged captions.
 *
 * These calls take 15-30 seconds. A static spinner reads as frozen, so the
 * caption advances to show work is happening.
 */
export function GenerateButton({ onClick, loading, disabled, label, stages }) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    if (!loading) return setStage(0);
    const t = setInterval(() => setStage((s) => (s + 1) % stages.length), 2600);
    return () => clearInterval(t);
  }, [loading, stages.length]);

  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className="generate-btn"
      style={{ opacity: disabled ? 0.5 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}
    >
      {loading
        ? <><RefreshCw size={17} className="spin" />{stages[stage]}</>
        : <><Sparkles size={17} />{label}</>}
    </button>
  );
}

export function LoadingSkeleton() {
  return (
    <div className="surface" style={{ padding: '1.5rem', display: 'grid', gap: '0.75rem' }}>
      <div className="skeleton" style={{ height: 24, width: '55%' }} />
      <div className="skeleton" style={{ height: 14 }} />
      <div className="skeleton" style={{ height: 14, width: '88%' }} />
      <div className="skeleton" style={{ height: 14, width: '72%' }} />
    </div>
  );
}

export function ErrorNote({ children }) {
  if (!children) return null;
  return (
    <div className="surface" style={{ padding: '0.9375rem', borderColor: '#F87171', color: '#F87171', fontSize: '0.875rem' }}>
      {children}
    </div>
  );
}

/** Markdown result with copy / regenerate and meta pills. */
export function ResultPanel({
  title, icon: Icon, accent = '#FBBF24', markdown, pills = [], onRegenerate, footer,
  apiBase, savedPlan, planType, params,
}) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(markdown || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="surface-hero" style={{ padding: '1.5rem', display: 'grid', gap: '1.125rem' }}>
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          {Icon && <Icon size={18} color={accent} />}
          <span style={{ fontWeight: 700, fontSize: '1.0625rem' }}>{title}</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="ghost-btn" onClick={copy}>
            {copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy</>}
          </button>
          {onRegenerate && (
            <button className="ghost-btn" onClick={onRegenerate}>
              <RefreshCw size={14} /> Another
            </button>
          )}
          {apiBase && (savedPlan || markdown) && (
            <PlanActions
              apiBase={apiBase} plan={savedPlan} compact
              planType={planType} content={markdown} params={params} title={title}
            />
          )}
        </div>
      </div>

      {pills.length > 0 && (
        <div style={{ display: 'flex', gap: '0.4375rem', flexWrap: 'wrap' }}>
          {pills.map((p, i) => (
            <span key={i} className={`pill ${p.tone || 'pill-muted'}`}>{p.label}</span>
          ))}
        </div>
      )}

      <hr className="hairline" />
      <div className="recipe-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(markdown) }} />
      {footer}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, body }) {
  return (
    <div className="surface" style={{ padding: '2.5rem 1.5rem', textAlign: 'center' }}>
      <Icon size={30} color="#3A4453" style={{ marginBottom: '0.75rem' }} />
      <div style={{ color: '#98A2B3', fontSize: '0.9375rem', fontWeight: 600 }}>{title}</div>
      <div style={{ color: '#667085', fontSize: '0.8125rem', marginTop: 5, maxWidth: 380, marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.55 }}>
        {body}
      </div>
    </div>
  );
}

/* --------------------------------------------------------- persistence */

const authHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${localStorage.getItem('token')}`,
});

/**
 * Keep a generated plan across sessions.
 *
 * Plans previously lived only in React state, so closing the tab - or
 * backgrounding the app on a phone, which often unloads it - lost them. This
 * loads whatever was saved last on mount and writes new output back, so you
 * can close the app mid-workout and come back to the same plan.
 */
export function usePersistentPlan(apiBase, planType) {
  const [saved, setSaved] = useState(null);
  const [restoring, setRestoring] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${apiBase}/plans/current/${planType}`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setSaved(d || null); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setRestoring(false); });
    return () => { cancelled = true; };
  }, [apiBase, planType]);

  const persist = async (content, params, title) => {
    if (!content) return null;
    try {
      const res = await fetch(`${apiBase}/plans/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ plan_type: planType, content, params, title }),
      });
      if (!res.ok) return null;
      const stored = await res.json();
      setSaved(stored);
      return stored;
    } catch {
      return null; // saving is best-effort; never block showing the plan
    }
  };

  const clear = () => setSaved(null);

  return { saved, restoring, persist, clear };
}

/**
 * Download and share for one specific plan.
 *
 * Each plan is fetched by its own id, so they download independently rather
 * than bundling everything into one file.
 */
export function PlanActions({
  apiBase, plan, compact = false,
  // Fallbacks so the buttons still work if the background save failed.
  planType, content, params, title,
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState('');
  const [localPlan, setLocalPlan] = useState(null);
  const [emailAvailable, setEmailAvailable] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [anchor, setAnchor] = useState(null);
  const emailBtnRef = useRef(null);
  const [defaultEmail, setDefaultEmail] = useState('');

  // Only offer Email when the server has SMTP configured - a button that
  // always fails is worse than no button.
  useEffect(() => {
    fetch(`${apiBase}/plans/email/status`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setEmailAvailable(Boolean(d?.enabled));
        setDefaultEmail(d?.default_recipient || '');
      })
      .catch(() => {});
  }, [apiBase]);

  const effective = plan || localPlan;

  // Only hide when there is genuinely nothing to export. Previously this
  // returned null whenever the background save had not completed, which made
  // the buttons silently disappear and looked like a missing feature.
  if (!effective?.id && !content) return null;

  /** Ensure the plan exists server-side, saving it now if it doesn't. */
  const ensureSaved = async () => {
    if (effective?.id) return effective;
    const res = await fetch(`${apiBase}/plans/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ plan_type: planType, content, params, title }),
    });
    if (!res.ok) throw new Error('save');
    const stored = await res.json();
    setLocalPlan(stored);
    return stored;
  };

  const fetchPdf = async () => {
    const target = await ensureSaved();
    const res = await fetch(`${apiBase}/plans/${target.id}/pdf`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    });
    if (!res.ok) {
      let detail = '';
      try { detail = (await res.json()).detail || ''; } catch { /* not JSON */ }
      throw new Error(detail || `pdf-${res.status}`);
    }
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    return { blob: await res.blob(), filename: match ? match[1] : 'plan.pdf' };
  };

  /*
   * Both buttons go through nativeFiles rather than touching the DOM.
   *
   * They used to create an <a download> and call navigator.share directly.
   * Neither exists in the Android WebView, and neither throws when it is
   * missing - so in the APK the anchor click did nothing, the share check fell
   * through to that same dead anchor, and the app then displayed "Downloaded".
   * A button that reports success while doing nothing is worse than one that
   * is visibly broken, because there is nothing to report.
   */

  const download = async () => {
    setBusy(true); setDone('');
    try {
      const { blob, filename } = await fetchPdf();
      const { native, where, cancelled } = await saveFile(blob, filename);
      // The Documents folder was refused and the share sheet came up instead,
      // and the user backed out of it. Nothing was saved, so say nothing.
      if (cancelled) { setDone(''); return; }
      const message = native ? `Saved to ${where}` : 'Downloaded';
      setDone(message);
      toast(message, { detail: filename });
    } catch (e) {
      // Surface the actual reason - a missing reportlab install is the most
      // likely cause and is not something the user can guess at.
      const msg = String(e?.message || '');
      const failure = msg.includes('reportlab') ? 'Server needs: pip install reportlab'
        : msg === 'save' ? 'Could not save the plan'
        : 'Download failed';
      setDone(failure);
      toastError(failure, msg.includes('reportlab') ? '' : msg.slice(0, 120));
    } finally {
      setBusy(false);
      setTimeout(() => setDone(''), 4000);
    }
  };

  const share = async () => {
    setBusy(true); setDone('');
    try {
      const { blob, filename } = await fetchPdf();
      const { method, cancelled } = await shareFile(
        blob, filename, effective?.title || title || 'My plan',
      );
      if (cancelled) { setDone(''); return; }

      const message = method === 'download'
        // Only ever shown in a desktop browser now, which genuinely cannot
        // share a file. In the app this branch is unreachable.
        ? 'Downloaded — this browser cannot share files'
        : 'Shared';
      setDone(message);
      if (method === 'download') toast(message, { detail: filename });
    } catch (e) {
      if (e?.name === 'AbortError') { setDone(''); return; }
      setDone('Share failed');
      toastError('Share failed', String(e?.message || '').slice(0, 120));
    } finally {
      setBusy(false);
      setTimeout(() => setDone(''), 2600);
    }
  };

  const emailPlan = async ({ toEmail, note }) => {
    setBusy(true); setDone('');
    try {
      const target = await ensureSaved();
      const res = await fetch(`${apiBase}/plans/${target.id}/email`, {
        method: 'POST',
        headers: authHeaders(),
        // Omitting to_email tells the server to use the account's own address.
        body: JSON.stringify({ to_email: toEmail || null, note: note || null }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setDone(data.was_self ? 'Sent to your inbox' : `Sent to ${data.to}`);
        setEmailOpen(false);
      } else {
        setDone(data.detail || 'Email failed');
      }
    } catch {
      setDone('Email failed');
    } finally {
      setBusy(false);
      setTimeout(() => setDone(''), 5000);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
      <button className="ghost-btn" onClick={download} disabled={busy}>
        <Download size={14} /> {compact ? 'PDF' : 'Download PDF'}
      </button>
      <button className="ghost-btn" onClick={share} disabled={busy}>
        <Share2 size={14} /> Share
      </button>
      {emailAvailable && (
        <>
          <button
            ref={emailBtnRef}
            className="ghost-btn"
            onClick={() => {
              // Capture the button's viewport rect. The popover renders into
              // document.body and positions itself against these numbers.
              const r = emailBtnRef.current?.getBoundingClientRect();
              setAnchor(r ? { top: r.top, bottom: r.bottom, left: r.left, right: r.right } : null);
              setEmailOpen((o) => !o);
            }}
            disabled={busy}
          >
            <Mail size={14} /> Email
          </button>
          {emailOpen && (
            <EmailDialog
              anchor={anchor}
              ignoreRef={emailBtnRef}
              defaultAddress={defaultEmail}
              busy={busy}
              onSend={emailPlan}
              onClose={() => setEmailOpen(false)}
            />
          )}
        </>
      )}
      {done && (
        <span style={{
          fontSize: '0.6875rem',
          color: /fail|could not|needs|refus|reject|limit/i.test(done) ? '#F87171' : '#34D399',
          maxWidth: 260, lineHeight: 1.35,
        }}>
          {done}
        </span>
      )}
    </div>
  );
}

/**
 * Recipient picker.
 *
 * Sending to yourself is the common case, so it is one click and preselected.
 * Sending to someone else - a trainer, a dietitian, a friend - reveals an
 * address field and an optional note, because a plan arriving unannounced in a
 * stranger's inbox needs context.
 */
function EmailDialog({ anchor, ignoreRef, defaultAddress, busy, onSend, onClose }) {
  const [mode, setMode] = useState('self');
  const [address, setAddress] = useState('');
  const [note, setNote] = useState('');
  const [pos, setPos] = useState(null);
  const ref = useRef(null);

  // Close on outside click, Escape, or scroll. Scrolling matters because the
  // popover is viewport-positioned and would otherwise detach from its button.
  useEffect(() => {
    const onDown = (e) => {
      if (ref.current && ref.current.contains(e.target)) return;
      // The Email button gets to handle its own click, otherwise mousedown
      // closes the popover and the click immediately reopens it - so the
      // button would never close what it opened.
      if (ignoreRef?.current && ignoreRef.current.contains(e.target)) return;
      onClose();
    };
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onClose, true);
    window.addEventListener('resize', onClose);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onClose, true);
      window.removeEventListener('resize', onClose);
    };
  }, [onClose, ignoreRef]);

  const valid = mode === 'self' || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(address.trim());

  const send = () => {
    if (!valid || busy) return;
    onSend({ toEmail: mode === 'self' ? null : address.trim(), note: mode === 'other' ? note : null });
  };

  const WIDTH = 300;
  const GAP = 8;

  // Measure the real height rather than guessing it. The popover grows when
  // "Someone else" is chosen, and a wrong guess is what decides whether it
  // flips above the button or hangs off the bottom of the screen.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { height } = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // Prefer below the button; go above if it would not fit; if neither fits
    // (a short window), sit against the bottom edge.
    let top = (anchor?.bottom ?? 100) + GAP;
    if (top + height > vh - 12) {
      const above = (anchor?.top ?? 0) - height - GAP;
      top = above >= 12 ? above : Math.max(12, vh - height - 12);
    }

    // Right-aligned to the button, then clamped inside the viewport.
    let left = (anchor?.right ?? WIDTH + 16) - WIDTH;
    left = Math.max(12, Math.min(left, vw - WIDTH - 12));

    setPos({ top, left });
  }, [anchor, mode]);

  /*
   * Rendered into <body> through a portal.
   *
   * position:fixed alone was not enough. `.stagger > *` keeps a transform
   * after its entry animation (fill mode `forwards`), and an ancestor with any
   * transform becomes the containing block for fixed-position descendants - so
   * the popover was being offset by the card's position instead of the
   * viewport's. That put it off the right edge on FitMentor and halfway down
   * the day list on the meal planner. A portal removes it from that subtree
   * entirely, which no amount of z-index or overflow tuning could do.
   */
  return createPortal(
    <div
      ref={ref}
      className="surface"
      style={{
        position: 'fixed',
        top: pos?.top ?? -9999,
        left: pos?.left ?? -9999,
        // Hidden for the single frame between mount and measurement, so it
        // never appears in the wrong place first.
        visibility: pos ? 'visible' : 'hidden',
        zIndex: 9999,
        width: WIDTH, padding: '1rem', display: 'grid', gap: '0.75rem',
        boxShadow: '0 20px 50px -12px rgba(0,0,0,0.9)',
        animation: 'fade-up 0.18s ease both',
      }}
    >
      <div className="section-title" style={{ fontSize: '0.8125rem' }}>Send this plan to</div>

      <button
        onClick={() => setMode('self')}
        className={`toggle-chip ${mode === 'self' ? 'is-active' : ''}`}
        style={{ justifyContent: 'flex-start', width: '100%' }}
      >
        <Mail size={14} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {defaultAddress || 'My email'}
        </span>
        {mode === 'self' && <Check size={13} style={{ marginLeft: 'auto' }} />}
      </button>

      <button
        onClick={() => setMode('other')}
        className={`toggle-chip ${mode === 'other' ? 'is-active' : ''}`}
        style={{ justifyContent: 'flex-start', width: '100%' }}
      >
        <Share2 size={14} />
        <span>Someone else</span>
        {mode === 'other' && <Check size={13} style={{ marginLeft: 'auto' }} />}
      </button>

      {mode === 'other' && (
        <>
          <input
            className="form-input"
            autoFocus
            type="email"
            placeholder="their@email.com"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
          />
          <input
            className="form-input"
            placeholder="Add a note (optional)"
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
          />
          {address && !valid && (
            <div style={{ fontSize: '0.6875rem', color: '#F87171' }}>
              That doesn't look like an email address.
            </div>
          )}
        </>
      )}

      <button
        className="btn btn-primary"
        onClick={send}
        disabled={!valid || busy}
        style={{ justifyContent: 'center', opacity: valid && !busy ? 1 : 0.45, padding: '0.5rem' }}
      >
        {busy
          ? <><RefreshCw size={14} className="spin" style={{ marginRight: 6 }} /> Sending…</>
          : <><Mail size={14} style={{ marginRight: 6 }} /> Send PDF</>}
      </button>
    </div>,
    document.body
  );
}

/** Banner shown when a plan was restored from a previous session. */
export function RestoredNote({ createdAt, onDismiss }) {
  if (!createdAt) return null;
  const when = new Date(createdAt);
  const days = Math.floor((Date.now() - when.getTime()) / 86400000);
  const ago = days === 0 ? 'earlier today' : days === 1 ? 'yesterday' : `${days} days ago`;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.625rem',
      background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.25)',
      borderRadius: '0.75rem', padding: '0.75rem 1rem', fontSize: '0.8125rem', color: '#34D399',
    }}>
      <History size={15} style={{ flexShrink: 0 }} />
      <span style={{ flex: 1 }}>Picking up the plan you made {ago}.</span>
      {onDismiss && (
        <button onClick={onDismiss} className="ghost-btn" style={{ padding: '0.25rem 0.5rem' }}>
          Start fresh
        </button>
      )}
    </div>
  );
}

/** Shared fetch + state for a generate-style specialist page. */
export function useGenerator(apiBase, path) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const generate = async (body) => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch(`${apiBase}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok && data.success && data.data) {
        setResult(data.data);
      } else {
        setError(
          typeof data.detail === 'string' ? data.detail
            : data.message || 'That didn\'t work. Try again in a moment.'
        );
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return { result, loading, error, generate, setError };
}
