import React, { useState, useEffect } from 'react';
import {
  Dumbbell, Sprout, Activity, Flame, Home, Building2, HandMetal,
  TrendingDown, HeartPulse, Wind, Timer, AlertTriangle,
  MessageSquarePlus, Gauge, Zap, Clock3, Shuffle, Repeat, ShieldAlert, RefreshCw,
  X, Plus, Download,
} from 'lucide-react';
import {
  PageHero, Section, TileGroup, SliderField,
  GenerateButton, LoadingSkeleton, ErrorNote, ResultPanel, EmptyState, useGenerator,
  usePersistentPlan, RestoredNote,
} from './SpecialistUI';
import renderMarkdown from './markdown';
import { solid, tint } from '../theme';
import {
  SEVERITY_LABELS, BLOCKING_SEVERITY, severityColor, stageFor,
  encodeInjury, decodeInjury,
} from './severity';

/**
 * One injury, with its own severity.
 *
 * Severity used to be absent here entirely, so every injury was treated as a
 * default 5/10 - a niggle you'd train through and something that needs three
 * weeks off produced the same plan. The slider is per injury rather than one
 * global one because people rarely hurt in only one place, and a 2/10 wrist
 * alongside a 7/10 knee is a completely different week from both at 7.
 */
function InjuryRow({ injury, onChange, onRemove }) {
  const [, consequence] = stageFor(injury.severity);
  const colour = severityColor(injury.severity);
  const blocking = injury.severity >= BLOCKING_SEVERITY;

  return (
    <div style={{
      background: 'rgba(var(--white-rgb),0.03)',
      border: `1px solid ${blocking ? 'rgba(var(--danger-rgb),0.4)' : 'rgba(var(--white-rgb),0.08)'}`,
      borderRadius: '0.75rem', padding: '0.875rem', display: 'grid', gap: '0.625rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ flex: 1, fontSize: '0.875rem', fontWeight: 600, textTransform: 'capitalize' }}>
          {injury.text}
        </span>
        {injury.tracked && (
          <span className="pill pill-muted" style={{ fontSize: '0.625rem' }}>tracked</span>
        )}
        <span className="pill tabular" style={{
          fontSize: '0.6875rem', color: solid(colour),
          background: tint(colour, 0.1), border: `1px solid ${tint(colour, 0.27)}`,
        }}>
          {injury.severity}/10 · {SEVERITY_LABELS[injury.severity]}
        </span>
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${injury.text}`}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-faint)', display: 'flex', padding: 2,
          }}
        >
          <X size={15} />
        </button>
      </div>

      <input
        type="range" min={0} max={10} step={1}
        value={injury.severity}
        aria-label={`Severity of ${injury.text}`}
        onChange={(e) => onChange({ ...injury, severity: Number(e.target.value) })}
        className="range-slider"
        style={{ '--pct': `${injury.severity * 10}%`, accentColor: solid(colour) }}
      />

      {/* Showing the consequence before generating matters: severity is not a
          label, it decides what the plan is allowed to contain, and at 8+ it
          means no plan at all. Finding that out after a 20-second generation
          reads like a failure rather than a decision. */}
      <div style={{
        fontSize: '0.75rem', lineHeight: 1.5,
        color: blocking ? 'var(--danger)' : 'var(--text-muted)',
        display: 'flex', gap: '0.4rem', alignItems: 'flex-start',
      }}>
        {blocking && <ShieldAlert size={13} style={{ flexShrink: 0, marginTop: 2 }} />}
        <span>{consequence}</span>
      </div>
    </div>
  );
}

/**
 * One-tap adjustments.
 *
 * A blank feedback box mostly goes unused, and when it is used the wording is
 * often too vague for the model to act on - which wastes a full generation.
 * These send a precise instruction for the same cost.
 */
const QUICK_FEEDBACK = [
  { key: 'easier', label: 'Too hard', icon: Gauge,
    text: 'This is too hard for me. Reduce the volume and intensity - fewer sets, lower reps, more rest days.' },
  { key: 'harder', label: 'Too easy', icon: Zap,
    text: 'This is too easy. Increase the difficulty - more sets, higher intensity, harder progressions.' },
  { key: 'shorter', label: 'Less time', icon: Clock3,
    text: 'I have less time than this needs. Compress each session to about 20-25 minutes while keeping the important work.' },
  { key: 'more_cardio', label: 'More cardio', icon: Wind,
    text: 'Add more cardiovascular work across the week without cutting the strength sessions entirely.' },
  { key: 'more_strength', label: 'More strength', icon: Dumbbell,
    text: 'Shift the balance toward strength training and reduce the cardio.' },
  { key: 'swap', label: 'Swap a day', icon: Shuffle,
    text: 'Replace the hardest day with something different that trains the same areas.' },
  { key: 'variety', label: 'More variety', icon: Repeat,
    text: 'The exercises repeat too much. Vary the movements across the week while keeping the same structure.' },
  { key: 'injury', label: 'Something hurts', icon: ShieldAlert,
    text: '', needsDetail: true,
    detailPrompt: 'Which part of your body? e.g. "my left knee hurts when I squat"' },
];

const LEVELS = [
  { key: 'beginner', label: 'Beginner', icon: Sprout },
  { key: 'intermediate', label: 'Intermediate', icon: Activity },
  { key: 'advanced', label: 'Advanced', icon: Flame },
];

const GOALS = [
  { key: 'weight_loss', label: 'Lose fat', icon: TrendingDown },
  { key: 'muscle_gain', label: 'Build muscle', icon: Dumbbell },
  { key: 'endurance', label: 'Endurance', icon: Wind },
  { key: 'general_fitness', label: 'General', icon: HeartPulse },
];

const EQUIPMENT = [
  { key: 'none', label: 'Bodyweight', icon: HandMetal },
  { key: 'home', label: 'Home kit', icon: Home },
  { key: 'gym', label: 'Full gym', icon: Building2 },
];

// The sports people in this app are most likely to name. Free text still
// works for anything not listed - these are shortcuts, not a whitelist.
const SPORTS = [
  'Football', 'Cricket', 'Running', 'Badminton', 'Basketball',
  'Swimming', 'Cycling', 'Tennis', 'Volleyball', 'Kabaddi',
];

const COMMON_CONSTRAINTS = [
  'knee pain', 'lower back pain', 'shoulder injury', 'wrist pain',
  'hamstring injury', 'asthma', 'recovering from surgery',
];

const STAGES = [
  'Reading your goal…',
  'Choosing the split…',
  'Balancing volume and rest…',
  'Writing the week…',
];

/**
 * Feedback panel shown once a plan exists.
 *
 * Refines the plan in place by calling /fitness/adapt-workout-plan directly,
 * so FitMentor is fully usable on its own without going through the assistant.
 */
function FeedbackPanel({ apiBase, plan, onAdapted }) {
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState('');
  const [freeText, setFreeText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const option = QUICK_FEEDBACK.find((q) => q.key === selected);
  const needsDetail = option?.needsDetail;
  const feedback = needsDetail ? detail.trim() : (option?.text || freeText.trim());
  const canSend = Boolean(feedback);

  const send = async () => {
    if (!canSend) return;
    setBusy(true);
    setErr('');
    try {
      const res = await fetch(`${apiBase}/fitness/adapt-workout-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          current_plan: plan,
          feedback,
          progress_notes: null,
        }),
      });
      const data = await res.json();
      if (res.ok && data.success && data.data) {
        onAdapted(data.data);
        setSelected(null); setDetail(''); setFreeText('');
      } else {
        setErr(data.message || 'Could not adjust the plan. Try again.');
      }
    } catch {
      setErr('Could not reach the server.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section
      title="Not quite right?"
      hint="Pick an adjustment and FitMentor will rework the plan"
      right={<MessageSquarePlus size={16} color="var(--accent-soft)" />}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        {QUICK_FEEDBACK.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setSelected(selected === key ? null : key); setDetail(''); }}
            className={`toggle-chip ${selected === key ? 'is-active' : ''}`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {needsDetail && (
        <input
          className="form-input"
          autoFocus
          placeholder={option.detailPrompt}
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
      )}

      {!selected && (
        <input
          className="form-input"
          placeholder="Or describe the change in your own words…"
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
      )}

      {err && <div style={{ fontSize: '0.8125rem', color: 'var(--danger)' }}>{err}</div>}

      <button
        className="btn btn-primary"
        onClick={send}
        disabled={!canSend || busy}
        style={{ justifyContent: 'center', opacity: canSend ? 1 : 0.45 }}
      >
        {busy
          ? <><RefreshCw size={15} className="spin" style={{ marginRight: 6 }} /> Reworking your plan…</>
          : 'Update my plan'}
      </button>
    </Section>
  );
}

