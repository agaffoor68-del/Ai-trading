// File: app/broker-connect/page.tsx
"use client";

import { Link } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function BrokerConnectPage() {
  return (
    <PlaceholderPage
      title="Broker Connect"
      description="Manage broker connections: Fyers API v3 (market data) and Kotak Neo (order execution). OAuth flow, token management, connection health, and API status monitoring."
      icon={Link}
    />
  );
}