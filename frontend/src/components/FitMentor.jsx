import React, { useState, useEffect } from 'react';
import {
  Dumbbell, Sprout, Activity, Flame, Home, Building2, HandMetal,
  TrendingDown, HeartPulse, Wind, Timer, AlertTriangle,
  MessageSquarePlus, Gauge, Zap, Clock3, Shuffle, Repeat, ShieldAlert, RefreshCw,
} from 'lucide-react';
import {
  PageHero, Section, TileGroup, SliderField, ChipInput,
  GenerateButton, LoadingSkeleton, ErrorNote, ResultPanel, EmptyState, useGenerator,
  usePersistentPlan, RestoredNote,
} from './SpecialistUI';
import renderMarkdown from './markdown';

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
      right={<MessageSquarePlus size={16} color="#A78BFA" />}
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

      {err && <div style={{ fontSize: '0.8125rem', color: '#F87171' }}>{err}</div>}

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
  const [constraints, setConstraints] = useState([]);
  const [adapted, setAdapted] = useState(null);
  const { result, loading, error, generate } = useGenerator(apiBase, '/fitness/generate-workout-plan');
  const { saved, persist, clear } = usePersistentPlan(apiBase, 'workout');

  // What's on screen, in priority order: an adaptation from this session, a
  // fresh generation, or whatever was saved last time. The last case is what
  // makes closing the app mid-workout safe.
  const currentPlan = adapted?.adapted_plan || result?.workout_plan || saved?.content;
  const isRestored = !adapted && !result && Boolean(saved);
  const detected = adapted?.contraindications;

  // Persist every new or adapted plan so it survives the app closing.
  useEffect(() => {
    const text = adapted?.adapted_plan || result?.workout_plan;
    if (text) {
      persist(text, {
        fitness_goal: goal, activity_level: level,
        equipment, time_per_day: minutes, constraints,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, adapted]);

  const run = () => {
    setAdapted(null);
    generate({
      activity_level: level,
      fitness_goal: goal,
      time_per_day: minutes,
      equipment,
      constraints,
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
        gradient="#8B5CF6,#F87171"
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

      <Section
        title="Any injuries or limitations?"
        hint="Named injuries are excluded from the plan — worth being specific"
      >
        <ChipInput
          values={constraints}
          onChange={setConstraints}
          placeholder="e.g. upper hamstring injury"
          suggestions={COMMON_CONSTRAINTS}
          suggestLabel="Common ones"
        />
        {constraints.length > 0 && (
          <div style={{
            display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
            background: 'rgba(251,191,36,0.09)', border: '1px solid rgba(251,191,36,0.28)',
            borderRadius: '0.625rem', padding: '0.75rem', fontSize: '0.75rem',
            color: '#FBBF24', lineHeight: 1.5,
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

      <GenerateButton
        onClick={run}
        loading={loading}
        label={`Build my ${minutes}-minute plan`}
        stages={STAGES}
      />

      {loading && <LoadingSkeleton />}

      {currentPlan && !loading && (
        <>
          {isRestored && <RestoredNote createdAt={saved?.created_at} onDismiss={clear} />}
          {/* What the injury detector removed, so it isn't taken on trust */}
          {detected && (
            <div style={{
              background: detected.red_flag ? 'rgba(248,113,113,0.09)' : 'rgba(251,191,36,0.09)',
              border: `1px solid ${detected.red_flag ? 'rgba(248,113,113,0.3)' : 'rgba(251,191,36,0.28)'}`,
              borderRadius: '0.75rem', padding: '1rem', display: 'grid', gap: '0.5rem',
            }}>
              {detected.injuries.map((inj, i) => (
                <div key={i} style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-start' }}>
                  <ShieldAlert size={16} color={detected.red_flag ? '#F87171' : '#FBBF24'} style={{ flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', color: detected.red_flag ? '#F87171' : '#FBBF24', textTransform: 'capitalize' }}>
                      {inj.label} — {inj.excluded.length} movements removed
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#98A2B3', marginTop: 4, lineHeight: 1.5 }}>
                      {inj.excluded.slice(0, 8).join(', ')}
                      {inj.excluded.length > 8 && ` and ${inj.excluded.length - 8} more`}
                    </div>
                  </div>
                </div>
              ))}
              {detected.red_flag && (
                <div style={{ fontSize: '0.8125rem', color: '#F87171', paddingLeft: '2.1rem', lineHeight: 1.5 }}>
                  What you described — sharp pain, numbness, swelling or something getting worse — is worth
                  getting looked at before you train that area at all.
                </div>
              )}
            </div>
          )}

          <ResultPanel
            title={adapted ? 'Your updated week' : 'Your week'}
            icon={Dumbbell}
            accent="#F87171"
            markdown={currentPlan}
            onRegenerate={run}
            apiBase={apiBase}
            savedPlan={saved}
            planType="workout"
            params={{ fitness_goal: goal, activity_level: level, equipment, time_per_day: minutes, constraints }}
            pills={[
              { label: LEVELS.find((l) => l.key === level)?.label, tone: 'pill-muted' },
              { label: GOALS.find((g) => g.key === goal)?.label, tone: 'pill-brand' },
              { label: `${minutes} min/day`, tone: 'pill-muted' },
              ...(adapted ? [{ label: 'adjusted', tone: 'pill-good' }] : []),
              ...constraints.map((c) => ({ label: c, tone: 'pill-warn' })),
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
