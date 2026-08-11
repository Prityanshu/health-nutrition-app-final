/**
 * Shared injury-severity vocabulary.
 *
 * InjuryTracker and FitMentor both ask "how bad is it, 0-10", and the answer
 * has to mean the same thing in both places - a 6 that reads "Sore most days"
 * on the dashboard and "Moderate" in FitMentor is the same bug as two parsers
 * for one field. One table, imported twice.
 *
 * STAGES mirrors _STAGE_BY_SEVERITY in app/services/injury_taxonomy.py. That
 * duplication is deliberate (the UI has to show the consequence before it
 * calls the API) but it IS a drift risk, so scripts/test_severity.py parses
 * this file and asserts the two tables agree. If you change one, that test
 * fails until you change the other.
 */

export const SEVERITY_LABELS = [
  'Gone', 'Barely there', 'Mild', 'Noticeable', 'Nagging', 'Moderate',
  'Sore most days', 'Painful', 'Bad', 'Very bad', 'Severe',
];

// severity -> [stage key, what the plan will do about it]
export const STAGES = {
  0: ['return', 'Full training, rebuild speed and impact gradually'],
  1: ['return', 'Full training, rebuild speed and impact gradually'],
  2: ['strength', 'Loaded through full range, but no sprinting or jumping'],
  3: ['strength', 'Loaded through full range, but no sprinting or jumping'],
  4: ['controlled', 'Controlled range only, nothing fast or lengthening under load'],
  5: ['controlled', 'Controlled range only, nothing fast or lengthening under load'],
  6: ['acute', 'Static, pain-free work only around the injury'],
  7: ['acute', 'Static, pain-free work only around the injury'],
  8: ['medical', 'Too painful for a training plan — needs assessing first'],
  9: ['medical', 'Too painful for a training plan — needs assessing first'],
  10: ['medical', 'Too painful for a training plan — needs assessing first'],
};

/** Severity at or above this is refused by the backend, not worked around. */
export const BLOCKING_SEVERITY = 8;

/**
 * The RGB TRIPLE VARIABLE for a severity, not a colour string.
 *
 * Callers need both the solid colour and translucent versions of it, and a
 * `var(--danger)` string cannot have an alpha appended - see src/theme.js.
 * Wrap with solid() to render it.
 */
export const severityColor = (v) =>
  (v >= 8 ? '--danger-rgb' : v >= 6 ? '--orange-rgb' : v >= 4 ? '--warning-rgb' : '--success-rgb');

export const stageFor = (v) => STAGES[Math.max(0, Math.min(10, v))] || STAGES[5];

/**
 * The wire format. Severity travels inside the constraint string because
 * `injury_taxonomy.parse` already reads exactly this, and it is the same
 * shape `injury_service.as_constraints` emits for tracked injuries. Adding a
 * separate structured field would mean two ways to say the same thing.
 */
export const encodeInjury = ({ text, severity }) =>
  `${text.trim()} (severity ${severity}/10)`;

/** Inverse of encodeInjury, for restoring a saved plan's parameters. */
export const decodeInjury = (raw) => {
  const match = /^(.*?)\s*\(severity\s*(\d{1,2})\s*\/\s*10[^)]*\)\s*$/i.exec(String(raw));
  return match
    ? { text: match[1].trim(), severity: Math.max(0, Math.min(10, Number(match[2]))) }
    : { text: String(raw).trim(), severity: 5 };
};
