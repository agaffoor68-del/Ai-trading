// File: app/option-chain/page.tsx
"use client";

import { List } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function OptionChainPage() {
  return (
    <PlaceholderPage
      title="Option Chain"
      description="Complete options chain with Greeks, OI analysis, IV charts, and PCR. Filter by expiry, strike range, and option type. Powered by Fyers Symbol Master."
      icon={List}
    />
  );
}