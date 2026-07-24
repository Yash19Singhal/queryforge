"use client";

import React from "react";
import type { HistoryEntry } from "../types";

interface HistoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  history: HistoryEntry[];
  onSelectEntry: (entry: HistoryEntry) => void;
  onClearHistory: () => void;
}

export default function HistoryPanel({
  isOpen,
  onClose,
  history,
  onSelectEntry,
  onClearHistory,
}: HistoryPanelProps) {
  const formatTime = (timestamp: number) => {
    const d = new Date(timestamp);
    const now = Date.now();
    const diff = now - timestamp;

    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  };

  return (
    <>
      <div
        className={`history-overlay ${isOpen ? "open" : ""}`}
        onClick={onClose}
      />
      <div className={`history-sidebar ${isOpen ? "open" : ""}`}>
        <div className="history-header">
          <span className="history-title">📜 QUERY HISTORY</span>
          <div style={{ display: "flex", gap: "8px" }}>
            {history.length > 0 && (
              <button
                className="pixel-btn pixel-btn--ghost"
                style={{ padding: "4px 10px", fontSize: "7px" }}
                onClick={onClearHistory}
              >
                CLEAR
              </button>
            )}
            <button
              className="pixel-btn pixel-btn--ghost"
              style={{ padding: "4px 10px", fontSize: "7px" }}
              onClick={onClose}
            >
              ✕ CLOSE
            </button>
          </div>
        </div>

        <div className="history-list">
          {history.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📭</div>
              <div className="empty-state-text">NO HISTORY YET</div>
              <div className="empty-state-hint">
                Your optimized queries will appear here
              </div>
            </div>
          ) : (
            history.map((entry) => (
              <div
                key={entry.id}
                className="history-item"
                onClick={() => {
                  onSelectEntry(entry);
                  onClose();
                }}
              >
                <div className="history-item-query">{entry.query}</div>
                <div className="history-item-meta">
                  <span>{entry.dialect.toUpperCase()}</span>
                  <span>
                    {entry.optimizations_count > 0
                      ? `${entry.optimizations_count} optimizations`
                      : "No issues"}
                  </span>
                  <span>{formatTime(entry.timestamp)}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