export default function FitMentor({ apiBase }) {
  const [level, setLevel] = useState('beginner');
  const [goal, setGoal] = useState('general_fitness');
  const [minutes, setMinutes] = useState(30);
  const [equipment, setEquipment] = useState('none');
  // [{ text, severity, tracked? }] - not plain strings any more. Severity is
  // encoded into the string only at the API boundary.
  const [constraints, setConstraints] = useState([]);
  const [draft, setDraft] = useState('');
  const [tracked, setTracked] = useState([]);
  // What they train FOR. Not a fitness goal - a footballer and someone
  // chasing general fitness want completely different weeks, and the goal
  // enum has nowhere to put "football".
  const [sport, setSport] = useState('');
  const [preferences, setPreferences] = useState('');
  const [adapted, setAdapted] = useState(null);
  const { result, loading, error, generate } = useGenerator(apiBase, '/fitness/generate-workout-plan');
  const { saved, persist, clear } = usePersistentPlan(apiBase, 'workout');

  // What's on screen, in priority order: an adaptation from this session, a
  // fresh generation, or whatever was saved last time. The last case is what
  // makes closing the app mid-workout safe.
  const currentPlan = adapted?.adapted_plan || result?.workout_plan || saved?.content;
  const isRestored = !adapted && !result && Boolean(saved);
  const detected = adapted?.contraindications;
  const stages = result?.injury_stages;

  // Injuries already being tracked on the dashboard, minus any the user has
  // added here - offering a duplicate import is just noise.
  const importable = tracked.filter(
    (t) => !constraints.some((c) => c.text.toLowerCase() === t.text.toLowerCase()),
  );
  const suggestions = COMMON_CONSTRAINTS.filter(
    (s) => !constraints.some((c) => c.text.toLowerCase() === s.toLowerCase()),
  ).slice(0, 8);

  // Generation is blocked client-side at 8+ because the backend refuses it
  // anyway. Better to say so next to the slider than after a 20-second wait.
  const blocked = constraints.filter((c) => c.severity >= BLOCKING_SEVERITY);

  const addInjury = (text) => {
    const clean = (text || '').trim().toLowerCase();
    if (!clean || constraints.some((c) => c.text === clean)) return;
    setConstraints([...constraints, { text: clean, severity: 5 }]);
    setDraft('');
  };

  // Pull whatever the user is already tracking. Best-effort: FitMentor has
  // always worked without this endpoint and must keep doing so.
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const res = await fetch(`${apiBase}/challenges/injuries`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
        });
        const data = await res.json();
        if (!live || !data?.injuries) return;
        setTracked(
          data.injuries.map((i) => ({
            text: String(i.label || i.body_part || '').toLowerCase(),
            severity: Math.max(0, Math.min(10, Number(i.severity ?? 5))),
            tracked: true,
          })).filter((i) => i.text),
        );
      } catch {
        /* dashboard injuries are a convenience, not a dependency */
      }
    })();
    return () => { live = false; };
  }, [apiBase]);

  // Persist every new or adapted plan so it survives the app closing.
  useEffect(() => {
    const text = adapted?.adapted_plan || result?.workout_plan;
    if (text) {
      persist(text, {
        fitness_goal: goal, activity_level: level,
        equipment, time_per_day: minutes,
        constraints: constraints.map(encodeInjury), sport, preferences,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, adapted]);

  // Restore severities from a saved plan rather than resetting everyone to 5.
  useEffect(() => {
    // `params`, not `parameters` - that is the key /plans/current returns.
    const saved_constraints = saved?.params?.constraints;
    if (saved_constraints?.length && !constraints.length) {
      setConstraints(saved_constraints.map(decodeInjury));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saved]);

  const run = () => {
    if (blocked.length) return;
    setAdapted(null);
    generate({
      activity_level: level,
      fitness_goal: goal,
      time_per_day: minutes,
      equipment,
      // Severity travels inside the string: the backend parser, the severity
      // refusal and injury_service.as_constraints all already speak this
      // format. A parallel structured field would be a second source of truth.
      constraints: constraints.map(encodeInjury),
      sport: sport.trim() || null,
      preferences: preferences.trim() || null,
      age: null,
      weight: null,
    });
  };

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <PageHero
        icon={Dumbbell}
        title="FitMentor"
        subtitle="A seven-day plan built around your level, kit and time."
        from="--accent-rgb" to="--danger-rgb"
      />

      <Section title="Where are you now?" hint="Be honest — the plan scales to it" hero>
        <TileGroup options={LEVELS} value={level} onChange={setLevel} columns={3} />
      </Section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: '1rem' }}>
        <Section title="What are you training for?">
          <TileGroup options={GOALS} value={goal} onChange={setGoal} columns={4} />
        </Section>

        <Section title="What have you got access to?">
          <TileGroup options={EQUIPMENT} value={equipment} onChange={setEquipment} columns={3} />
        </Section>
      </div>

      <Section
        title="Time per session"
        right={<span className="pill pill-brand tabular"><Timer size={12} /> {minutes} min</span>}
      >
        <SliderField
          value={minutes} onChange={setMinutes}
          min={10} max={120} step={5}
          presets={[15, 30, 45, 60, 90]} unit="m"
        />
      </Section>

      {/* Sport is separate from the fitness goal on purpose. Training FOR
          something has different demands from training in general, and it has
          to leave enough in the legs to actually play. */}
      <Section
        title="Training for a sport?"
        hint="Optional — the plan is built around its demands and your match days"
      >
        <div style={{ display: 'grid', gap: '0.6rem' }}>
          <input
            className="form-input"
            placeholder="e.g. football, cricket, running, swimming"
            value={sport}
            onChange={(e) => setSport(e.target.value)}
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {SPORTS.map((s) => (
              <button
                key={s}
                type="button"
                className={`suggest-chip ${sport.toLowerCase() === s.toLowerCase() ? 'is-active' : ''}`}
                onClick={() => setSport(sport.toLowerCase() === s.toLowerCase() ? '' : s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </Section>

      <Section
        title="Anything else?"
        hint="Exercises you hate, days you can't train, equipment quirks"
      >
        <input
          className="form-input"
          placeholder="e.g. no burpees, mornings only, matches on Sundays"
          value={preferences}
          onChange={(e) => setPreferences(e.target.value)}
        />
      </Section>

      <Section
        title="Any injuries or limitations?"
        hint="Rate each one — how bad it is decides what the plan may contain"
      >
        {/* Anything already being tracked on the dashboard, offered rather
            than imposed: the user may want a plan that ignores a niggle they
            are still logging. Importing carries the severity across, so a
            check-in on the dashboard changes the next workout without anyone
            retyping anything. */}
        {importable.length > 0 && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center',
            background: 'rgba(var(--accent-rgb),0.08)', border: '1px solid rgba(var(--accent-rgb),0.25)',
            borderRadius: '0.625rem', padding: '0.75rem',
          }}>
            <HeartPulse size={14} color="var(--accent-soft)" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: '0.75rem', color: '#C4B5FD', flex: 1, minWidth: 160 }}>
              You're tracking {importable.length === 1 ? 'an injury' : `${importable.length} injuries`} on your dashboard.
            </span>
            {importable.map((inj) => (
              <button
                key={inj.text}
                type="button"
                className="suggest-chip"
                onClick={() => setConstraints([...constraints, inj])}
              >
                <Download size={12} /> {inj.text} · {inj.severity}/10
              </button>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            className="form-input"
            style={{ flex: 1 }}
            placeholder="e.g. upper hamstring injury"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addInjury(draft); } }}
          />
          <button
            className="btn btn-primary"
            onClick={() => addInjury(draft)}
            disabled={!draft.trim()}
            style={{ opacity: draft.trim() ? 1 : 0.45 }}
          >
            <Plus size={16} />
          </button>
        </div>

        {constraints.length > 0 && (
          <div style={{ display: 'grid', gap: '0.625rem' }}>
            {constraints.map((inj, i) => (
              <InjuryRow
                key={`${inj.text}-${i}`}
                injury={inj}
                onChange={(next) => setConstraints(constraints.map((c, j) => (j === i ? next : c)))}
                onRemove={() => setConstraints(constraints.filter((_, j) => j !== i))}
              />
            ))}
          </div>
        )}

        {suggestions.length > 0 && (
          <div>
            <div style={{
              fontSize: '0.6875rem', color: 'var(--text-faint)', marginBottom: '0.5rem',
              fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
            }}>
              Common ones
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {suggestions.map((s) => (
                <button key={s} type="button" className="suggest-chip" onClick={() => addInjury(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {constraints.length > 0 && (
          <div style={{
            display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
            background: 'rgba(var(--warning-rgb),0.09)', border: '1px solid rgba(var(--warning-rgb),0.28)',
            borderRadius: '0.625rem', padding: '0.75rem', fontSize: '0.75rem',
            color: 'var(--warning)', lineHeight: 1.5,
          }}>
            <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              A generated plan is not rehab. If something is painful or getting worse, get it
              looked at before training that area.
            </span>
          </div>
        )}
      </Section>

      <ErrorNote>{error}</ErrorNote>

      {blocked.length > 0 && (
        <div style={{
          display: 'flex', gap: '0.625rem', alignItems: 'flex-start',
          background: 'rgba(var(--danger-rgb),0.09)', border: '1px solid rgba(var(--danger-rgb),0.3)',
          borderRadius: '0.75rem', padding: '1rem', fontSize: '0.8125rem',
          color: 'var(--danger)', lineHeight: 1.55,
        }}>
          <ShieldAlert size={16} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>
            You've rated {blocked.map((c) => c.text).join(' and ')} at{' '}
            {blocked.map((c) => `${c.severity}/10`).join(' and ')}. That's past the point where a
            training plan is the right answer — it needs looking at properly before you load it
            again. Lower the rating once it settles and I'll build you a week.
          </span>
        </div>
      )}

      <GenerateButton
        onClick={run}
        loading={loading}
        disabled={blocked.length > 0}
        label={blocked.length ? 'Rated too high to train around' : `Build my ${minutes}-minute plan`}
        stages={STAGES}
      />

      {loading && <LoadingSkeleton />}

      {currentPlan && !loading && (
        <>
          {isRestored && <RestoredNote createdAt={saved?.created_at} onDismiss={clear} />}

          {/* How the rating shaped the week. Without this, severity is a
              slider that appears to do nothing - the plan just quietly comes
              back different, and there's no way to tell whether it was the
              rating or the model's mood. */}
          {stages?.length > 0 && !adapted && (
            <div style={{
              background: 'rgba(var(--accent-rgb),0.07)', border: '1px solid rgba(var(--accent-rgb),0.22)',
              borderRadius: '0.75rem', padding: '1rem', display: 'grid', gap: '0.75rem',
            }}>
              {stages.map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-start' }}>
                  <Gauge size={15} color={solid(severityColor(s.severity))} style={{ flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'capitalize' }}>
                      {s.side && s.side !== 'bilateral' ? `${s.side} ` : ''}{s.label}
                      {s.side === 'bilateral' ? ' (both sides)' : ''}
                      <span style={{ color: solid(severityColor(s.severity)), marginLeft: 6 }}>
                        {s.severity}/10
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.5 }}>
                      {s.stage_label} — {s.guidance}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {/* What the injury detector removed, so it isn't taken on trust */}
          {detected && (
            <div style={{
              background: detected.red_flag ? 'rgba(var(--danger-rgb),0.09)' : 'rgba(var(--warning-rgb),0.09)',
              border: `1px solid ${detected.red_flag ? 'rgba(var(--danger-rgb),0.3)' : 'rgba(var(--warning-rgb),0.28)'}`,
              borderRadius: '0.75rem', padding: '1rem', display: 'grid', gap: '0.5rem',
            }}>
              {detected.injuries.map((inj, i) => (
                <div key={i} style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-start' }}>
                  <ShieldAlert size={16} color={detected.red_flag ? 'var(--danger)' : 'var(--warning)'} style={{ flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', color: detected.red_flag ? 'var(--danger)' : 'var(--warning)', textTransform: 'capitalize' }}>
                      {inj.label} — {inj.excluded.length} movements removed
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.5 }}>
                      {inj.excluded.slice(0, 8).join(', ')}
                      {inj.excluded.length > 8 && ` and ${inj.excluded.length - 8} more`}
                    </div>
                  </div>
                </div>
              ))}
              {detected.red_flag && (
                <div style={{ fontSize: '0.8125rem', color: 'var(--danger)', paddingLeft: '2.1rem', lineHeight: 1.5 }}>
                  What you described — sharp pain, numbness, swelling or something getting worse — is worth
                  getting looked at before you train that area at all.
                </div>
              )}
            </div>
          )}

          <ResultPanel
            title={adapted ? 'Your updated week' : 'Your week'}
            icon={Dumbbell}
            accent="var(--danger)"
            markdown={currentPlan}
            onRegenerate={run}
            apiBase={apiBase}
            savedPlan={saved}
            planType="workout"
            params={{
              fitness_goal: goal, activity_level: level, equipment,
              time_per_day: minutes, constraints: constraints.map(encodeInjury),
            }}
            pills={[
              { label: LEVELS.find((l) => l.key === level)?.label, tone: 'pill-muted' },
              { label: GOALS.find((g) => g.key === goal)?.label, tone: 'pill-brand' },
              { label: `${minutes} min/day`, tone: 'pill-muted' },
              ...(adapted ? [{ label: 'adjusted', tone: 'pill-good' }] : []),
              // Severity on the pill, so the plan carries the rating it was
              // built for - useful when you come back to a restored plan and
              // your knee is a 3 now rather than the 6 it was on Monday.
              ...constraints.map((c) => ({ label: `${c.text} ${c.severity}/10`, tone: 'pill-warn' })),
            ]}
          />

          <FeedbackPanel
            apiBase={apiBase}
            plan={currentPlan}
            onAdapted={setAdapted}
          />
        </>
      )}

      {!currentPlan && !loading && (
        <EmptyState
          icon={Dumbbell}
          title="No plan yet"
          body="Pick your level, goal and kit above, then generate. The plan works around anything you list as an injury."
        />
      )}
    </div>
  );
}
