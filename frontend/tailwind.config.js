/** @type {import('tailwindcss').Config} */

// Design tokens for the dark, data-forward theme (Whoop / Oura direction).
// Kept here rather than as raw hex in components so the palette can be
// retuned in one place.
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}', './public/index.html'],
  theme: {
    extend: {
      colors: {
        // Base surfaces, darkest to lightest
        ink: {
          900: '#0B0D11', // page background
          800: '#12151B', // raised panel
          700: '#171B23', // card
          600: '#1E242E', // card hover / input
          500: '#2A3240', // border
          400: '#3A4453', // strong border
        },
        // Text
        chalk: {
          DEFAULT: '#EEF2F7',
          muted: '#98A2B3',
          faint: '#667085',
        },
        // Brand accent - carries over the purple from the previous theme
        violet: {
          DEFAULT: '#8B5CF6',
          bright: '#A78BFA',
          deep: '#6D28D9',
        },
        // Semantic data colours - one per macro so charts stay consistent
        macro: {
          protein: '#22D3EE',
          carbs: '#A78BFA',
          fat: '#FBBF24',
        },
        signal: {
          good: '#34D399',
          warn: '#FBBF24',
          bad: '#F87171',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        mono: ['"SF Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // Oversized numerals for the metric readouts
        metric: ['3.5rem', { lineHeight: '1', letterSpacing: '-0.03em', fontWeight: '700' }],
        'metric-sm': ['2rem', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '700' }],
      },
      borderRadius: {
        card: '1rem',
        pill: '999px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -8px rgba(0,0,0,0.5)',
        glow: '0 0 24px -4px rgba(139, 92, 246, 0.45)',
        'glow-good': '0 0 24px -4px rgba(52, 211, 153, 0.4)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.4s ease-out both',
        shimmer: 'shimmer 1.6s infinite',
      },
    },
  },
  plugins: [],
};
