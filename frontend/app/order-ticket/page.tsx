"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ShieldCheck,
  AlertCircle,
  ChevronRight,
  Plus,
  Minus,
  ArrowUpRight,
  ArrowDownRight,
  DollarSign,
  Layers,
  ShieldAlert,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const SYMBOLS = ["NIFTY 50", "BANKNIFTY", "SENSEX"];
const STRIKES = ["ATM", "ITM-1", "ITM-2", "OTM-1", "OTM-2"];
const EXPIRIES = ["26 Nov 2026", "03 Dec 2026", "10 Dec 2026", "24 Dec 2026"];

interface OrderForm {
  mode: "PAPER" | "LIVE";
  tradeType: "BUY" | "SELL";
  symbol: string;
  optionType: "CE" | "PE";
  strike: string;
  expiry: string;
  orderType: "MARKET" | "LIMIT";
  quantity: number;
  price: string;
  stopLoss: string;
  target: string;
}

const INITIAL_FORM: OrderForm = {
  mode: "PAPER",
  tradeType: "BUY",
  symbol: "NIFTY 50",
  optionType: "CE",
  strike: "ATM",
  expiry: EXPIRIES[0],
  orderType: "MARKET",
  quantity: 1,
  price: "",
  stopLoss: "2",
  target: "4",
};

