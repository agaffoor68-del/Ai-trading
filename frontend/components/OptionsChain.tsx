"use client";

import { motion } from "framer-motion";
import { Maximize2, Search, Filter } from "lucide-react";

interface OptionChainRow {
  strike: number;
  callLTP: number;
  callOI: number;
  callOIChange: number;
  putOI: number;
  putOIChange: number;
  putLTP: number;
  isATM: boolean;
}

const mockOptionChain: OptionChainRow[] = [
  { strike: 24200, callLTP: 245.50, callOI: 125400, callOIChange: 5.2, putOI: 98200, putOIChange: -2.1, putLTP: 85.30, isATM: false },
  { strike: 24250, callLTP: 198.20, callOI: 189600, callOIChange: 8.7, putOI: 112400, putOIChange: 1.5, putLTP: 108.60, isATM: false },
  { strike: 24300, callLTP: 156.75, callOI: 234800, callOIChange: 12.3, putOI: 145600, putOIChange: 3.8, putLTP: 138.40, isATM: false },
  { strike: 24350, callLTP: 120.40, callOI: 287900, callOIChange: 15.6, putOI: 178900, putOIChange: 5.2, putLTP: 175.20, isATM: true }, // ATM
  { strike: 24400, callLTP: 89.15, callOI: 312400, callOIChange: 18.9, putOI: 201300, putOIChange: 7.1, putLTP: 218.75, isATM: false },
  { strike: 24450, callLTP: 63.80, callOI: 298100, callOIChange: 14.2, putOI: 234500, putOIChange: 9.4, putLTP: 267.50, isATM: false },
  { strike: 24500, callLTP: 43.25, callOI: 256700, callOIChange: 10.8, putOI: 267800, putOIChange: 12.3, putLTP: 320.10, isATM: false },
  { strike: 24550, callLTP: 27.90, callOI: 198400, callOIChange: 6.5, putOI: 298100, putOIChange: 15.7, putLTP: 378.90, isATM: false },
  { strike: 24600, callLTP: 16.45, callOI: 145600, callOIChange: 3.2, putOI: 312400, putOIChange: 18.9, putLTP: 442.30, isATM: false },
];

export function OptionsChain() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white">Options Chain</h3>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">NIFTY</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">24 OCT</span>
        </div>
        <div className="flex items-center gap-2">
          <button className="p-1.5 rounded-lg bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-colors" title="Search strike">
            <Search className="w-4 h-4 text-text-secondary" strokeWidth={2} />
          </button>
          <button className="p-1.5 rounded-lg bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-colors" title="Filters">
            <Filter className="w-4 h-4 text-text-secondary" strokeWidth={2} />
          </button>
          <button className="p-1.5 rounded-lg bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-colors" title="Expand">
            <Maximize2 className="w-4 h-4 text-text-secondary" strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-x-auto overflow-y-auto p-2">
        <table className="w-full text-sm" role="grid">
          <thead>
            <tr className="border-b border-glow-border text-text-muted">
              <th className="px-2 py-2 text-left font-medium">Call LTP</th>
              <th className="px-2 py-2 text-right font-medium">Call OI</th>
              <th className="px-2 py-2 text-right font-medium">Δ OI</th>
              <th className="px-2 py-2 text-center font-medium w-20">STRIKE</th>
              <th className="px-2 py-2 text-right font-medium">Δ OI</th>
              <th className="px-2 py-2 text-right font-medium">Put OI</th>
              <th className="px-2 py-2 text-right font-medium">Put LTP</th>
            </tr>
          </thead>
          <tbody>
            {mockOptionChain.map((row, index) => (
              <motion.tr
                key={row.strike}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 + index * 0.04 }}
                className={`transition-colors ${row.isATM ? "bg-gradient-to-r from-neon-cyan/5 via-neon-yellow/5 to-transparent" : "hover:bg-card-bg"}`}
                style={row.isATM ? { boxShadow: "inset 0 0 0 1px rgba(0, 240, 255, 0.1)" } : undefined}
              >
                <td className="px-2 py-1.5 font-mono font-medium text-neon-green">{row.callLTP.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-right font-mono text-text-secondary">{row.callOI.toLocaleString()}</td>
                <td className={`px-2 py-1.5 text-right font-mono text-xs ${row.callOIChange >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {row.callOIChange >= 0 ? "+" : ""}{row.callOIChange.toFixed(1)}%
                </td>
                <td className={`px-2 py-1.5 text-center font-mono font-bold ${row.isATM ? "text-neon-cyan text-glow-cyan" : "text-white"}`}>
                  {row.strike.toLocaleString()}
                  {row.isATM && <span className="ml-1 text-[10px] bg-neon-cyan/20 text-neon-cyan px-1 rounded">ATM</span>}
                </td>
                <td className={`px-2 py-1.5 text-right font-mono text-xs ${row.putOIChange >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {row.putOIChange >= 0 ? "+" : ""}{row.putOIChange.toFixed(1)}%
                </td>
                <td className="px-2 py-1.5 text-right font-mono text-text-secondary">{row.putOI.toLocaleString()}</td>
                <td className="px-2 py-1.5 font-mono font-medium text-neon-red">{row.putLTP.toFixed(2)}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}