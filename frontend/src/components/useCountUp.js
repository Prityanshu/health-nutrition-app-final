import { useEffect, useRef, useState } from 'react';

/**
 * Animate a number from its previous value to the next one.
 *
 * Metrics that snap instantly read as static text; counting up makes them feel
 * measured. Uses requestAnimationFrame with an ease-out curve so the motion
 * decelerates rather than running at constant speed.
 *
 * Respects prefers-reduced-motion by jumping straight to the target.
 */
export default function useCountUp(target, duration = 900) {
  const safeTarget = Number.isFinite(target) ? target : 0;
  const [value, setValue] = useState(safeTarget);
  const fromRef = useRef(safeTarget);
  const frameRef = useRef();

  useEffect(() => {
    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduce || duration <= 0) {
      fromRef.current = safeTarget;
      setValue(safeTarget);
      return;
    }

    const from = fromRef.current;
    const delta = safeTarget - from;
    if (delta === 0) return;

    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setValue(from + delta * eased);
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = safeTarget;
      }
    };
    frameRef.current = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(frameRef.current);
  }, [safeTarget, duration]);

  return value;
}
