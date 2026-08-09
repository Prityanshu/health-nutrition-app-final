import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, AlertCircle, Info } from 'lucide-react';

/**
 * Transient confirmations.
 *
 * WHY THIS EXISTS
 * ---------------
 * Logging a meal already rendered a green "logged" card - but it rendered
 * *above* the analysis panel the user had just tapped. On a phone that panel is
 * the bottom of a long page, so the moment it disappeared the page got shorter,
 * the confirmation ended up somewhere off-screen above, and the action looked
 * like it had done nothing at all.
 *
 * A confirmation has to appear where the user is looking, not where the layout
 * happens to put it. Fixed positioning is the only thing that guarantees that
 * regardless of scroll position, so it lives outside the page flow entirely.
 *
 * No provider and no context: `toast()` is a plain function any module can
 * import and call, including from inside an async handler that has already
 * unmounted its own component. <ToastHost /> is mounted once in AppShell.
 */

let nextId = 1;
const listeners = new Set();

// Long enough to read a short sentence, short enough not to sit over the tab
// bar while someone is trying to use it.
const LIFETIME = 3200;

/**
 * Show a message.
 *
 * @param {string} message  the headline - keep it to a few words
 * @param {object} [opts]
 * @param {'success'|'error'|'info'} [opts.tone]
 * @param {string} [opts.detail]  a second line, for the numbers
 */
export function toast(message, opts = {}) {
  const entry = {
    id: nextId++,
    message: String(message || ''),
    tone: opts.tone || 'success',
    detail: opts.detail ? String(opts.detail) : '',
  };
  listeners.forEach((fn) => fn(entry));
  return entry.id;
}

export const toastError = (message, detail) => toast(message, { tone: 'error', detail });

const ICONS = { success: Check, error: AlertCircle, info: Info };

export default function ToastHost() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    const add = (entry) => {
      // Two at a time is plenty. A stack that grows without limit turns a
      // confirmation into a wall.
      setItems((current) => [...current.slice(-1), entry]);
      setTimeout(() => {
        setItems((current) => current.filter((i) => i.id !== entry.id));
      }, LIFETIME);
    };
    listeners.add(add);
    return () => listeners.delete(add);
  }, []);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <div className="toast-stack" role="status" aria-live="polite">
      {items.map((item) => {
        const Icon = ICONS[item.tone] || Check;
        return (
          <div key={item.id} className={`toast toast-${item.tone}`}>
            <span className="toast-icon"><Icon size={16} /></span>
            <span style={{ minWidth: 0 }}>
              <span className="toast-message">{item.message}</span>
              {item.detail && <span className="toast-detail">{item.detail}</span>}
            </span>
          </div>
        );
      })}
    </div>,
    document.body
  );
}
