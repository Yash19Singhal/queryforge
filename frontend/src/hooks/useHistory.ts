"use client";

import { useState, useCallback, useEffect } from "react";
import type { HistoryEntry, SQLDialect } from "../types";

const STORAGE_KEY = "queryforge_history";
const MAX_HISTORY = 50;

interface UseHistoryReturn {
  history: HistoryEntry[];
  addEntry: (
    query: string,
    dialect: SQLDialect,
    complexityScore: number | null,
    optimizationsCount: number
  ) => void;
  removeEntry: (id: string) => void;
  clearHistory: () => void;
}

export function useHistory(): UseHistoryReturn {
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setHistory(JSON.parse(stored));
      }
    } catch {
      // Ignore parse errors
    }
  }, []);

  // Save to localStorage on change
  const persist = useCallback((entries: HistoryEntry[]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    } catch {
      // Ignore storage errors
    }
  }, []);

  const addEntry = useCallback(
    (
      query: string,
      dialect: SQLDialect,
      complexityScore: number | null,
      optimizationsCount: number
    ) => {
      const entry: HistoryEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        query: query.trim(),
        dialect,
        timestamp: Date.now(),
        complexity_score: complexityScore,
        optimizations_count: optimizationsCount,
      };

      setHistory((prev) => {
        const updated = [entry, ...prev].slice(0, MAX_HISTORY);
        persist(updated);
        return updated;
      });
    },
    [persist]
  );

  const removeEntry = useCallback(
    (id: string) => {
      setHistory((prev) => {
        const updated = prev.filter((e) => e.id !== id);
        persist(updated);
        return updated;
      });
    },
    [persist]
  );

  const clearHistory = useCallback(() => {
    setHistory([]);
    persist([]);
  }, [persist]);

  return { history, addEntry, removeEntry, clearHistory };
}
