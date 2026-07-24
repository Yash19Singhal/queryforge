from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SQLDialect(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


# ── Request Models ──────────────────────────────────────────────


class ColumnDefinition(BaseModel):
    name: str
    data_type: str = "varchar"
    is_nullable: bool = True


class IndexDefinition(BaseModel):
    name: str
    columns: list[str]
    is_unique: bool = False


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnDefinition] = []
    indexes: list[IndexDefinition] = []
    approximate_rows: Optional[int] = None


class OptimizeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    dialect: SQLDialect = SQLDialect.POSTGRESQL
    schema_context: list[TableSchema] = []


class FormatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    dialect: SQLDialect = SQLDialect.POSTGRESQL


class ParseRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    dialect: SQLDialect = SQLDialect.POSTGRESQL


# ── Response Models ─────────────────────────────────────────────


class ComplexityBreakdown(BaseModel):
    factor: str
    score: int
    description: str


class ComplexityResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    label: str  # "Simple", "Moderate", "Complex", "Very Complex"
    breakdown: list[ComplexityBreakdown] = []


class PerformanceGain(BaseModel):
    estimate: str  # e.g., "30-45%"
    description: str


class Bottleneck(BaseModel):
    type: str
    table: Optional[str] = None
    description: str


class OptimizationApplied(BaseModel):
    rule: str
    category: str  # "query_rewrite", "join_optimization", "anti_pattern", "index_advisory"
    impact: str  # "high", "medium", "low"
    description: str
    explanation: str


class IndexSuggestion(BaseModel):
    table: str
    columns: list[str]
    type: str  # "single", "composite", "covering"
    impact: str
    rationale: str
    create_statement: str


class QueryPlanNode(BaseModel):
    id: str
    type: str  # "Project", "Sort", "Aggregate", "Filter", "Join", "Scan"
    label: str
    details: dict = {}
    estimated_cost: Optional[float] = None
    children: list["QueryPlanNode"] = []


class CostEstimate(BaseModel):
    before: float
    after: float
    unit: str = "relative cost units"
    improvement_percent: float


class RowsScanned(BaseModel):
    before: str
    after: str
    description: str


class OptimizeResponse(BaseModel):
    original_query: str
    optimized_query: str
    dialect: str
    complexity: ComplexityResult
    performance_gain: PerformanceGain
    bottleneck: Optional[Bottleneck] = None
    cost_estimate: CostEstimate
    optimizations_applied: list[OptimizationApplied] = []
    index_suggestions: list[IndexSuggestion] = []
    query_plan: Optional[QueryPlanNode] = None
    rows_scanned: Optional[RowsScanned] = None


class ParseResponse(BaseModel):
    is_valid: bool
    error_message: Optional[str] = None
    tables: list[str] = []
    columns: list[str] = []
    query_type: Optional[str] = None  # SELECT, INSERT, UPDATE, DELETE


class FormatResponse(BaseModel):
    formatted_query: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
