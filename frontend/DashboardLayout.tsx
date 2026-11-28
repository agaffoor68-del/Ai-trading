"use client";

import { motion } from "framer-motion";
import { Sidebar, SidebarProvider } from "./Sidebar";
import { Header } from "./Header";
import { HeroBanner } from "./HeroBanner";
import { MarketWatch } from "./MarketWatch";
import { CandlestickChart } from "./CandlestickChart";
import { SymbolProvider, useSelectedSymbol } from "@/lib/symbol-context";
import { OptionsChain } from "./OptionsChain";
import { AISignalCard } from "./AISignalCard";
import { OrderTicket } from "./OrderTicket";
import { BrainAnimation } from "./BrainAnimation";
import { DashboardErrorBoundary } from "./DashboardErrorBoundary";

function MainChart() {
  const { selectedSymbol } = useSelectedSymbol();
  return <CandlestickChart symbol={selectedSymbol} height={340} />;
}

export function DashboardLayout() {
  return (
    <DashboardErrorBoundary>
      <SymbolProvider>
      <SidebarProvider>
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
              <MainChart />
              <OptionsChain />
            </div>
            
            {/* Column 3: AI Signal + Order Ticket + Brain Animation */}
            <div className="lg:col-span-1 space-y-4">
              <AISignalCard />
              <OrderTicket />
              <BrainAnimation 
                className="glass rounded-2xl border border-glow-border p-4 bg-card-bg/50"
                aiActive={true}
                speed={1}
              />
            </div>
          </div>
        </main>
      </div>
    </div>
    </SidebarProvider>
    </SymbolProvider>
    </DashboardErrorBoundary>
  );
}


interface BrainSvgProps {
  /** Custom className for the brain SVG */
  className?: string;
}

/** Self-contained SVG brain animation - no external dependencies */
      <line x1="180" y1="210" x2="220" y2="190"/>
      <line x1="180" y1="210" x2="140" y2="190"/>
      <line x1="140" y1="110" x2="180" y2="150"/>
      <line x1="220" y1="190" x2="260" y2="170"/>
    </g>
    
    <!-- Neuron nodes with pulse animation -->
    <g fill="rgba(0, 255, 255, 0.8)" opacity="0.8">
      <circle cx="100" cy="90" r="3" class="neuron-node"/>
      <circle cx="140" cy="110" r="3" class="neuron-node"/>
      <circle cx="60" cy="110" r="3" class="neuron-node"/>
      <circle cx="220" cy="190" r="3" class="neuron-node"/>
      <circle cx="260" cy="170" r="3" class="neuron-node"/>
      <circle cx="180" cy="150" r="3" class="neuron-node"/>
      <circle cx="300" cy="90" r="3" class="neuron-node"/>
      <circle cx="340" cy="50" r="3" class="neuron-node"/>
    </g>
    
    <!-- Glowing connections -->
    <g fill="none" stroke="rgba(0, 255, 255, 0.4)" stroke-width="2" opacity="0.5">
      <circle cx="100" cy="90" r="8" class="glow-connection"/>
      <circle cx="140" cy="110" r="8" class="glow-connection"/>
      <circle cx="60" cy="110" r="8" class="glow-connection"/>
      <circle cx="220" cy="190" r="8" class="glow-connection"/>
      <circle cx="260" cy="170" r="8" class="glow-connection"/>
      <circle cx="180" cy="150" r="8" class="glow-connection"/>
      <circle cx="300" cy="90" r="8" class="glow-connection"/>
      <circle cx="340" cy="50" r="8" class="glow-connection"/>
    </g>
    
    <!-- Electrical wave arcs -->
    <g fill="none" stroke="rgba(128, 0, 255, 0.8)" stroke-width="2" opacity="0.9">
      <path d="M100 90 A40 30 0 0 1 140 110" class="wave-arc"/>
      <path d="M60 110 A40 30 0 0 1 100 90" class="wave-arc"/>
      <path d="M220 190 A40 30 0 0 1 260 170" class="wave-arc"/>
      <path d="M260 170 A40 30 0 0 1 300 90" class="wave-arc"/>
    </g>
    
    <!-- Synaptic activity -->
    <g fill="rgba(255, 255, 0, 0.9)">
      <circle cx="100" cy="90" r="2" class="synaptic-activity"/>
      <circle cx="140" cy="110" r="2" class="synaptic-activity"/>
      <circle cx="60" cy="110" r="2" class="synaptic-activity"/>
      <circle cx="180" cy="150" r="2" class="synaptic-activity"/>
      <circle cx="220" cy="190" r="2" class="synaptic-activity"/>
      <circle cx="260" cy="170" r="2" class="synaptic-activity"/>
    </g>
  </svg>
  
  <!-- Lighting glow -->
  <div style="position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; 
              background: radial-gradient(circle, rgba(0, 255, 255, 0.15) 0%, transparent 70%);
              pointer-events: none; animation: pulse-glow 4s ease-in-out infinite;">
  </div>
  
  <style>
    @keyframes pulse-glow {
      0%, 100% { opacity: 0.5; transform: scale(1); }
      50% { opacity: 0.8; transform: scale(1.1); }
    }
    .neuron-node { animation: node-pulse 2s ease-in-out infinite; }
    @keyframes node-pulse {
      0%, 100% { opacity: 0.8; transform: scale(1); }
      50% { opacity: 1; transform: scale(1.2); }
    }
    .glow-connection { animation: glow-pulse 3s ease-in-out infinite; }
    @keyframes glow-pulse {
      0%, 100% { opacity: 0.3; }
      50% { opacity: 0.6; }
    }
    .synaptic-activity { animation: synaptic-fire 1s ease-in-out infinite; }
    @keyframes synaptic-fire {
      0%, 90% { opacity: 0.8; }
      100% { opacity: 0; transform: scale(2); }
    }
    .wave-arc { animation: wave-travel 2s linear infinite; }
    @keyframes wave-travel {
      from { stroke-dashoffset: 0; }
      to { stroke-dashoffset: -100; }
    }
  </style>
</div>`;
