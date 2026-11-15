"use client";

import { motion } from "framer-motion";
import { Shield, ArrowLeft, Home } from "lucide-react";
import Link from "next/link";

export default function ForbiddenPage() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="min-h-screen bg-true-black flex items-center justify-center p-4"
    >
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-neon-red/5 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-neon-purple/5 blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="relative w-full max-w-md glass rounded-3xl border border-neon-red/30 p-6 md:p-8 text-center"
      >
        <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-neon-red/10 flex items-center justify-center">
          <Shield className="w-8 h-8 text-neon-red" strokeWidth={2.5} />
        </div>
        
        <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight mb-2">Access Denied</h1>
        <p className="text-text-muted mb-6">
          You don't have permission to access this page. This area requires administrator privileges.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => window.history.back()}
            className="flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold shadow-glow-cyan hover:opacity-90"
          >
            <ArrowLeft className="w-4 h-4" strokeWidth={2.5} />
            Go Back
          </motion.button>
          
          <Link
            href="/"
            className="flex items-center gap-2 px-5 py-3 rounded-xl bg-card-bg border border-glow-border text-white font-bold hover:bg-card-bg/80 hover:border-neon-cyan/50 transition-all duration-300"
          >
            <Home className="w-4 h-4" strokeWidth={2.5} />
            Dashboard
          </Link>
        </div>
      </motion.div>
    </motion.div>
  );
}