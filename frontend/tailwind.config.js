/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Chakra Petch"', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        ink: {
          950: '#080B11',
          900: '#0A0E14',
          850: '#0E131C',
          800: '#121826',
          700: '#161D2B',
          600: '#1C2536',
          500: '#232B3A',
        },
        gold: {
          300: '#FFD264',
          400: '#F2B12C',
          500: '#E9A114',
          600: '#C9860B',
        },
        volt: {
          400: '#38BDF8',
          500: '#0EA5E9',
        },
        chalk: '#E6EDF3',
        muted: '#8A99AD',
        danger: '#F04747',
        good: '#35C46B',
        // Back-compat alias so any leftover `gridiron-*` classes still resolve.
        gridiron: {
          400: '#F2B12C',
          500: '#F2B12C',
          600: '#E9A114',
          700: '#C9860B',
        },
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(242,177,44,0.4), 0 0 24px -6px rgba(242,177,44,0.35)',
      },
      keyframes: {
        clock: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(242,177,44,0.5)' },
          '50%': { boxShadow: '0 0 0 6px rgba(242,177,44,0)' },
        },
      },
      animation: {
        clock: 'clock 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
