"use client";

import { useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Users,
  User,
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
import { api } from "@/lib/api-client";

interface AdminUser {
  id: number;
  email: string;
  name?: string;
  role: string;
  plan?: string;
  subscription_status?: string;
  expiry_date?: string | null;
  created_at?: string;
  is_active?: boolean;
  last_login?: string | null;
  api_calls_today?: number;
  subscription?: {
    plan_type?: string;
    start_date?: string | null;
    end_date?: string | null;
    is_active?: boolean;
  } | null;
}

interface AdminUsersResponse {
  users: AdminUser[];
  total: number;
}

const PLANS = ["Basic", "Pro"] as const;
const ROLES = ["ADMIN", "USER"] as const;
const STATUSES = ["active", "expired", "cancelled", "trial"] as const;

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [grantModalOpen, setGrantModalOpen] = useState(false);
  const [grantForm, setGrantForm] = useState({
    email: "",
    plan: "Pro" as "Basic" | "Pro",
    days: 30,
  });
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const safeUsers = Array.isArray(users) ? users : [];

  const filteredUsers = safeUsers.filter((u) => {
    const email = typeof u?.email === "string" ? u.email : "";
    const name = typeof u?.name === "string" ? u.name : "";
    const query = searchQuery.toLowerCase();
    return email.toLowerCase().includes(query) || name.toLowerCase().includes(query);
  });

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    const checkAdmin = async () => {
      try {
        const data = await api.getAdminUsers();
        const responseUsers = Array.isArray(data?.users) ? (data.users as AdminUser[]) : [];
        setIsAdmin(true);
        setUsers(responseUsers);
        setLoadError(null);
      } catch {
        setUsers([]);
        setLoadError("Failed to load users. Please check your admin session.");
        setIsAdmin(false);
      } finally {
        setIsLoading(false);
        setAuthChecked(true);
      }
    };
    checkAdmin();
  }, []);

  if (authChecked && !isAdmin) {
    return (
      <div className="min-h-screen bg-true-black text-white flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center p-8 max-w-md"
        >
          <ShieldAlert className="w-16 h-16 mx-auto mb-4 text-neon-red/50" strokeWidth={1.5} />
          <h1 className="text-2xl font-bold text-white mb-2">{loadError ? "Unable to load users" : "Access Denied"}</h1>
          <p className="text-text-secondary mb-6">{loadError || "Admin panel is only accessible to administrators."}</p>
          <motion.button
            onClick={() => window.history.back()}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold shadow-glow-cyan"
          >
            Go Back
          </motion.button>
        </motion.div>
      </div>
    );
  }

  const handleRevoke = async (userId: number) => {
    const user = safeUsers.find((u) => u.id === userId);
    if (!user) return;

    if (!confirm(`Revoke access for ${user.email}? This will deactivate their account.`)) return;

    setIsLoading(true);
    try {
      await api.revokeAccess(userId);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_active: false, subscription_status: "cancelled" } : u)));
      showToast(`Access revoked for ${user.email}`, "success");
    } catch {
      showToast("Failed to revoke access", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleReactivate = async (userId: number) => {
    const user = safeUsers.find((u) => u.id === userId);
    if (!user) return;

    if (!confirm(`Reactivate access for ${user.email}?`)) return;

    setIsLoading(true);
    try {
      await api.grantAccess({ email: user.email, plan: "Pro", days: 30 });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_active: true, subscription_status: "active" } : u)));
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

    const existingUser = safeUsers.find((u) => u.email === grantForm.email);
    if (existingUser && existingUser.is_active) {
      showToast("User already has active access", "error");
      return;
    }

    setIsLoading(true);
    try {
      await api.grantAccess(grantForm);

      if (existingUser) {
        setUsers((prev) =>
          prev.map((u) =>
            u.id === existingUser.id
              ? { ...u, is_active: true, plan: grantForm.plan, subscription_status: "active", expiry_date: new Date(Date.now() + grantForm.days * 86400000).toISOString().split("T")[0] }
              : u
          )
        );
      } else {
        const newUser: AdminUser = {
          id: Date.now(),
          email: grantForm.email,
          name: grantForm.email.split("@")[0],
          role: "USER",
          plan: grantForm.plan,
          subscription_status: "active",
          expiry_date: new Date(Date.now() + grantForm.days * 86400000).toISOString().split("T")[0],
          created_at: new Date().toISOString().split("T")[0],
          is_active: true,
          last_login: null,
          api_calls_today: 0,
          subscription: {
            plan_type: grantForm.plan,
            start_date: new Date().toISOString().split("T")[0],
            end_date: new Date(Date.now() + grantForm.days * 86400000).toISOString().split("T")[0],
            is_active: true,
          },
        };
        setUsers((prev) => [newUser, ...prev]);
      }

      showToast(`Access granted to ${grantForm.email} (${grantForm.plan}, ${grantForm.days} days)`, "success");
      setGrantModalOpen(false);
      setGrantForm({ email: "", plan: "Pro", days: 30 });
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
      case "ADMIN": return "text-neon-purple bg-neon-purple/20 border-neon-purple/30";
      case "USER": return "text-neon-green bg-neon-green/20 border-neon-green/30";
      default: return "text-text-muted";
    }
  };

  const getPlanColor = (plan: string) => {
    switch (plan) {
      case "Pro": return "text-neon-green bg-neon-green/20 border-neon-green/30";
      case "Basic": return "text-text-muted bg-card-bg/50 border-glow-border";
      default: return "text-text-muted";
    }
  };

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return "N/A";
    try {
      return new Date(dateStr).toLocaleDateString();
    } catch {
      return dateStr;
    }
  };

  const formatDateTime = (dateStr: string | null | undefined) => {
    if (!dateStr) return "Never";
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  if (isLoading && !authChecked) {
    return (
      <div className="min-h-screen bg-true-black text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-neon-cyan" strokeWidth={2.5} />
          <span className="text-text-secondary">Checking permissions...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-7xl mx-auto w-full">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-3">
                <Shield className="w-8 h-8 text-neon-purple drop-shadow-[0_0_10px_rgba(168,85,247,0.6)]" strokeWidth={2.5} />
                <div>
                  <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Admin Panel</h1>
                  <p className="text-text-secondary">User management, subscriptions, and platform configuration</p>
                </div>
              </div>
              <motion.button
                onClick={() => { setGrantForm({ email: "", plan: "Pro", days: 30 }); setGrantModalOpen(true); }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-medium hover:opacity-90 transition-opacity shadow-glow-cyan"
              >
                <UserPlus className="w-4 h-4" strokeWidth={2.5} />
                <span>Grant Access</span>
              </motion.button>
            </div>
          </motion.div>

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

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
          >
            <StatCard label="Total Users" value={safeUsers.length} icon={Users} color="text-neon-cyan" />
            <StatCard label="Active Subscriptions" value={safeUsers.filter((u) => u.subscription_status === "active").length} icon={ShieldCheck} color="text-neon-green" />
            <StatCard label="Pro Users" value={safeUsers.filter((u) => u.plan === "Pro").length} icon={Shield} color="text-neon-purple" />
            <StatCard label="API Calls Today" value={safeUsers.reduce((sum, u) => sum + Number(u.api_calls_today ?? 0), 0).toLocaleString()} icon={Activity} color="text-neon-orange" />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass rounded-2xl border border-glow-border overflow-hidden"
          >
            <div className="px-4 md:px-6 py-4 border-b border-glow-border bg-card-bg/50 flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-white">User Management</h2>
                <span className="text-xs px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">
                  {filteredUsers.length} / {safeUsers.length} users
                </span>
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search users..."
                  className="w-full md:w-64 pl-10 pr-4 py-2 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white placeholder-text-muted text-sm"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-[1000px] w-full border-collapse" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                    <th className="px-3 md:px-5 py-3 md:py-4 text-left">User</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Role</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Plan</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Subscription</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Expiry</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Status</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Last Login</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">API Calls</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user, index) => {
                    const userName = user?.name ?? user?.email ?? "Unknown user";
                    const role = user?.role ?? "USER";
                    const plan = user?.plan ?? user?.subscription?.plan_type ?? "Basic";
                    const subscriptionStatus = user?.subscription_status ?? "inactive";
                    const expiryDate = user?.expiry_date ?? user?.subscription?.end_date ?? null;
                    const isActive = Boolean(user?.is_active);
                    const lastLogin = user?.last_login ?? null;
                    const apiCalls = Number(user?.api_calls_today ?? 0);

                    return (
                      <motion.tr
                        key={user.id ?? index}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.03 }}
                        className="border-b border-glow-border/50 hover:bg-card-bg/30 transition-colors"
                      >
                        <td className="px-3 md:px-5 py-3 md:py-4">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${getRoleColor(role).replace("text-", "bg-").replace(" border", "")}`}>
                              <User className="w-4 h-4" strokeWidth={2.5} style={{ color: "white" }} />
                            </div>
                            <div>
                              <p className="font-medium text-white">{userName}</p>
                              <p className="text-xs text-text-muted">{user.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getRoleColor(role)}`}>
                            {role}
                          </span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getPlanColor(plan)}`}>
                            {plan}
                          </span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(subscriptionStatus)}`}>
                            {(subscriptionStatus || "inactive").toUpperCase()}
                          </span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center font-mono text-text-secondary">
                          {formatDate(expiryDate)}
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`w-3 h-3 rounded-full ${isActive ? "bg-neon-green" : "bg-neon-red"}`} />
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center text-text-secondary text-sm">
                          {formatDateTime(lastLogin)}
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center font-mono text-text-secondary">
                          {apiCalls.toLocaleString()}
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
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
                                {isActive ? (
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
                    );
                  })}
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Plan</label>
                    <div className="relative">
                      <select
                        value={grantForm.plan}
                        onChange={(e) => setGrantForm((prev) => ({ ...prev, plan: e.target.value as "Basic" | "Pro" }))}
                        className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                      >
                        {PLANS.map((p) => (
                          <option key={p} value={p}>{p.toUpperCase()}</option>
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
                    className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-bold disabled:opacity-50 hover:opacity-90 transition-opacity shadow-glow-cyan"
                  >
                    {isLoading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" strokeWidth={2.5} /> : "Grant Access"}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

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
                    value={editingUser.name ?? ""}
                    onChange={(e) => setEditingUser((prev) => prev ? { ...prev, name: e.target.value } : null)}
                    className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Role</label>
                    <div className="relative">
                      <select
                        value={editingUser.role}
                        onChange={(e) => setEditingUser((prev) => prev ? { ...prev, role: e.target.value } : null)}
                        className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Plan</label>
                    <div className="relative">
                      <select
                        value={editingUser.plan ?? "Basic"}
                        onChange={(e) => setEditingUser((prev) => prev ? { ...prev, plan: e.target.value } : null)}
                        className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                      >
                        {PLANS.map((p) => (
                          <option key={p} value={p}>{p}</option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Subscription</label>
                    <div className="relative">
                      <select
                        value={editingUser.subscription_status ?? "active"}
                        onChange={(e) => setEditingUser((prev) => prev ? { ...prev, subscription_status: e.target.value } : null)}
                        className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>{s.toUpperCase()}</option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Expiry Date</label>
                    <input
                      type="date"
                      value={editingUser.expiry_date || ""}
                      onChange={(e) => setEditingUser((prev) => prev ? { ...prev, expiry_date: e.target.value } : null)}
                      className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={Boolean(editingUser.is_active)}
                      onChange={(e) => setEditingUser((prev) => prev ? { ...prev, is_active: e.target.checked } : null)}
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
      className="glass rounded-2xl border border-glow-border p-4 md:p-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wider">{label}</p>
          <p className="text-2xl md:text-3xl font-bold text-white mt-1">{value}</p>
        </div>
        <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl flex items-center justify-center" style={{ backgroundColor: "rgba(255,255,255,0.03)" }}>
          <Icon className="w-6 h-6 md:w-7 md:h-7" strokeWidth={2.5} style={{ color: "currentColor" }} />
        </div>
      </div>
    </motion.div>
  );
}

