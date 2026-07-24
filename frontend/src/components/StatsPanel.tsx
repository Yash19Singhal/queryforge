"use client";

import React from "react";
import type { ComplexityResult, PerformanceGain, RowsScanned, Bottleneck, CostEstimate } from "@/types";
import PixelProgress from "./PixelProgress";

interface StatsPanelProps {
  complexity: ComplexityResult;
  performanceGain: PerformanceGain;
  rowsScanned: RowsScanned | null;
  bottleneck: Bottleneck | null;
  costEstimate: CostEstimate;
}

export default function StatsPanel({
  complexity,
  performanceGain,
  rowsScanned,
  bottleneck,
  costEstimate,
}: StatsPanelProps) {
  const progressColor =
    complexity.score <= 30 ? "green" : complexity.score <= 60 ? "amber" : "red";

  return (
    <div className="stats-grid">
      {/* Complexity */}
      <div className="stat-card stat-card--complexity">
        <div className="stat-label">
          <span>🛡️</span> COMPLEXITY
        </div>
        <div className="stat-value">{complexity.score}/100</div>
        <div className="stat-description">{complexity.label}</div>
        <PixelProgress value={complexity.score} colorClass={progressColor} />
      </div>

      {/* Performance Gain */}
      <div className="stat-card stat-card--performance">
        <div className="stat-label">
          <span>⚡</span> PERFORMANCE GAIN
        </div>
        <div className="stat-value">{performanceGain.estimate}</div>
        <div className="stat-description">{performanceGain.description}</div>
      </div>

      {/* Rows Scanned */}
      <div className="stat-card stat-card--rows">
        <div className="stat-label">
          <span>📊</span> ROWS SCANNED
        </div>
        <div className="stat-value">
          {rowsScanned ? rowsScanned.description : "N/A"}
        </div>
        <div className="stat-description">
          {rowsScanned ? `${rowsScanned.before} → ${rowsScanned.after}` : "Add schema for estimates"}
        </div>
      </div>

      {/* Bottleneck */}
      <div className="stat-card stat-card--bottleneck">
        <div className="stat-label">
          <span>⚠️</span> BOTTLENECK
        </div>
        <div className="stat-value" style={{ fontSize: bottleneck ? "18px" : "28px" }}>
          {bottleneck
            ? bottleneck.type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
            : "None"}
        </div>
        <div className="stat-description">
          {bottleneck?.description || "No major bottlenecks detected"}
        </div>
      </div>

      {/* Cost Comparison (spans full width on next row) */}
      {costEstimate && (
        <div className="stat-card" style={{ gridColumn: "1 / -1" }}>
          <div className="stat-label">
            <span>💰</span> COST COMPARISON
          </div>
          <div className="cost-bar">
            <span className="cost-bar-label">Before</span>
            <div className="cost-bar-track">
              <div
                className="cost-bar-fill cost-bar-fill--before"
                style={{ width: "100%" }}
              />
            </div>
            <span className="cost-bar-value">{costEstimate.before.toFixed(1)}</span>
          </div>
          <div className="cost-bar">
            <span className="cost-bar-label">After</span>
            <div className="cost-bar-track">
              <div
                className="cost-bar-fill cost-bar-fill--after"
                style={{
                  width: `${Math.max(5, (costEstimate.after / costEstimate.before) * 100)}%`,
                }}
              />
            </div>
            <span className="cost-bar-value">{costEstimate.after.toFixed(1)}</span>
          </div>
          <div className="stat-description" style={{ marginTop: "8px" }}>
            {costEstimate.improvement_percent > 0
              ? `${costEstimate.improvement_percent.toFixed(1)}% cost reduction`
              : "No cost change"}
          </div>
        </div>
      )}
    </div>
  );
}
