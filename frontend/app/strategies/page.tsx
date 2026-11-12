"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  GitBranch,
  Plus,
  Save,
  Trash2,
  Edit,
  ChevronDown,
  Settings,
  AlertCircle,
  CheckCircle,
  Layers,
  Zap,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight,
  ArrowLeft,
  X,
  ShieldAlert,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

interface StrategyCondition {
  id: string;
  indicator1: string;
  condition: string;
  indicator2: string;
  value?: number;
}

interface Strategy {
  id: string;
  name: string;
  description: string;
  conditions: StrategyCondition[];
  stopLoss: number;
  target: number;
  timeframe: string;
  isActive: boolean;
  createdAt: string;
}

const INDICATORS = ["EMA", "RSI", "Supertrend", "MACD", "VWAP", "Bollinger Bands", "ATR", "ADX"];
const CONDITIONS = [">", "<", ">=", "<=", "Crossover Up", "Crossover Down", "Crosses Above", "Crosses Below"];
const TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"];

const MOCK_STRATEGIES: Strategy[] = [
  {
    id: "1",
    name: "NIFTY Momentum Breakout",
    description: "EMA Crossover + RSI Momentum on 15m timeframe",
    conditions: [
      { id: "1", indicator1: "EMA(9)", condition: "Crossover Up", indicator2: "EMA(21)" },
      { id: "2", indicator1: "RSI(14)", condition: ">", indicator2: "50" },
    ],
    stopLoss: 1.5,
    target: 3.0,
    timeframe: "15m",
    isActive: true,
    createdAt: "2024-11-10",
  },
  {
    id: "2",
    name: "BANKNIFTY Mean Reversion",
    description: "Bollinger Band squeeze + RSI oversold",
    conditions: [
      { id: "3", indicator1: "Price", condition: "Crosses Below", indicator2: "Lower BB" },
      { id: "4", indicator1: "RSI(14)", condition: "<", indicator2: "30" },
    ],
    stopLoss: 2.0,
    target: 2.5,
    timeframe: "5m",
    isActive: false,
    createdAt: "2024-11-08",
  },
];

