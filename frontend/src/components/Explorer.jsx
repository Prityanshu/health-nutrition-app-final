import React, { useState, useEffect } from 'react';
import {
  Globe, Sunrise, Sun, Moon, CalendarDays, Leaf, Wheat, Milk, Nut,
  Sprout, Activity, Flame, Clock, Compass,
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

  const run = () =>
    generate({
      cuisine_region: effectiveRegion,
      meal_type: mealType,
      dietary_restrictions: diets,
      time_constraint: minutes,
      cooking_skill: skill,
      available_ingredients: pantry,
    });

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <PageHero
        icon={Globe}
        title="Explorer"
        subtitle="Cook something from somewhere else, adapted to your kitchen."
        gradient="#22D3EE,#8B5CF6"
      />

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
        label={`Explore ${selectedLabel} cooking`}
        stages={STAGES}
      />

      {loading && <LoadingSkeleton />}

      {activeContent && !loading && (
        <>
          {isRestored && <RestoredNote createdAt={saved?.created_at} onDismiss={clear} />}
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
