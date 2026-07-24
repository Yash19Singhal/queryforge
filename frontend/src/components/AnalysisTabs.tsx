"use client";

import React, { useState } from "react";
import type { OptimizationApplied, IndexSuggestion, QueryPlanNode } from "../types";
import QueryPlan from "./QueryPlan";

interface AnalysisTabsProps {
  optimizations: OptimizationApplied[];
  indexSuggestions: IndexSuggestion[];
  queryPlan: QueryPlanNode | null;
  originalQuery: string;
  optimizedQuery: string;
}

type TabKey = "rewrites" | "indexes" | "plan" | "diff";

export default function AnalysisTabs({
  optimizations,
  indexSuggestions,
  queryPlan,
  originalQuery,
  optimizedQuery,
}: AnalysisTabsProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("rewrites");

  const tabs: { key: TabKey; label: string; badge?: number; icon: string }[] = [
    { key: "rewrites", label: "OPTIMIZATIONS", icon: "⚙️", badge: optimizations.length },
    { key: "indexes", label: "INDEX SUGGESTIONS", icon: "⚡", badge: indexSuggestions.length },
    { key: "plan", label: "EXPLAIN PLAN", icon: "🗺️" },
    { key: "diff", label: "DIFF VIEW", icon: "📝" },
  ];

  const impactBadgeClass = (impact: string) => {
    switch (impact) {
      case "high": return "pixel-badge pixel-badge--high";
      case "medium": return "pixel-badge pixel-badge--medium";
      case "low": return "pixel-badge pixel-badge--low";
      default: return "pixel-badge pixel-badge--medium";
    }
  };

  const categoryLabel = (category: string) =>
    category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  // Simple diff computation
  const computeDiff = () => {
    const origLines = originalQuery.split("\n");
    const optLines = optimizedQuery.split("\n");
    const maxLen = Math.max(origLines.length, optLines.length);
    const diff: { type: "added" | "removed" | "unchanged"; text: string }[] = [];

    for (let i = 0; i < maxLen; i++) {
      const orig = origLines[i] || "";
      const opt = optLines[i] || "";

      if (orig === opt) {
        diff.push({ type: "unchanged", text: orig });
      } else {
        if (orig) diff.push({ type: "removed", text: orig });
        if (opt) diff.push({ type: "added", text: opt });
      }
    }

    return diff;
  };

  return (
    <div className="analysis-section">
      <div className="analysis-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`analysis-tab ${activeTab === tab.key ? "active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            <span>{tab.icon}</span>
            {tab.label}
            {tab.badge !== undefined && tab.badge > 0 && (
              <span className="tab-badge">{tab.badge}</span>
            )}
          </button>
        ))}
      </div>

      <div className="analysis-content">
        {/* ── AI Rewrites Tab ──────────────────────────────── */}
        {activeTab === "rewrites" && (
          <>
            {optimizations.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✅</div>
                <div className="empty-state-text">NO ISSUES FOUND</div>
                <div className="empty-state-hint">
                  Your query looks well-optimized!
                </div>
              </div>
            ) : (
              optimizations.map((opt, i) => (
                <div key={i} className="optimization-card">
                  <div className="optimization-card-header">
                    <div className="optimization-card-title">
                      <span className="check-icon">✅</span>
                      {opt.description}
                    </div>
                    <div className="optimization-card-badges">
                      <span className="pixel-badge pixel-badge--category">
                        {categoryLabel(opt.category)}
                      </span>
                      <span className={impactBadgeClass(opt.impact)}>
                        {opt.impact.toUpperCase()} IMPACT
                      </span>
                    </div>
                  </div>
                  <div className="optimization-card-body">{opt.explanation}</div>
                </div>
              ))
            )}
          </>
        )}

        {/* ── Index Suggestions Tab ───────────────────────── */}
        {activeTab === "indexes" && (
          <>
            {indexSuggestions.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">🎯</div>
                <div className="empty-state-text">NO INDEX SUGGESTIONS</div>
                <div className="empty-state-hint">
                  Add schema context for index recommendations
                </div>
              </div>
            ) : (
              indexSuggestions.map((idx, i) => (
                <div key={i} className="optimization-card">
                  <div className="optimization-card-header">
                    <div className="optimization-card-title">
                      <span className="check-icon">✅</span>
                      Add {idx.type} index on {idx.table}({idx.columns.join(", ")})
                    </div>
                    <div className="optimization-card-badges">
                      <span className="pixel-badge pixel-badge--category">INDEX</span>
                      <span className={impactBadgeClass(idx.impact)}>
                        {idx.impact.toUpperCase()} IMPACT
                      </span>
                    </div>
                  </div>
                  <div className="optimization-card-body">
                    <p>{idx.rationale}</p>
                    <pre
                      style={{
                        marginTop: "8px",
                        padding: "8px 12px",
                        background: "var(--bg-deepest)",
                        border: "1px solid var(--border-color)",
                        fontFamily: "var(--font-code)",
                        fontSize: "13px",
                        color: "var(--neon-green)",
                        overflowX: "auto",
                      }}
                    >
                      {idx.create_statement}
                    </pre>
                  </div>
                </div>
              ))
            )}
          </>
        )}

        {/* ── Explain Plan Tab ────────────────────────────── */}
        {activeTab === "plan" && (
          <>
            {queryPlan ? (
              <QueryPlan plan={queryPlan} />
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">🗺️</div>
                <div className="empty-state-text">NO PLAN AVAILABLE</div>
                <div className="empty-state-hint">
                  Run an optimization to see the query execution plan
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Diff View Tab ───────────────────────────────── */}
        {activeTab === "diff" && (
          <div className="diff-container">
            <div className="diff-pane diff-pane--original">
              <div className="diff-pane-header">⬅ ORIGINAL</div>
              <div className="diff-pane-body">
                {computeDiff()
                  .filter((d) => d.type !== "added")
                  .map((d, i) => (
                    <span
                      key={i}
                      className={
                        d.type === "removed"
                          ? "diff-line--removed"
                          : "diff-line--unchanged"
                      }
                    >
                      {d.text}
                    </span>
                  ))}
              </div>
            </div>
            <div className="diff-pane diff-pane--optimized">
              <div className="diff-pane-header">OPTIMIZED ➡</div>
              <div className="diff-pane-body">
                {computeDiff()
                  .filter((d) => d.type !== "removed")
                  .map((d, i) => (
                    <span
                      key={i}
                      className={
                        d.type === "added"
                          ? "diff-line--added"
                          : "diff-line--unchanged"
                      }
                    >
                      {d.text}
                    </span>
                  ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
