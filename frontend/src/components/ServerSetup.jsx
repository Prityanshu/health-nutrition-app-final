import React, { useState, useEffect } from 'react';
import { Wifi, Loader2, Check, AlertCircle, Server, RotateCcw } from 'lucide-react';
import {
  apiBase, getStoredBase, setStoredBase, testBase, isNativeApp,
  builtInBase, isOverridden, resetToBuiltIn,
} from '../apiBase';

/**
 * Where should the app look for the backend?
 *
 * Shown automatically on the phone when nothing is reachable, and reachable
 * on purpose from the profile screen.
 *
 * This used to be the ONLY way to set an address, because there was nothing
 * stable to bake in: a laptop's LAN IP changes with every network and a quick
 * tunnel hands out a new URL on every restart, so a compiled-in address meant
 * a rebuild and a re-install each time.
 *
 * A named tunnel has a permanent hostname, so the address is now compiled in
 * and this screen is the override rather than the only route. It still earns
 * its place - the tunnel goes down, someone tests against their own laptop,
 * the URL changes when the project moves - but nobody has to use it to get
 * started.
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
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem', lineHeight: 1.5 }}>
          The address of the machine running the backend. A tunnel hostname
          works here, and so does a laptop on the same WiFi — find that with{' '}
          <code style={{ color: 'var(--accent-soft)' }}>ipconfig getifaddr en0</code>.
        </div>
        <input
          className="form-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()}
          placeholder="my-laptop.tail1234.ts.net"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          inputMode="url"
        />
        {/* Typing a bare address is the common case, so say what it becomes
            rather than silently rewriting it. The two defaults differ, and a
            surprised user cannot tell why one worked and the other did not. */}
        <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', marginTop: 5 }}>
          <code style={{ color: 'var(--text-muted)' }}>/api</code> is added for you. A
          name like <code style={{ color: 'var(--text-muted)' }}>x.ts.net</code> is
          assumed to be https; an address like{' '}
          <code style={{ color: 'var(--text-muted)' }}>192.168.1.5</code> is assumed to be
          http on port 8001.
        </div>
      </div>

      {/* A manual address is stored forever and outranks the one the app was
          built with. Without a way back, someone who typed a LAN IP once keeps
          pointing at it after everyone else has moved to the tunnel - and the
          app simply stops working away from home with no clue why. */}
      {isOverridden() && builtInBase() && (
        <button
          className="ghost-btn"
          style={{ justifyContent: 'center' }}
          onClick={() => {
            const restored = resetToBuiltIn();
            setValue(restored);
            setState({ ok: true, message: `Back to the built-in address: ${restored}` });
            setTimeout(() => window.location.reload(), 800);
          }}
        >
          <RotateCcw size={14} /> Use the built-in address
        </button>
      )}

      {state && (
        <div style={{
          display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
          padding: '0.75rem', borderRadius: '0.625rem', fontSize: '0.8125rem',
          lineHeight: 1.5,
          background: state.ok ? 'rgba(var(--success-rgb),0.1)' : 'rgba(var(--danger-rgb),0.1)',
          border: `1px solid ${state.ok ? 'rgba(var(--success-rgb),0.3)' : 'rgba(var(--danger-rgb),0.3)'}`,
          color: state.ok ? 'var(--success)' : 'var(--danger)',
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

      <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', lineHeight: 1.6 }}>
        Not connecting? The laptop has to be awake with the server running —{' '}
        <code style={{ color: 'var(--text-muted)' }}>./scripts/serve-public.sh</code>{' '}
        starts it and opens the tunnel. On the same WiFi instead, it must be{' '}
        <code style={{ color: 'var(--text-muted)' }}>--host 0.0.0.0</code>: without that it
        only accepts connections from the laptop itself.
      </div>
    </div>
  );

  if (embedded) {
    return (
      <div className="surface" style={{ padding: '1.25rem' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
          <span className="section-title">Server</span>
          <Server size={16} color="var(--accent-soft)" />
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
            background: 'linear-gradient(135deg,var(--accent),var(--cyan))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Wifi size={20} color="var(--bg)" />
          </div>
          <div>
            <div style={{ fontSize: '1.125rem', fontWeight: 700 }}>Connect to your server</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {isNativeApp() ? 'Needed once per network' : 'Point the app at a backend'}
            </div>
          </div>
        </div>
        {body}
      </div>
    </div>
  );
}
