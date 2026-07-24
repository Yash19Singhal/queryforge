/* ══════════════════════════════════════════════════════════════
   QueryForge — API Client
   ══════════════════════════════════════════════════════════════ */

import type {
  OptimizeRequest,
  OptimizeResponse,
  ParseResponse,
  FormatResponse,
  SQLDialect,
} from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

export async function optimizeQuery(
  query: string,
  dialect: SQLDialect,
  schemaContext: OptimizeRequest["schema_context"] = []
): Promise<OptimizeResponse> {
  return request<OptimizeResponse>("/api/optimize", {
    method: "POST",
    body: JSON.stringify({
      query,
      dialect,
      schema_context: schemaContext,
    }),
  });
}

export async function parseQuery(
  query: string,
  dialect: SQLDialect
): Promise<ParseResponse> {
  return request<ParseResponse>("/api/parse", {
    method: "POST",
    body: JSON.stringify({ query, dialect }),
  });
}

export async function formatQuery(
  query: string,
  dialect: SQLDialect
): Promise<FormatResponse> {
  return request<FormatResponse>("/api/format", {
    method: "POST",
    body: JSON.stringify({ query, dialect }),
  });
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return request("/api/health");
}
