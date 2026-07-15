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
    },
  },
  plugins: [],
}

export default config
