"use client";

import { motion } from "framer-motion";

export function ChartPlaceholder() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-[300px] relative"
    >
      {/* Grid background */}
      <div className="absolute inset-0" style={{
        backgroundImage: `
          linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px'
      }} />
      
      {/* Mock candlesticks */}
      <div className="absolute inset-0 flex items-end justify-center p-4 pointer-events-none">
        {[45, 52, 48, 65, 58, 72, 68, 78, 74, 85, 82, 90, 88, 95, 92, 88, 92, 96, 94, 100].map((h, i) => (
          <motion.div
            key={i}
            initial={{ height: 0 }}
            animate={{ height: `${h}%` }}
            transition={{ type: "spring", stiffness: 100, damping: 15, delay: i * 0.05 }}
            className="w-6 rounded-t transition-colors"
            style={{
              background: h > 70 
                ? "linear-gradient(to top, #00FF66, #00F0FF)" 
                : "linear-gradient(to top, #FF003C, #F97316)",
              boxShadow: h > 70 
                ? "0 0 10px rgba(0, 255, 102, 0.5)" 
                : "0 0 10px rgba(255, 0, 60, 0.5)",
            }}
          />
        ))}
      </div>

      {/* Overlay info */}
      <div className="absolute inset-0 p-4 flex flex-col justify-between pointer-events-none">
        <div className="flex justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">NIFTY</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">15m</span>
          </div>
          <div className="flex items-center gap-2 text-text-muted text-sm">
            <span>24,345.85</span>
            <span className="text-neon-green">+0.51%</span>
          </div>
        </div>
        <div className="flex justify-between items-end">
          <div className="flex gap-1">
            {["1m", "5m", "15m", "1H", "4H", "1D"].map((tf) => (
              <button key={tf} className="px-2 py-1 text-[10px] rounded bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-text-secondary hover:text-white transition-colors">
                {tf}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button className="p-1.5 rounded-lg bg-card-bg/80 border border-glow-border hover:border-neon-cyan/50 backdrop-blur" title="Indicators">
              <svg className="w-4 h-4 text-text-secondary" strokeWidth={2} fill="none" viewBox="0 0 24 24"><path stroke="currentColor" d="M3 3h18v18H3z"/><path stroke="currentColor" d="M9 9h6v6H9z"/></svg>
            </button>
            <button className="p-1.5 rounded-lg bg-card-bg/80 border border-glow-border hover:border-neon-cyan/50 backdrop-blur" title="Settings">
              <svg className="w-4 h-4 text-text-secondary" strokeWidth={2} fill="none" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path stroke="currentColor" d="M12 1v2M12 21v2M1 12h2M21 12h2"/></svg>
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}