export default function OrderTicketPage() {
  const [form, setForm] = useState<OrderForm>(INITIAL_FORM);
  const [isExecuting, setIsExecuting] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const spotPrice = form.symbol === "NIFTY 50" ? 24345 : form.symbol === "BANKNIFTY" ? 51890 : 79875;

  const estimatePremium = useCallback(() => {
    const base = form.optionType === "CE" ? 150 : 120;
    const strikePremium = form.strike === "ATM" ? base : form.strike === "ITM-1" ? base * 1.5 : base * 0.7;
    return Math.round(strikePremium * form.quantity * 50);
  }, [form.optionType, form.strike, form.quantity]);

  const marginRequired = useCallback(() => Math.round(estimatePremium() * 1.2), [estimatePremium]);
  const estimatedCharges = useCallback(() => Math.round(estimatePremium() * 0.001), [estimatePremium]);
  const totalPremium = useCallback(() => estimatePremium(), [estimatePremium]);

  const handleExecute = () => {
    setIsExecuting(true);
    setToast({
      message: `Order Placed Successfully (${form.mode} Mode)`,
      type: "success",
    });
    setTimeout(() => {
      setIsExecuting(false);
    }, 1500);
  };

  const toggleMode = () => setForm((prev) => ({ ...prev, mode: prev.mode === "PAPER" ? "LIVE" : "PAPER" }));
  const toggleTrade = () => setForm((prev) => ({ ...prev, tradeType: prev.tradeType === "BUY" ? "SELL" : "BUY" }));
  const toggleOption = () => setForm((prev) => ({ ...prev, optionType: prev.optionType === "CE" ? "PE" : "CE" }));
  const toggleOrderType = () =>
    setForm((prev) => ({ ...prev, orderType: prev.orderType === "MARKET" ? "LIMIT" : "MARKET", price: prev.orderType === "MARKET" ? "" : prev.price }));

  const incrementQty = () => setForm((prev) => ({ ...prev, quantity: prev.quantity + 1 }));
  const decrementQty = () => setForm((prev) => ({ ...prev, quantity: Math.max(1, prev.quantity - 1) }));

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24">
          {/* Page Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <Activity className="w-8 h-8 text-neon-cyan drop-shadow-[0_0_10px_rgba(0,240,255,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Order Execution</h1>
                <p className="text-text-secondary">Institutional-grade order entry with risk preview</p>
              </div>
            </div>
            <RefreshCw className="w-6 h-6 text-text-muted" strokeWidth={2.5} />
          </div>

          {/* Toast Notification */}
          {toast && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className={`fixed top-6 right-6 px-6 py-4 rounded-xl border text-white font-medium z-50 shadow-lg ${
                toast.type === "success"
                  ? "bg-neon-green/20 border-neon-green/50 text-neon-green shadow-[0_0_20px_rgba(0,255,102,0.3)]"
                  : "bg-neon-red/20 border-neon-red/50 text-neon-red shadow-[0_0_20px_rgba(255,0,60,0.3)]"
              }`}
            >
              <div className="flex items-center gap-2">
                {toast.type === "success" ? (
                  <ShieldCheck className="w-5 h-5" strokeWidth={2.5} />
                ) : (
                  <AlertCircle className="w-5 h-5" strokeWidth={2.5} />
                )}
                <span>{toast.message}</span>
              </div>
            </motion.div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Order Form */}
            <div className="lg:col-span-7 space-y-6">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass rounded-2xl border border-glow-border p-6"
              >
                {/* Mode & Trade Type */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="flex items-center gap-3 px-4 py-3 rounded-xl border bg-card-bg/50">
                    <button
                      onClick={toggleMode}
                      className={`flex items-center gap-2 flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
                        form.mode === "PAPER"
                          ? "bg-neon-cyan/10 border-neon-cyan/30 text-neon-cyan"
                          : "border-glow-border text-text-secondary"
                      }`}
                    >
                      PAPER
                    </button>
                    <button
                      onClick={toggleMode}
                      className={`flex items-center gap-2 flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
                        form.mode === "LIVE"
                          ? "bg-neon-red/10 border-neon-red/30 text-neon-red"
                          : "border-glow-border text-text-secondary"
                      }`}
                    >
                      LIVE
                    </button>
                  </div>
                  <div className="flex items-center gap-3 px-4 py-3 rounded-xl border bg-card-bg/50">
                    <button
                      onClick={toggleTrade}
                      className={`flex items-center gap-2 flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
                        form.tradeType === "BUY"
                          ? "bg-neon-green/10 border-neon-green/30 text-neon-green"
                          : "border-glow-border text-text-secondary"
                      }`}
                    >
                      <ArrowUpRight className="w-3 h-3" strokeWidth={2} />
                      BUY
                    </button>
                    <button
                      onClick={toggleTrade}
                      className={`flex items-center gap-2 flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
                        form.tradeType === "SELL"
                          ? "bg-neon-red/10 border-neon-red/30 text-neon-red"
                          : "border-glow-border text-text-secondary"
                      }`}
                    >
                      <ArrowDownRight className="w-3 h-3" strokeWidth={2} />
                      SELL
                    </button>
                  </div>
                </div>

                <div className="space-y-4">
                  {/* Symbol */}
                  <div>
                    <label className="text-[10px] text-text-muted uppercase tracking-wider block mb-2">Symbol / Index</label>
                    <select
                      value={form.symbol}
                      onChange={(e) => setForm((prev) => ({ ...prev, symbol: e.target.value }))}
                      className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                    >
                      {SYMBOLS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                    <ChevronRight className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                  </div>

                  {/* Option Type */}
                  <div className="flex items-center gap-3 px-4 py-3 rounded-xl border bg-card-bg/50">
                    <button
                      onClick={toggleOption}
                      className={`flex items-center gap-2 flex-1 py-2 text-xs font-bold transition-colors ${
                        form.optionType === "CE"
                          ? "bg-neon-green/10 border-neon-green/30 text-neon-green border"
                          : "text-text-secondary"
                      }`}
                    >
                      CE
                    </button>
                    <button
                      onClick={toggleOption}
                      className={`flex items-center gap-2 flex-1 py-2 text-xs font-bold transition-colors ${
                        form.optionType === "PE"
                          ? "bg-neon-red/10 border-neon-red/30 text-neon-red border"
                          : "text-text-secondary"
                      }`}
                    >
                      PE
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-[10px] text-text-muted uppercase tracking-wider block mb-2">Strike</label>
                      <select
                        value={form.strike}
                        onChange={(e) => setForm((prev) => ({ ...prev, strike: e.target.value }))}
                        className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                      >
                        {STRIKES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                      <ChevronRight className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                    </div>
                    <div>
                      <label className="text-[10px] text-text-muted uppercase tracking-wider block mb-2">Expiry</label>
                      <select
                        value={form.expiry}
                        onChange={(e) => setForm((prev) => ({ ...prev, expiry: e.target.value }))}
                        className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                      >
                        {EXPIRIES.map((e) => (
                          <option key={e} value={e}>
                            {e}
                          </option>
                        ))}
                      </select>
                      <ChevronRight className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                    </div>
                  </div>

                  {/* Order Type */}
                  <div className="flex items-center gap-3 px-4 py-3 rounded-xl border bg-card-bg/50">
                    <button
                      onClick={toggleOrderType}
                      className={`flex items-center gap-2 flex-1 py-2 text-xs font-bold transition-colors ${
                        form.orderType === "MARKET"
                          ? "bg-neon-cyan/10 border-neon-cyan/30 text-neon-cyan border"
                          : "text-text-secondary"
                      }`}
                    >
                      Market
                    </button>
                    <button
                      onClick={toggleOrderType}
                      className={`flex items-center gap-2 flex-1 py-2 text-xs font-bold transition-colors ${
                        form.orderType === "LIMIT"
                          ? "bg-neon-orange/10 border-neon-orange/30 text-neon-orange border"
                          : "text-text-secondary"
                      }`}
                    >
                      Limit
                    </button>
                  </div>

                  {/* Quantity */}
                  <div className="flex items-center gap-3">
                    <label className="text-[10px] text-text-muted uppercase tracking-wider">Quantity (Lots)</label>
                    <button
                      onClick={decrementQty}
                      disabled={form.quantity <= 1}
                      className="w-8 h-8 rounded-lg border border-glow-border bg-card-bg/50 text-xs font-bold flex items-center justify-center disabled:opacity-50 transition-colors"
                    >
                      <Minus className="w-3 h-3" strokeWidth={2} />
                    </button>
                    <span className="w-10 text-center font-mono font-bold text-white">{form.quantity}</span>
                    <button
                      onClick={incrementQty}
                      className="w-8 h-8 rounded-lg border border-glow-border bg-card-bg/50 text-xs font-bold flex items-center justify-center transition-colors"
                    >
                      <Plus className="w-3 h-3" strokeWidth={2} />
                    </button>
                  </div>

                  {/* Price */}
                  <div className="flex items-end gap-2">
                    <label className="text-[10px] text-text-muted uppercase tracking-wider">Price</label>
                    {form.orderType === "MARKET" && (
                      <span className="text-[10px] px-2 py-1 rounded bg-neon-red/10 text-neon-red">Market</span>
                    )}
                  </div>
                  <input
                    type="number"
                    step="0.05"
                    disabled={form.orderType === "MARKET"}
                    value={form.price}
                    onChange={(e) => setForm((prev) => ({ ...prev, price: e.target.value }))}
                    placeholder="0.00"
                    className={`w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base ${
                      form.orderType === "MARKET" ? "opacity-50 cursor-not-allowed" : ""
                    }`}
                  />

                  {/* Risk Management */}
                  <div className="pt-4 border-t border-glow-border">
                    <label className="text-[10px] text-text-muted uppercase tracking-wider block mb-3 flex items-center gap-2">
                      <ShieldAlert className="w-3 h-3 text-neon-purple" strokeWidth={2} />
                      Risk Management (%)
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex items-end gap-1">
                        <input
                          type="number"
                          step="0.1"
                          value={form.stopLoss}
                          onChange={(e) => setForm((prev) => ({ ...prev, stopLoss: e.target.value }))}
                          className="w-full pl-3 py-2 bg-card-bg border border-glow-border focus:border-neon-purple focus:outline-none rounded-lg text-white text-sm"
                          placeholder="SL %"
                        />
                        <span className="text-[10px] text-text-muted">%</span>
                      </div>
                      <div className="flex items-end gap-1">
                        <input
                          type="number"
                          step="0.1"
                          value={form.target}
                          onChange={(e) => setForm((prev) => ({ ...prev, target: e.target.value }))}
                          className="w-full pl-3 py-2 bg-card-bg border border-glow-border focus:border-neon-purple focus:outline-none rounded-lg text-white text-sm"
                          placeholder="TP %"
                        />
                        <span className="text-[10px] text-text-muted">%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Order Summary */}
            <div className="lg:col-span-5 space-y-6">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="glass rounded-2xl border border-glow-border p-6"
              >
                <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                  <DollarSign className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                  Order Summary
                </h3>

                <div className="space-y-4">
                  <SummaryRow label="Margin Required" value={`₹${marginRequired().toLocaleString()}`} color="text-neon-cyan" />
                  <SummaryRow label="Estimated Charges" value={`₹${estimatedCharges().toLocaleString()}`} color="text-text-secondary" />
                  <SummaryRow label="Total Premium" value={`₹${totalPremium().toLocaleString()}`} color="text-neon-green" fontBold />
                </div>

                <div className="mt-6 p-4 rounded-xl bg-neon-green/10 border border-neon-green/20">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-text-muted">Product Type</span>
                    <span className="text-xs font-mono text-white">{form.mode === "PAPER" ? "PAPER" : "MIS"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">Lot Size</span>
                    <span className="text-xs font-mono text-white">50 × {form.quantity}</span>
                  </div>
                </div>

                <motion.button
                  onClick={handleExecute}
                  disabled={isExecuting}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className={`w-full py-4 rounded-xl font-bold text-xs tracking-wider uppercase transition-all duration-300 flex items-center justify-center gap-2 ${
                    isExecuting
                      ? "bg-card-bg/50 border border-glow-border text-text-muted disabled:cursor-not-allowed"
                      : "bg-gradient-to-r from-neon-green to-neon-cyan text-black shadow-[0_0_25px_rgba(0,255,102,0.4)] hover:shadow-[0_0_40px_rgba(0,255,102,0.6)]"
                  }`}
                >
                  {isExecuting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
                      Executing...
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="w-5 h-5" strokeWidth={2.5} />
                      EXECUTE ORDER
                    </>
                  )}
                  <ChevronRight className="w-4 h-4" strokeWidth={2.5} />
                </motion.button>

                <p className="text-[10px] text-text-muted text-center mt-3">
                  {form.mode === "PAPER" ? "Paper trading - no real funds at risk" : "Live trading - real funds at risk"}
                </p>
              </motion.div>

              {/* Quick Stats */}
              <div className="grid grid-cols-2 gap-4">
                <StatCard label="Spot Price" value={spotPrice.toLocaleString()} icon={Activity} color="text-neon-cyan" />
                <StatCard label="Premium/Lot" value={`₹${Math.round(estimatePremium() / form.quantity)}`} icon={Layers} color="text-neon-green" />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function Loader2({ className, strokeWidth }: { className?: string; strokeWidth?: number }) {
  return (
    <svg className={`animate-spin ${className}`} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth ?? 2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
      <circle cx="12" cy="12" r="4" />
    </svg>
  );
}

function SummaryRow({ label, value, color, fontBold }: { label: string; value: string; color: string; fontBold?: boolean }) {
  return (
    <div className="flex items-center justify-between px-4 py-2 rounded-lg bg-card-bg/30 border border-glow-border/50">
      <span className="text-xs text-text-muted">{label}</span>
      <span className={`text-sm font-mono ${color} ${fontBold ? "font-bold" : ""}`}>{value}</span>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: string; icon: React.ComponentType<{ className?: string; strokeWidth?: number }>; color: string }) {
  return (
    <div className="p-3 rounded-xl bg-card-bg/50 border border-glow-border">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] text-text-muted uppercase tracking-wider">{label}</p>
          <p className="text-sm font-mono font-bold text-white">{value}</p>
        </div>
        <Icon className="w-4 h-4" strokeWidth={2} style={{ color: "currentColor" }} />
      </div>
    </div>
  );
}
