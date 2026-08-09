import React, { useState, useEffect } from 'react';
import {
  Globe, Sunrise, Sun, Moon, CalendarDays, Leaf, Wheat, Milk, Nut,
  Sprout, Activity, Flame, Clock, Compass, Sparkles, Check, Target,
} from 'lucide-react';
import {
  PageHero, Section, TileGroup, SliderField, ChipToggles, ChipInput,
  GenerateButton, LoadingSkeleton, ErrorNote, ResultPanel, EmptyState, useGenerator,
  usePersistentPlan, RestoredNote,
} from './SpecialistUI';

/**
 * Explorer - regional cuisine.
 *
 * The region was previously a free-text box, which meant typos silently
 * produced worse results. It is now a visual picker with a free-text escape
 * hatch for anything not listed.
 */

/**
 * Regions the backend actually accepts.
 *
 * `cuisine_region` is a strict Enum on the server, so anything not listed here
 * is rejected with a 422 before it reaches the agent. An earlier version of
 * this file used invented keys ("punjabi", "south indian", "bengali") which
 * looked reasonable but matched no enum member, so every request failed.
 *
 * Keys must match app/routers/culinary.py::CuisineRegion exactly. Labels are
 * for display only.
 */
const REGIONS = [
  // Global
  { key: 'indian', label: 'Indian', flag: '🍛', group: 'World' },
  { key: 'mediterranean', label: 'Mediterranean', flag: '🫒', group: 'World' },
  { key: 'japanese', label: 'Japanese', flag: '🍱', group: 'World' },
  { key: 'thai', label: 'Thai', flag: '🍜', group: 'World' },
  { key: 'chinese', label: 'Chinese', flag: '🥡', group: 'World' },
  { key: 'italian', label: 'Italian', flag: '🍝', group: 'World' },
  { key: 'mexican', label: 'Mexican', flag: '🌮', group: 'World' },
  { key: 'french', label: 'French', flag: '🥐', group: 'World' },
  // Indian states
  { key: 'punjab', label: 'Punjab', flag: '🧈', group: 'India' },
  { key: 'kerala', label: 'Kerala', flag: '🥥', group: 'India' },
  { key: 'tamil_nadu', label: 'Tamil Nadu', flag: '🥘', group: 'India' },
  { key: 'west_bengal', label: 'West Bengal', flag: '🐟', group: 'India' },
  { key: 'gujarat', label: 'Gujarat', flag: '🥗', group: 'India' },
  { key: 'rajasthan', label: 'Rajasthan', flag: '🌶️', group: 'India' },
  { key: 'maharashtra', label: 'Maharashtra', flag: '🫓', group: 'India' },
  { key: 'karnataka', label: 'Karnataka', flag: '🍲', group: 'India' },
  { key: 'andhra_pradesh', label: 'Andhra Pradesh', flag: '🔥', group: 'India' },
  { key: 'telangana', label: 'Telangana', flag: '🍚', group: 'India' },
  { key: 'goa', label: 'Goa', flag: '🦐', group: 'India' },
  { key: 'assam', label: 'Assam', flag: '🍵', group: 'India' },
  { key: 'bihar', label: 'Bihar', flag: '🥔', group: 'India' },
  { key: 'odisha', label: 'Odisha', flag: '🍥', group: 'India' },
  { key: 'uttar_pradesh', label: 'Uttar Pradesh', flag: '🍢', group: 'India' },
  { key: 'himachal_pradesh', label: 'Himachal', flag: '🏔️', group: 'India' },
  { key: 'jammu_kashmir', label: 'Kashmir', flag: '🍖', group: 'India' },
  { key: 'delhi', label: 'Delhi', flag: '🌯', group: 'India' },
  { key: 'madhya_pradesh', label: 'Madhya Pradesh', flag: '🫘', group: 'India' },
  { key: 'haryana', label: 'Haryana', flag: '🥛', group: 'India' },
  { key: 'uttarakhand', label: 'Uttarakhand', flag: '⛰️', group: 'India' },
  { key: 'jharkhand', label: 'Jharkhand', flag: '🌾', group: 'India' },
  { key: 'chhattisgarh', label: 'Chhattisgarh', flag: '🌽', group: 'India' },
  { key: 'sikkim', label: 'Sikkim', flag: '🥟', group: 'India' },
  { key: 'manipur', label: 'Manipur', flag: '🍜', group: 'India' },
  { key: 'meghalaya', label: 'Meghalaya', flag: '🍄', group: 'India' },
  { key: 'nagaland', label: 'Nagaland', flag: '🌶️', group: 'India' },
  { key: 'mizoram', label: 'Mizoram', flag: '🎋', group: 'India' },
  { key: 'tripura', label: 'Tripura', flag: '🍤', group: 'India' },
  { key: 'arunachal_pradesh', label: 'Arunachal', flag: '🏞️', group: 'India' },
  { key: 'puducherry', label: 'Puducherry', flag: '🥖', group: 'India' },
  { key: 'chandigarh', label: 'Chandigarh', flag: '🍛', group: 'India' },
  { key: 'ladakh', label: 'Ladakh', flag: '🏔️', group: 'India' },
];

