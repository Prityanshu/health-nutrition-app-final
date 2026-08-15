import React from 'react';
import { ArrowRight, Target } from 'lucide-react';
import Lotus from './Lotus';

/**
 * The first thing a new account sees.
 *
 * WHY THIS EXISTS
 * ---------------
 * Of the seven people who signed up in the app's first week, four did nothing
 * at all afterwards - no goal, no meal, no weigh-in. That is not a feature
 * problem. They landed on an empty dashboard with fourteen navigation items
 * and no indication of which one mattered, so they left.
 *
 * WHY IT IS PROSE AND NOT A CAROUSEL
 * ----------------------------------
 * The instinct is a swipeable tour of feature cards. Those get dismissed
 * without reading, because each card is a fragment and none of them answer the
 * only question a new user has: what is this for, and what do I do now?
 *
 * A few short paragraphs answer it in one screen, in the order someone
 * actually needs to know things. There is one button, and it goes to the one
 * thing that has to happen first.
 *
 * `hasGoal` is true when this is being replayed on purpose from Profile ->
 * Help rather than shown as the first-run gate - the account already has a
 * goal, so the button returns to the app instead of pushing them back into
 * goal setup, and there is nothing left to "skip".
 */

export default function Welcome({ name, onStart, onSkip, hasGoal = false }) {
  const first = (name || '').trim().split(' ')[0];

  return (
    <div className="stagger" style={{ display: 'grid', gap: '1.25rem', maxWidth: 640 }}>
      <div className="surface-hero" style={{ padding: '1.75rem', display: 'grid', gap: '1.25rem' }}>
        {/* The one screen where the mark earns real size - this is the first
            thing a new account sees, and the motto does more introducing than
            any sentence underneath it. */}
        <div style={{ display: 'grid', gap: '1rem', justifyItems: 'center', textAlign: 'center' }}>
          <Lotus size={76} strokeWidth={3.2} />
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
              {first ? `Welcome, ${first}` : 'Welcome to Kayosha'}
            </div>
            <div
              style={{
                fontSize: '0.6875rem', letterSpacing: '0.18em', textTransform: 'uppercase',
                color: 'var(--brand-magenta)', fontWeight: 600, marginTop: 6,
              }}
            >
              Nourish. Move. Thrive.
            </div>
          </div>
        </div>

        <div style={{ fontSize: '0.9375rem', lineHeight: 1.75, color: 'var(--text-secondary)', display: 'grid', gap: '0.875rem' }}>
          <p style={{ margin: 0 }}>
            Kayosha works out what you should be eating and training, and then
            checks whether you actually did. It is built around one idea: advice
            is only useful if it is based on your real numbers, so almost
            everything here follows from a goal and a food log.
          </p>

          <p style={{ margin: 0 }}>
            <strong style={{ color: 'var(--text)' }}>Start by setting a goal.</strong>{' '}
            You pick an objective — lose fat, gain muscle, or hold steady — and
            your calorie and macro targets are calculated from your height,
            weight, age and activity level. You are not asked to invent numbers.
            If you have a target weight in mind you can add it, and the pace is
            capped at what is actually safe rather than what sounds impressive.
          </p>

          <p style={{ margin: 0 }}>
            <strong style={{ color: 'var(--text)' }}>Then log what you eat.</strong>{' '}
            Describe a meal in plain words and the nutrition is worked out for
            you. For anything packaged, scan the barcode instead and the figures
            come off the actual product label. Every number tells you where it
            came from, so you always know whether you are looking at measured
            data or an estimate.
          </p>

          <p style={{ margin: 0 }}>
            <strong style={{ color: 'var(--text)' }}>The rest builds on those two.</strong>{' '}
            The specialists — recipes from what is in your kitchen, workouts
            that avoid your injuries, meal plans to a budget or a cuisine — all
            read your goal and your history. Points, streaks and the leaderboard
            come from logging consistently. A dashboard with nothing behind it
            can only show you empty boxes, which is why the goal comes first.
          </p>

          <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Nothing here is medical advice, and the AI-generated plans are
            suggestions rather than prescriptions. If something looks wrong,
            it might be — tell Prityanshu, that is the whole point of you
            being here.
          </p>
        </div>

        <div style={{ display: 'grid', gap: '0.625rem', justifyItems: 'center' }}>
          <button
            className="generate-btn"
            onClick={onStart}
            style={{ justifyContent: 'center', width: '100%' }}
          >
            <Target size={16} /> {hasGoal ? 'Back to the app' : 'Set my goal'} <ArrowRight size={15} />
          </button>

          {!hasGoal && onSkip && (
            <button
              type="button"
              onClick={onSkip}
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: '0.25rem',
                fontSize: '0.8125rem', color: 'var(--text-muted)', textDecoration: 'underline',
              }}
            >
              Skip for now — don't show this again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
