// File: app/analytics/page.tsx
"use client";

import { BarChart } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function AnalyticsPage() {
  return (
    <PlaceholderPage
      title="Analytics"
      description="Advanced analytics dashboard with performance attribution, risk metrics, trade distribution, equity curves, and regime analysis. Export reports for compliance."
      icon={BarChart}
    />
  );
}