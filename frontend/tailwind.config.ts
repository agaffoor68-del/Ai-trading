import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "true-black": "#000000",
        "card-bg": "#0A0A0A",
        "neon-cyan": "#00F0FF",
        "neon-green": "#00FF66",
        "neon-red": "#FF003C",
        "neon-orange": "#FF7800",
        "neon-purple": "#A855F7",
        "neon-yellow": "#FFEB00",
        "text-muted": "#6B7280",
        "text-secondary": "#9CA3AF",
        "glow-border": "rgba(0, 240, 255, 0.15)",
        "glow-green": "rgba(0, 255, 102, 0.15)",
        "glow-red": "rgba(255, 0, 60, 0.15)",
        "glow-orange": "rgba(255, 120, 0, 0.15)",
        "glow-purple": "rgba(168, 85, 247, 0.15)",
      },
      boxShadow: {
        "glow-cyan": "0 0 20px rgba(0, 240, 255, 0.3), 0 0 40px rgba(0, 240, 255, 0.1)",
        "glow-green": "0 0 20px rgba(0, 255, 102, 0.3), 0 0 40px rgba(0, 255, 102, 0.1)",
        "glow-red": "0 0 20px rgba(255, 0, 60, 0.3), 0 0 40px rgba(255, 0, 60, 0.1)",
        "glow-orange": "0 0 20px rgba(255, 120, 0, 0.3), 0 0 40px rgba(255, 120, 0, 0.1)",
        "glow-purple": "0 0 20px rgba(168, 85, 247, 0.3), 0 0 40px rgba(168, 85, 247, 0.1)",
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "spin-slow": "spin 3s linear infinite",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
    },
  },
  plugins: [],
};

export default config;