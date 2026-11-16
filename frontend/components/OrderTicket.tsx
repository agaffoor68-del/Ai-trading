"use client";

import { motion } from "framer-motion";
import { ShoppingBag, TrendingUp, Target, Shield, Radio, Check, AlertCircle, X, Maximize2, Loader2 } from "lucide-react";
import { useState, useCallback } from "react";
import { useCandles, useMarketQuotes, useMarketStatus, formatFyersSymbol } from "@/lib/hooks";
import { fetchWithTimeout } from "@/lib/api-client";

export function OrderTicket() {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [mode, setMode] = useState<"PAPER" | "LIVE">("PAPER");
  const [quantity, setQuantity] = useState(1);
  const [price, setPrice] = useState<string>("");
  const [stopLoss, setStopLoss] = useState<string>("");
  const [target, setTarget] = useState<string>("");
  const [selectedSymbol, setSelectedSymbol] = useState("NIFTY 50");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [selectedStrike, setSelectedStrike] = useState<number | null>(null);
  const [selectedOptionType, setSelectedOptionType] = useState<"CE" | "PE">("CE");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Get market status for live trading check
  const { status: marketStatus } = useMarketStatus();
  const isMarketOpen = marketStatus?.is_open || false;

  // Get quotes for live price
  const { quotes, isLoading: quotesLoading } = useMarketQuotes([selectedSymbol]);
  const fyersSymbol = formatFyersSymbol(selectedSymbol);
  const quote = quotes[fyersSymbol] || quotes[selectedSymbol];

  // Auto-fill price from LTP when available
  const handlePriceFromLTP = useCallback(() => {
    if (quote?.ltp) {
      setPrice(quote.ltp.toFixed(2));
      // Auto-calculate SL/TP based on 2% risk/reward
      const ltp = quote.ltp;
      if (side === "BUY") {
        setStopLoss((ltp * 0.98).toFixed(2));
        setTarget((ltp * 1.04).toFixed(2));
      } else {
        setStopLoss((ltp * 1.02).toFixed(2));
        setTarget((ltp * 0.96).toFixed(2));
      }
    }
  }, [quote, side]);

  // Lot size from symbol master (would need symbol info API)
  // For now, use common lot sizes
  const getLotSize = (symbol: string): number => {
    const sizes: Record<string, number> = {
      "NIFTY 50": 50,
      "BANKNIFTY": 15,
      "FINNIFTY": 40,
      "MIDCPNIFTY": 75,
      "SENSEX": 10,
    };
    return sizes[symbol] || 1;
  };

  const lotSize = getLotSize(selectedSymbol);
  const effectiveQty = quantity * lotSize;

  const validateForm = () => {
    if (!selectedSymbol) return "Select a symbol";
    if (!selectedExpiry) return "Select an expiry";
    if (!selectedStrike) return "Select a strike";
    if (!price || parseFloat(price) <= 0) return "Enter a valid price";
    if (mode === "LIVE" && !isMarketOpen) return "Market is closed - cannot place live orders";
    if (mode === "LIVE" && !confirm("⚠️ LIVE ORDER: This will place a REAL order with Kotak Neo. Are you sure?")) return "Live order cancelled";
    return null;
  };

  const handleSubmit = async () => {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetchWithTimeout("/api/v1/execution/order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          symbol: selectedSymbol,
          quantity: effectiveQty,
          order_type: "LIMIT",
          trade_type: side,
          option_type: selectedOptionType,
          strike: selectedStrike,
          expiry: selectedExpiry,
          price: parseFloat(price),
          stop_loss: stopLoss ? parseFloat(stopLoss) : undefined,
          target: target ? parseFloat(target) : undefined,
          mode,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ message: "Order failed" }));
        throw new Error(err.message || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setSuccess(`Order placed: ${data.order_id} (${data.status})`);
      // Reset form
      setPrice("");
      setStopLoss("");
      setTarget("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.6 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[420px] flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
        <div className="flex items-center gap-2">
          <ShoppingBag className="w-5 h-5 text-neon-orange" strokeWidth={2.5} />
          <h3 className="font-semibold text-white">Order Ticket</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${mode === "LIVE" ? "bg-neon-red/20 text-neon-red" : "bg-neon-green/20 text-neon-green"}`}>
            {mode}
          </span>
          {mode === "LIVE" && isMarketOpen && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-green/20 text-neon-green font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse-glow" />
              MARKET OPEN
            </span>
          )}
        </div>
      </div>

      {/* Form */}
      <div className="flex-1 p-5 space-y-4 overflow-y-auto">
        {/* Symbol Selector */}
        <div>
          <label className="text-[11px] text-text-muted uppercase tracking-wider mb-2 block">Symbol</label>
          <select
            value={selectedSymbol}
            onChange={(e) => {
              setSelectedSymbol(e.target.value);
              setSelectedExpiry("");
              setSelectedStrike(null);
              setPrice("");
              setStopLoss("");
              setTarget("");
            }}
            className="w-full px-4 py-2.5 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white"
          >
            <option value="NIFTY 50">NIFTY 50 (50 lot)</option>
            <option value="BANKNIFTY">BANKNIFTY (15 lot)</option>
            <option value="FINNIFTY">FINNIFTY (40 lot)</option>
            <option value="MIDCPNIFTY">MIDCPNIFTY (75 lot)</option>
            <option value="SENSEX">SENSEX (10 lot)</option>
          </select>
        </div>

        {/* Side Toggle */}
        <div>
          <label className="text-[11px] text-text-muted uppercase tracking-wider mb-2 block">Side</label>
          <div className="flex gap-2">
            {["BUY", "SELL"].map((s) => (
              <motion.button
                key={s}
                onClick={() => setSide(s as "BUY" | "SELL")}
                whileTap={{ scale: 0.97 }}
                className={`flex-1 py-2.5 rounded-xl font-bold text-sm transition-all duration-300 ${
                  side === s
                    ? s === "BUY"
                      ? "bg-neon-green/20 text-neon-green border border-neon-green/30 shadow-glow-green"
                      : "bg-neon-red/20 text-neon-red border border-neon-red/30 shadow-glow-red"
                    : "bg-card-bg text-text-secondary border border-glow-border hover:border-neon-cyan/30"
                }`}
              >
                {s}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Mode Toggle */}
        <div>
          <label className="text-[11px] text-text-muted uppercase tracking-wider mb-2 block">Mode</label>
          <div className="flex gap-2">
            {["PAPER", "LIVE"].map((m) => (
              <motion.button
                key={m}
                onClick={() => {
                  if (m === "LIVE" && !isMarketOpen) {
                    alert("Market is closed - Live trading only available during market hours");
                    return;
                  }
                  setMode(m as "PAPER" | "LIVE");
                }}
                disabled={m === "LIVE" && !isMarketOpen}
                whileTap={{ scale: 0.97 }}
                className={`flex-1 py-2.5 rounded-xl font-bold text-sm transition-all duration-300 ${
                  mode === m
                    ? m === "LIVE"
                      ? "bg-neon-red/20 text-neon-red border border-neon-red/30 shadow-glow-red"
                      : "bg-neon-green/20 text-neon-green border border-neon-green/30 shadow-glow-green"
                    : "bg-card-bg text-text-secondary border border-glow-border hover:border-neon-cyan/30"
                } ${m === "LIVE" && !isMarketOpen ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                {m} {m === "LIVE" && !isMarketOpen && "(Closed)"}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Inputs Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Qty (Lots)</label>
            <div className="relative">
              <ShoppingBag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              <input
                type="number"
                min="1"
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
                placeholder="1"
              />
            </div>
            <p className="text-[10px] text-text-muted mt-1">Lot size: {lotSize} × {quantity} = {effectiveQty} qty</p>
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Expiry</label>
            <input
              type="text"
              value={selectedExpiry}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              placeholder="YYYY-MM-DD"
              className="w-full pl-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
            />
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Strike</label>
            <input
              type="number"
              value={selectedStrike || ""}
              onChange={(e) => setSelectedStrike(e.target.value ? parseInt(e.target.value) : null)}
              placeholder="ATM Strike"
              className="w-full pl-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
            />
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Option Type</label>
            <select
              value={selectedOptionType}
              onChange={(e) => setSelectedOptionType(e.target.value as "CE" | "PE")}
              className="w-full pl-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white"
            >
              <option value="CE">Call (CE)</option>
              <option value="PE">Put (PE)</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Limit Price</label>
            <div className="relative flex gap-2">
              <div className="relative flex-1">
                <TrendingUp className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                <input
                  type="text"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="Enter price or click LTP"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
                />
              </div>
              <motion.button
                onClick={handlePriceFromLTP}
                disabled={quotesLoading || !quote?.ltp}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="px-3 py-2.5 rounded-xl bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30 font-medium text-sm whitespace-nowrap hover:bg-neon-cyan/30 transition-colors disabled:opacity-50"
              >
                Use LTP: ₹{quote?.ltp?.toFixed(2) || "—"}
              </motion.button>
            </div>
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Stop Loss</label>
            <div className="relative">
              <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              <input
                type="text"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                placeholder="Auto from LTP"
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
              />
            </div>
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Target</label>
            <div className="relative">
              <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              <input
                type="text"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="Auto from LTP"
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
              />
            </div>
          </div>
        </div>

        {/* Risk Summary */}
        <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-text-secondary">Risk:Reward</span>
            {price && stopLoss && target && (
              <span className="font-mono font-bold text-neon-cyan">
                1:{((parseFloat(target) - parseFloat(price)) / (parseFloat(price) - parseFloat(stopLoss))).toFixed(2)}
              </span>
            )}
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">Max Loss</span>
            {price && stopLoss && (
              <span className="font-mono font-bold text-neon-red">
                ₹{(effectiveQty * Math.abs(parseFloat(price) - parseFloat(stopLoss))).toLocaleString()}
              </span>
            )}
          </div>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm"
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={2.5} />
            <span>{error}</span>
          </motion.div>
        )}
        {success && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neon-green/10 border border-neon-green/30 text-neon-green text-sm"
          >
            <Check className="w-4 h-4 flex-shrink-0" strokeWidth={2.5} />
            <span>{success}</span>
          </motion.div>
        )}

        {/* Place Order Button */}
        <motion.button
          onClick={handleSubmit}
          disabled={isSubmitting}
          whileHover={{ scale: 1.02, boxShadow: "0 0 25px rgba(249, 115, 22, 0.5)" }}
          whileTap={{ scale: 0.98 }}
          className={`w-full py-3.5 rounded-xl font-bold text-lg shadow-glow-orange transition-all duration-300 flex items-center justify-center gap-2 ${
            isSubmitting 
              ? "bg-gradient-to-r from-neon-orange/50 to-neon-red/50 cursor-not-allowed" 
              : mode === "LIVE"
                ? "bg-gradient-to-r from-neon-red to-neon-orange text-white"
                : "bg-gradient-to-r from-neon-green to-neon-cyan text-true-black"
          }`}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
              Placing Order...
            </>
          ) : (
            <>
              <Radio className="w-5 h-5" strokeWidth={2.5} />
              {mode === "LIVE" ? "Place LIVE Order" : "Place Paper Order"}
            </>
          )}
        </motion.button>
      </div>
    </motion.div>
  );
}