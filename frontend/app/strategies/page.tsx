"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { GitBranch, Plus, Save, Trash2, Edit, Settings, Layers, Zap, X, ShieldAlert, AlertCircle, Loader2 } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useStrategies, useIndicatorLibrary } from "@/lib/hooks";

const TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"];


export default function StrategiesPage() {
  const { strategies, isLoading, isError, error, mutate } = useStrategies();
  const { indicators, categories, isLoading: indicatorsIsLoading, error: indicatorsError, mutate: mutateIndicators } = useIndicatorLibrary({ q: "all" });
  const [showBuilder, setShowBuilder] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<any | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState({
    name: "", description: "",
    conditions: [],
    stopLoss: 1.5, target: 3.0, timeframe: "15m",
  });

  // Map indicator registry into searchable options
  const indicatorOptions = indicators.map((ind: any) => ({
    id: ind.id,
    name: ind.name || ind.id,
    category: ind.category || "advanced",
  }));

  const categoryMap = categories || {
    trend: "Trend",
    momentum: "Momentum",
    volatility: "Volatility",
    volume: "Volume",
    levels: "Support & Resistance",
    structure: "Market Structure",
    statistics: "Advanced & Statistical",
    options: "Options & Derivatives",
  };

  const addCondition = () => setForm((prev) => ({
    ...prev, conditions: [...prev.conditions, { id: Date.now().toString(), indicator1: indicatorOptions[0]?.id || "EMA", condition: ">", indicator2: indicatorOptions[1]?.id || "RSI" }],
  }));

  const removeCondition = (id: string) => {
    if (form.conditions.length <= 1) return;
    setForm((prev) => ({ ...prev, conditions: prev.conditions.filter((c: any) => c.id !== id) }));
  };

  const updateCondition = (id: string, field: string, value: string) => {
    setForm((prev) => ({ ...prev, conditions: prev.conditions.map((c: any) => (c.id === id ? { ...c, [field]: value } : c)) }));
  };

  const handleSave = async () => {
    if (!form.name.trim()) { alert("Please enter a strategy name"); return; }
    if (form.conditions.some((c: any) => !c.indicator1 || !c.condition || !c.indicator2)) { alert("Please fill all condition fields"); return; }
    setIsSaving(true);
    try {
      await fetch("/api/v1/strategies", {
        method: editingStrategy ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: editingStrategy?.id || null, name: form.name, description: form.description, conditions: form.conditions, stopLoss: form.stopLoss, target: form.target, timeframe: form.timeframe, isActive: editingStrategy?.isActive || false }),
      });
      await mutate();
      setShowBuilder(false); setEditingStrategy(null);
      setForm({ name: "", description: "", conditions: [{ id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }], stopLoss: 1.5, target: 3.0, timeframe: "15m" });
    } catch (err) { console.error(err); alert("Failed to save strategy"); }
    finally { setIsSaving(false); }
  };

  const handleEdit = (s: any) => {
    setEditingStrategy(s);
    setForm({ name: s.name, description: s.description || "", conditions: (s.conditions || []).map((c: any) => ({ ...c })), stopLoss: s.stopLoss || 1.5, target: s.target || 3.0, timeframe: s.timeframe || "15m" });
    setShowBuilder(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this strategy?")) return;
    try { await fetch("/api/v1/strategies", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }) }); await mutate(); }
    catch (err) { console.error(err); alert("Failed to delete strategy"); }
  };

  const handleToggle = async (s: any) => {
    try { await fetch("/api/v1/strategies", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...s, isActive: !s.isActive }) }); await mutate(); }
    catch (err) { console.error(err); }
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-7xl mx-auto w-full">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <GitBranch className="w-8 h-8 text-neon-purple" strokeWidth={2.5} />
              <div><h1 className="text-2xl md:text-3xl font-bold text-white">Strategy Builder</h1><p className="text-text-secondary">Create and manage algorithmic trading strategies</p></div>
            </div>
            <button onClick={() => { setEditingStrategy(null); setForm({ name: "", description: "", conditions: [{ id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }], stopLoss: 1.5, target: 3.0, timeframe: "15m" }); setShowBuilder(true); }} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-medium">
              <Plus className="w-4 h-4" />New Strategy
            </button>
          </div>

          {showBuilder && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => { setShowBuilder(false); setEditingStrategy(null); }}>
              <div onClick={(e) => e.stopPropagation()} className="w-full max-w-4xl max-h-[90vh] overflow-y-auto glass rounded-2xl border border-glow-border p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-white">{editingStrategy ? "Edit Strategy" : "Create New Strategy"}</h2>
                  <button onClick={() => { setShowBuilder(false); setEditingStrategy(null); }} className="p-2 rounded-lg bg-card-bg/50 border border-glow-border text-text-muted hover:text-white"><X className="w-5 h-5" /></button>
                </div>
                <div className="space-y-6">
                  <div className="p-4 rounded-xl bg-card-bg/50 border border-glow-border">
                    <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2"><Settings className="w-4 h-4 text-neon-cyan" />Basic Information</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div><label className="text-xs text-text-muted uppercase block mb-1">Strategy Name</label><input type="text" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} placeholder="e.g., NIFTY Momentum Breakout" className="w-full pl-4 py-2.5 bg-true-black border border-glow-border rounded-lg text-white" /></div>
                      <div><label className="text-xs text-text-muted uppercase block mb-1">Timeframe</label><select value={form.timeframe} onChange={(e) => setForm((p) => ({ ...p, timeframe: e.target.value }))} className="w-full pl-4 py-2.5 bg-true-black border border-glow-border rounded-lg text-white">{TIMEFRAMES.map((tf) => (<option key={tf} value={tf}>{tf}</option>))}</select></div>
                    </div>
                    <div className="mt-4"><label className="text-xs text-text-muted uppercase block mb-1">Description</label><textarea value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} rows={3} className="w-full pl-4 py-2.5 bg-true-black border border-glow-border rounded-lg text-white" /></div>
                  </div>
                  <div className="p-4 rounded-xl bg-card-bg/50 border border-glow-border">
                    <div className="flex items-center justify-between mb-4"><h3 className="text-sm font-medium text-white flex items-center gap-2"><Layers className="w-4 h-4 text-neon-purple" />Entry Conditions</h3><button onClick={addCondition} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-neon-purple/10 border border-neon-purple/30 text-neon-purple rounded-lg"><Plus className="w-3 h-3" />Add Condition</button></div>
                    <div className="space-y-3">{form.conditions.map((condition: any) => (
                      <div key={condition.id} className="flex flex-col md:flex-row items-start md:items-center gap-3 p-3 rounded-lg bg-true-black border border-glow-border/50">
                        <select value={condition.indicator1} onChange={(e) => updateCondition(condition.id, "indicator1", e.target.value)} className="flex-1 min-w-[140px] pl-3 py-2 bg-true-black border border-glow-border rounded-lg text-white text-sm">{INDICATORS.map((ind) => (<option key={ind} value={ind}>{ind}</option>))}</select>
                        <select value={condition.condition} onChange={(e) => updateCondition(condition.id, "condition", e.target.value)} className="flex-1 min-w-[140px] pl-3 py-2 bg-true-black border border-glow-border rounded-lg text-white text-sm">{CONDITIONS.map((c) => (<option key={c} value={c}>{c}</option>))}</select>
                        <select value={condition.indicator2} onChange={(e) => updateCondition(condition.id, "indicator2", e.target.value)} className="flex-1 min-w-[140px] pl-3 py-2 bg-true-black border border-glow-border rounded-lg text-white text-sm">{INDICATORS.map((ind) => (<option key={ind} value={ind}>{ind}</option>))}{["50", "30", "70", "20", "80"].map((v) => (<option key={v} value={v}>{v}</option>))}</select>
                        {form.conditions.length > 1 && (<button onClick={() => removeCondition(condition.id)} className="p-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red"><Trash2 className="w-4 h-4" /></button>)}
                      </div>
                    ))}</div>
                  </div>
                  <div className="p-4 rounded-xl bg-card-bg/50 border border-glow-border">
                    <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-neon-orange" />Risk Management</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div><label className="text-xs text-text-muted uppercase block mb-1">Stop Loss (%)</label><input type="number" step="0.1" value={form.stopLoss} onChange={(e) => setForm((p) => ({ ...p, stopLoss: parseFloat(e.target.value) }))} className="w-full pl-4 py-2.5 bg-true-black border border-glow-border rounded-lg text-white" /></div>
                      <div><label className="text-xs text-text-muted uppercase block mb-1">Target (%)</label><input type="number" step="0.1" value={form.target} onChange={(e) => setForm((p) => ({ ...p, target: parseFloat(e.target.value) }))} className="w-full pl-4 py-2.5 bg-true-black border border-glow-border rounded-lg text-white" /></div>
                    </div>
                    <p className="text-xs text-text-muted mt-3">Risk:Reward ratio = 1:{((form.target / form.stopLoss).toFixed(2))}</p>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-glow-border">
                    <button onClick={() => { setShowBuilder(false); setEditingStrategy(null); }} className="px-6 py-2.5 rounded-xl bg-card-bg/50 border border-glow-border text-text-secondary">Cancel</button>
                    <button onClick={handleSave} disabled={isSaving} className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold disabled:opacity-50">{isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}<span>{editingStrategy ? "Update Strategy" : "Save Strategy"}</span></button>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="glass rounded-2xl border border-glow-border overflow-hidden">
            <div className="px-4 md:px-6 py-4 border-b border-glow-border bg-card-bg/50 flex items-center justify-between flex-wrap gap-4">
              <h2 className="text-lg font-semibold text-white">Strategy Library</h2>
              <span className="text-xs px-2 py-0.5 rounded bg-neon-purple/20 text-neon-purple font-medium">{strategies.length} strategies</span>
            </div>
            {isLoading && <div className="flex items-center justify-center h-32"><Loader2 className="w-6 h-6 text-neon-cyan animate-spin" /><span className="ml-2 text-text-secondary">Loading strategies...</span></div>}
            {isError && <div className="flex items-center gap-2 p-4 text-neon-red"><AlertCircle className="w-5 h-5" /><span>Failed to load strategies: {error}</span></div>}
            {!isLoading && !isError && <div className="overflow-x-auto"><table className="min-w-[800px] w-full border-collapse" role="grid">
              <thead><tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                <th className="px-3 md:px-5 py-3 text-left">Name</th><th className="px-3 md:px-5 py-3 text-left">Description</th><th className="px-3 md:px-5 py-3 text-center">Timeframe</th><th className="px-3 md:px-5 py-3 text-center">SL / TP</th><th className="px-3 md:px-5 py-3 text-center">Status</th><th className="px-3 md:px-5 py-3 text-center">Actions</th>
              </tr></thead>
              <tbody>{strategies.map((s: any) => (
                <tr key={s.id} className="border-b border-glow-border/50 hover:bg-card-bg/30">
                  <td className="px-3 md:px-5 py-3"><div className="flex items-center gap-3"><div className="w-8 h-8 rounded-lg bg-neon-purple/20 flex items-center justify-center"><Zap className="w-4 h-4 text-neon-purple" /></div><div><p className="font-medium text-white">{s.name}</p><p className="text-xs text-text-muted">{(s.conditions || []).length} conditions</p></div></div></td>
                  <td className="px-3 md:px-5 py-3 text-text-secondary text-sm max-w-xs truncate">{s.description}</td>
                  <td className="px-3 md:px-5 py-3 text-center font-mono text-white">{s.timeframe}</td>
                  <td className="px-3 md:px-5 py-3 text-center"><div className="flex items-center justify-center gap-2"><span className="text-[10px] px-2 py-0.5 rounded bg-neon-red/20 text-neon-red">SL {s.stopLoss}%</span><span className="text-[10px] px-2 py-0.5 rounded bg-neon-green/20 text-neon-green">TP {s.target}%</span></div></td>
                  <td className="px-3 md:px-5 py-3 text-center"><button onClick={() => handleToggle(s)} className={`px-3 py-1 rounded-full text-xs font-medium ${s.isActive ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : "bg-neon-red/20 text-neon-red border border-neon-red/30"}`}>{s.isActive ? "Active" : "Inactive"}</button></td>
                  <td className="px-3 md:px-5 py-3 text-center"><div className="flex items-center justify-center gap-1"><button onClick={() => handleEdit(s)} className="p-2 rounded-lg bg-neon-cyan/10 border border-neon-cyan/30 text-neon-cyan"><Edit className="w-4 h-4" /></button><button onClick={() => handleDelete(s.id)} className="p-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red"><Trash2 className="w-4 h-4" /></button></div></td>
                </tr>
              ))}</tbody>
            </table></div>}
            {!isLoading && !isError && strategies.length === 0 && <div className="flex flex-col items-center justify-center h-64 text-center px-6"><GitBranch className="w-16 h-16 text-text-muted mb-4" /><h3 className="text-lg font-semibold text-white mb-2">No Strategies Yet</h3><p className="text-text-secondary mb-4">Create your first algorithmic strategy</p><button onClick={() => { setEditingStrategy(null); setForm({ name: "", description: "", conditions: [{ id: Date.now().toString(), indicator1: "EMA", condition: ">", indicator2: "EMA" }], stopLoss: 1.5, target: 3.0, timeframe: "15m" }); setShowBuilder(true); }} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-medium"><Plus className="w-4 h-4" />Create Strategy</button></div>}
          </div>
        </main>
      </div>
    </div>
  );
}
