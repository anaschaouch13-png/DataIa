/** @type {import('tailwindcss').Config} */

// Phase 6 — FOND BLANC : le frontend fourni était conçu en thème sombre avec la palette
// « slate » (bg-slate-950, text-slate-100...). Plutôt que de réécrire ~300 classes, on
// INVERSE l'échelle de gris : slate-950 devient presque blanc et slate-100 presque noir.
// Les contrastes du design d'origine sont ainsi conservés, mais sur fond clair.
const slateInverse = {
  50: '#0f172a',   // (était le plus clair) -> texte le plus foncé
  100: '#1e293b',
  200: '#334155',
  300: '#475569',
  400: '#64748b',
  500: '#64748b',
  600: '#94a3b8',
  700: '#cbd5e1',
  800: '#e2e8f0',
  850: '#eef2f6',
  900: '#f1f5f9',
  950: '#ffffff',  // (était le plus foncé) -> fond blanc
};

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        slate: slateInverse,
        brand: {
          cyan: '#00A8B5',
          blue: '#0A84E0',
          dark: '#ffffff',
          surface: '#f8fafc',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      keyframes: {
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '0.4', transform: 'scale(1)' },
          '50%': { opacity: '0.8', transform: 'scale(1.05)' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s infinite',
        glow: 'pulseGlow 4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
