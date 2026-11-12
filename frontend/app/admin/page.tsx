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
  UserPlus,
  Key,
  Eye,
  EyeOff,
  Edit,
  ShieldCheck,
  ShieldAlert,
  Bell,
  BarChart2,
  Activity,
  ArrowRight,
  ArrowLeft,
  ChevronDown,
  X,
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
  lastLogin: string;
  apiCallsToday: number;
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
    lastLogin: "2024-11-11 14:30:00",
    apiCallsToday: 1247,
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
    lastLogin: "2024-11-11 10:15:00",
    apiCallsToday: 892,
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
    lastLogin: "2024-11-10 18:45:00",
    apiCallsToday: 567,
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
    lastLogin: "2024-11-11 09:30:00",
    apiCallsToday: 45,
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
    lastLogin: "2024-10-15 12:00:00",
    apiCallsToday: 0,
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
    lastLogin: "2024-09-10 16:20:00",
    apiCallsToday: 0,
  },
  {
    id: "7",
    email: "kavya.nair@new.com",
    name: "Kavya Nair",
    role: "trader",
    plan: "pro",
    subscriptionStatus: "active",
    expiryDate: "2025-03-20",
    createdAt: "2024-09-15",
    isActive: true,
    lastLogin: "2024-11-11 11:00:00",
    apiCallsToday: 234,
  },
  {
    id: "8",
    email: "arjun.mehta@pro.com",
    name: "Arjun Mehta",
    role: "trader",
    plan: "enterprise",
    subscriptionStatus: "active",
    expiryDate: "2025-11-30",
    createdAt: "2024-06-01",
    isActive: true,
    lastLogin: "2024-11-11 13:45:00",
    apiCallsToday: 1890,
  },
];

