// File: app/settings/page.tsx
"use client";

import { Settings } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function SettingsPage() {
  return (
    <PlaceholderPage
      title="Settings"
      description="Platform configuration: API keys, notification preferences, theme customization, trading hours, default order types, risk parameters, and account management."
      icon={Settings}
    />
  );
}