"use client";

import React, { useState } from "react";
import type { QueryPlanNode } from "../types";

interface QueryPlanProps {
  plan: QueryPlanNode;
}

function PlanNodeComponent({ node, depth = 0 }: { node: QueryPlanNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 3);
  const [showDetails, setShowDetails] = useState(false);

  const typeIcons: Record<string, string> = {
    Project: "📋",
    Sort: "🔀",
    Aggregate: "📊",
    Filter: "🔍",
    Join: "🔗",
    Scan: "💿",
    Limit: "✂️",
    Execute: "⚙️",
  };

  const icon = typeIcons[node.type] || "▪️";

  return (
    <div className="plan-node">
      <div
        className="plan-node-content"
        onClick={() => setShowDetails(!showDetails)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setShowDetails(!showDetails)}
      >
        <span className="plan-node-icon">{icon}</span>
        <span className="plan-node-type">{node.type}</span>
        <span className="plan-node-label">{node.label}</span>
        {node.estimated_cost && (
          <span className="plan-node-cost">
            cost: {node.estimated_cost.toFixed(1)}
          </span>
        )}
        {node.children.length > 0 && (
          <span
            style={{
              cursor: "pointer",
              fontSize: "12px",
              color: "var(--text-dim)",
              marginLeft: "4px",
            }}
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
          >
            {expanded ? "▼" : "▶"}
          </span>
        )}
      </div>

      {showDetails && Object.keys(node.details).length > 0 && (
        <div className="plan-node-details expanded">
          {Object.entries(node.details).map(([key, value]) => (
            <div key={key}>
              <strong style={{ color: "var(--neon-cyan)" }}>{key}:</strong>{" "}
              {Array.isArray(value)
                ? (value as string[]).join(", ")
                : String(value)}
            </div>
          ))}
        </div>
      )}

      {expanded && node.children.length > 0 && (
        <div className="plan-node-children">
          {node.children.map((child) => (
            <PlanNodeComponent key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function QueryPlan({ plan }: QueryPlanProps) {
  return (
    <div className="plan-tree">
      <PlanNodeComponent node={plan} />
    </div>
  );
}