const MEAL_TYPES = [
  { key: 'breakfast', label: 'Breakfast', icon: Sunrise },
  { key: 'lunch', label: 'Lunch', icon: Sun },
  { key: 'dinner', label: 'Dinner', icon: Moon },
  { key: 'full_day', label: 'Full day', icon: CalendarDays },
];

const SKILL = [
  { key: 'beginner', label: 'Beginner', icon: Sprout },
  { key: 'intermediate', label: 'Comfortable', icon: Activity },
  { key: 'advanced', label: 'Confident', icon: Flame },
];

const DIETS = [
  { key: 'vegetarian', label: 'Vegetarian', icon: Leaf },
  { key: 'vegan', label: 'Vegan', icon: Leaf },
  { key: 'gluten-free', label: 'Gluten free', icon: Wheat },
  { key: 'dairy-free', label: 'Dairy free', icon: Milk },
  { key: 'nut-free', label: 'Nut free', icon: Nut },
];

const PANTRY = ['rice', 'lentils', 'paneer', 'yogurt', 'tomato', 'onion', 'coconut', 'chickpeas'];

const STAGES = [
  'Travelling to the region…',
  'Picking authentic dishes…',
  'Adapting to your kitchen…',
  'Writing the method…',
];

export default function Explorer({ apiBase }) {
  const [region, setRegion] = useState('indian');
  const [search, setSearch] = useState('');
  const [mealType, setMealType] = useState('full_day');
  const [skill, setSkill] = useState('intermediate');
  const [minutes, setMinutes] = useState(60);
  const [diets, setDiets] = useState([]);
  const [pantry, setPantry] = useState([]);
  // Two ways to cook. Standard is exactly what it was: authentic food from a
  // region, nutritionally arbitrary. Personalised additionally holds the plan
  // to the user's macro targets - the generator has never had access to a
  // single one of their numbers, so a full day of regional food could total
  // 40g of protein against a 150g target and look completely reasonable.
  const [personalised, setPersonalised] = useState(false);
  // daily = the day's goal, split by meal type
  // remaining = what is left of today after what has already been logged
  const [basis, setBasis] = useState('daily');
  const [targets, setTargets] = useState(null);
  const { result, loading, error, generate } = useGenerator(apiBase, '/culinary/generate-meal-plan');
  const { saved, persist, clear } = usePersistentPlan(apiBase, 'regional');

  // Show a freshly generated plan if there is one, otherwise whatever was
  // saved last session - so closing the app does not lose it.
  const activeContent = (result?.meal_plan || result?.recipe) || saved?.content;
  const isRestored = !result && Boolean(saved);

  // Always a valid enum key - the picker cannot produce anything else.
  const effectiveRegion = region;
  const selectedLabel = REGIONS.find((r) => r.key === region)?.label || region;
  const visibleRegions = search.trim()
    ? REGIONS.filter((r) =>
        (r.label + ' ' + r.key + ' ' + r.group).toLowerCase().includes(search.trim().toLowerCase()))
    : REGIONS.slice(0, 12);

  useEffect(() => {
    const text = result?.meal_plan || result?.recipe;
    if (text) persist(text, { cuisine_region: effectiveRegion, meal_type: mealType, time_constraint: minutes });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  // What each mode would aim at. Fetched up front so the numbers can be shown
  // on the picker rather than personalisation being applied invisibly.
  useEffect(() => {
    fetch(`${apiBase}/culinary/macro-targets`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.success && setTargets(d))
      .catch(() => {});
  }, [apiBase]);

  const hasGoal = Boolean(targets?.has_goal);
  // What the current selection resolves to, for the summary line.
  const activeTarget = !personalised ? null
    : basis === 'remaining' ? targets?.remaining
    : targets?.meals?.[mealType];
  const remainingUsable = targets?.remaining?.usable !== false;

  const run = () =>
    generate({
      cuisine_region: effectiveRegion,
      meal_type: mealType,
      dietary_restrictions: diets,
      time_constraint: minutes,
      cooking_skill: skill,
      available_ingredients: pantry,
      personalised,
      basis,
    });

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <PageHero
        icon={Globe}
        title="Explorer"
        subtitle="Cook something from somewhere else, adapted to your kitchen."
        gradient="#22D3EE,#8B5CF6"
      />

      {/* Mode selector - the same two-card pattern as the meal planner, so
          "personalised" means the same thing in both places. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(250px,1fr))', gap: '0.75rem' }}>
        {[
          {
            key: false, icon: Globe, title: 'Standard recipes',
            body: 'Authentic food from the region, built from the settings below. Same result for anyone with the same inputs.',
          },
          {
            key: true, icon: Sparkles, title: 'Personalised plan',
            body: hasGoal
              ? 'The same regional cooking, with portions and dishes chosen to hit your protein, carb and fat targets.'
              : 'Set a nutrition goal first and this will build the food around your targets.',
            disabled: !hasGoal,
          },
        ].map(({ key, icon: Icon, title, body, disabled }) => (
          <button
            key={String(key)}
            disabled={disabled}
            onClick={() => setPersonalised(key)}
            className="surface lift"
            style={{
              padding: '1.125rem', textAlign: 'left', cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
              borderColor: personalised === key ? '#8B5CF6' : undefined,
              background: personalised === key
                ? 'linear-gradient(135deg, rgba(139,92,246,0.16), rgba(34,211,238,0.05))'
                : undefined,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <Icon size={17} color={personalised === key ? '#A78BFA' : '#667085'} />
              <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{title}</span>
              {personalised === key && <Check size={15} color="#34D399" style={{ marginLeft: 'auto' }} />}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#98A2B3', lineHeight: 1.5 }}>{body}</div>
          </button>
        ))}
      </div>

      {/* The numbers it will actually aim at. Shown before generating for the
          same reason the meal planner shows its profile: a target you cannot
          see is indistinguishable from no target at all. */}
      {personalised && hasGoal && (
        <div style={{
          background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.25)',
          borderRadius: '0.75rem', padding: '1rem', display: 'grid', gap: '0.875rem',
        }}>
          <div style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-start' }}>
            <Target size={15} color="#A78BFA" style={{ flexShrink: 0, marginTop: 2 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Build the food to hit
              </div>
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                {[
                  { key: 'daily', label: 'My daily targets',
                    hint: mealType === 'full_day' ? 'the whole day' : `the ${mealType.replace('_', ' ')} share` },
                  { key: 'remaining', label: "What's left today",
                    hint: 'after everything logged so far' },
                ].map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className={`suggest-chip ${basis === option.key ? 'is-active' : ''}`}
                    onClick={() => setBasis(option.key)}
                    disabled={option.key === 'remaining' && !remainingUsable}
                    style={{ opacity: option.key === 'remaining' && !remainingUsable ? 0.45 : 1 }}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {activeTarget && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(90px,1fr))',
              gap: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(139,92,246,0.2)',
            }}>
              {[
                ['Calories', `${activeTarget.calories}`, 'kcal', '#FBBF24'],
                ['Protein', `${activeTarget.protein}`, 'g', '#22D3EE'],
                ['Carbs', `${activeTarget.carbs}`, 'g', '#A78BFA'],
                ['Fat', `${activeTarget.fat}`, 'g', '#F87171'],
              ].map(([label, value, unit, colour]) => (
                <div key={label}>
                  <div style={{ fontSize: '0.625rem', color: '#667085', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {label}
                  </div>
                  <div className="tabular" style={{ fontSize: '1.0625rem', fontWeight: 700, color: colour, marginTop: 2 }}>
                    {value}<span style={{ fontSize: '0.6875rem', color: '#667085', fontWeight: 500 }}> {unit}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* "Remaining" is meaningless before anything is logged, so say so
              rather than quietly answering a different question. */}
          {basis === 'remaining' && targets?.remaining?.fell_back && (
            <div style={{ fontSize: '0.75rem', color: '#FBBF24', lineHeight: 1.5 }}>
              Nothing logged today yet, so nothing is used up — this is the same as
              your daily target.
            </div>
          )}
          {!remainingUsable && (
            <div style={{ fontSize: '0.75rem', color: '#98A2B3', lineHeight: 1.5 }}>
              You've already met today's targets — "what's left" has nothing to work with.
            </div>
          )}
        </div>
      )}

      {/* Region picker */}
      <div className="surface-hero" style={{ padding: '1.5rem', display: 'grid', gap: '1rem' }}>
        <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <div className="section-title">Where are we cooking from?</div>
            <div className="section-sub">{REGIONS.length} regions — search to narrow it down</div>
          </div>
          <span className="pill pill-brand">
            <Compass size={12} /> {selectedLabel}
          </span>
        </div>

        {/* A filter over the supported list, not free text. The backend only
            accepts known regions, so letting someone type "Korean" would just
            produce a validation error they cannot act on. */}
        <input
          className="form-input"
          placeholder="Search regions… e.g. kerala, punjab, japanese"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        {visibleRegions.length === 0 ? (
          <div style={{ fontSize: '0.8125rem', color: '#98A2B3', padding: '0.5rem 0' }}>
            No region matches “{search}”. Try a state name, or one of: Indian,
            Mediterranean, Japanese, Thai, Chinese, Italian, Mexican, French.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(118px,1fr))', gap: '0.5rem' }}>
            {visibleRegions.map((r) => (
              <button
                key={r.key}
                onClick={() => setRegion(r.key)}
                className={`region-tile ${region === r.key ? 'is-active' : ''}`}
              >
                <span style={{ fontSize: '1.25rem' }}>{r.flag}</span>
                <span>{r.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: '1rem' }}>
        <Section title="What are you making?">
          <TileGroup options={MEAL_TYPES} value={mealType} onChange={setMealType} columns={4} />
        </Section>

        <Section title="Your comfort level">
          <TileGroup options={SKILL} value={skill} onChange={setSkill} columns={3} />
        </Section>
      </div>

      <Section
        title="Time available"
        right={<span className="pill pill-brand tabular"><Clock size={12} /> {minutes} min</span>}
      >
        <SliderField
          value={minutes} onChange={setMinutes}
          min={15} max={180} step={15}
          presets={[30, 45, 60, 90, 120]} unit="m"
        />
      </Section>

      <Section title="Anything already in the kitchen?" hint="Optional — it'll build around these">
        <ChipInput
          values={pantry}
          onChange={setPantry}
          placeholder="e.g. coconut milk, curry leaves"
          suggestions={PANTRY}
          suggestLabel="Common staples"
        />
      </Section>

      <Section title="Dietary preferences" hint="Optional">
        <ChipToggles options={DIETS} values={diets} onChange={setDiets} />
      </Section>

      <ErrorNote>{error}</ErrorNote>

      <GenerateButton
        onClick={run}
        loading={loading}
        label={personalised
          ? `Build a ${selectedLabel} plan for my targets`
          : `Explore ${selectedLabel} cooking`}
        stages={STAGES}
      />

      {loading && <LoadingSkeleton />}

      {activeContent && !loading && (
        <>
          {isRestored && <RestoredNote createdAt={saved?.created_at} onDismiss={clear} />}

          {/* Did it actually hit the numbers? Reported per macro and read back
              out of the plan itself, because asking a model for four figures
              and assuming it complied is not a check. */}
          {result?.verification && (
            <div style={{
              background: result.verification.hit
                ? 'rgba(52,211,153,0.08)' : 'rgba(251,191,36,0.08)',
              border: `1px solid ${result.verification.hit
                ? 'rgba(52,211,153,0.28)' : 'rgba(251,191,36,0.28)'}`,
              borderRadius: '0.75rem', padding: '1rem', display: 'grid', gap: '0.875rem',
            }}>
              <div style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-start' }}>
                {result.verification.hit
                  ? <Check size={15} color="#34D399" style={{ flexShrink: 0, marginTop: 2 }} />
                  : <Target size={15} color="#FBBF24" style={{ flexShrink: 0, marginTop: 2 }} />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                    {result.verification.checked
                      ? (result.verification.hit
                          ? 'Hit every macro'
                          : 'Close, but not everything landed')
                      : 'Could not verify the totals'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#98A2B3', marginTop: 2, lineHeight: 1.5 }}>
                    {result.verification.summary || result.verification.reason}
                    {result.verification.retried && ' (regenerated once to get closer.)'}
                  </div>
                </div>
              </div>

              {result.verification.checked && (
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(110px,1fr))',
                  gap: '0.75rem', paddingTop: '0.75rem',
                  borderTop: '1px solid rgba(255,255,255,0.07)',
                }}>
                  {['calories', 'protein', 'carbs', 'fat'].map((macro) => {
                    const m = result.verification.macros[macro];
                    if (!m) return null;
                    const ok = m.status === 'on_target';
                    return (
                      <div key={macro}>
                        <div style={{ fontSize: '0.625rem', color: '#667085', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          {macro}
                        </div>
                        <div className="tabular" style={{
                          fontSize: '1.0625rem', fontWeight: 700, marginTop: 2,
                          color: ok ? '#34D399' : '#FBBF24',
                        }}>
                          {m.stated}<span style={{ fontSize: '0.6875rem', color: '#667085', fontWeight: 500 }}> {m.unit}</span>
                        </div>
                        <div style={{ fontSize: '0.625rem', color: '#667085', marginTop: 1 }}>
                          {ok ? `target ${m.target}` : `${m.delta > 0 ? '+' : ''}${m.delta} vs range`}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <ResultPanel
            title={`${selectedLabel} kitchen`}
            icon={Globe}
            accent="#22D3EE"
            markdown={activeContent}
            onRegenerate={run}
            apiBase={apiBase}
            savedPlan={saved}
            planType="regional"
            params={{ cuisine_region: effectiveRegion, meal_type: mealType, time_constraint: minutes }}
            pills={[
              { label: selectedLabel, tone: 'pill-brand' },
              { label: mealType.replace('_', ' '), tone: 'pill-muted' },
              { label: `${minutes} min`, tone: 'pill-muted' },
              ...pantry.map((p) => ({ label: p, tone: 'pill-good' })),
            ]}
          />
        </>
      )}

      {!activeContent && !loading && (
        <EmptyState
          icon={Globe}
          title="Nowhere chosen yet"
          body="Pick a region above and Explorer will suggest dishes from there, adapted to your skill level and the time you have."
        />
      )}
    </div>
  );
}
