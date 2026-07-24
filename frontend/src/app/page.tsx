"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import type { SQLDialect, TableSchema } from "../types";
import { useOptimizer } from "../hooks/useOptimizer";
import { useHistory } from "../hooks/useHistory";
import StatsPanel from "../components/StatsPanel";
import AnalysisTabs from "../components/AnalysisTabs";
import SchemaInput from "../components/SchemaInput";
import HistoryPanel from "../components/HistoryPanel";

const DIALECTS: { key: SQLDialect; label: string }[] = [
  { key: "postgresql", label: "PostgreSQL" },
  { key: "mysql", label: "MySQL" },
  { key: "sqlite", label: "SQLite" },
];

const SAMPLE_QUERY = `-- Type or paste your SQL here
SELECT u.name, COUNT(o.id) AS orders
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.country = 'US'
GROUP BY u.name
ORDER BY orders DESC
LIMIT 20;`;

// ── SQL Syntax Highlighter ───────────────────────────────────

function highlightSQL(sql: string): React.ReactNode[] {
  const keywords = new Set([
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER",
    "FULL", "CROSS", "ON", "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN",
    "LIKE", "IS", "NULL", "AS", "GROUP", "BY", "ORDER", "HAVING", "LIMIT",
    "OFFSET", "UNION", "ALL", "DISTINCT", "CASE", "WHEN", "THEN", "ELSE",
    "END", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE", "CREATE",
    "TABLE", "INDEX", "ALTER", "DROP", "ASC", "DESC", "WITH", "RECURSIVE",
    "OVER", "PARTITION", "ROWS", "RANGE", "UNBOUNDED", "PRECEDING",
    "FOLLOWING", "CURRENT", "ROW", "FILTER", "EXCEPT", "INTERSECT",
  ]);
  const functions = new Set([
    "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "NULLIF", "CAST",
    "LOWER", "UPPER", "TRIM", "LENGTH", "SUBSTRING", "CONCAT", "NOW",
    "DATE", "EXTRACT", "ROUND", "ABS", "FLOOR", "CEIL", "STRING_AGG",
    "ARRAY_AGG", "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD",
    "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE",
  ]);

  const lines = sql.split("\n");
  return lines.map((line, lineIdx) => {
    const tokens: React.ReactNode[] = [];
    // Simple tokenizer
    const regex = /('(?:[^'\\]|\\.)*')|(--.*)|([\w.]+)|([^\w\s.]+)|(\s+)/g;
    let match;
    let tokenIdx = 0;

    while ((match = regex.exec(line)) !== null) {
      const [full, str, comment, word, op, space] = match;
      const key = `${lineIdx}-${tokenIdx++}`;

      if (comment) {
        tokens.push(<span key={key} className="sql-comment">{full}</span>);
      } else if (str) {
        tokens.push(<span key={key} className="sql-string">{full}</span>);
      } else if (word) {
        const upper = word.toUpperCase();
        if (keywords.has(upper)) {
          tokens.push(<span key={key} className="sql-keyword">{word}</span>);
        } else if (functions.has(upper)) {
          tokens.push(<span key={key} className="sql-function">{word}</span>);
        } else if (/^\d+(\.\d+)?$/.test(word)) {
          tokens.push(<span key={key} className="sql-number">{word}</span>);
        } else {
          tokens.push(<span key={key}>{word}</span>);
        }
      } else if (op) {
        tokens.push(<span key={key} className="sql-operator">{full}</span>);
      } else if (space) {
        tokens.push(<span key={key}>{full}</span>);
      }
    }

    return (
      <React.Fragment key={lineIdx}>
        {tokens}
        {lineIdx < lines.length - 1 && "\n"}
      </React.Fragment>
    );
  });
}

// ── Main Page Component ──────────────────────────────────────

