"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface Ctx {
  selectedSymbol: string;
  setSelectedSymbol: (s: string) => void;
}

const SymbolContext = createContext<Ctx>({ selectedSymbol: "NIFTY 50", setSelectedSymbol: () => {} });

export function SymbolProvider({ children }: { children: ReactNode }) {
  const [selectedSymbol, setSelectedSymbol] = useState("NIFTY 50");
  return <SymbolContext.Provider value={{ selectedSymbol, setSelectedSymbol }}>{children}</SymbolContext.Provider>;
}

export const useSelectedSymbol = () => useContext(SymbolContext);
