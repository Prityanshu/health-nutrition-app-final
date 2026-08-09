import { useEffect, useState } from 'react';

/**
 * Is this a phone-sized screen?
 *
 * WHY A HOOK AND NOT A MEDIA QUERY
 * --------------------------------
 * Most of this app sets layout with inline `style={{ gridTemplateColumns }}`.
 * An inline style beats every stylesheet rule regardless of specificity, so a
 * `@media (max-width: 900px)` block simply cannot override it - which is why
 * the dashboard's three-column band kept rendering three columns on a 360px
 * phone, with the text overlapping into an unreadable mess.
 *
 * The honest fix for an inline layout is to decide it in JS. This hook is that
 * decision, in one place, so the breakpoint cannot drift between components.
 */

// Below this a three-column layout is never readable, whatever the content.
export const PHONE_MAX = 760;

const query = () =>
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia(`(max-width: ${PHONE_MAX}px)`)
    : null;

export default function useIsPhone() {
  const [isPhone, setIsPhone] = useState(() => query()?.matches ?? false);

  useEffect(() => {
    const mq = query();
    if (!mq) return undefined;

    const update = (e) => setIsPhone(e.matches);
    // Safari below 14 only has the deprecated listener API, and Capacitor's
    // webview on older Android is similarly behind. Falling back keeps the
    // layout correct instead of silently freezing at its initial value.
    if (mq.addEventListener) {
      mq.addEventListener('change', update);
      return () => mq.removeEventListener('change', update);
    }
    mq.addListener(update);
    return () => mq.removeListener(update);
  }, []);

  return isPhone;
}
