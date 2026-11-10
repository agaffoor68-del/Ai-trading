// File: app/market-watch/page.tsx
"use client";

import { TrendingUp } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function MarketWatchPage() {
  return (
    <PlaceholderPage
      title="Market Watch"
      description="Real-time market data, quotes, and watchlists powered by Fyers API v3. Track indices, stocks, and derivatives with live updates."
      icon={TrendingUp}
    />
  );
}