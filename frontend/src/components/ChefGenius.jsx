import React, { useState, useEffect, useRef } from 'react';
import {
  ChefHat, Plus, X, Sparkles, Clock, Sunrise, Sun, Moon, Cookie,
  Leaf, Wheat, Milk, Nut, Copy, Check, RefreshCw, Flame,
} from 'lucide-react';
import renderMarkdown from './markdown';
import { usePersistentPlan, RestoredNote, PlanActions } from './SpecialistUI';

/**
 * ChefGenius - generate a recipe from what the user actually has.
 *
 * The previous screen was a stack of plain inputs, a dropdown and five raw
 * checkboxes. Same logic, but the interaction now matches the rest of the app:
 * ingredients are chips, choices are toggles, and the form pulls the user's
 * most-logged foods as one-tap suggestions so the common case is a single click.
 */

const MEAL_TYPES = [
  { key: 'breakfast', label: 'Breakfast', icon: Sunrise },
  { key: 'lunch', label: 'Lunch', icon: Sun },
  { key: 'dinner', label: 'Dinner', icon: Moon },
  { key: 'snack', label: 'Snack', icon: Cookie },
];

const DIETARY = [
  { key: 'vegetarian', label: 'Vegetarian', icon: Leaf },
  { key: 'vegan', label: 'Vegan', icon: Leaf },
  { key: 'gluten free', label: 'Gluten free', icon: Wheat },
  { key: 'dairy free', label: 'Dairy free', icon: Milk },
  { key: 'nut free', label: 'Nut free', icon: Nut },
];

const TIME_PRESETS = [15, 30, 45, 60, 90];

const COMMON = [
  'eggs', 'paneer', 'chicken', 'rice', 'onion', 'tomato',
  'potato', 'spinach', 'lentils', 'yogurt', 'oats', 'tofu',
];

// Staged messages so a 20-second generation doesn't feel frozen.
const STAGES = [
  'Reading your ingredients…',
  'Balancing the macros…',
  'Working out the method…',
  'Writing it up…',
];

