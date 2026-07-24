/* ══════════════════════════════════════════════════════════════
   QueryForge — TypeScript Types
   ══════════════════════════════════════════════════════════════ */

export type SQLDialect = "postgresql" | "mysql" | "sqlite";

// ── Request Types ──────────────────────────────────────────

export interface ColumnDefinition {
  name: string;
  data_type: string;
  is_nullable: boolean;
}

export interface IndexDefinition {
  name: string;
  columns: string[];
  is_unique: boolean;
}

export interface TableSchema {
  name: string;
  columns: ColumnDefinition[];
  indexes: IndexDefinition[];
  approximate_rows: number | null;
}

export interface OptimizeRequest {
  query: string;
  dialect: SQLDialect;
  schema_context: TableSchema[];
}

// ── Response Types ─────────────────────────────────────────

export interface ComplexityBreakdown {
  factor: string;
  score: number;
  description: string;
}

export interface ComplexityResult {
  score: number;
  label: string;
  breakdown: ComplexityBreakdown[];
}

export interface PerformanceGain {
  estimate: string;
  description: string;
}

export interface Bottleneck {
  type: string;
  table: string | null;
  description: string;
}

export interface OptimizationApplied {
  rule: string;
  category: string;
  impact: string;
  description: string;
  explanation: string;
}

export interface IndexSuggestion {
  table: string;
  columns: string[];
  type: string;
  impact: string;
  rationale: string;
  create_statement: string;
}

export interface QueryPlanNode {
  id: string;
  type: string;
  label: string;
  details: Record<string, unknown>;
  estimated_cost: number | null;
  children: QueryPlanNode[];
}

export interface CostEstimate {
  before: number;
  after: number;
  unit: string;
  improvement_percent: number;
}

export interface RowsScanned {
  before: string;
  after: string;
  description: string;
}

export interface OptimizeResponse {
  original_query: string;
  optimized_query: string;
  dialect: string;
  complexity: ComplexityResult;
  performance_gain: PerformanceGain;
  bottleneck: Bottleneck | null;
  cost_estimate: CostEstimate;
  optimizations_applied: OptimizationApplied[];
  index_suggestions: IndexSuggestion[];
  query_plan: QueryPlanNode | null;
  rows_scanned: RowsScanned | null;
}

export interface ParseResponse {
  is_valid: boolean;
  error_message: string | null;
  tables: string[];
  columns: string[];
  query_type: string | null;
}

export interface FormatResponse {
  formatted_query: string;
}

// ── History ────────────────────────────────────────────────

export interface HistoryEntry {
  id: string;
  query: string;
  dialect: SQLDialect;
  timestamp: number;
  complexity_score: number | null;
  optimizations_count: number;
}