export default function StrategiesPage() {
  const [strategies] = useState<Strategy[]>(MOCK_STRATEGIES);
  const [showBuilder, setShowBuilder] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null);

  const [form, setForm] = useState({
    name: "",
    description: "",
    conditions: [{ id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }] as StrategyCondition[],
    stopLoss: 1.5,
    target: 3.0,
    timeframe: "15m",
  });

  const addCondition = () => {
    setForm((prev) => ({
      ...prev,
      conditions: [...prev.conditions, { id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }],
    }));
  };

  const removeCondition = (id: string) => {
    if (form.conditions.length <= 1) return;
    setForm((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((c) => c.id !== id),
    }));
  };

  const updateCondition = (id: string, field: keyof StrategyCondition, value: string) => {
    setForm((prev) => ({
      ...prev,
      conditions: prev.conditions.map((c) => (c.id === id ? { ...c, [field]: value } : c)),
    }));
  };

  const handleSave = () => {
    if (!form.name.trim()) {
      alert("Please enter a strategy name");
      return;
    }
    if (form.conditions.some((c) => !c.indicator1 || !c.condition || !c.indicator2)) {
      alert("Please fill all condition fields");
      return;
    }

    const newStrategy: Strategy = {
      id: editingStrategy?.id || Date.now().toString(),
      name: form.name,
      description: form.description,
      conditions: form.conditions,
      stopLoss: form.stopLoss,
      target: form.target,
      timeframe: form.timeframe,
      isActive: false,
      createdAt: new Date().toISOString().split("T")[0],
    };

    if (editingStrategy) {
      // Update existing
    } else {
      // Add new
    }

    setShowBuilder(false);
    setEditingStrategy(null);
    setForm({
      name: "",
      description: "",
      conditions: [{ id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }],
      stopLoss: 1.5,
      target: 3.0,
      timeframe: "15m",
    });
  };

  const handleEdit = (strategy: Strategy) => {
    setEditingStrategy(strategy);
    setForm({
      name: strategy.name,
      description: strategy.description,
      conditions: strategy.conditions.map((c) => ({ ...c })),
      stopLoss: strategy.stopLoss,
      target: strategy.target,
      timeframe: strategy.timeframe,
    });
    setShowBuilder(true);
  };

  const handleDelete = (id: string) => {
    if (confirm("Delete this strategy?")) {
      // Delete logic
    }
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-7xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <GitBranch className="w-8 h-8 text-neon-purple drop-shadow-[0_0_10px_rgba(168,85,247,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Strategy Builder</h1>
                <p className="text-text-secondary">Create and manage algorithmic trading strategies</p>
              </div>
            </div>
            <motion.button
              onClick={() => { setEditingStrategy(null); setForm({ name: "", description: "", conditions: [{ id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }], stopLoss: 1.5, target: 3.0, timeframe: "15m" }); setShowBuilder(true); }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-medium hover:opacity-90 transition-opacity shadow-glow-purple"
            >
              <Plus className="w-4 h-4" strokeWidth={2.5} />
              <span>New Strategy</span>
            </motion.button>
          </motion.div>

          {/* Strategy Builder Modal/Panel */}
          {showBuilder && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
              onClick={() => { setShowBuilder(false); setEditingStrategy(null); }}
            >
              <motion.div
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-4xl max-h-[90vh] overflow-y-auto glass rounded-2xl border border-glow-border p-6"
              >
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-white">{editingStrategy ? "Edit Strategy" : "Create New Strategy"}</h2>
                  <motion.button
                    onClick={() => { setShowBuilder(false); setEditingStrategy(null); }}
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    className="p-2 rounded-lg bg-card-bg/50 border border-glow-border text-text-muted hover:bg-card-bg hover:text-white transition-colors"
                  >
                    <X className="w-5 h-5" strokeWidth={2} />
                  </motion.button>
                </div>

                <div className="space-y-6">
                  {/* Basic Info */}
                  <div className="p-4 rounded-xl bg-card-bg/50 border border-glow-border">
                    <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
                      <Settings className="w-4 h-4 text-neon-cyan" strokeWidth={2.5} />
                      Basic Information
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Strategy Name</label>
                        <input
                          type="text"
                          value={form.name}
                          onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                          placeholder="e.g., NIFTY Momentum Breakout"
                          className="w-full pl-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Timeframe</label>
                        <select
                          value={form.timeframe}
                          onChange={(e) => setForm((prev) => ({ ...prev, timeframe: e.target.value }))}
                          className="w-full pl-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white"
                        >
                          {TIMEFRAMES.map((tf) => (
                            <option key={tf} value={tf}>{tf}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="mt-4">
                      <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Description</label>
                      <textarea
                        value={form.description}
                        onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                        placeholder="Brief description of the strategy logic..."
                        rows={3}
                        className="w-full pl-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white"
                      />
                    </div>
                  </div>

                  {/* Entry Conditions */}
                  <div className="p-4 rounded-xl bg-card-bg/50 border border-glow-border">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-medium text-white flex items-center gap-2">
                        <Layers className="w-4 h-4 text-neon-purple" strokeWidth={2.5} />
                        Entry Conditions
                      </h3>
                      <motion.button
                        onClick={addCondition}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-neon-purple/10 border border-neon-purple/30 text-neon-purple rounded-lg hover:bg-neon-purple/20 transition-colors"
                      >
                        <Plus className="w-3 h-3" strokeWidth={2.5} />
                        Add Condition
                      </motion.button>
                    </div>

                    <div className="space-y-3">
                      {form.conditions.map((condition, index) => (
                        <motion.div
                          key={condition.id}
                          initial={{ opacity: 0, x: -20 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05 }}
                          className="flex flex-col md:flex-row items-start md:items-center gap-3 p-3 rounded-lg bg-true-black border border-glow-border/50"
                        >
                          <select
                            value={condition.indicator1}
                            onChange={(e) => updateCondition(condition.id, "indicator1", e.target.value)}
                            className="flex-1 min-w-[140px] pl-3 py-2 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white text-sm"
                          >
                            {INDICATORS.map((ind) => (
                              <option key={ind} value={ind}>{ind}</option>
                            ))}
                          </select>

                          <select
                            value={condition.condition}
                            onChange={(e) => updateCondition(condition.id, "condition", e.target.value)}
                            className="flex-1 min-w-[140px] pl-3 py-2 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white text-sm"
                          >
                            {CONDITIONS.map((cond) => (
                              <option key={cond} value={cond}>{cond}</option>
                            ))}
                          </select>

                          <select
                            value={condition.indicator2}
                            onChange={(e) => updateCondition(condition.id, "indicator2", e.target.value)}
                            className="flex-1 min-w-[140px] pl-3 py-2 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white text-sm"
                          >
                            {INDICATORS.map((ind) => (
                              <option key={ind} value={ind}>{ind}</option>
                            ))}
                            {["50", "30", "70", "20", "80"].map((val) => (
                              <option key={val} value={val}>{val}</option>
                            ))}
                          </select>

                          {form.conditions.length > 1 && (
                            <motion.button
                              onClick={() => removeCondition(condition.id)}
                              whileHover={{ scale: 1.1 }}
                              whileTap={{ scale: 0.9 }}
                              className="p-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red hover:bg-neon-red/20 transition-colors"
                              title="Remove Condition"
                            >
                              <Trash2 className="w-4 h-4" strokeWidth={2.5} />
                            </motion.button>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  </div>

                  {/* Risk Management */}
                  <div className="p-4 rounded-xl bg-card-bg/50 border border-glow-border">
                    <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-neon-orange" strokeWidth={2.5} />
                      Risk Management
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Stop Loss (%)</label>
                        <input
                          type="number"
                          step="0.1"
                          min="0.1"
                          max="10"
                          value={form.stopLoss}
                          onChange={(e) => setForm((prev) => ({ ...prev, stopLoss: parseFloat(e.target.value) }))}
                          className="w-full pl-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-red focus:outline-none rounded-lg text-white"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Target (%)</label>
                        <input
                          type="number"
                          step="0.1"
                          min="0.1"
                          max="20"
                          value={form.target}
                          onChange={(e) => setForm((prev) => ({ ...prev, target: parseFloat(e.target.value) }))}
                          className="w-full pl-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-green focus:outline-none rounded-lg text-white"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-text-muted mt-3">Risk:Reward ratio = 1:{((form.target / form.stopLoss).toFixed(2))}</p>
                  </div>

                  {/* Save Button */}
                  <div className="flex justify-end gap-3 pt-4 border-t border-glow-border">
                    <motion.button
                      onClick={() => { setShowBuilder(false); setEditingStrategy(null); }}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="px-6 py-2.5 rounded-xl bg-card-bg/50 border border-glow-border text-text-secondary hover:bg-card-bg hover:text-white transition-colors"
                    >
                      Cancel
                    </motion.button>
                    <motion.button
                      onClick={handleSave}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold hover:opacity-90 transition-opacity shadow-glow-green"
                    >
                      <Save className="w-4 h-4" strokeWidth={2.5} />
                      <span>{editingStrategy ? "Update Strategy" : "Save Strategy"}</span>
                    </motion.button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}

          {/* Strategy Library */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass rounded-2xl border border-glow-border overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-glow-border bg-card-bg/50 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Strategy Library</h2>
              <span className="text-xs px-2 py-0.5 rounded bg-neon-purple/20 text-neon-purple font-medium">{strategies.length} strategies</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                    <th className="px-5 py-4 text-left">Name</th>
                    <th className="px-5 py-4 text-left">Description</th>
                    <th className="px-5 py-4 text-center">Conditions</th>
                    <th className="px-5 py-4 text-center">Timeframe</th>
                    <th className="px-5 py-4 text-center">SL / TP</th>
                    <th className="px-5 py-4 text-center">Status</th>
                    <th className="px-5 py-4 text-center">Created</th>
                    <th className="px-5 py-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {strategies.map((strategy, index) => (
                    <motion.tr
                      key={strategy.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.03 }}
                      className="border-b border-glow-border/50 hover:bg-card-bg/30 transition-colors"
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-neon-purple/20 flex items-center justify-center">
                            <Zap className="w-4 h-4 text-neon-purple" strokeWidth={2.5} />
                          </div>
                          <div>
                            <p className="font-medium text-white">{strategy.name}</p>
                            <p className="text-xs text-text-muted">{strategy.conditions.length} condition{strategy.conditions.length > 1 ? "s" : ""}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-text-secondary text-sm max-w-xs truncate">{strategy.description}</td>
                      <td className="px-5 py-4 text-center text-sm font-mono text-text-muted">{strategy.conditions.length}</td>
                      <td className="px-5 py-4 text-center font-mono text-white">{strategy.timeframe}</td>
                      <td className="px-5 py-4 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-red/20 text-neon-red font-mono">SL {strategy.stopLoss}%</span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-green/20 text-neon-green font-mono">TP {strategy.target}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-center">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${strategy.isActive ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : "bg-neon-red/20 text-neon-red border border-neon-red/30"}`}>
                          {strategy.isActive ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-center font-mono text-text-secondary">{strategy.createdAt}</td>
                      <td className="px-5 py-4 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <motion.button
                            onClick={() => handleEdit(strategy)}
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            className="p-2 rounded-lg bg-neon-cyan/10 border border-neon-cyan/30 text-neon-cyan hover:bg-neon-cyan/20 transition-colors"
                            title="Edit Strategy"
                          >
                            <Edit className="w-4 h-4" strokeWidth={2.5} />
                          </motion.button>
                          <motion.button
                            onClick={() => handleDelete(strategy.id)}
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            className="p-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red hover:bg-neon-red/20 transition-colors"
                            title="Delete Strategy"
                          >
                            <Trash2 className="w-4 h-4" strokeWidth={2.5} />
                          </motion.button>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>

            {strategies.length === 0 && (
              <div className="flex flex-col items-center justify-center h-64 text-center px-6">
                <GitBranch className="w-16 h-16 text-text-muted mb-4" strokeWidth={1.5} />
                <h3 className="text-lg font-semibold text-white mb-2">No Strategies Yet</h3>
                <p className="text-text-secondary mb-4">Create your first algorithmic strategy</p>
                <motion.button
                  onClick={() => { setEditingStrategy(null); setForm({ name: "", description: "", conditions: [{ id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }], stopLoss: 1.5, target: 3.0, timeframe: "15m" }); setShowBuilder(true); }}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-medium hover:opacity-90 transition-opacity"
                >
                  <Plus className="w-4 h-4" strokeWidth={2.5} />
                  Create Strategy
                </motion.button>
              </div>
            )}
          </motion.div>
        </main>
      </div>
    </div>
  );
}