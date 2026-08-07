import React from 'react';
import {
  Flame, UtensilsCrossed, MessageSquare, Trophy, Target,
  ChevronRight, Plus, Sparkles, TrendingDown, TrendingUp, Minus, Scale,
} from 'lucide-react';
import useCountUp from './useCountUp';

/**
 * Dashboard - today at a glance, measured against the active goal.
 *
 * Everything here compares intake to the targets calculated when the goal was
 * set. Where there is no active goal the numbers are shown without comparison
 * and the user is prompted to set one, rather than being silently measured
 * against invented defaults.
 */

const clamp = (n, min = 0, max = 100) => Math.min(max, Math.max(min, n));
const num = (v) => (typeof v === 'number' && !Number.isNaN(v) ? v : 0);

/** Concentric progress rings: calories outer, protein inner. */
function GoalRings({ calories, calorieTarget, protein, proteinTarget, hasGoal }) {
  const size = 224;
  const animatedCals = useCountUp(calories);

  const rings = [
    {
      r: 96, stroke: 15, value: calories, target: calorieTarget,
      from: '#8B5CF6', to: '#22D3EE', label: 'calories',
    },
    {
      r: 74, stroke: 11, value: protein, target: proteinTarget,
      from: '#22D3EE', to: '#34D399', label: 'protein',
    },
  ];

  const over = hasGoal && calorieTarget > 0 && calories > calorieTarget * 1.05;
  const remaining = Math.max(0, calorieTarget - calories);

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <defs>
          {rings.map((ring, i) => (
            <linearGradient key={i} id={`ring${i}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={over && i === 0 ? '#FBBF24' : ring.from} />
              <stop offset="100%" stopColor={over && i === 0 ? '#F87171' : ring.to} />
            </linearGradient>
          ))}
        </defs>
        {rings.map((ring, i) => {
          const c = 2 * Math.PI * ring.r;
          const pct = ring.target > 0 ? clamp((ring.value / ring.target) * 100) : 0;
          const offset = c - (pct / 100) * c;
          return (
            <g key={i}>
              <circle
                cx={size / 2} cy={size / 2} r={ring.r}
                fill="none" stroke="#232A35" strokeWidth={ring.stroke}
              />
              <circle
                cx={size / 2} cy={size / 2} r={ring.r}
                fill="none"
                stroke={`url(#ring${i})`}
                strokeWidth={ring.stroke}
                strokeLinecap="round"
                strokeDasharray={c}
                strokeDashoffset={offset}
                className="ring-animate"
                style={{
                  '--dash-from': `${c}px`,
                  '--dash-to': `${offset}px`,
                  animationDelay: `${i * 0.12}s`,
                  filter: `drop-shadow(0 0 7px ${ring.from}66)`,
                }}
              />
            </g>
          );
        })}
      </svg>

      <div style={{
        position: 'absolute', inset: 0, display: 'flex',
        flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <div className="metric-value tabular" style={{ fontSize: '3rem' }}>
          {Math.round(animatedCals).toLocaleString()}
        </div>
        <div className="metric-label" style={{ marginTop: 5 }}>
          {hasGoal ? `of ${calorieTarget.toLocaleString()} kcal` : 'kcal today'}
        </div>
        {hasGoal && (
          <div style={{
            marginTop: 9, fontSize: '0.75rem', fontWeight: 700,
            color: over ? '#FBBF24' : '#34D399',
          }}>
            {over
              ? `${(calories - calorieTarget).toLocaleString()} over`
              : `${remaining.toLocaleString()} to go`}
          </div>
        )}
      </div>
    </div>
  );
}

function MacroBar({ label, grams, target, color, hasGoal, delay = 0 }) {
  const pct = target > 0 ? clamp((grams / target) * 100) : 0;
  const animated = useCountUp(grams);
  const hit = hasGoal && pct >= 95;

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 6 }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{label}</span>
        <span className="tabular" style={{ fontSize: '0.75rem', color: hit ? '#34D399' : '#98A2B3' }}>
          {Math.round(animated)}g
          {hasGoal && <span style={{ color: '#667085' }}> / {Math.round(target)}g</span>}
        </span>
      </div>
      <div className="macro-track">
        <div
          className="macro-fill macro-fill-animate"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${color}, ${color}CC)`,
            animationDelay: `${delay}s`,
            boxShadow: pct > 0 ? `0 0 10px ${color}55` : 'none',
          }}
        />
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, label, value, sub, accent, onClick }) {
  return (
    <div
      className="surface lift"
      onClick={onClick}
      style={{ padding: '1.125rem', cursor: onClick ? 'pointer' : 'default' }}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
        <span className="metric-label">{label}</span>
        <Icon size={16} color={accent} />
      </div>
      <div className="tabular" style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

/** Progress along a weight goal, start → now → target. */
function WeightProgress({ weight, goal, onNavigate }) {
  const entries = weight?.entries || [];
  if (!goal?.target_weight || entries.length === 0) return null;

  const start = entries[0].weight_kg;
  const current = entries[entries.length - 1].weight_kg;
  const target = goal.target_weight;

  const total = Math.abs(target - start);
  const done = Math.abs(current - start);
  const pct = total > 0 ? clamp((done / total) * 100) : 0;
  const movedRight = Math.sign(target - start) === Math.sign(current - start) || current === start;

  const change = current - start;
  const Trend = change < -0.05 ? TrendingDown : change > 0.05 ? TrendingUp : Minus;

  return (
    <div className="surface lift" style={{ padding: '1.25rem' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
        <div>
          <div className="section-title">Weight goal</div>
          <div className="section-sub">{start} kg → {target} kg</div>
        </div>
        <span className={`pill ${movedRight ? 'pill-good' : 'pill-warn'}`}>
          <Trend size={13} />
          {change > 0 ? '+' : ''}{change.toFixed(1)} kg
        </span>
      </div>

      <div className="macro-track" style={{ height: '0.625rem' }}>
        <div
          className="macro-fill macro-fill-animate"
          style={{
            width: `${pct}%`,
            background: 'linear-gradient(90deg,#8B5CF6,#22D3EE)',
            boxShadow: '0 0 12px rgba(139,92,246,0.5)',
          }}
        />
      </div>

      <div className="flex items-center justify-between" style={{ marginTop: '0.625rem', fontSize: '0.75rem', color: '#667085' }}>
        <span>{Math.round(pct)}% there</span>
        <span className="tabular" style={{ color: '#EEF2F7', fontWeight: 600 }}>{current} kg now</span>
        <button
          onClick={() => onNavigate('view-progress')}
          style={{ background: 'none', border: 'none', color: '#A78BFA', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}
        >
          Details
        </button>
      </div>
    </div>
  );
}

export default function Dashboard({ user, dashboardData, onNavigate, isLoading }) {
  const stats = dashboardData?.dailyStats || {};
  const meals = dashboardData?.recentMeals || [];
  const challenges = dashboardData?.challenges || [];
  const goals = dashboardData?.goals || [];
  const weight = dashboardData?.weight;

  const goal = goals.find((g) => g.is_active) || goals[0] || null;
  const hasGoal = Boolean(goal?.target_calories);

  const calorieTarget = num(goal?.target_calories);
  const proteinTarget = num(goal?.target_protein);
  const carbTarget = num(goal?.target_carbs);
  const fatTarget = num(goal?.target_fat);

  const consumed = num(stats.total_calories);
  const protein = num(stats.total_protein);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = (user?.full_name || user?.username || '').split(' ')[0] || 'there';

  const goalLabel = goal?.goal_type
    ? goal.goal_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : null;

  if (isLoading) {
    return (
      <div style={{ display: 'grid', gap: '1rem' }}>
        <div className="skeleton" style={{ height: 40, width: 260 }} />
        <div className="skeleton" style={{ height: 300 }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '1rem' }}>
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 110 }} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem' }}>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div className="metric-label">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', marginTop: 4 }}>
            {greeting}, {firstName}
          </h1>
          {goalLabel && (
            <span className="pill pill-brand" style={{ marginTop: 8 }}>
              <Target size={12} /> {goalLabel}
            </span>
          )}
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('log-meal')}>
          <Plus size={16} style={{ marginRight: 6 }} /> Log a meal
        </button>
      </div>

      {/* No goal yet */}
      {!hasGoal && (
        <button
          onClick={() => onNavigate('set-goals')}
          className="surface-hero lift"
          style={{
            padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem',
            textAlign: 'left', cursor: 'pointer', width: '100%',
            borderColor: 'rgba(139,92,246,0.35)',
          }}
        >
          <div className="flex items-center justify-center" style={{
            width: 44, height: 44, borderRadius: 12, flexShrink: 0,
            background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
          }}>
            <Target size={20} color="#fff" />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>Set a goal to unlock targets</div>
            <div style={{ fontSize: '0.8125rem', color: '#98A2B3', marginTop: 2 }}>
              Pick what you're aiming for and we'll work out your calories and macros.
            </div>
          </div>
          <ChevronRight size={18} color="#667085" />
        </button>
      )}

      {/* Rings + macros */}
      <div className="surface-hero dash-hero" style={{ padding: '1.75rem', display: 'flex', gap: '2rem', alignItems: 'center' }}>
        <GoalRings
          calories={consumed} calorieTarget={calorieTarget}
          protein={protein} proteinTarget={proteinTarget}
          hasGoal={hasGoal}
        />
        <div style={{ flex: 1, minWidth: 220, display: 'grid', gap: '1.125rem' }}>
          <div className="flex items-center justify-between">
            <span className="metric-label">Macronutrients</span>
            <span className="pill pill-brand">
              {num(stats.meal_count)} {num(stats.meal_count) === 1 ? 'meal' : 'meals'} today
            </span>
          </div>
          <MacroBar label="Protein" grams={protein} target={proteinTarget} color="#22D3EE" hasGoal={hasGoal} delay={0.05} />
          <MacroBar label="Carbs" grams={num(stats.total_carbs)} target={carbTarget} color="#A78BFA" hasGoal={hasGoal} delay={0.12} />
          <MacroBar label="Fat" grams={num(stats.total_fat)} target={fatTarget} color="#FBBF24" hasGoal={hasGoal} delay={0.19} />
        </div>
      </div>

      <WeightProgress weight={weight} goal={goal} onNavigate={onNavigate} />

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '1rem' }}>
        <StatTile
          icon={Flame} accent="#FBBF24" label="Calories"
          value={consumed.toLocaleString()}
          sub={hasGoal ? `${Math.round((consumed / calorieTarget) * 100)}% of target` : 'no target set'}
        />
        <StatTile
          icon={UtensilsCrossed} accent="#22D3EE" label="Meals"
          value={num(stats.meal_count)} sub="logged today"
          onClick={() => onNavigate('log-meal')}
        />
        <StatTile
          icon={Scale} accent="#34D399" label="Weight"
          value={weight?.latest ? `${weight.latest} kg` : '—'}
          sub={weight?.count > 1 ? `${weight.change_kg > 0 ? '+' : ''}${weight.change_kg} kg overall` : 'log your first'}
          onClick={() => onNavigate('set-goals')}
        />
        <StatTile
          icon={Trophy} accent="#A78BFA" label="Challenges"
          value={challenges.length} sub={challenges.length ? 'in progress' : 'none active'}
          onClick={() => onNavigate('enhanced-challenges')}
        />
      </div>

      {/* Assistant */}
      <button
        onClick={() => onNavigate('chatbot')}
        className="surface lift"
        style={{
          padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem',
          textAlign: 'left', cursor: 'pointer', width: '100%',
          background: 'linear-gradient(100deg, rgba(139,92,246,0.14), rgba(34,211,238,0.05))',
          borderColor: 'rgba(139,92,246,0.3)',
        }}
      >
        <div className="flex items-center justify-center" style={{
          width: 44, height: 44, borderRadius: 12, flexShrink: 0,
          background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
        }}>
          <MessageSquare size={20} color="#fff" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>Ask your AI coach</div>
          <div style={{ fontSize: '0.8125rem', color: '#98A2B3', marginTop: 2 }}>
            {hasGoal
              ? `Plan meals that fit ${calorieTarget.toLocaleString()} kcal`
              : 'Plan meals, adapt workouts, or check what to eat next'}
          </div>
        </div>
        <ChevronRight size={18} color="#667085" />
      </button>

      {/* Recent meals */}
      <div className="surface" style={{ padding: '1.25rem' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
          <span className="section-title">Recent meals</span>
          <button
            onClick={() => onNavigate('view-progress')}
            style={{ background: 'none', border: 'none', color: '#A78BFA', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}
          >
            View all
          </button>
        </div>

        {meals.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem 1rem' }}>
            <Sparkles size={26} color="#3A4453" style={{ marginBottom: 10 }} />
            <div style={{ color: '#98A2B3', fontSize: '0.875rem' }}>Nothing logged yet today</div>
            <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => onNavigate('log-meal')}>
              Log your first meal
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {meals.slice(0, 5).map((meal, i) => (
              <div
                key={meal.id ?? i}
                className="flex items-center justify-between lift"
                style={{
                  padding: '0.75rem', borderRadius: '0.625rem',
                  background: '#12151B', border: '1px solid #2A3240',
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {meal.food_name || meal.name || 'Meal'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#667085', marginTop: 2, textTransform: 'capitalize' }}>
                    {meal.meal_type || 'meal'}
                  </div>
                </div>
                <div className="tabular" style={{ fontSize: '0.875rem', fontWeight: 700, color: '#FBBF24', flexShrink: 0 }}>
                  {Math.round(num(meal.calories))} kcal
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
