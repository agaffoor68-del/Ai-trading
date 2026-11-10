"use client";

import { motion } from "framer-motion";
import { Wrench, Construction, Sparkles } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

export default function PlaceholderPage({ title, description, icon: Icon }: { title: string; description: string; icon: React.ComponentType<{ className?: string; strokeWidth?: number | string }> }) {
  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />
        
        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 flex items-center justify-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="text-center max-w-xl px-6"
          >
            {/* Icon */}
            <div className="relative inline-block mb-8">
              <div className="w-24 h-24 mx-auto rounded-2xl bg-gradient-to-br from-neon-purple/20 to-neon-cyan/20 border border-neon-purple/30 flex items-center justify-center glass shadow-glow-purple">
                <Icon className="w-12 h-12 text-neon-cyan text-glow-cyan" strokeWidth={2} />
              </div>
              <motion.div
                className="absolute -top-4 -right-4 w-16 h-16 rounded-full bg-neon-purple/20 blur-2xl"
                animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
                transition={{ duration: 3, repeat: Infinity }}
              />
            </div>

            {/* Title */}
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 tracking-tight">
              {title}
            </h1>
            
            {/* Subtitle */}
            <p className="text-lg text-text-secondary mb-8 max-w-md mx-auto leading-relaxed">
              {description}
            </p>

            {/* Status Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-card-bg border border-glow-border glass">
              <motion.span
                className="w-2 h-2 rounded-full bg-neon-orange"
                animate={{ boxShadow: ["0 0 0 0 rgba(249, 115, 22, 0.7)", "0 0 0 8px rgba(249, 115, 22, 0)"] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              <span className="text-sm font-medium text-neon-orange">Under Construction</span>
            </div>

            {/* Feature highlights */}
            <div className="mt-10 grid grid-cols-3 gap-4 text-left">
              {[
                { icon: Wrench, label: "Backend API", desc: "Fyers v3 + Kotak Neo" },
                { icon: Construction, label: "UI Components", desc: "HDR OLED Design System" },
                { icon: Sparkles, label: "AI Integration", desc: "Grok Signal Engine" },
              ].map((item, i) => (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 + i * 0.1 }}
                  className="p-4 rounded-xl bg-card-bg border border-glow-border glass-hover text-left group"
                >
                  <item.icon className="w-5 h-5 text-neon-cyan mb-2 group-hover:text-neon-green transition-colors" strokeWidth={2.5} />
                  <p className="font-medium text-white text-sm">{item.label}</p>
                  <p className="text-xs text-text-muted mt-0.5">{item.desc}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  );
}