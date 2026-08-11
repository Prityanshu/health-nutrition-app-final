import React, { useState, useEffect } from 'react';
import {
  CalendarDays, Flame, Wallet, Clock, Briefcase, Leaf, Wheat, Milk, Nut,
  Egg, Flame as Stove, Microwave, Refrigerator, ShoppingCart, ChevronDown,
  Coffee, UtensilsCrossed, Sparkles, Check, Target,
} from 'lucide-react';
import {
  PageHero, Section, TileGroup, SliderField, ChipToggles, ChipInput,
  GenerateButton, LoadingSkeleton, ErrorNote, EmptyState, useGenerator,
  usePersistentPlan, RestoredNote, PlanActions,
} from './SpecialistUI';
import useCountUp from './useCountUp';

/**
 * Meal Planner - the full seven-day plan.
 *
 * Unlike the other specialists this endpoint returns structured JSON rather
 * than markdown, so the result is rendered as expandable day cards with a
 * shopping list, instead of a wall of text.
 */

const MEALS_PER_DAY = [
  { key: 2, label: '2', icon: Coffee },
  { key: 3, label: '3', icon: UtensilsCrossed },
  { key: 4, label: '4', icon: UtensilsCrossed },
  { key: 5, label: '5', icon: UtensilsCrossed },
];

const EQUIPMENT = [
  { key: 'stove', label: 'Stove', icon: Stove },
  { key: 'oven', label: 'Oven', icon: Stove },
  { key: 'microwave', label: 'Microwave', icon: Microwave },
  { key: 'fridge', label: 'Fridge', icon: Refrigerator },
];

const DIETS = [
  { key: 'vegetarian', label: 'Vegetarian', icon: Leaf },
  { key: 'vegan', label: 'Vegan', icon: Leaf },
  { key: 'eggetarian', label: 'Eggs ok', icon: Egg },
  { key: 'gluten-free', label: 'Gluten free', icon: Wheat },
  { key: 'dairy-free', label: 'Dairy free', icon: Milk },
  { key: 'nut-free', label: 'Nut free', icon: Nut },
];

const CUISINES = ['north indian', 'south indian', 'mediterranean', 'continental', 'asian', 'mixed'];

const STAGES = [
  'Working out your daily targets…',
  'Choosing meals for each day…',
  'Balancing macros across the week…',
  'Building the shopping list…',
];

