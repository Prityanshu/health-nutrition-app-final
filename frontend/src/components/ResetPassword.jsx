import React, { useEffect, useState } from 'react';
import { AlertCircle, Check, Loader2, Lock } from 'lucide-react';
import Lotus from './Lotus';

/**
 * The screen the emailed reset link opens.
 *
 * WHY IT CHECKS THE TOKEN ON MOUNT
 * --------------------------------
 * A reset link can be stale in three ordinary ways - already used, expired, or
 * simply wrong. Finding that out only after someone has chosen a password and
 * typed it twice is a small cruelty, so the token is checked as soon as the
 * screen opens and a dead link says so immediately.
 *
 * The failure messages are specific on purpose. "Invalid link" covers all
 * three cases and helps with none of them: expired and already-used both mean
 * "ask for another", but already-used on a link you never clicked is worth
 * noticing.
 *
 * There is no enumeration concern here. The token is 256 bits of randomness,
 * so telling someone their guess was wrong tells them nothing they did not
 * already know.
 */

const MIN_LENGTH = 6;

export default function ResetPassword({ apiBase, token, onDone, onCancel }) {
  const [checking, setChecking] = useState(true);
  const [tokenProblem, setTokenProblem] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');

  useEffect(() => {
    document.body.classList.add('theme-dark');
    return () => document.body.classList.remove('theme-dark');
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `${apiBase}/auth/reset-password/check?token=${encodeURIComponent(token)}`
        );
        const data = await res.json().catch(() => ({}));
        if (cancelled) return;
        if (!data.valid) setTokenProblem(data.message || 'That reset link is not valid.');
      } catch {
        if (!cancelled) setTokenProblem('Could not reach the server to check that link.');
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => { cancelled = true; };
  }, [apiBase, token]);

  const submit = async (e) => {
    e.preventDefault();
    setError('');

    // Checked here as well as on the server so a mismatch costs a keystroke
    // rather than a round trip - and, more importantly, so a typo does not
    // burn the one-shot link.
    if (password.length < MIN_LENGTH) {
      setError(`Choose a password of at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError('Those two passwords do not match.');
      return;
    }

    setBusy(true);
    try {
      const res = await fetch(`${apiBase}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setDone(data.message || 'Your password has been changed.');
        setTimeout(() => onDone?.(), 1800);
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Could not change the password.');
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: '1.5rem',
    }}>
      <div className="surface" style={{ padding: '1.75rem', maxWidth: 420, width: '100%' }}>
        <div style={{ display: 'grid', gap: '0.5rem', justifyItems: 'center', textAlign: 'center', marginBottom: '1.25rem' }}>
          <Lotus size={54} />
          <div style={{ fontSize: '1.125rem', fontWeight: 700 }}>Choose a new password</div>
        </div>

        {checking && (
          <div className="section-sub" style={{ textAlign: 'center', padding: '1rem' }}>
            <Loader2 size={16} className="spin" /> Checking that link…
          </div>
        )}

        {!checking && tokenProblem && (
          <div style={{ display: 'grid', gap: '1rem' }}>
            <div className="auth-error">
              <AlertCircle size={15} /> <span>{tokenProblem}</span>
            </div>
            <button className="generate-btn" onClick={onCancel} style={{ justifyContent: 'center' }}>
              Back to sign in
            </button>
          </div>
        )}

        {!checking && !tokenProblem && !done && (
          <form onSubmit={submit} style={{ display: 'grid', gap: '0.875rem' }}>
            <div style={{ display: 'grid', gap: '0.4rem' }}>
              <label className="section-title" style={{ fontSize: '0.8125rem' }}>New password</label>
              <input
                className="form-input" type="password" autoFocus
                autoComplete="new-password" placeholder="••••••••"
                value={password} onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div style={{ display: 'grid', gap: '0.4rem' }}>
              <label className="section-title" style={{ fontSize: '0.8125rem' }}>Again, to be sure</label>
              <input
                className="form-input" type="password"
                autoComplete="new-password" placeholder="••••••••"
                value={confirm} onChange={(e) => setConfirm(e.target.value)}
              />
            </div>

            {error && (
              <div className="auth-error">
                <AlertCircle size={15} /> <span>{error}</span>
              </div>
            )}

            <button type="submit" className="generate-btn" disabled={busy} style={{ justifyContent: 'center' }}>
              {busy
                ? <><Loader2 size={15} className="spin" /> Saving…</>
                : <><Lock size={15} /> Set my password</>}
            </button>

            <button type="button" className="ghost-btn" onClick={onCancel} style={{ justifyContent: 'center' }}>
              Cancel
            </button>
          </form>
        )}

        {done && (
          <div style={{ display: 'grid', gap: '0.75rem', justifyItems: 'center', textAlign: 'center' }}>
            <div className="flex items-center justify-center" style={{
              width: 40, height: 40, borderRadius: 12,
              background: 'rgba(var(--success-rgb), 0.16)', color: 'var(--success)',
            }}>
              <Check size={20} />
            </div>
            <div style={{ fontSize: '0.9375rem' }}>{done}</div>
            <div className="section-sub">Taking you to sign in…</div>
          </div>
        )}
      </div>
    </div>
  );
}
