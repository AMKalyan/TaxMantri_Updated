/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Design tokens — clean fintech, emerald accent
        brand: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          800: '#065f46',
          900: '#064e3b',
        },
        ink: '#0f172a',
        muted: '#475569',
        subtle: '#64748b',
        line: '#e2e8f0',
        surface: '#f8fafc',
        navy: {
          DEFAULT: '#1a3a5c',
          50: '#f0f5fb',
          100: '#d9e8f5',
          200: '#b3d0eb',
          300: '#7baed9',
          400: '#4487c3',
          500: '#2867a8',
          600: '#1a3a5c',
          700: '#162f4a',
          800: '#112438',
          900: '#0b1926',
        },
        amber: {
          DEFAULT: '#f59e0b',
        },
        success: {
          DEFAULT: '#16a34a',
          light: '#d5f5e3',
        },
        custom: {
          dark: '#1a1924',
          purple: '#8450f5', // Vibrant purple for the animated section
          green: '#2eac85', // Vibrant green block
          grayLight: '#f6f6f9',
          textDark: '#1a1a1a',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06)',
        lift: '0 4px 6px -1px rgba(15, 23, 42, 0.06), 0 12px 24px -6px rgba(15, 23, 42, 0.10)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
      maxWidth: {
        page: '72rem',
      },
      gridTemplateColumns: {
        'regime-left': '280px 1fr',
        'regime-right': '1fr 280px',
      },
    },
  },
  plugins: [],
}
