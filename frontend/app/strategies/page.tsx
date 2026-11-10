// File: app/strategies/page.tsx
"use client";

import { GitBranch } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function StrategiesPage() {
  return (
    <PlaceholderPage
      title="Strategies"
      description="Strategy builder and library. Create, manage, and deploy algorithmic strategies with visual editor, parameter optimization, and version control."
      icon={GitBranch}
    />
  );
}