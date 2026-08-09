import React, { useState, useEffect } from 'react';
import { Wifi, Loader2, Check, AlertCircle, Server } from 'lucide-react';
import { apiBase, getStoredBase, setStoredBase, testBase, isNativeApp } from '../apiBase';

/**
 * Where should the app look for the backend?
 *
 * Shown automatically on the phone when nothing is reachable, and reachable
 * on purpose from the profile screen.
 *
 * The alternative - baking the address in at build time - means a rebuild and
 * a fresh APK every time the laptop's IP changes, every time a tunnel restarts
 * and hands out a new URL, and for every friend on a different network. That
 * is a lot of re-installing to avoid one text box.
 */
export default function ServerSetup({ onSaved, embedded = false }) {
  const [value, setValue] = useState('');
  const [state, setState] = useState(null);      // {ok, message}
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setValue(getStoredBase() || apiBase());
  }, []);

  const save = async () => {
    setBusy(true);
    setState(null);
    const result = await testBase(value);
    setState(result);
    if (result.ok) {
      setStoredBase(value);
      // A full reload is deliberate: the API base is read once at module load
      // by every screen, so re-rendering would leave half the app pointing at
      // the old address.
      setTimeout(() => {
        if (onSaved) onSaved(result.base);
        else window.location.reload();
      }, 600);
    }
    setBusy(false);
  };

  const body = (
    <div style={{ display: 'grid', gap: '0.875rem' }}>
      <div>
        <div style={{ fontSize: '0.75rem', color: '#98A2B3', marginBottom: '0.5rem', lineHeight: 1.5 }}>
          The address of the machine running the backend. On the same WiFi this
          is your laptop's local IP — find it with{' '}
          <code style={{ color: '#A78BFA' }}>ipconfig getifaddr en0</code>.
        </div>
        <input
          className="form-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()}
          placeholder="192.168.1.5:8001"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          inputMode="url"
        />
        {/* Typing a bare IP is the common case, so say what it becomes rather
            than silently rewriting it. */}
        <div style={{ fontSize: '0.6875rem', color: '#667085', marginTop: 5 }}>
          http:// and /api are added automatically if you leave them out.
        </div>
      </div>

      {state && (
        <div style={{
          display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
          padding: '0.75rem', borderRadius: '0.625rem', fontSize: '0.8125rem',
          lineHeight: 1.5,
          background: state.ok ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)',
          border: `1px solid ${state.ok ? 'rgba(52,211,153,0.3)' : 'rgba(248,113,113,0.3)'}`,
          color: state.ok ? '#34D399' : '#F87171',
        }}>
          {state.ok ? <Check size={15} style={{ flexShrink: 0, marginTop: 2 }} />
                    : <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 2 }} />}
          <span>{state.message}</span>
        </div>
      )}

      <button
        className="btn btn-primary"
        onClick={save}
        disabled={busy || !value.trim()}
        style={{ justifyContent: 'center' }}
      >
        {busy ? <><Loader2 size={15} className="spin" /> Checking…</> : 'Connect'}
      </button>

      <div style={{ fontSize: '0.6875rem', color: '#667085', lineHeight: 1.6 }}>
        Not connecting? The laptop must be running{' '}
        <code style={{ color: '#98A2B3' }}>uvicorn main:app --host 0.0.0.0 --port 8001</code>
        {' '}— without <code style={{ color: '#98A2B3' }}>--host 0.0.0.0</code> it only
        accepts connections from the laptop itself.
      </div>
    </div>
  );

  if (embedded) {
    return (
      <div className="surface" style={{ padding: '1.25rem' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
          <span className="section-title">Server</span>
          <Server size={16} color="#A78BFA" />
        </div>
        {body}
      </div>
    );
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: '1.5rem',
    }}>
      <div className="surface" style={{ padding: '1.75rem', maxWidth: 420, width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
          <div style={{
            width: 40, height: 40, borderRadius: 12,
            background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Wifi size={20} color="#0B0E14" />
          </div>
          <div>
            <div style={{ fontSize: '1.125rem', fontWeight: 700 }}>Connect to your server</div>
            <div style={{ fontSize: '0.75rem', color: '#98A2B3' }}>
              {isNativeApp() ? 'Needed once per network' : 'Point the app at a backend'}
            </div>
          </div>
        </div>
        {body}
      </div>
    </div>
  );
}