export default function Home() {
  const [query, setQuery] = useState(SAMPLE_QUERY);
  const [dialect, setDialect] = useState<SQLDialect>("postgresql");
  const [schema, setSchema] = useState<TableSchema[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { result, isLoading, error, optimize, format } = useOptimizer();
  const { history, addEntry, clearHistory } = useHistory();

  // Show toast
  const showToast = useCallback((message: string) => {
    setToast(message);
    setTimeout(() => setToast(null), 2500);
  }, []);

  // Handle optimize
  const handleOptimize = useCallback(async () => {
    await optimize(query, dialect, schema);
  }, [query, dialect, schema, optimize]);

  // Add to history after successful optimization
  useEffect(() => {
    if (result) {
      addEntry(
        query,
        dialect,
        result.complexity.score,
        result.optimizations_applied.length
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  // Handle format
  const handleFormat = useCallback(async () => {
    const formatted = await format(query, dialect);
    setQuery(formatted);
    showToast("Query formatted!");
  }, [query, dialect, format, showToast]);

  // Copy to clipboard
  const copyToClipboard = useCallback(
    (text: string) => {
      navigator.clipboard.writeText(text);
      showToast("Copied to clipboard!");
    },
    [showToast]
  );

  // Line numbers
  const lineCount = query.split("\n").length;
  const charCount = query.length;

  // Keyboard shortcut: Ctrl+Enter to optimize
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleOptimize();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleOptimize]);

  return (
    <div className="app-container">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">⚡</div>
          <div>
            <h1 className="header-title">QUERYFORGE</h1>
            <div className="header-subtitle">OPTIMIZER · V1.0</div>
          </div>
          <div className="header-status">
            <div className="status-dot" />
            ENGINE READY
          </div>
        </div>
        <div className="header-actions">
          <button
            className="pixel-btn pixel-btn--ghost"
            onClick={() => setHistoryOpen(true)}
          >
            📜 HISTORY
          </button>
        </div>
      </header>

      {/* ── Dialect Selector ────────────────────────────────── */}
      <div className="dialect-bar">
        <span className="dialect-label">DIALECT</span>
        <div className="dialect-tabs">
          {DIALECTS.map((d) => (
            <button
              key={d.key}
              className={`dialect-tab ${dialect === d.key ? "active" : ""}`}
              onClick={() => setDialect(d.key)}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
          <button
            className="pixel-btn pixel-btn--secondary"
            onClick={handleFormat}
          >
            {"</>"} FORMAT
          </button>
          <button
            className="pixel-btn pixel-btn--secondary"
            onClick={() => copyToClipboard(query)}
          >
            📋 COPY
          </button>
          <button
            className="pixel-btn pixel-btn--primary"
            onClick={handleOptimize}
            disabled={isLoading}
          >
            {isLoading ? "⏳ ANALYZING..." : "▶ OPTIMIZE QUERY"}
          </button>
        </div>
      </div>

      {/* ── Schema Input ────────────────────────────────────── */}
      <SchemaInput schema={schema} onSchemaChange={setSchema} />

      {/* ── Query Editor ────────────────────────────────────── */}
      <div className="editor-panel">
        <div className="editor-header">
          <div className="editor-title">
            <div className="editor-title-dot" />
            ORIGINAL QUERY
          </div>
          <div className="editor-meta">
            {charCount} chars · {lineCount} lines · Ctrl+Enter to optimize
          </div>
        </div>
        <div className="editor-body">
          <div className="line-numbers">
            {Array.from({ length: lineCount }).map((_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>
          <textarea
            ref={textareaRef}
            className="editor-textarea"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            spellCheck={false}
            autoCorrect="off"
            autoCapitalize="off"
          />
        </div>
      </div>

      {/* ── Error Display ───────────────────────────────────── */}
      {error && (
        <div
          style={{
            background: "rgba(255, 59, 59, 0.1)",
            border: "1px solid var(--neon-red)",
            padding: "12px 16px",
            marginBottom: "20px",
            fontFamily: "var(--font-terminal)",
            fontSize: "16px",
            color: "var(--neon-red)",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* ── Loading State ───────────────────────────────────── */}
      {isLoading && (
        <div className="loading-container">
          <div className="loading-bar">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="loading-bar-segment" />
            ))}
          </div>
          <div className="loading-text">ANALYZING QUERY...</div>
        </div>
      )}

      {/* ── Results ─────────────────────────────────────────── */}
      {result && !isLoading && (
        <>
          {/* Stats Panel */}
          <StatsPanel
            complexity={result.complexity}
            performanceGain={result.performance_gain}
            rowsScanned={result.rows_scanned}
            bottleneck={result.bottleneck}
            costEstimate={result.cost_estimate}
          />

          {/* Optimized Query */}
          <div className="optimized-panel">
            <div className="optimized-header">
              <div className="optimized-title">
                <span>✨</span>
                OPTIMIZED QUERY
              </div>
              <button
                className="pixel-btn pixel-btn--ghost"
                style={{ padding: "4px 12px", fontSize: "7px" }}
                onClick={() => copyToClipboard(result.optimized_query)}
              >
                📋 COPY
              </button>
            </div>
            <div className="optimized-body">
              <div className="line-numbers">
                {result.optimized_query.split("\n").map((_, i) => (
                  <div key={i}>{i + 1}</div>
                ))}
              </div>
              {highlightSQL(result.optimized_query)}
            </div>
          </div>

          {/* Analysis Tabs */}
          <AnalysisTabs
            optimizations={result.optimizations_applied}
            indexSuggestions={result.index_suggestions}
            queryPlan={result.query_plan}
            originalQuery={result.original_query}
            optimizedQuery={result.optimized_query}
          />
        </>
      )}

      {/* ── Empty State (before first optimization) ─────────── */}
      {!result && !isLoading && !error && (
        <div className="empty-state" style={{ padding: "64px 24px" }}>
          <div className="empty-state-icon">⚔️</div>
          <div className="empty-state-text">READY TO FORGE</div>
          <div className="empty-state-hint">
            Paste a SQL query above and hit ▶ OPTIMIZE QUERY
          </div>
        </div>
      )}

      {/* ── Footer ──────────────────────────────────────────── */}
      <footer className="footer">
        QueryForge v1.0 · Built with FastAPI + Next.js ·{" "}
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
      </footer>

      {/* ── History Panel ───────────────────────────────────── */}
      <HistoryPanel
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        history={history}
        onSelectEntry={(entry) => {
          setQuery(entry.query);
          setDialect(entry.dialect);
        }}
        onClearHistory={clearHistory}
      />

      {/* ── Toast ───────────────────────────────────────────── */}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
