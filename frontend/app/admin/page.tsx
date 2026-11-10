// File: app/admin/page.tsx
"use client";

import { Users } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function AdminPage() {
  return (
    <PlaceholderPage
      title="Admin Panel"
      description="Administrative controls: user management, subscription plans, system health, audit logs, feature flags, database monitoring, and platform-wide configuration."
      icon={Users}
    />
  );
}