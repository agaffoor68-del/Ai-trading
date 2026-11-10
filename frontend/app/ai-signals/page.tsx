// File: app/ai-signals/page.tsx
"use client";

import { Brain } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function AISignalsPage() {
  return (
    <PlaceholderPage
      title="AI Signals"
      description="Grok AI-powered trading signals with confidence scoring, reasoning, and risk parameters. Analyzes market structure, order flow, news sentiment, and technical patterns."
      icon={Brain}
    />
  );
}