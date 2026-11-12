"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Users,
  Shield,
  Mail,
  Calendar,
  UserX,
  Loader2,
  AlertCircle,
  CheckCircle,
  Trash2,
  MoreHorizontal,
  Search,
  Plus,
  LucideIcon,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: "admin" | "trader" | "viewer";
  plan: "free" | "pro" | "enterprise";
  subscriptionStatus: "active" | "expired" | "cancelled" | "trial";
  expiryDate: string;
  createdAt: string;
  isActive: boolean;
}

const MOCK_USERS: AdminUser[] = [
  {
    id: "1",
    email: "admin@alphatrade.com",
    name: "Admin User",
    role: "admin",
    plan: "enterprise",
    subscriptionStatus: "active",
    expiryDate: "2025-12-31",
    createdAt: "2024-01-15",
    isActive: true,
  },
  {
    id: "2",
    email: "rajesh.kumar@trader.com",
    name: "Rajesh Kumar",
    role: "trader",
    plan: "pro",
    subscriptionStatus: "active",
    expiryDate: "2025-06-15",
    createdAt: "2024-03-22",
    isActive: true,
  },
  {
    id: "3",
    email: "priya.sharma@investor.com",
    name: "Priya Sharma",
    role: "trader",
    plan: "pro",
    subscriptionStatus: "active",
    expiryDate: "2025-08-30",
    createdAt: "2024-04-10",
    isActive: true,
  },
  {
    id: "4",
    email: "amit.patel@free.com",
    name: "Amit Patel",
    role: "viewer",
    plan: "free",
    subscriptionStatus: "trial",
    expiryDate: "2024-12-01",
    createdAt: "2024-11-01",
    isActive: true,
  },
  {
    id: "5",
    email: "sneha.reddy@expired.com",
    name: "Sneha Reddy",
    role: "trader",
    plan: "pro",
    subscriptionStatus: "expired",
    expiryDate: "2024-10-01",
    createdAt: "2024-02-14",
    isActive: false,
  },
  {
    id: "6",
    email: "vikram.singh@cancelled.com",
    name: "Vikram Singh",
    role: "viewer",
    plan: "free",
    subscriptionStatus: "cancelled",
    expiryDate: "2024-09-15",
    createdAt: "2024-05-20",
    isActive: false,
  },
];

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>(MOCK_USERS);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const filteredUsers = users.filter(
    (u) =>
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleRevoke = async (userId: string) => {
    const user = users.find((u) => u.id === userId);
    if (!user) return;

    if (!confirm(`Revoke access for ${user.email}? This will deactivate their account.`)) return;

    setIsLoading(true);
    try {
      // TODO: Call backend API when available
      // await api.revokeUser(userId);
      await new Promise((resolve) => setTimeout(resolve, 800));
      
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, isActive: false, subscriptionStatus: "cancelled" } : u)));
      showToast(`Access revoked for ${user.email}`, "success");
    } catch {
      showToast("Failed to revoke access", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "text-neon-green bg-neon-green/20 border-neon-green/30";
      case "expired":
        return "text-neon-red bg-neon-red/20 border-neon-red/30";
      case "cancelled":
        return "text-neon-orange bg-neon-orange/20 border-neon-orange/30";
      case "trial":
        return "text-neon-cyan bg-neon-cyan/20 border-neon-cyan/30";
      default:
        return "text-text-muted bg-card-bg/50 border-glow-border";
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case "admin":
        return "text-neon-purple bg-neon-purple/20 border-neon-purple/30";
      case "trader":
        return "text-neon-green bg-neon-green/20 border-neon-green/30";
      case "viewer":
        return "text-neon-cyan bg-neon-cyan/20 border-neon-cyan/30";
      default:
        return "text-text-muted";
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-7xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Shield className="w-8 h-8 text-neon-purple drop-shadow-[0_0_10px_rgba(168,85,247,0.6)]" strokeWidth={2.5} />
                <div>
                  <h1 className="text-3xl font-bold text-white tracking-tight">Admin Panel</h1>
                  <p className="text-text-secondary">User management, subscriptions, and platform configuration</p>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-medium hover:opacity-90 transition-opacity"
              >
                <Plus className="w-4 h-4" strokeWidth={2.5} />
                Add User
              </motion.button>
            </div>
          </motion.div>

          {/* Toast Notification */}
          {toast && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className={`fixed top-6 right-6 px-6 py-4 rounded-xl border text-white font-medium z-50 shadow-lg ${
                toast.type === "success"
                  ? "bg-neon-green/20 border-neon-green/50 text-neon-green shadow-[0_0_20px_rgba(0,255,102,0.3)]"
                  : "bg-neon-red/20 border-neon-red/50 text-neon-red shadow-[0_0_20px_rgba(255,0,60,0.3)]"
              }`}
            >
              <div className="flex items-center gap-2">
                {toast.type === "success" ? (
                  <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                ) : (
                  <AlertCircle className="w-5 h-5" strokeWidth={2.5} />
                )}
                <span>{toast.message}</span>
              </div>
            </motion.div>
          )}

          {/* Stats Overview */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <StatCard
              label="Total Users"
              value={users.length}
              icon={Users}
              color="text-neon-cyan"
            />
            <StatCard
              label="Active Subscriptions"
              value={users.filter((u) => u.subscriptionStatus === "active").length}
              icon={CheckCircle}
              color="text-neon-green"
            />
            <StatCard
              label="Pro/Enterprise"
              value={users.filter((u) => u.plan !== "free").length}
              icon={Shield}
              color="text-neon-purple"
            />
            <StatCard
              label="Trial Users"
              value={users.filter((u) => u.subscriptionStatus === "trial").length}
              icon={Calendar}
              color="text-neon-orange"
            />
          </div>

          {/* Users Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass rounded-2xl border border-glow-border overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-glow-border bg-card-bg/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-white">User Management</h2>
                <span className="text-xs px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">
                  {filteredUsers.length} users
                </span>
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search users..."
                  className="w-64 pl-10 pr-4 py-2 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white placeholder-text-muted text-sm"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                    <th className="px-5 py-4 text-left">User</th>
                    <th className="px-5 py-4 text-center">Role</th>
                    <th className="px-5 py-4 text-center">Plan</th>
                    <th className="px-5 py-4 text-center">Subscription</th>
                    <th className="px-5 py-4 text-center">Expiry</th>
                    <th className="px-5 py-4 text-center">Status</th>
                    <th className="px-5 py-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user, index) => (
                    <motion.tr
                      key={user.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.03 }}
                      className="border-b border-glow-border/50 hover:bg-card-bg/30 transition-colors"
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-neon-purple/20 flex items-center justify-center">
                            <Mail className="w-4 h-4 text-neon-purple" strokeWidth={2.5} />
                          </div>
                          <div>
                            <p className="font-medium text-white">{user.name}</p>
                            <p className="text-xs text-text-muted">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-center">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${getRoleColor(user.role)} border`}>
                          {user.role.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-center">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                          user.plan === "enterprise" ? "text-neon-purple bg-neon-purple/20 border-neon-purple/30" :
                          user.plan === "pro" ? "text-neon-green bg-neon-green/20 border-neon-green/30" :
                          "text-text-muted bg-card-bg/50 border-glow-border"
                        } border`}>
                          {user.plan.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-center">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(user.subscriptionStatus)} border`}>
                          {user.subscriptionStatus.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-center font-mono text-text-secondary">
                        {formatDate(user.expiryDate)}
                      </td>
                      <td className="px-5 py-4 text-center">
                        <span className={`w-3 h-3 rounded-full ${user.isActive ? "bg-neon-green" : "bg-neon-red"}`} />
                      </td>
                      <td className="px-5 py-4 text-center">
                        <motion.button
                          onClick={() => handleRevoke(user.id)}
                          disabled={isLoading || !user.isActive}
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          className="p-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red hover:bg-neon-red/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          title={user.isActive ? "Revoke Access" : "Already Revoked"}
                        >
                          <UserX className="w-4 h-4" strokeWidth={2.5} />
                        </motion.button>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredUsers.length === 0 && (
              <div className="flex flex-col items-center justify-center h-64 text-center px-6">
                <AlertCircle className="w-12 h-12 text-neon-red/50 mb-4" strokeWidth={1.5} />
                <h3 className="text-lg font-semibold text-white mb-2">No users found</h3>
                <p className="text-text-secondary">Try adjusting your search query</p>
              </div>
            )}
          </motion.div>
        </main>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: LucideIcon; color: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl border border-glow-border p-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wider">{label}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
        </div>
        <div className="w-14 h-14 rounded-xl flex items-center justify-center" style={{ backgroundColor: "rgba(255,255,255,0.03)" }}>
          <Icon className="w-7 h-7" strokeWidth={2.5} style={{ color: "currentColor" }} />
        </div>
      </div>
    </motion.div>
  );
}