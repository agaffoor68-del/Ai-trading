"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, Loader2, AlertCircle, CheckCircle, Lock, Mail, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append("username", email);
      formData.append("password", password);

      const response = await fetch("/api/auth/login", {
        method: "POST",
        body: formData,
        credentials: "include",
        headers: { Accept: "application/json" },
      });

      const contentType = response.headers.get("content-type") || "";
      const isJson = contentType.includes("application/json");
      const data = isJson ? await response.json().catch(() => null) : null;

      if (!response.ok) {
        // Distinguish between wrong credentials (401), forbidden (403), and other errors
        const status = response.status;
        const detail =
          data && typeof data === "object" && "detail" in data
            ? String((data as { detail: unknown }).detail)
            : null;

        if (status === 401) {
          setError(detail || "Invalid email or password. Please check your credentials.");
        } else if (status === 403) {
          setError(detail || "User account is deactivated. Please contact support.");
        } else if (status === 429) {
          setError(detail || "Too many login attempts. Please try again later.");
        } else if (detail) {
          setError(`${detail} (status ${status})`);
        } else if (!isJson) {
          setError(
            `Login failed with status ${status}: the server returned an unexpected non-JSON response.`
          );
        } else {
          setError(`Login failed (status ${status}). Please try again.`);
        }
        return;
      }

      setSuccess("Login successful! Redirecting...");
      setTimeout(() => {
        router.push("/");
      }, 1000);
    } catch (err) {
      // Network/error type determination
      if (err instanceof TypeError) {
        setError("Network error. Please check your connection and try again.");
      } else if (err instanceof DOMException && err.name === "AbortError") {
        setError("Request timed out. Please try again.");
      } else {
        setError(`Error: ${err instanceof Error ? err.message : 'Unknown error'}. Please try again.`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="min-h-screen bg-true-black flex items-center justify-center p-4"
    >
      {/* Background glow effects */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-neon-cyan/5 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-neon-purple/5 blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="relative w-full max-w-md glass rounded-3xl border border-glow-border p-6 md:p-8"
      >
        {/* Logo/Title */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-gradient-to-br from-neon-cyan to-neon-purple flex items-center justify-center shadow-glow-cyan">
            <Lock className="w-8 h-8 text-true-black" strokeWidth={2.5} />
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Welcome Back</h1>
          <p className="text-text-muted mt-2">Sign in to your AlphaTradePro account</p>
        </div>

        {/* Error Message */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 p-4 rounded-xl bg-neon-red/10 border border-neon-red/30 text-neon-red flex items-center gap-3"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0" strokeWidth={2.5} />
            <p className="text-sm">{error}</p>
          </motion.div>
        )}

        {/* Success Message */}
        {success && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 p-4 rounded-xl bg-neon-green/10 border border-neon-green/30 text-neon-green flex items-center gap-3"
          >
            <CheckCircle className="w-5 h-5 flex-shrink-0" strokeWidth={2.5} />
            <p className="text-sm">{success}</p>
          </motion.div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email */}
          <div>
            <label htmlFor="email" className="text-xs text-text-muted uppercase tracking-wider block mb-2">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" strokeWidth={2.5} />
              <input
                type="email"
                id="email"
                name="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@alphatradepro.com"
                className="w-full pl-12 pr-4 py-3.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white placeholder-text-muted transition-colors"
                autoComplete="email"
                autoFocus
                required
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label htmlFor="password" className="text-xs text-text-muted uppercase tracking-wider block mb-2">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" strokeWidth={2.5} />
              <input
                type={showPassword ? "text" : "password"}
                id="password"
                name="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-12 pr-14 py-3.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white placeholder-text-muted transition-colors"
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 p-1 text-text-muted hover:text-white transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff className="w-5 h-5" strokeWidth={2} />
                ) : (
                  <Eye className="w-5 h-5" strokeWidth={2} />
                )}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <motion.button
            type="submit"
            disabled={isLoading}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className={`w-full py-3.5 rounded-xl font-bold text-lg transition-all duration-300 flex items-center justify-center gap-2 ${
              isLoading
                ? "bg-gradient-to-r from-neon-orange/50 to-neon-red/50 cursor-not-allowed"
                : "bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black shadow-glow-cyan hover:shadow-glow-cyan/50"
            }`}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
                <span>Signing in...</span>
              </>
            ) : (
              <>
                <ArrowRight className="w-5 h-5" strokeWidth={2.5} />
                <span>Sign In</span>
              </>
            )}
          </motion.button>
        </form>

        {/* Footer */}
        <div className="mt-8 text-center text-text-muted text-sm">
          <p>AlphaTradePro - Autonomous Options Trading Platform</p>
          <p className="text-[11px] mt-1">Fyers API v3 • Kotak Neo • Grok AI</p>
        </div>
      </motion.div>
    </motion.div>
  );
}