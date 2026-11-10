// File: app/risk-management/page.tsx
"use client";

import { Shield } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function RiskManagementPage() {
  return (
    <PlaceholderPage
      title="Risk Management"
      description="Enterprise risk controls: position limits, daily loss limits, sector exposure, margin alerts, kill switch, and real-time risk monitoring with automated position flattening."
      icon={Shield}
    />
  );
}