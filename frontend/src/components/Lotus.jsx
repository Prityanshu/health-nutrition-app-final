import React from 'react';
import markSrc from '../assets/kayosha-mark.png';
import logoSrc from '../assets/kayosha-logo.png';

/**
 * The Kayosha lotus mark.
 *
 * This is the real artwork, not a redrawing of it. An earlier version of this
 * file reconstructed the petals as SVG paths, which was sharper in principle
 * and wrong in practice - the proportions and the overlaps were subtly off,
 * and a logo that is nearly right reads as a cheap copy of itself.
 *
 * The source PNG has had its dark background keyed out by alpha rather than by
 * a hard colour threshold, so the anti-aliased strokes fade cleanly instead of
 * carrying a dark fringe onto whatever surface they sit on. Verified against
 * both the app background and pure white, down to 20px.
 */

// 775 x 427 in the source. Fixing the ratio here means callers give one number.
const MARK_RATIO = 427 / 775;

export default function Lotus({ size = 28, className, style, alt = '' }) {
  return (
    <img
      src={markSrc}
      alt={alt}
      aria-hidden={alt ? undefined : true}
      className={className}
      width={size}
      height={Math.round(size * MARK_RATIO)}
      style={{ display: 'block', objectFit: 'contain', ...style }}
    />
  );
}

/** The full lockup - mark, name and motto - as drawn in the original artwork. */
export function LogoLockup({ width = 220, className, style }) {
  return (
    <img
      src={logoSrc}
      alt="Kayosha - nourish, move, thrive"
      className={className}
      width={width}
      style={{ display: 'block', height: 'auto', maxWidth: '100%', ...style }}
    />
  );
}

/**
 * Name, mark and motto, laid out for the app chrome.
 *
 * Set as live text rather than using the image lockup, because in the sidebar
 * the name has to sit at the app's own type size and stay crisp at every zoom
 * level - and because the image's wordmark is white, which would disappear if
 * the shell ever renders on a light surface.
 */
export function Wordmark({ size = 'md', motto = true, style }) {
  const scale = { sm: 1, md: 1.2, lg: 1.9 }[size] || 1.2;

  return (
    <div style={{ display: 'grid', gap: 3, ...style }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: `${0.45 * scale}rem` }}>
        <span
          style={{
            fontWeight: 700,
            fontSize: `${scale}rem`,
            letterSpacing: '-0.015em',
            lineHeight: 1,
            color: 'var(--text)',
          }}
        >
          Kayosha
        </span>
        <Lotus size={30 * scale} />
      </div>
      {motto && (
        <div
          style={{
            fontSize: `${0.5 * scale}rem`,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: '#D264C8',
            fontWeight: 600,
            whiteSpace: 'nowrap',
          }}
        >
          Nourish. Move. Thrive.
        </div>
      )}
    </div>
  );
}
