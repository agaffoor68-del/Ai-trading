// File: app/backtest/page.tsx
"use client";

import { RotateCcw } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function BacktestPage() {
  return (
    <PlaceholderPage
      title="Backtest"
      description="Historical backtesting engine with tick-level data, walk-forward analysis, Monte Carlo simulation, and detailed performance metrics (Sharpe, Sortino, Max DD, Calmar)."
      icon={RotateCcw}
    />
  );
}