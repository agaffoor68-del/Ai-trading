"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Loader2, Maximize2, Wifi } from "lucide-react";
import {
  useOptionChain,
  useExpiries,
  SERVER_WAKING_MESSAGE,
} from "@/lib/hooks";

interface OptionStrike {
  strike: number;
  isATM: boolean;
  ceSymbol: string | null;
  ceLtp: number;
  peSymbol: string | null;
  peLtp: number;
}

interface IndexInfo {
  label: string;
  value: string;
}

const INDEXES: IndexInfo[] = [
  { label: "NIFTY", value: "NIFTY" },
  { label: "BANKNIFTY", value: "BANKNIFTY" },
  { label: "FINNIFTY", value: "FINNIFTY" },
  { label: "MIDCPNIFTY", value: "MIDCPNIFTY" },
  { label: "SENSEX", value: "SENSEX" },
];

export default function OptionChainPage() {
  const [selectedIndex, setSelectedIndex] = useState<IndexInfo>(INDEXES[0]);
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [strikes, setStrikes] = useState(10);
  const [searchQuery, setSearchQuery] = useState("");

  const { expiries, isLoading: expiriesLoading } = useExpiries(selectedIndex.value);

  useEffect(() => {
    if (expiries.length > 0 && (!selectedExpiry || !expiries.includes(selectedExpiry))) {
      setSelectedExpiry(expiries[0]);
    }
  }, [expiries, selectedExpiry]);

  const {
    chainData,
    isLoading,
    isError,
    error,
    isFyersNotConnected,
    isFyersConnected,
    isServerWakingUp: wakingUp,
    mutate,
  } = useOptionChain(selectedIndex.value, selectedExpiry, strikes);

  const transformedStrikes = useMemo<OptionStrike[]>(() => {
    if (!Array.isArray(chainData?.option_chain)) return [];

    return chainData.option_chain.map((row) => ({
      strike: Number(row.strike),
      isATM: Boolean(row.is_atm),
      ceSymbol: row.call?.symbol ?? null,
      ceLtp: row.call?.ltp == null ? 0 : Number(row.call.ltp),
      peSymbol: row.put?.symbol ?? null,
      peLtp: row.put?.ltp == null ? 0 : Number(row.put.ltp),
    }));
  }, [chainData]);

  const filteredStrikes = useMemo(() => {
    if (!searchQuery.trim()) return transformedStrikes;
    return transformedStrikes.filter((row) =>
      String(row.strike).includes(searchQuery.trim())
    );
  }, [transformedStrikes, searchQuery]);

  const formatNumber = (value: number) =>
    value.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden min-h-[350px] flex flex-col"
        aria-busy="true"
      >
        <div className="flex items-center px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <h3 className="font-semibold text-white">Options Chain</h3>
          <span className="ml-2 text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan">
            {selectedIndex.label}
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center gap-3 text-text-secondary">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading option chain...
        </div>
      </motion.div>
    );
  }

  if (isError) {
    const showConnectCard = isFyersNotConnected && !isFyersConnected;

    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden min-h-[350px] flex flex-col"
      >
        <div className="flex items-center px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <h3 className="font-semibold text-white">Options Chain</h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center max-w-md">
            {wakingUp ? (
              <>
                <Loader2 className="w-7 h-7 mx-auto mb-3 text-neon-cyan animate-spin" />
                <p className="font-medium text-white">{SERVER_WAKING_MESSAGE}</p>
              </>
            ) : (
              <>
                <AlertCircle className="w-7 h-7 mx-auto mb-3 text-neon-red" />
                <p className="font-medium text-white">
                  {showConnectCard ? "Fyers is not connected" : "Failed to load option chain"}
                </p>
                <p className="text-sm mt-2 text-text-muted">
                  {showConnectCard ? "Connect your Fyers account to load the option chain." : error}
                </p>
                {showConnectCard && (
                  <motion.a
                    href="/settings"
                    className="mt-4 inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold"
                  >
                    <Wifi className="w-4 h-4" />
                    Connect Fyers
                  </motion.a>
                )}
              </>
            )}
          </div>
        </div>
      </motion.div>
    );
  }

  if (!chainData || transformedStrikes.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden min-h-[350px] flex flex-col"
      >
        <div className="flex items-center px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <h3 className="font-semibold text-white">Options Chain</h3>
          <span className="ml-2 text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan">
            {selectedIndex.label}
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center text-text-muted">
          <div className="text-center">
            <AlertCircle className="mx-auto mb-2 h-8 w-8 text-neon-orange/50" />
            <p>No options available for this expiry</p>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white">Options Chain</h3>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan">
            {selectedIndex.label}
          </span>
          {selectedExpiry && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange">
              {selectedExpiry}
            </span>
          )}
          {chainData.atm_strike > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-purple/20 text-neon-purple">
              ATM: {chainData.atm_strike.toLocaleString()}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <select
            aria-label="Underlying symbol"
            value={selectedIndex.value}
            onChange={(event) => {
              const index = INDEXES.find((item) => item.value === event.target.value) ?? INDEXES[0];
              setSelectedIndex(index);
              setSelectedExpiry("");
            }}
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm"
          >
            {INDEXES.map((index) => (
              <option key={index.value} value={index.value}>{index.label}</option>
            ))}
          </select>

          <select
            aria-label="Expiry"
            value={selectedExpiry}
            onChange={(event) => setSelectedExpiry(event.target.value)}
            disabled={expiriesLoading || expiries.length === 0}
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm"
          >
            {expiries.map((expiry) => (
              <option key={expiry} value={expiry}>{expiry}</option>
            ))}
          </select>

          <select
            aria-label="Number of strikes"
            value={strikes}
            onChange={(event) => setStrikes(Number(event.target.value))}
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm"
          >
            {[5, 10, 15, 20].map((count) => (
              <option key={count} value={count}>{count} strikes each side</option>
            ))}
          </select>

          <input
            type="text"
            aria-label="Search strikes"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search strike..."
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm w-32"
          />

          <motion.button
            onClick={() => mutate()}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="p-1.5 rounded-lg bg-card-bg border border-glow-border"
            title="Refresh"
            aria-label="Refresh options chain"
          >
            <Maximize2 className="w-4 h-4 text-text-secondary" />
          </motion.button>
        </div>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-auto p-2">
        <table className="w-full text-sm min-w-[800px]" role="grid">
          <thead>
            <tr className="border-b border-glow-border text-text-muted sticky top-0 bg-card-bg/80">
              <th className="px-2 py-2 text-right">Call</th>
              <th className="px-2 py-2 text-center">Strike</th>
              <th className="px-2 py-2 text-left">Put</th>
            </tr>
          </thead>
          <tbody>
            {filteredStrikes.map((row) => (
              <motion.tr
                key={row.strike}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={row.isATM ? "bg-neon-cyan/10" : "hover:bg-card-bg/50"}
              >
                <td className="px-2 py-2 text-right font-mono font-medium text-neon-green">
                  {formatNumber(row.ceLtp)}
                  {row.ceSymbol && (
                    <span className="ml-2 text-xs text-text-secondary">{row.ceSymbol}</span>
                  )}
                </td>
                <td className={`px-2 py-2 text-center font-mono font-bold ${row.isATM ? "text-neon-cyan" : "text-white"}`}>
                  {row.strike.toLocaleString()}
                  {row.isATM && <span className="ml-1 text-[10px]">ATM</span>}
                </td>
                <td className="px-2 py-2 text-left font-mono font-medium text-neon-red">
                  {formatNumber(row.peLtp)}
                  {row.peSymbol && (
                    <span className="ml-2 text-xs text-text-secondary">{row.peSymbol}</span>
                  )}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
