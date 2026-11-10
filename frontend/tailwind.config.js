/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  safelist: ['border-emerald-500/30', 'border-blue-500/30', 'border-violet-500/30', 'border-orange-500/30', 'from-emerald-900/25', 'from-blue-900/25', 'from-violet-900/25', 'from-orange-900/25', 'bg-emerald-500/15', 'bg-blue-500/15', 'bg-violet-500/15', 'bg-orange-500/15', 'text-emerald-300', 'text-blue-300', 'text-violet-300', 'text-orange-300'],
  theme: { extend: {} },
  plugins: [],
};
