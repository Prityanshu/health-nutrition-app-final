/**
 * Colours that need an opacity.
 *
 * WHY THESE HELPERS EXIST
 * -----------------------
 * Several components build a translucent version of a colour by appending a
 * two-digit hex alpha to it:
 *
 *     boxShadow: `0 0 10px ${color}55`
 *
 * That works when `color` is "#22D3EE" and breaks silently the moment it
 * becomes "var(--cyan)", because `var(--cyan)55` is not a colour - the browser
 * drops the whole declaration and the glow just disappears. Nothing throws;
 * the shadow is simply gone.
 *
 * So anything that needs a tint carries the RGB TRIPLE variable name rather
 * than a colour string, and builds both the solid and the translucent form
 * from it. One source of truth, and a future palette change follows through to
 * the tints instead of leaving them behind.
 *
 * Comma-separated triples rather than the modern `rgb(r g b / a)` syntax on
 * purpose: the newer form needs a recent Chrome, and this ships inside an
 * Android WebView that can be several years old.
 */

/** Fully opaque, e.g. solid('--cyan-rgb') -> "rgb(var(--cyan-rgb))" */
export const solid = (rgbVar) => `rgb(var(${rgbVar}))`;

/** Translucent, e.g. tint('--cyan-rgb', 0.33) -> "rgba(var(--cyan-rgb), 0.33)" */
export const tint = (rgbVar, alpha) => `rgba(var(${rgbVar}), ${alpha})`;
