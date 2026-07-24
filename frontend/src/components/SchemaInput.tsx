"use client";

import React, { useState } from "react";
import type { TableSchema, ColumnDefinition, IndexDefinition } from "@/types";

interface SchemaInputProps {
  schema: TableSchema[];
  onSchemaChange: (schema: TableSchema[]) => void;
}

export default function SchemaInput({ schema, onSchemaChange }: SchemaInputProps) {
  const [isOpen, setIsOpen] = useState(false);

  const addTable = () => {
    onSchemaChange([
      ...schema,
      {
        name: "",
        columns: [{ name: "", data_type: "varchar", is_nullable: true }],
        indexes: [],
        approximate_rows: null,
      },
    ]);
  };

  const updateTable = (index: number, updates: Partial<TableSchema>) => {
    const updated = [...schema];
    updated[index] = { ...updated[index], ...updates };
    onSchemaChange(updated);
  };

  const removeTable = (index: number) => {
    onSchemaChange(schema.filter((_, i) => i !== index));
  };

  const addColumn = (tableIndex: number) => {
    const updated = [...schema];
    updated[tableIndex].columns.push({
      name: "",
      data_type: "varchar",
      is_nullable: true,
    });
    onSchemaChange(updated);
  };

  const updateColumn = (
    tableIndex: number,
    colIndex: number,
    updates: Partial<ColumnDefinition>
  ) => {
    const updated = [...schema];
    updated[tableIndex].columns[colIndex] = {
      ...updated[tableIndex].columns[colIndex],
      ...updates,
    };
    onSchemaChange(updated);
  };

  const removeColumn = (tableIndex: number, colIndex: number) => {
    const updated = [...schema];
    updated[tableIndex].columns = updated[tableIndex].columns.filter(
      (_, i) => i !== colIndex
    );
    onSchemaChange(updated);
  };

  const addIndex = (tableIndex: number) => {
    const updated = [...schema];
    updated[tableIndex].indexes.push({
      name: "",
      columns: [],
      is_unique: false,
    });
    onSchemaChange(updated);
  };

  const updateIndex = (
    tableIndex: number,
    idxIndex: number,
    updates: Partial<IndexDefinition>
  ) => {
    const updated = [...schema];
    updated[tableIndex].indexes[idxIndex] = {
      ...updated[tableIndex].indexes[idxIndex],
      ...updates,
    };
    onSchemaChange(updated);
  };

  const removeIndex = (tableIndex: number, idxIndex: number) => {
    const updated = [...schema];
    updated[tableIndex].indexes = updated[tableIndex].indexes.filter(
      (_, i) => i !== idxIndex
    );
    onSchemaChange(updated);
  };

  return (
    <div className="schema-panel">
      <button className="schema-toggle" onClick={() => setIsOpen(!isOpen)}>
        <span className="schema-toggle-title">
          <span>📦</span>
          SCHEMA CONTEXT (OPTIONAL)
          {schema.length > 0 && (
            <span className="tab-badge">{schema.length}</span>
          )}
        </span>
        <span className={`schema-toggle-arrow ${isOpen ? "open" : ""}`}>
          ▼
        </span>
      </button>

      <div className={`schema-content ${isOpen ? "open" : ""}`}>
        <div style={{ marginBottom: "8px", fontFamily: "var(--font-terminal)", fontSize: "15px", color: "var(--text-dim)" }}>
          Define your tables for smarter, context-aware optimizations.
        </div>

        {schema.map((table, ti) => (
          <div key={ti} className="schema-table-card">
            <div className="schema-table-name">
              <span>TABLE {ti + 1}</span>
              <button
                className="pixel-btn pixel-btn--ghost"
                style={{ padding: "4px 8px", fontSize: "8px" }}
                onClick={() => removeTable(ti)}
              >
                ✕
              </button>
            </div>

            <div className="schema-row" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <input
                className="schema-input"
                placeholder="Table name (e.g., users)"
                value={table.name}
                onChange={(e) => updateTable(ti, { name: e.target.value })}
              />
              <input
                className="schema-input"
                type="number"
                placeholder="Approx. rows (e.g., 500000)"
                value={table.approximate_rows || ""}
                onChange={(e) =>
                  updateTable(ti, {
                    approximate_rows: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
              />
            </div>

            {/* Columns */}
            <div style={{ marginTop: "8px" }}>
              <div style={{ fontFamily: "var(--font-pixel)", fontSize: "7px", color: "var(--text-dim)", marginBottom: "4px", letterSpacing: "1px" }}>
                COLUMNS
              </div>
              {table.columns.map((col, ci) => (
                <div key={ci} className="schema-row">
                  <input
                    className="schema-input"
                    placeholder="Column name"
                    value={col.name}
                    onChange={(e) =>
                      updateColumn(ti, ci, { name: e.target.value })
                    }
                  />
                  <input
                    className="schema-input"
                    placeholder="Type (varchar, int...)"
                    value={col.data_type}
                    onChange={(e) =>
                      updateColumn(ti, ci, { data_type: e.target.value })
                    }
                  />
                  <button
                    className="pixel-btn pixel-btn--ghost"
                    style={{ padding: "4px 8px", fontSize: "8px" }}
                    onClick={() => removeColumn(ti, ci)}
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                className="pixel-btn pixel-btn--ghost"
                style={{ padding: "4px 10px", fontSize: "7px", marginTop: "4px" }}
                onClick={() => addColumn(ti)}
              >
                + COLUMN
              </button>
            </div>

            {/* Indexes */}
            <div style={{ marginTop: "8px" }}>
              <div style={{ fontFamily: "var(--font-pixel)", fontSize: "7px", color: "var(--text-dim)", marginBottom: "4px", letterSpacing: "1px" }}>
                INDEXES
              </div>
              {table.indexes.map((idx, ii) => (
                <div key={ii} className="schema-row" style={{ gridTemplateColumns: "1fr 1fr auto auto" }}>
                  <input
                    className="schema-input"
                    placeholder="Index name"
                    value={idx.name}
                    onChange={(e) =>
                      updateIndex(ti, ii, { name: e.target.value })
                    }
                  />
                  <input
                    className="schema-input"
                    placeholder="Columns (comma-separated)"
                    value={idx.columns.join(", ")}
                    onChange={(e) =>
                      updateIndex(ti, ii, {
                        columns: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                      })
                    }
                  />
                  <label style={{ display: "flex", alignItems: "center", gap: "4px", fontFamily: "var(--font-terminal)", fontSize: "14px", color: "var(--text-dim)", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={idx.is_unique}
                      onChange={(e) =>
                        updateIndex(ti, ii, { is_unique: e.target.checked })
                      }
                    />
                    UQ
                  </label>
                  <button
                    className="pixel-btn pixel-btn--ghost"
                    style={{ padding: "4px 8px", fontSize: "8px" }}
                    onClick={() => removeIndex(ti, ii)}
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                className="pixel-btn pixel-btn--ghost"
                style={{ padding: "4px 10px", fontSize: "7px", marginTop: "4px" }}
                onClick={() => addIndex(ti)}
              >
                + INDEX
              </button>
            </div>
          </div>
        ))}

        <button
          className="pixel-btn pixel-btn--secondary"
          style={{ marginTop: "8px" }}
          onClick={addTable}
        >
          + ADD TABLE
        </button>
      </div>
    </div>
  );
}
