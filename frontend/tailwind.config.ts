import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        primary: '#000000',
        background: '#FFFFFF',
        border: '#E5E5E5',
        muted: '#F5F5F5',
        'muted-foreground': '#737373',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15,23,42,0.04), 0 12px 32px -12px rgba(15,23,42,0.10)',
        'card-hover': '0 2px 4px rgba(15,23,42,0.05), 0 18px 40px -12px rgba(79,70,229,0.20)',
        glow: '0 0 0 4px rgba(99,102,241,0.12)',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(14px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'pop-in': {
          '0%': { opacity: '0', transform: 'scale(0.6)' },
          '60%': { opacity: '1', transform: 'scale(1.08)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'draw-check': {
          from: { strokeDashoffset: '24' },
          to: { strokeDashoffset: '0' },
        },
        'confetti-fall': {
          '0%': { opacity: '1', transform: 'translate3d(0,0,0) rotate(0deg)' },
          '100%': { opacity: '0', transform: 'translate3d(var(--dx), var(--dy), 0) rotate(var(--rot))' },
        },
        'toast-in': {
          from: { opacity: '0', transform: 'translateY(16px) scale(0.96)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'pulse-ring': {
          '0%': { boxShadow: '0 0 0 0 rgba(99,102,241,0.45)' },
          '100%': { boxShadow: '0 0 0 14px rgba(99,102,241,0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.55s cubic-bezier(0.22,1,0.36,1) both',
        'pop-in': 'pop-in 0.5s cubic-bezier(0.34,1.56,0.64,1) both',
        float: 'float 5s ease-in-out infinite',
        shimmer: 'shimmer 2.4s linear infinite',
        'draw-check': 'draw-check 0.5s ease-out 0.15s both',
        'confetti-fall': 'confetti-fall 1.4s cubic-bezier(0.2,0.7,0.3,1) forwards',
        'toast-in': 'toast-in 0.4s cubic-bezier(0.22,1,0.36,1) both',
        'pulse-ring': 'pulse-ring 1.8s ease-out infinite',
      },
    },
  },
  plugins: [],
}

export default config
