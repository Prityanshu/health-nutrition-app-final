import React, { useState, useEffect } from 'react';
import {
  Wallet, Leaf, Wheat, Milk, Nut, Egg, Zap, Clock, ChefHat,
  Coffee, UtensilsCrossed, Sparkles, IndianRupee,
} from 'lucide-react';
import {
  PageHero, Section, TileGroup, SliderField, ChipToggles,
  GenerateButton, LoadingSkeleton, ErrorNote, ResultPanel, EmptyState, useGenerator,
  usePersistentPlan, RestoredNote,
} from './SpecialistUI';

const DIETS = [
  { key: 'vegetarian', label: 'Vegetarian', icon: Leaf },
  { key: 'vegan', label: 'Vegan', icon: Leaf },
  { key: 'eggetarian', label: 'Eggs ok', icon: Egg },
  { key: 'gluten-free', label: 'Gluten free', icon: Wheat },
  { key: 'dairy-free', label: 'Dairy free', icon: Milk },
  { key: 'nut-free', label: 'Nut free', icon: Nut },
];

const MEALS_PER_DAY = [
  { key: 2, label: '2 meals', icon: Coffee },
  { key: 3, label: '3 meals', icon: UtensilsCrossed },
  { key: 4, label: '4 meals', icon: UtensilsCrossed },
  { key: 5, label: '5 meals', icon: UtensilsCrossed },
];

const COOKING_TIME = [
  { key: 'quick', label: 'Quick', icon: Zap },
  { key: 'moderate', label: 'Moderate', icon: Clock },
  { key: 'relaxed', label: 'No rush', icon: ChefHat },
];

const SKILL = [
  { key: 'beginner', label: 'Beginner' },
  { key: 'intermediate', label: 'Comfortable' },
  { key: 'advanced', label: 'Confident' },
];

const STAGES = [
  'Checking your budget…',
  'Costing out ingredients…',
  'Balancing nutrition against price…',
  'Writing the plan…',
];

export default function BudgetChef({ apiBase }) {
  const [budget, setBudget] = useState(300);
  const [calories, setCalories] = useState(2000);
  const [diets, setDiets] = useState([]);
  const [mealsPerDay, setMealsPerDay] = useState(3);
  const [cookingTime, setCookingTime] = useState('moderate');
  const [skill, setSkill] = useState('intermediate');
  const [goalCalories, setGoalCalories] = useState(null);
  const { result, loading, error, generate } = useGenerator(apiBase, '/budget/generate-meal-plan');
  const { saved, persist, clear } = usePersistentPlan(apiBase, 'budget_meal_plan');

  // Show a freshly generated plan if there is one, otherwise whatever was
  // saved last session - so closing the app does not lose it.
  const activeContent = (result?.meal_plan) || saved?.content;
  const isRestored = !result && Boolean(saved);

  // Default the calorie target to the user's actual goal rather than a
  // made-up 2000, so the plan lines up with the rest of the app.
  useEffect(() => {
    fetch(`${apiBase}/goals/?active_only=true`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((goals) => {
        const target = goals?.[0]?.target_calories;
        if (target) { setCalories(Math.round(target)); setGoalCalories(Math.round(target)); }
      })
      .catch(() => {});
  }, [apiBase]);

  const perMeal = Math.round(budget / mealsPerDay);

  useEffect(() => {
    const text = result?.meal_plan;
    if (text) persist(text, { budget_per_day: budget, calorie_target: calories, meals_per_day: mealsPerDay, dietary_preferences: diets });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const run = () =>
    generate({
      budget_per_day: budget,
      calorie_target: calories,
      dietary_preferences: diets,
      meals_per_day: mealsPerDay,
      cooking_time: cookingTime,
      skill_level: skill,
      age: null,
      weight: null,
      activity_level: 'moderate',
    });

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      <PageHero
        icon={Wallet}
        title="BudgetChef"
        subtitle="Eat well without overspending. Set a daily budget and it works within it."
        gradient="#34D399,#22D3EE"
      />

      {/* Budget hero */}
      <div className="surface-hero" style={{ padding: '1.75rem' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div className="metric-label">Daily food budget</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: 6 }}>
              <IndianRupee size={26} color="#34D399" />
              <span className="metric-value tabular" style={{ fontSize: '3rem' }}>{budget}</span>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="metric-label">Per meal</div>
            <div className="tabular" style={{ fontSize: '1.5rem', fontWeight: 700, color: '#22D3EE', marginTop: 6 }}>
              ₹{perMeal}
            </div>
            <div style={{ fontSize: '0.6875rem', color: '#667085' }}>across {mealsPerDay} meals</div>
          </div>
        </div>
        <SliderField
          value={budget} onChange={setBudget}
          min={50} max={1500} step={25}
          presets={[100, 200, 300, 500, 800]}
          format={(v) => `₹${v}`}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: '1rem' }}>
        <Section title="How many meals a day?">
          <TileGroup options={MEALS_PER_DAY} value={mealsPerDay} onChange={setMealsPerDay} columns={4} />
        </Section>

        <Section title="How much time for cooking?">
          <TileGroup options={COOKING_TIME} value={cookingTime} onChange={setCookingTime} columns={3} />
        </Section>
      </div>

      <Section
        title="Daily calories"
        hint={goalCalories ? 'Pulled from your active goal' : 'No goal set — using a general default'}
        right={<span className="pill pill-brand tabular">{calories} kcal</span>}
      >
        <SliderField
          value={calories} onChange={setCalories}
          min={1200} max={4000} step={50}
          presets={goalCalories ? [goalCalories, 1800, 2200, 2600] : [1600, 2000, 2400, 2800]}
          unit=" kcal"
        />
      </Section>

      <Section title="How confident are you in the kitchen?">
        <TileGroup options={SKILL} value={skill} onChange={setSkill} columns={3} />
      </Section>

      <Section title="Dietary preferences" hint="Optional">
        <ChipToggles options={DIETS} values={diets} onChange={setDiets} />
      </Section>

      <ErrorNote>{error}</ErrorNote>

      <GenerateButton
        onClick={run}
        loading={loading}
        label={`Plan meals for ₹${budget}/day`}
        stages={STAGES}
      />

      {loading && <LoadingSkeleton />}

      {activeContent && !loading && (
        <>
          {isRestored && <RestoredNote createdAt={saved?.created_at} onDismiss={clear} />}
          <ResultPanel
            title="Your budget plan"
            icon={Sparkles}
            accent="#34D399"
            markdown={activeContent}
            onRegenerate={run}
            apiBase={apiBase}
            savedPlan={saved}
            planType="budget_meal_plan"
            params={{ budget_per_day: budget, calorie_target: calories, meals_per_day: mealsPerDay }}
            pills={[
              { label: `₹${budget}/day`, tone: 'pill-good' },
              { label: `${calories} kcal`, tone: 'pill-brand' },
              { label: `${mealsPerDay} meals`, tone: 'pill-muted' },
              ...diets.map((d) => ({ label: d, tone: 'pill-muted' })),
            ]}
          />
        </>
      )}

      {!activeContent && !loading && (
        <EmptyState
          icon={Wallet}
          title="No plan yet"
          body="Set your daily budget above and BudgetChef will build a week of meals that fits inside it."
        />
      )}
    </div>
  );
}
