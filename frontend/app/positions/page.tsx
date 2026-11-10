// File: app/positions/page.tsx
"use client";

import { Briefcase } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function PositionsPage() {
  return (
    <PlaceholderPage
      title="Positions"
      description="Real-time position tracking with PnL, Greeks, margin usage, and exit management. Supports both paper and live positions from Kotak Neo."
      icon={Briefcase}
    />
  );
}