export default function ChefGenius({ apiBase, onNavigate }) {
  const [ingredients, setIngredients] = useState([]);
  const [draft, setDraft] = useState('');
  const [mealType, setMealType] = useState('dinner');
  const [minutes, setMinutes] = useState(30);
  const [restrictions, setRestrictions] = useState([]);
  const [recipe, setRecipe] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [regulars, setRegulars] = useState([]);
  const { saved, persist, clear } = usePersistentPlan(apiBase, 'recipe');
  const inputRef = useRef(null);

  const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  });

  // Pull the user's most-logged foods as one-tap suggestions. Reuses the
  // personalisation endpoint rather than adding another.
  useEffect(() => {
    fetch(`${apiBase}/ml/for-you`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const favs = d?.profile?.favourites || [];
        setRegulars(favs.map((f) => f.name).slice(0, 6));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  // Advance the loading caption while the request is in flight.
  useEffect(() => {
    if (!loading) return setStage(0);
    const t = setInterval(() => setStage((s) => (s + 1) % STAGES.length), 2600);
    return () => clearInterval(t);
  }, [loading]);

  const addIngredient = (value) => {
    const v = (value || '').trim().toLowerCase();
    if (!v || ingredients.includes(v)) return;
    setIngredients((prev) => [...prev, v]);
    setDraft('');
    inputRef.current?.focus();
  };

  const removeIngredient = (v) =>
    setIngredients((prev) => prev.filter((i) => i !== v));

  const toggleRestriction = (key) =>
    setRestrictions((prev) =>
      prev.includes(key) ? prev.filter((r) => r !== key) : [...prev, key]
    );

  const generate = async () => {
    if (!ingredients.length) {
      setError('Add at least one ingredient first.');
      return;
    }
    setLoading(true);
    setError('');
    setRecipe(null);
    try {
      const res = await fetch(`${apiBase}/v1/recipes/generate-from-ingredients`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          ingredients,
          dietary_restrictions: restrictions,
          time_constraint: minutes,
          meal_type: mealType,
        }),
      });
      const data = await res.json();
      if (res.ok && data.success && data.data) {
        setRecipe(data.data);
        // Persist so the recipe is still here after closing the app.
        persist(data.data.recipe, { ingredients, meal_type: mealType, time_constraint: minutes },
                `Recipe with ${ingredients.slice(0, 3).join(', ')}`);
      } else {
        setError(
          typeof data.detail === 'string'
            ? data.detail
            : 'Could not generate a recipe. Try again in a moment.'
        );
      }
    } catch {
      setError('Could not reach the kitchen. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const copyRecipe = () => {
    if (!shown?.recipe) return;
    navigator.clipboard?.writeText(shown.recipe);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  // Fall back to the last saved recipe when nothing was generated this session.
  const shown = recipe || (saved ? { recipe: saved.content, meal_type: saved.params?.meal_type,
    time_constraint: saved.params?.time_constraint, ingredients_used: saved.params?.ingredients || [] } : null);
  const isRestored = !recipe && Boolean(saved);

  const suggestions = [...regulars, ...COMMON]
    .map((s) => s.toLowerCase())
    .filter((s, i, arr) => arr.indexOf(s) === i && !ingredients.includes(s))
    .slice(0, 10);

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      {/* Hero */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div
          className="flex items-center justify-center"
          style={{
            width: 52, height: 52, borderRadius: 15, flexShrink: 0,
            background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
            boxShadow: '0 0 28px -6px rgba(139,92,246,0.7)',
          }}
        >
          <ChefHat size={25} color="#fff" />
        </div>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
            ChefGenius
          </h1>
          <p className="section-sub" style={{ fontSize: '0.875rem' }}>
            Tell it what's in your kitchen. It builds the recipe around that.
          </p>
        </div>
      </div>

      {/* Ingredients */}
      <div className="surface-hero" style={{ padding: '1.5rem', display: 'grid', gap: '1rem' }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="section-title">What have you got?</div>
            <div className="section-sub">Type and press Enter, or tap a suggestion</div>
          </div>
          {ingredients.length > 0 && (
            <span className="pill pill-brand">{ingredients.length} added</span>
          )}
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            ref={inputRef}
            className="form-input"
            style={{ flex: 1 }}
            placeholder="e.g. paneer, spinach, cumin…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); addIngredient(draft); }
              if (e.key === 'Backspace' && !draft && ingredients.length) {
                removeIngredient(ingredients[ingredients.length - 1]);
              }
            }}
          />
          <button
            className="btn btn-primary"
            onClick={() => addIngredient(draft)}
            disabled={!draft.trim()}
            style={{ opacity: draft.trim() ? 1 : 0.45 }}
          >
            <Plus size={16} />
          </button>
        </div>

        {/* Chosen ingredients */}
        {ingredients.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4375rem' }}>
            {ingredients.map((ing) => (
              <span
                key={ing}
                className="ingredient-chip"
                onClick={() => removeIngredient(ing)}
                title="Remove"
              >
                {ing}
                <X size={13} />
              </span>
            ))}
          </div>
        )}

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div>
            <div style={{ fontSize: '0.6875rem', color: '#667085', marginBottom: '0.5rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {regulars.length ? 'From your regulars & staples' : 'Common staples'}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4375rem' }}>
              {suggestions.map((s) => (
                <button key={s} className="suggest-chip" onClick={() => addIngredient(s)}>
                  <Plus size={12} /> {s}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Options */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: '1rem' }}>
        {/* Meal type */}
        <div className="surface" style={{ padding: '1.25rem' }}>
          <div className="section-title" style={{ marginBottom: '0.875rem' }}>Meal</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.4375rem' }}>
            {MEAL_TYPES.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setMealType(key)}
                className={`choice-tile ${mealType === key ? 'is-active' : ''}`}
              >
                <Icon size={17} />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Time */}
        <div className="surface" style={{ padding: '1.25rem' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: '0.875rem' }}>
            <div className="section-title">Time you have</div>
            <span className="pill pill-brand tabular">
              <Clock size={12} /> {minutes} min
            </span>
          </div>
          <input
            type="range" min="10" max="120" step="5"
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
            className="range-slider"
            style={{ '--pct': `${((minutes - 10) / 110) * 100}%` }}
          />
          <div style={{ display: 'flex', gap: '0.375rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
            {TIME_PRESETS.map((t) => (
              <button
                key={t}
                onClick={() => setMinutes(t)}
                className={`suggest-chip ${minutes === t ? 'is-active' : ''}`}
              >
                {t}m
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dietary */}
      <div className="surface" style={{ padding: '1.25rem' }}>
        <div className="section-title" style={{ marginBottom: '0.25rem' }}>Anything to avoid?</div>
        <div className="section-sub" style={{ marginBottom: '0.875rem' }}>Optional — leave blank for no restrictions</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          {DIETARY.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => toggleRestriction(key)}
              className={`toggle-chip ${restrictions.includes(key) ? 'is-active' : ''}`}
            >
              <Icon size={14} /> {label}
              {restrictions.includes(key) && <Check size={13} />}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="surface" style={{ padding: '0.9375rem', borderColor: '#F87171', color: '#F87171', fontSize: '0.875rem' }}>
          {error}
        </div>
      )}

      {/* Generate */}
      <button
        onClick={generate}
        disabled={loading || !ingredients.length}
        className="generate-btn"
        style={{ opacity: ingredients.length ? 1 : 0.5, cursor: ingredients.length ? 'pointer' : 'not-allowed' }}
      >
        {loading ? (
          <>
            <RefreshCw size={17} className="spin" />
            {STAGES[stage]}
          </>
        ) : (
          <>
            <Sparkles size={17} />
            {ingredients.length ? `Create a ${mealType} recipe` : 'Add an ingredient to start'}
          </>
        )}
      </button>

      {/* Loading skeleton */}
      {loading && (
        <div className="surface" style={{ padding: '1.5rem', display: 'grid', gap: '0.75rem' }}>
          <div className="skeleton" style={{ height: 24, width: '55%' }} />
          <div className="skeleton" style={{ height: 14 }} />
          <div className="skeleton" style={{ height: 14, width: '88%' }} />
          <div className="skeleton" style={{ height: 14, width: '72%' }} />
        </div>
      )}

      {/* Result */}
      {isRestored && !loading && <RestoredNote createdAt={saved?.created_at} onDismiss={clear} />}

      {shown && !loading && (
        <div className="surface-hero" style={{ padding: '1.5rem', display: 'grid', gap: '1.125rem' }}>
          <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
              <Flame size={18} color="#FBBF24" />
              <span style={{ fontWeight: 700, fontSize: '1.0625rem' }}>Your recipe</span>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="ghost-btn" onClick={copyRecipe}>
                {copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy</>}
              </button>
              <button className="ghost-btn" onClick={generate}>
                <RefreshCw size={14} /> Another
              </button>
              <PlanActions
                apiBase={apiBase} plan={saved} compact
                planType="recipe" content={shown?.recipe}
                params={{ ingredients, meal_type: mealType, time_constraint: minutes }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.4375rem', flexWrap: 'wrap' }}>
            <span className="pill pill-muted" style={{ textTransform: 'capitalize' }}>{shown.meal_type}</span>
            <span className="pill pill-muted"><Clock size={12} /> under {shown.time_constraint} min</span>
            {(shown.ingredients_used || []).map((i) => (
              <span key={i} className="pill pill-brand">{i}</span>
            ))}
          </div>

          <hr className="hairline" />

          <div
            className="recipe-body"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(shown.recipe) }}
          />

          <button className="btn btn-secondary" style={{ justifyContent: 'center' }} onClick={() => onNavigate('log-meal')}>
            Log this meal
          </button>
        </div>
      )}

      {/* Empty state */}
      {!shown && !loading && ingredients.length === 0 && (
        <div className="surface" style={{ padding: '2.5rem 1.5rem', textAlign: 'center' }}>
          <ChefHat size={30} color="#3A4453" style={{ marginBottom: '0.75rem' }} />
          <div style={{ color: '#98A2B3', fontSize: '0.9375rem', fontWeight: 600 }}>
            Nothing in the pan yet
          </div>
          <div style={{ color: '#667085', fontSize: '0.8125rem', marginTop: 5 }}>
            Add a couple of ingredients above and ChefGenius will build something around them.
          </div>
        </div>
      )}
    </div>
  );
}