const PLANS = ["free", "pro", "enterprise"] as const;
const ROLES = ["admin", "trader", "viewer"] as const;
const STATUSES = ["active", "expired", "cancelled", "trial"] as const;

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>(MOCK_USERS);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [grantModalOpen, setGrantModalOpen] = useState(false);
  const [grantForm, setGrantForm] = useState({
    email: "",
    plan: "pro" as "free" | "pro" | "enterprise",
    role: "trader" as "admin" | "trader" | "viewer",
    days: 30,
  });
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);

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

  const handleReactivate = async (userId: string) => {
    const user = users.find((u) => u.id === userId);
    if (!user) return;

    if (!confirm(`Reactivate access for ${user.email}?`)) return;

    setIsLoading(true);
    try {
      // await api.reactivateUser(userId);
      await new Promise((resolve) => setTimeout(resolve, 800));
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, isActive: true, subscriptionStatus: "active" })));
      showToast(`Access reactivated for ${user.email}`, "success");
    } catch {
      showToast("Failed to reactivate access", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGrantAccess = async () => {
    if (!grantForm.email.trim()) {
      showToast("Please enter an email address", "error");
      return;
    }

    const existingUser = users.find((u) => u.email === grantForm.email);
    if (existingUser && existingUser.isActive) {
      showToast("User already has active access", "error");
      return;
    }

    setIsLoading(true);
    try {
      // await api.grantAccess(grantForm);
      await new Promise((resolve) => setTimeout(resolve, 1000));
      
      if (existingUser) {
        setUsers((prev) => prev.map((u) => 
          u.id === existingUser.id 
            ? { ...u, isActive: true, plan: grantForm.plan, role: grantForm.role, subscriptionStatus: "active", expiryDate: new Date(Date.now() + grantForm.days * 86400000).toISOString().split("T")[0] }
            : u
        ));
      } else {
        const newUser: AdminUser = {
          id: Date.now().toString(),
          email: grantForm.email,
          name: grantForm.email.split("@")[0],
          role: grantForm.role,
          plan: grantForm.plan,
          subscriptionStatus: "active",
          expiryDate: new Date(Date.now() + grantForm.days * 86400000).toISOString().split("T")[0],
          createdAt: new Date().toISOString().split("T")[0],
          isActive: true,
          lastLogin: "Never",
          apiCallsToday: 0,
        };
        setUsers((prev) => [newUser, ...prev]);
      }
      
      showToast(`Access granted to ${grantForm.email} (${grantForm.plan}, ${grantForm.days} days)`, "success");
      setGrantModalOpen(false);
      setGrantForm({ email: "", plan: "pro", role: "trader", days: 30 });
    } catch {
      showToast("Failed to grant access", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditUser = (user: AdminUser) => {
    setEditingUser(user);
  };

  const handleSaveEdit = async () => {
    if (!editingUser) return;
    setIsLoading(true);
    try {
      // await api.updateUser(editingUser.id, editingUser);
      await new Promise((resolve) => setTimeout(resolve, 800));
      setUsers((prev) => prev.map((u) => (u.id === editingUser.id ? editingUser : u)));
      showToast(`Updated ${editingUser.email}`, "success");
      setEditingUser(null);
    } catch {
      showToast("Failed to update user", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active": return "text-neon-green bg-neon-green/20 border-neon-green/30";
      case "expired": return "text-neon-red bg-neon-red/20 border-neon-red/30";
      case "cancelled": return "text-neon-orange bg-neon-orange/20 border-neon-orange/30";
      case "trial": return "text-neon-cyan bg-neon-cyan/20 border-neon-cyan/30";
      default: return "text-text-muted bg-card-bg/50 border-glow-border";
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case "admin": return "text-neon-purple bg-neon-purple/20 border-neon-purple/30";
      case "trader": return "text-neon-green bg-neon-green/20 border-neon-green/30";
      case "viewer": return "text-neon-cyan bg-neon-cyan/20 border-neon-cyan/30";
      default: return "text-text-muted";
    }
  };

  const getPlanColor = (plan: string) => {
    switch (plan) {
      case "enterprise": return "text-neon-purple bg-neon-purple/20 border-neon-purple/30";
      case "pro": return "text-neon-green bg-neon-green/20 border-neon-green/30";
      case "free": return "text-text-muted bg-card-bg/50 border-glow-border";
      default: return "text-text-muted";
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString();
    } catch {
      return dateStr;
    }
  };

  const formatDateTime = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
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
                onClick={() => { setGrantForm({ email: "", plan: "pro", role: "trader", days: 30 }); setGrantModalOpen(true); }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-medium hover:opacity-90 transition-opacity shadow-glow-purple"
              >
                <UserPlus className="w-4 h-4" strokeWidth={2.5} />
                <span>Grant Access</span>
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
                {toast.type === "success" ? <CheckCircle className="w-5 h-5" strokeWidth={2.5} /> : <AlertCircle className="w-5 h-5" strokeWidth={2.5} />}
                <span>{toast.message}</span>
              </div>
            </motion.div>
          )}

          {/* Stats Overview */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-1 md:grid-cols-4 gap-4"
          >
            <StatCard label="Total Users" value={users.length} icon={Users} color="text-neon-cyan" />
            <StatCard label="Active Subscriptions" value={users.filter((u) => u.subscriptionStatus === "active").length} icon={ShieldCheck} color="text-neon-green" />
            <StatCard label="Pro/Enterprise" value={users.filter((u) => u.plan !== "free").length} icon={Shield} color="text-neon-purple" />
            <StatCard label="API Calls Today" value={users.reduce((sum, u) => sum + u.apiCallsToday, 0).toLocaleString()} icon={Activity} color="text-neon-orange" />
          </motion.div>

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
                  {filteredUsers.length} / {users.length} users
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
                    <th className="px-5 py-4 text-center">Last Login</th>
                    <th className="px-5 py-4 text-center">API Calls</th>
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
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${getRoleColor(user.role).replace("text-", "bg-").replace(" border", "")}`}>
                            <User className="w-4 h-4" strokeWidth={2.5} style={{ color: "white" }} />
                          </div>
                          <div>
                            <p className="font-medium text-white">{user.name}</p>
                            <p className="text-xs text-text-muted">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-center">
                        <select
                          value={user.role}
                          onChange={(e) => { if (!editingUser) setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, role: e.target.value as any } : u)); }}
                          disabled={!!editingUser && editingUser.id !== user.id}
                          className={`w-auto px-2 py-1 rounded text-xs font-medium bg-transparent border-none text-white appearance-none cursor-pointer ${getRoleColor(user.role)}`}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>{r.toUpperCase()}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-5 py-4 text-center">
                        <select
                          value={user.plan}
                          onChange={(e) => { if (!editingUser) setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, plan: e.target.value as any } : u)); }}
                          disabled={!!editingUser && editingUser.id !== user.id}
                          className={`w-auto px-2 py-1 rounded text-xs font-medium bg-transparent border-none text-white appearance-none cursor-pointer ${getPlanColor(user.plan)}`}
                        >
                          {PLANS.map((p) => (
                            <option key={p} value={p}>{p.toUpperCase()}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-5 py-4 text-center">
                        <select
                          value={user.subscriptionStatus}
                          onChange={(e) => { if (!editingUser) setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, subscriptionStatus: e.target.value as any } : u)); }}
                          disabled={!!editingUser && editingUser.id !== user.id}
                          className={`w-auto px-2 py-1 rounded text-xs font-medium bg-transparent border-none text-white appearance-none cursor-pointer ${getStatusColor(user.subscriptionStatus)}`}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>{s.toUpperCase()}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-5 py-4 text-center font-mono text-text-secondary">
                        {formatDate(user.expiryDate)}
                      </td>
                      <td className="px-5 py-4 text-center">
                        <span className={`w-3 h-3 rounded-full ${user.isActive ? "bg-neon-green" : "bg-neon-red"}`} />
                      </td>
                      <td className="px-5 py-4 text-center text-text-secondary text-sm">
                        {user.lastLogin === "Never" ? "Never" : formatDateTime(user.lastLogin)}
                      </td>
                      <td className="px-5 py-4 text-center font-mono text-text-secondary">
                        {user.apiCallsToday.toLocaleString()}
                      </td>
                      <td className="px-5 py-4 text-center">
                        <div className="flex items-center justify-center gap-1">
                          {editingUser?.id === user.id ? (
                            <>
                              <motion.button
                                onClick={() => handleSaveEdit()}
                                disabled={isLoading}
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                                className="p-2 rounded-lg bg-neon-green/20 border border-neon-green/30 text-neon-green hover:bg-neon-green/30 transition-colors disabled:opacity-50"
                                title="Save Changes"
                              >
                                <CheckCircle className="w-4 h-4" strokeWidth={2.5} />
                              </motion.button>
                              <motion.button
                                onClick={() => setEditingUser(null)}
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                                className="p-2 rounded-lg bg-neon-red/20 border border-neon-red/30 text-neon-red hover:bg-neon-red/30 transition-colors"
                                title="Cancel"
                              >
                                <X className="w-4 h-4" strokeWidth={2.5} />
                              </motion.button>
                            </>
                          ) : (
                            <>
                              <motion.button
                                onClick={() => handleEditUser(user)}
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                                className="p-2 rounded-lg bg-neon-cyan/10 border border-neon-cyan/30 text-neon-cyan hover:bg-neon-cyan/20 transition-colors"
                                title="Edit"
                              >
                                <Edit className="w-4 h-4" strokeWidth={2.5} />
                              </motion.button>
                              {user.isActive ? (
                                <motion.button
                                  onClick={() => handleRevoke(user.id)}
                                  disabled={isLoading}
                                  whileHover={{ scale: 1.1 }}
                                  whileTap={{ scale: 0.9 }}
                                  className="p-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red hover:bg-neon-red/20 transition-colors disabled:opacity-50"
                                  title="Revoke Access"
                                >
                                  <UserX className="w-4 h-4" strokeWidth={2.5} />
                                </motion.button>
                              ) : (
                                <motion.button
                                  onClick={() => handleReactivate(user.id)}
                                  disabled={isLoading}
                                  whileHover={{ scale: 1.1 }}
                                  whileTap={{ scale: 0.9 }}
                                  className="p-2 rounded-lg bg-neon-green/10 border border-neon-green/30 text-neon-green hover:bg-neon-green/20 transition-colors disabled:opacity-50"
                                  title="Reactivate"
                                >
                                  <ShieldCheck className="w-4 h-4" strokeWidth={2.5} />
                                </motion.button>
                              )}
                            </>
                          )}
                        </div>
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

        {/* Grant Access Modal */}
        {grantModalOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={() => setGrantModalOpen(false)}
          >
            <motion.div
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md glass rounded-2xl border border-glow-border p-6"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <UserPlus className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
                  Grant Access
                </h3>
                <motion.button
                  onClick={() => setGrantModalOpen(false)}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  className="p-2 rounded-lg bg-card-bg/50 border border-glow-border text-text-muted hover:bg-card-bg hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" strokeWidth={2} />
                </motion.button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Email Address</label>
                  <input
                    type="email"
                    value={grantForm.email}
                    onChange={(e) => setGrantForm((prev) => ({ ...prev, email: e.target.value }))}
                    placeholder="user@example.com"
                    className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base"
                    autoFocus
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Plan</label>
                    <select
                      value={grantForm.plan}
                      onChange={(e) => setGrantForm((prev) => ({ ...prev, plan: e.target.value as any }))}
                      className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                    >
                      {PLANS.map((p) => (
                        <option key={p} value={p}>{p.toUpperCase()}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Role</label>
                    <select
                      value={grantForm.role}
                      onChange={(e) => setGrantForm((prev) => ({ ...prev, role: e.target.value as any }))}
                      className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r.toUpperCase()}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Access Duration (Days)</label>
                  <input
                    type="number"
                    value={grantForm.days}
                    onChange={(e) => setGrantForm((prev) => ({ ...prev, days: parseInt(e.target.value) || 30 }))}
                    min={1}
                    max={365}
                    className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base"
                  />
                </div>

                <div className="pt-4 border-t border-glow-border flex gap-3">
                  <motion.button
                    onClick={() => setGrantModalOpen(false)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 py-3 rounded-xl bg-card-bg/50 border border-glow-border text-text-secondary hover:bg-card-bg hover:text-white transition-colors"
                  >
                    Cancel
                  </motion.button>
                  <motion.button
                    onClick={handleGrantAccess}
                    disabled={isLoading}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-bold disabled:opacity-50 hover:opacity-90 transition-opacity shadow-glow-purple"
                  >
                    {isLoading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" strokeWidth={2.5} /> : "Grant Access"}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* Edit User Modal */}
        {editingUser && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={() => setEditingUser(null)}
          >
            <motion.div
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md glass rounded-2xl border border-glow-border p-6"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Edit className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                  Edit User
                </h3>
                <motion.button
                  onClick={() => setEditingUser(null)}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  className="p-2 rounded-lg bg-card-bg/50 border border-glow-border text-text-muted hover:bg-card-bg hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" strokeWidth={2} />
                </motion.button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Email</label>
                  <input
                    type="email"
                    value={editingUser.email}
                    onChange={(e) => setEditingUser((prev) => prev ? { ...prev, email: e.target.value } : null)}
                    className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base"
                  />
                </div>
                <div>
                  <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Name</label>
                  <input
                    type="text"
                    value={editingUser.name}
                    onChange={(e) => setEditingUser((prev) => prev ? { ...prev, name: e.target.value } : null)}
                    className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Role</label>
                    <select
                      value={editingUser.role}
                      onChange={(e) => setEditingUser((prev) => prev ? { ...prev, role: e.target.value as any } : null)}
                      className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r.toUpperCase()}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Plan</label>
                    <select
                      value={editingUser.plan}
                      onChange={(e) => setEditingUser((prev) => prev ? { ...prev, plan: e.target.value as any } : null)}
                      className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                    >
                      {PLANS.map((p) => (
                        <option key={p} value={p}>{p.toUpperCase()}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Subscription</label>
                    <select
                      value={editingUser.subscriptionStatus}
                      onChange={(e) => setEditingUser((prev) => prev ? { ...prev, subscriptionStatus: e.target.value as any } : null)}
                      className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>{s.toUpperCase()}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Expiry Date</label>
                    <input
                      type="date"
                      value={editingUser.expiryDate}
                      onChange={(e) => setEditingUser((prev) => prev ? { ...prev, expiryDate: e.target.value } : null)}
                      className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editingUser.isActive}
                      onChange={(e) => setEditingUser((prev) => prev ? { ...prev, isActive: e.target.checked } : null)}
                      className="w-4 h-4 rounded border-glow-border bg-card-bg text-neon-cyan focus:ring-neon-cyan"
                    />
                    <span className="text-sm text-text-secondary">Active</span>
                  </label>
                </div>

                <div className="pt-4 border-t border-glow-border flex gap-3">
                  <motion.button
                    onClick={() => setEditingUser(null)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 py-3 rounded-xl bg-card-bg/50 border border-glow-border text-text-secondary hover:bg-card-bg hover:text-white transition-colors"
                  >
                    Cancel
                  </motion.button>
                  <motion.button
                    onClick={handleSaveEdit}
                    disabled={isLoading}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold disabled:opacity-50 hover:opacity-90 transition-opacity shadow-glow-green"
                  >
                    {isLoading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" strokeWidth={2.5} /> : "Save Changes"}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number | string; icon: LucideIcon; color: string }) {
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