function DayCard({ dayKey, meals, index, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);
  const dayNum = dayKey.split('_').pop();
  const total = meals.reduce((s, m) => s + (m.macros?.calories || 0), 0);

  return (
    <div className="surface lift" style={{ overflow: 'hidden' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: '100%', padding: '1rem 1.125rem', background: 'none', border: 'none',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          color: 'inherit', textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            className="flex items-center justify-center tabular"
            style={{
              width: 32, height: 32, borderRadius: 9, flexShrink: 0,
              background: 'linear-gradient(135deg,rgba(var(--accent-rgb),0.3),rgba(var(--cyan-rgb),0.15))',
              border: '1px solid rgba(var(--accent-rgb),0.4)',
              fontSize: '0.8125rem', fontWeight: 700,
            }}
          >
            {dayNum}
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Day {dayNum}</div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)' }}>
              {meals.length} meals · {Math.round(total)} kcal
            </div>
          </div>
        </div>
        <ChevronDown
          size={17} color="var(--text-faint)"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.22s ease' }}
        />
      </button>

      {open && (
        <div style={{ padding: '0 1.125rem 1.125rem', display: 'grid', gap: '0.5rem' }}>
          {meals.map((m, i) => (
            <div
              key={i}
              className="flex items-center justify-between"
              style={{
                padding: '0.6875rem 0.875rem', borderRadius: '0.625rem',
                background: 'var(--surface-inset)', border: '1px solid var(--border)',
                animation: `fade-up 0.3s ease ${i * 0.04}s both`,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'capitalize' }}>
                  {m.recipe_name || 'Meal'}
                </div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', marginTop: 2, textTransform: 'capitalize' }}>
                  {m.meal_label || 'meal'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', flexShrink: 0 }}>
                <span className="tabular" style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--warning)' }}>
                  {Math.round(m.macros?.calories || 0)}
                </span>
                {m.macros?.protein && (
                  <span className="tabular" style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--cyan)' }}>
                    {Math.round(m.macros.protein)}g
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Flatten the structured plan into markdown.
 *
 * The PDF exporter and the saved-plan store both work in text, so the
 * structured response is serialised once here rather than teaching the PDF
 * layer about this one endpoint's JSON shape.
 */
function structuredPlanToText(mp) {
  const lines = [];
  const meta = mp.meta || {};
  const summary = mp.summary || {};

  if (meta.total_daily_calories) {
    lines.push(`**${meta.total_daily_calories} kcal/day** across ${meta.meals_per_day || '?'} meals`, '');
  }

  Object.keys(mp.plan || {}).sort().forEach((k) => {
    lines.push(`### Day ${k.split('_').pop()}`);
    (mp.plan[k] || []).forEach((m) => {
      const cal = m.macros?.calories ? ` (${Math.round(m.macros.calories)} kcal)` : '';
      lines.push(`- **${m.meal_label || 'Meal'}:** ${m.recipe_name || 'Meal'}${cal}`);
    });
    lines.push('');
  });

  const shopping = summary.weekly_shopping_list || [];
  if (shopping.length) {
    lines.push('### Shopping list');
    shopping.forEach((i) => lines.push(`- ${i.name}${i.qty_est ? ` — ${i.qty_est}` : ''}`));
    lines.push('');
  }
  if (summary.progression_tip) lines.push(`**Tip:** ${summary.progression_tip}`);

  return lines.join('\n');
}

export default function MealPlanner({ apiBase }) {
  const [calories, setCalories] = useState(2000);
  const [mealsPerDay, setMealsPerDay] = useState(3);
  // Off by default. A stated budget competes with the nutrition targets -
  // constrained spending pushes the plan toward cheap, carb-heavy filler -
  // so cost is opt-in rather than something every plan is optimised around.
  const [useBudget, setUseBudget] = useState(false);
  const [budget, setBudget] = useState(300);
  const [workHours, setWorkHours] = useState(8);
  const [timePerMeal, setTimePerMeal] = useState(30);
  const [diets, setDiets] = useState([]);
  const [equipment, setEquipment] = useState(['stove']);
  const [cuisine, setCuisine] = useState('mixed');
  const [prefs, setPrefs] = useState([]);
  const [notes, setNotes] = useState('');
  const [goalCalories, setGoalCalories] = useState(null);
  const [goalMacros, setGoalMacros] = useState(null);
  // Two ways to build a week. Standard uses only what is on this form.
  // Personalised additionally uses the profile behind the For You page -
  // logged meals, cuisine affinity, spending habits, stated restrictions -
  // so the plan reflects what this person actually eats.
  const [personalised, setPersonalised] = useState(false);
  const [profile, setProfile] = useState(null);

  // Below ~5 logged meals the profile is guesswork, so the option stays
  // disabled rather than promising personalisation it cannot deliver.
  const profileReady = Boolean(profile?.profile?.log_count >= 5);
  const { result, loading, error, generate } = useGenerator(apiBase, '/advanced-meal-planner/generate');
  const { saved, persist, clear } = usePersistentPlan(apiBase, 'weekly_meal_plan');

  // This planner returns structured JSON rather than markdown, so the
  // structured form is kept in `params` for re-rendering while a readable text
  // version is stored as `content` for the PDF.
  const restored = !result && saved?.params?.structured ? saved.params.structured : null;
  const isRestored = Boolean(restored);

  useEffect(() => {
    fetch(`${apiBase}/goals/?active_only=true`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((goals) => {
        const g = goals?.[0];
        const t = g?.target_calories;
        if (t) { setCalories(Math.round(t)); setGoalCalories(Math.round(t)); }
        // The macro targets were fetched and thrown away before - only
        // calories were kept, which is why the planner never knew them.
        if (g) {
          setGoalMacros({
            calories: Math.round(g.target_calories || 0),
            protein: Math.round(g.target_protein || 0),
            carbs: Math.round(g.target_carbs || 0),
            fat: Math.round(g.target_fat || 0),
          });
        }
      })
      .catch(() => {});
  }, [apiBase]);

  // Same endpoint the For You page uses - no extra backend work needed.
  useEffect(() => {
    fetch(`${apiBase}/ml/for-you`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setProfile)
      .catch(() => {});
  }, [apiBase]);

  // Switching to personalised pre-fills the form from that profile, so the
  // user can still see and override every value rather than it being applied
  // invisibly.
  const applyProfile = () => {
    const p = profile?.profile;
    if (!p) return;
    if (p.top_cuisine) {
      const match = CUISINES.find((c) => c.includes(p.top_cuisine.toLowerCase()));
      if (match) setCuisine(match);
    }
    if (p.vegetarian && !diets.includes('vegetarian')) setDiets((d) => [...d, 'vegetarian']);
    if (p.budget?.median_per_item) {
      setUseBudget(true);
      setBudget(Math.round(p.budget.median_per_item * mealsPerDay * 1.5 / 25) * 25);
    }
    const favs = (p.favourites || []).map((f) => f.name.toLowerCase()).slice(0, 4);
    if (favs.length) setPrefs((existing) => [...new Set([...existing, ...favs])]);
  };

  useEffect(() => {
    const mp = result;
    if (!mp?.plan) return;
    persist(structuredPlanToText(mp), {
      target_calories: calories, meals_per_day: mealsPerDay,
      budget_per_day: useBudget ? budget : null, region_or_cuisine: cuisine,
      structured: mp,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const animatedCals = useCountUp(calories, 400);

  /**
   * Describe the user's real eating patterns for the agent.
   *
   * The planner has no access to logged meals, so without this the
   * "personalised" mode would just be pre-filled defaults. Appending a short
   * factual summary is what actually changes the output.
   */
  const personalNotes = () => {
    const p = profile?.profile;
    if (!personalised || !p) return notes;

    const bits = [];
    const favs = (p.favourites || []).map((f) => f.name).slice(0, 5);
    if (favs.length) bits.push(`They regularly eat: ${favs.join(', ')}. Include some of these.`);
    if (p.top_cuisine) bits.push(`They mostly log ${p.top_cuisine} food.`);
    if (p.often_skipped?.length) {
      bits.push(`They usually skip ${p.often_skipped.join(' and ')} - keep those meals simple or very quick.`);
    }
    if (p.prep_preference === 'LOW') bits.push('They prefer low-effort meals.');
    if (p.daily_average?.protein && profile?.goal?.target_protein) {
      const avg = p.daily_average.protein;
      const target = Math.round(profile.goal.target_protein);
      if (avg < target * 0.8) {
        bits.push(
          `They average only ${avg}g protein a day against a ${target}g target - ` +
          `weight the plan toward protein-dense meals.`
        );
      }
    }
    if (p.variety?.in_a_rut) bits.push('Their meals repeat a lot, so favour variety across the week.');

    return [notes, ...bits].filter(Boolean).join(' ');
  };

  const run = () =>
    generate({
      target_calories: calories,
      meals_per_day: mealsPerDay,
      food_preferences: prefs,
      budget_per_day: useBudget ? budget : null,
      work_hours_per_day: workHours,
      dietary_restrictions: diets,
      equipment,
      time_per_meal_min: timePerMeal,
      region_or_cuisine: cuisine,
      user_notes: personalNotes(),
      // Personalised mode now holds every DAY to all four macros from the
      // goal. Before this the only macro instruction was "aim for a balance
      // appropriate for general healthy eating" - identical advice for every
      // user - while the plan still reported per-meal macros, so it looked
      // constrained by numbers it had never been given.
      match_macros: personalised,
    });

  // The endpoint returns `data = result["meal_plan"]`, so the response body
  // IS the plan - there is no nested .meal_plan key. Reading one made the
  // results block silently render nothing after a successful generation.
  const source = result || restored || {};
  const plan = source.plan || {};
  const meta = source.meta || {};
  const summary = source.summary || {};
  const shopping = summary.weekly_shopping_list || [];

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <PageHero
        icon={CalendarDays}
        title="Meal Planner"
        subtitle="A full week of meals built around your targets and schedule."
        from="--accent-soft-rgb" to="--warning-rgb"
      />

      {/* Mode selector */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(250px,1fr))', gap: '0.75rem' }}>
        {[
          {
            key: false, icon: CalendarDays, title: 'Standard plan',
            body: 'Built purely from the settings below. Same result for anyone with the same inputs.',
          },
          {
            key: true, icon: Sparkles, title: 'Personalised plan',
            body: profileReady
              ? (goalMacros?.protein
                  ? `Every day built to hit ${goalMacros.calories} kcal, ${goalMacros.protein}g protein, ${goalMacros.carbs}g carbs and ${goalMacros.fat}g fat — plus the foods you actually eat, from your ${profile.profile.log_count} logged meals.`
                  : `Also uses your ${profile.profile.log_count} logged meals — the foods you actually eat, your cuisine, and where your protein falls short.`)
              : 'Log a few meals first and this will use your real eating patterns.',
            disabled: !profileReady,
          },
        ].map(({ key, icon: Icon, title, body, disabled }) => (
          <button
            key={String(key)}
            disabled={disabled}
            onClick={() => { setPersonalised(key); if (key) applyProfile(); }}
            className="surface lift"
            style={{
              padding: '1.125rem', textAlign: 'left', cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
              borderColor: personalised === key ? 'var(--accent)' : undefined,
              background: personalised === key
                ? 'linear-gradient(135deg, rgba(var(--accent-rgb),0.16), rgba(var(--cyan-rgb),0.05))'
                : undefined,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <Icon size={17} color={personalised === key ? 'var(--accent-soft)' : 'var(--text-faint)'} />
              <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{title}</span>
              {personalised === key && <Check size={15} color="var(--success)" style={{ marginLeft: 'auto' }} />}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>{body}</div>
          </button>
        ))}
      </div>

      {/* What personalisation is actually using - shown so it is not applied
          invisibly and the user can override anything below. */}
      {personalised && profileReady && (
        <div style={{
          background: 'rgba(var(--accent-rgb),0.08)', border: '1px solid rgba(var(--accent-rgb),0.25)',
          borderRadius: '0.75rem', padding: '0.9375rem', display: 'flex',
          gap: '0.625rem', alignItems: 'flex-start',
        }}>
          <Sparkles size={15} color="var(--accent-soft)" style={{ flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
            Using your history:{' '}
            {[
              profile.profile.top_cuisine && `${profile.profile.top_cuisine} cuisine`,
              profile.profile.vegetarian && 'vegetarian',
              profile.profile.favourites?.length &&
                `favourites (${profile.profile.favourites.slice(0, 3).map((f) => f.name).join(', ')})`,
              profile.profile.often_skipped?.length &&
                `you often skip ${profile.profile.often_skipped.join(' & ')}`,
            ].filter(Boolean).join(' · ')}
            . Everything below is still editable.
          </div>
        </div>
      )}

      {/* The macro numbers every day will be built to. Shown before
          generating, because a target you cannot see is indistinguishable
          from no target - and this is the one thing the planner never had. */}
      {personalised && goalMacros?.protein > 0 && (
        <div style={{
          background: 'rgba(var(--cyan-rgb),0.07)', border: '1px solid rgba(var(--cyan-rgb),0.22)',
          borderRadius: '0.75rem', padding: '1rem', display: 'grid', gap: '0.75rem',
        }}>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <Target size={15} color="var(--cyan)" />
            <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
              Every day will be built to hit
            </span>
          </div>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(90px,1fr))', gap: '0.75rem',
          }}>
            {[
              ['Calories', goalMacros.calories, 'kcal', 'var(--warning)'],
              ['Protein', goalMacros.protein, 'g', 'var(--cyan)'],
              ['Carbs', goalMacros.carbs, 'g', 'var(--accent-soft)'],
              ['Fat', goalMacros.fat, 'g', 'var(--danger)'],
            ].map(([label, value, unit, colour]) => (
              <div key={label}>
                <div style={{ fontSize: '0.625rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {label}
                </div>
                <div className="tabular" style={{ fontSize: '1.0625rem', fontWeight: 700, color: colour, marginTop: 2 }}>
                  {value}<span style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', fontWeight: 500 }}> {unit}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Whether it actually landed - summed from the plan's own per-meal
          macros, so it reflects the food rather than a claimed total. */}
      {source.verification?.checked && (
        <div style={{
          background: source.verification.hit
            ? 'rgba(var(--success-rgb),0.08)' : 'rgba(var(--warning-rgb),0.08)',
          border: `1px solid ${source.verification.hit
            ? 'rgba(var(--success-rgb),0.28)' : 'rgba(var(--warning-rgb),0.28)'}`,
          borderRadius: '0.75rem', padding: '1rem', display: 'grid', gap: '0.75rem',
        }}>
          <div style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-start' }}>
            {source.verification.hit
              ? <Check size={15} color="var(--success)" style={{ flexShrink: 0, marginTop: 2 }} />
              : <Target size={15} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                {source.verification.days_on_target} of {source.verification.days_total} days
                hit every macro
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.5 }}>
                {source.verification.summary}
                {source.verification.retried && ' Regenerated once to get closer.'}
              </div>
            </div>
          </div>

          {/* Per day, so a single bad Thursday is visible rather than
              averaged into the week. */}
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            {source.verification.days.map((d) => (
              <div key={d.day} style={{ flex: 1, display: 'grid', gap: 3, justifyItems: 'center' }}>
                <span
                  title={`${d.day}: ${d.hit ? 'all macros in range'
                    : d.missed.map((m) => `${m} ${d.macros[m].total}${d.macros[m].unit}`).join(', ')}`}
                  style={{
                    width: '100%', height: 6, borderRadius: 3,
                    background: d.hit ? 'var(--success)' : d.missed.length > 2 ? 'var(--danger)' : 'var(--warning)',
                  }}
                />
                <span style={{ fontSize: '0.5625rem', color: 'var(--text-faint)' }}>
                  {d.day.replace('day_', '')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Targets hero */}
      <div className="surface-hero" style={{ padding: '1.75rem', display: 'grid', gap: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="metric-label">Daily calories</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', marginTop: 6 }}>
              <span className="metric-value tabular" style={{ fontSize: '3rem' }}>
                {Math.round(animatedCals).toLocaleString()}
              </span>
              <span style={{ color: 'var(--text-faint)', fontWeight: 500 }}>kcal</span>
            </div>
            {goalCalories && (
              <span className="pill pill-good" style={{ marginTop: 8 }}>from your goal</span>
            )}
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="metric-label">Per meal</div>
            <div className="tabular" style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-soft)', marginTop: 6 }}>
              ~{Math.round(calories / mealsPerDay)} kcal
            </div>
            {useBudget && (
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)' }}>
                ₹{Math.round(budget / mealsPerDay)} each
              </div>
            )}
          </div>
        </div>
        <SliderField
          value={calories} onChange={setCalories}
          min={1200} max={4000} step={50}
          presets={goalCalories ? [goalCalories, 1800, 2200, 2600] : [1600, 2000, 2400, 2800]}
          unit=" kcal"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: '1rem' }}>
        <Section title="Meals per day">
          <TileGroup options={MEALS_PER_DAY} value={mealsPerDay} onChange={setMealsPerDay} columns={4} />
        </Section>

        <Section title="Kitchen equipment" hint="What you can actually cook with">
          <ChipToggles options={EQUIPMENT} values={equipment} onChange={setEquipment} />
        </Section>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: '1rem' }}>
        <Section
          title="Daily budget"
          hint={useBudget ? 'Plans will stay within this' : 'Off — meals chosen purely on nutrition'}
          right={
            <button
              onClick={() => setUseBudget((v) => !v)}
              className={`toggle-chip ${useBudget ? 'is-active' : ''}`}
              style={{ padding: '0.3125rem 0.625rem', fontSize: '0.75rem' }}
            >
              <Wallet size={13} /> {useBudget ? `₹${budget}` : 'Set a budget'}
            </button>
          }
        >
          {useBudget ? (
            <>
              <SliderField value={budget} onChange={setBudget} min={50} max={1500} step={25}
                presets={[150, 300, 500, 800]} format={(v) => `₹${v}`} />
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                If the budget and your protein target conflict, nutrition wins and
                the plan will say so.
              </div>
            </>
          ) : (
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
              No spending limit, so meals are picked to hit your calorie and macro
              targets. Costs are still estimated for each item so you can see what
              the week would run to.
            </div>
          )}
        </Section>

        <Section title="Time per meal" right={<span className="pill pill-brand tabular"><Clock size={12} /> {timePerMeal}m</span>}>
          <SliderField value={timePerMeal} onChange={setTimePerMeal} min={10} max={90} step={5}
            presets={[15, 30, 45, 60]} unit="m" />
        </Section>
      </div>

      <Section title="Hours you work a day" hint="Busier days get simpler meals"
        right={<span className="pill pill-muted tabular"><Briefcase size={12} /> {workHours}h</span>}>
        <SliderField value={workHours} onChange={setWorkHours} min={0} max={16} step={1}
          presets={[6, 8, 10, 12]} unit="h" />
      </Section>

      <Section title="Cuisine leaning">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4375rem' }}>
          {CUISINES.map((c) => (
            <button key={c} onClick={() => setCuisine(c)}
              className={`suggest-chip ${cuisine === c ? 'is-active' : ''}`}>
              {c}
            </button>
          ))}
        </div>
      </Section>

      <Section title="Dietary preferences" hint="Optional">
        <ChipToggles options={DIETS} values={diets} onChange={setDiets} />
      </Section>

      <Section title="Foods you want included" hint="Optional">
        <ChipInput values={prefs} onChange={setPrefs} placeholder="e.g. paneer, oats"
          suggestions={['paneer', 'eggs', 'oats', 'chicken', 'dal', 'yogurt']} suggestLabel="Popular" />
      </Section>

      <Section title="Anything else?" hint="Optional — allergies, dislikes, schedule quirks">
        <input className="form-input" placeholder="e.g. no cooking on Sundays, hate mushrooms"
          value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Section>

      <ErrorNote>{error}</ErrorNote>

      <GenerateButton onClick={run} loading={loading} label="Build my week" stages={STAGES} />

      {loading && <LoadingSkeleton />}

      {/* Structured result */}
      {(result || restored) && !loading && Object.keys(plan).length > 0 && (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {isRestored && <RestoredNote createdAt={saved?.created_at} onDismiss={clear} />}
          {/* Title and stats on one row; actions on their own row below.
              Previously all three shared a justify-between row, which squeezed
              the buttons into the middle and left the email popover - which is
              absolutely positioned - no room to open. */}
          <div className="surface-hero" style={{ padding: '1.5rem', display: 'grid', gap: '1rem' }}>
            <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                <Sparkles size={18} color="var(--warning)" />
                <span style={{ fontWeight: 700, fontSize: '1.0625rem' }}>Your week</span>
                {personalised && (
                  <span className="pill pill-brand"><Sparkles size={11} /> personalised</span>
                )}
              </div>
              <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                {[
                  { label: 'kcal/day', value: meta.total_daily_calories ?? calories, color: 'var(--warning)' },
                  // Only claim a cost when one was actually produced or requested.
                  ...(summary.avg_daily_cost || useBudget
                    ? [{ label: 'avg cost',
                         value: `₹${summary.avg_daily_cost ?? budget}`, color: 'var(--success)' }]
                    : []),
                  { label: 'meals/day', value: meta.meals_per_day ?? mealsPerDay, color: 'var(--accent-soft)' },
                ].map((s, i) => (
                  <div key={i} style={{ textAlign: 'right' }}>
                    <div className="tabular" style={{ fontSize: '1.25rem', fontWeight: 700, color: s.color }}>{s.value}</div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)' }}>{s.label}</div>
                  </div>
                ))}
              </div>
            </div>

            <hr className="hairline" />

            <PlanActions
              apiBase={apiBase} plan={saved}
              planType="weekly_meal_plan"
              content={source.plan ? structuredPlanToText(source) : null}
              params={{
                target_calories: calories, meals_per_day: mealsPerDay,
                budget_per_day: useBudget ? budget : null,
                region_or_cuisine: cuisine, structured: source,
              }}
              title="Your 7-Day Meal Plan"
            />
          </div>

          <div style={{ display: 'grid', gap: '0.625rem' }}>
            {Object.keys(plan).sort().map((k, i) => (
              <DayCard key={k} dayKey={k} meals={plan[k] || []} index={i} defaultOpen={i === 0} />
            ))}
          </div>

          {shopping.length > 0 && (
            <Section title="Shopping list" hint={`${shopping.length} items for the week`}
              right={<ShoppingCart size={16} color="var(--success)" />}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: '0.5rem' }}>
                {shopping.map((item, i) => (
                  <div key={i} className="flex items-center justify-between"
                    style={{ padding: '0.625rem 0.75rem', borderRadius: '0.5rem', background: 'var(--surface-inset)', border: '1px solid var(--border)' }}>
                    <span style={{ fontSize: '0.8125rem', textTransform: 'capitalize' }}>{item.name}</span>
                    <span className="tabular" style={{ fontSize: '0.75rem', color: 'var(--success)', fontWeight: 600 }}>
                      {item.est_cost ? `₹${item.est_cost}` : item.qty_est}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {summary.progression_tip && (
            <div style={{
              display: 'flex', gap: '0.625rem', alignItems: 'flex-start',
              background: 'rgba(var(--accent-rgb),0.09)', border: '1px solid rgba(var(--accent-rgb),0.28)',
              borderRadius: '0.75rem', padding: '1rem', fontSize: '0.8125rem',
              color: 'var(--text-secondary)', lineHeight: 1.55,
            }}>
              <Flame size={16} color="var(--accent-soft)" style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{summary.progression_tip}</span>
            </div>
          )}
        </div>
      )}

      {!result && !restored && !loading && (
        <EmptyState icon={CalendarDays} title="No plan yet"
          body="Set your calories, budget and schedule above. The planner builds seven days of meals plus a shopping list." />
      )}
    </div>
  );
}
