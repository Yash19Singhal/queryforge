"use client";

import { useState, useCallback } from "react";
import type {
  OptimizeResponse,
  SQLDialect,
  TableSchema,
} from "../types";
import { optimizeQuery, formatQuery } from "../lib/api";

interface UseOptimizerReturn {
  result: OptimizeResponse | null;
  isLoading: boolean;
  error: string | null;
  optimize: (query: string, dialect: SQLDialect, schema: TableSchema[]) => Promise<void>;
  format: (query: string, dialect: SQLDialect) => Promise<string>;
  reset: () => void;
}

export function useOptimizer(): UseOptimizerReturn {
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const optimize = useCallback(
    async (query: string, dialect: SQLDialect, schema: TableSchema[]) => {
      if (!query.trim()) {
        setError("Please enter a SQL query");
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await optimizeQuery(query, dialect, schema);
        setResult(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to optimize query");
        setResult(null);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const format = useCallback(
    async (query: string, dialect: SQLDialect): Promise<string> => {
      try {
        const response = await formatQuery(query, dialect);
        return response.formatted_query;
      } catch {
        return query;
      }
    },
    []
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, isLoading, error, optimize, format, reset };
}
