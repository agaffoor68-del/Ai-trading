/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // True Black HDR/OLED
        'true-black': '#000000',
        'card-bg': '#0a0a0a',
        'card-border': '#1a1a1a',
        // Neon Accents
        'neon-cyan': '#00F0FF',
        'neon-green': '#00FF66',
        'neon-red': '#FF003C',
        'neon-purple': '#A855F7',
        'neon-orange': '#F97316',
        // Semantic
        'text-primary': '#FFFFFF',
        'text-secondary': '#888888',
        'text-muted': '#555555',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-gradient': 'linear-gradient(135deg, #1a0a2e 0%, #000000 100%)',
        'purple-gradient': 'linear-gradient(135deg, #2d1b4e 0%, #0a0a0a 100%)',
        'card-gradient': 'linear-gradient(135deg, #111111 0%, #0a0a0a 100%)',
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(0, 240, 255, 0.3), 0 0 40px rgba(0, 240, 255, 0.1)',
        'glow-green': '0 0 20px rgba(0, 255, 102, 0.3), 0 0 40px rgba(0, 255, 102, 0.1)',
        'glow-red': '0 0 20px rgba(255, 0, 60, 0.3), 0 0 40px rgba(255, 0, 60, 0.1)',
        'glow-purple': '0 0 20px rgba(168, 85, 247, 0.3), 0 0 40px rgba(168, 85, 247, 0.1)',
        'glow-orange': '0 0 20px rgba(249, 115, 22, 0.3), 0 0 40px rgba(249, 115, 22, 0.1)',
        'inner-glow': 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      },
      borderColor: {
        'glow-border': 'rgba(255, 255, 255, 0.06)',
        'glow-border-hover': 'rgba(0, 240, 255, 0.3)',
      },
    },
  },
  plugins: [],
};