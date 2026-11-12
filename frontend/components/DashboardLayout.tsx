"use client";

import { motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { HeroBanner } from "./HeroBanner";
import { MarketWatch } from "./MarketWatch";
import { ChartPlaceholder } from "./ChartPlaceholder";
import { OptionsChain } from "./OptionsChain";
import { AISignalCard } from "./AISignalCard";
import { OrderTicket } from "./OrderTicket";

export function DashboardLayout() {
  return (
    <div className="min-h-screen bg-true-black text-white">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        {/* Header */}
        <Header />
        
        {/* Page Content */}
        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-6">
          {/* Hero Banner */}
          <HeroBanner />
          
          {/* Row 2: 3 Column Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
            {/* Column 1: Market Watch */}
            <div className="lg:col-span-1">
              <MarketWatch />
            </div>
            
            {/* Column 2: Chart + Options Chain */}
            <div className="lg:col-span-1 space-y-4">
              <ChartPlaceholder />
              <OptionsChain />
            </div>
            
            {/* Column 3: AI Signal + Order Ticket */}
            <div className="lg:col-span-1 space-y-4">
              <AISignalCard />
              <OrderTicket />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}