// File: app/order-ticket/page.tsx
"use client";

import { ShoppingBag } from "lucide-react";
import PlaceholderPage from "@/components/PlaceholderPage";

export default function OrderTicketPage() {
  return (
    <PlaceholderPage
      title="Order Ticket"
      description="Professional order entry with BUY/SELL, PAPER/LIVE modes, bracket orders (SL/TP), quantity calculator, and risk preview. Executes via Kotak Neo API."
      icon={ShoppingBag}
    />
  );
}