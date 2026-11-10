// File: app/paper-trading/page.tsx
"use client";

import { FlaskConical } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function PaperTradingPage() {
  return (
    <PlaceholderPage
      title="Paper Trading"
      description="Simulated trading environment with virtual capital. Test strategies risk-free with realistic fills, slippage, and commission modeling. Perfect for strategy validation."
      icon={FlaskConical}
    />
  );
}