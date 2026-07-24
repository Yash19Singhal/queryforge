"""
QueryForge API — SQL Query Optimizer Backend.

FastAPI application with CORS support for the Next.js frontend.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    OptimizeRequest,
    OptimizeResponse,
    ParseRequest,
    ParseResponse,
    FormatRequest,
    FormatResponse,
    HealthResponse,
    PerformanceGain,
    Bottleneck,
    RowsScanned,
)
from app.parser.sql_parser import (
    parse_sql,
    validate_sql,
    extract_tables,
    extract_columns,
    get_query_type,
    format_sql,
    extract_joins,
    has_subqueries,
)
from app.optimizer.engine import run_optimizations
from app.optimizer.cost import compare_costs
from app.analyzer.complexity import score_complexity
from app.analyzer.plan import generate_query_plan
from app.analyzer.index_advisor import suggest_indexes


# ── App Setup ───────────────────────────────────────────────────

app = FastAPI(
    title="QueryForge API",
    description="SQL Query Optimizer — Parse, analyze, and optimize SQL queries",
    version="1.0.0",
)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ──────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", version="1.0.0")


@app.post("/api/parse", response_model=ParseResponse)
async def parse_query(request: ParseRequest):
    """Parse and validate a SQL query."""
    is_valid, error = validate_sql(request.query, request.dialect.value)

    if not is_valid:
        return ParseResponse(is_valid=False, error_message=error)

    ast = parse_sql(request.query, request.dialect.value)
    if not ast:
        return ParseResponse(is_valid=False, error_message="Failed to parse query")

    return ParseResponse(
        is_valid=True,
        tables=extract_tables(ast),
        columns=extract_columns(ast),
        query_type=get_query_type(ast),
    )


@app.post("/api/format", response_model=FormatResponse)
async def format_query(request: FormatRequest):
    """Format/prettify a SQL query."""
    formatted = format_sql(request.query, request.dialect.value)
    return FormatResponse(formatted_query=formatted)


@app.post("/api/optimize", response_model=OptimizeResponse)
async def optimize_query(request: OptimizeRequest):
    """
    Main optimization endpoint.
    Parses the query, runs optimization rules, estimates costs,
    generates a query plan, and suggests indexes.
    """
    # ── 1. Parse ────────────────────────────────────────────────
    is_valid, error = validate_sql(request.query, request.dialect.value)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid SQL: {error}")

    ast = parse_sql(request.query, request.dialect.value)
    if not ast:
        raise HTTPException(status_code=400, detail="Failed to parse SQL query")

    # ── 2. Analyze Complexity ───────────────────────────────────
    complexity = score_complexity(ast)

    # ── 3. Run Optimizations ────────────────────────────────────
    optimized_ast, optimizations = run_optimizations(ast, request.schema_context)

    # Generate optimized SQL
    dialect_map = {"postgresql": "postgres", "mysql": "mysql", "sqlite": "sqlite"}
    sqlglot_dialect = dialect_map.get(request.dialect.value, "postgres")

    try:
        optimized_sql = optimized_ast.sql(dialect=sqlglot_dialect, pretty=True)
    except Exception:
        optimized_sql = request.query

    # Format original too
    try:
        original_formatted = ast.sql(dialect=sqlglot_dialect, pretty=True)
    except Exception:
        original_formatted = request.query

    # ── 4. Cost Estimation ──────────────────────────────────────
    cost_estimate = compare_costs(ast, optimized_ast, request.schema_context)

    # ── 5. Performance Gain Estimate ────────────────────────────
    improvement = cost_estimate.improvement_percent
    if improvement > 50:
        perf_desc = "Major performance improvement expected"
        perf_estimate = f"~{int(improvement)}% faster"
    elif improvement > 25:
        perf_desc = "Significant performance improvement with proper indexing"
        perf_estimate = f"~{int(improvement)}% faster"
    elif improvement > 10:
        perf_desc = "Moderate improvement expected"
        perf_estimate = f"~{int(improvement)}% faster"
    elif optimizations:
        perf_desc = "Minor improvements from query restructuring"
        perf_estimate = "~5-15% faster"
    else:
        perf_desc = "Query is already well-optimized"
        perf_estimate = "Minimal"

    performance_gain = PerformanceGain(estimate=perf_estimate, description=perf_desc)

    # ── 6. Detect Bottleneck ────────────────────────────────────
    bottleneck = _detect_bottleneck(ast, request.schema_context)

    # ── 7. Generate Query Plan ──────────────────────────────────
    query_plan = generate_query_plan(ast, request.schema_context)

    # ── 8. Index Suggestions ────────────────────────────────────
    index_suggestions = suggest_indexes(ast, request.schema_context)

    # ── 9. Rows Scanned Estimate ────────────────────────────────
    rows_scanned = _estimate_rows_scanned(ast, request.schema_context, optimizations)

    return OptimizeResponse(
        original_query=original_formatted,
        optimized_query=optimized_sql,
        dialect=request.dialect.value,
        complexity=complexity,
        performance_gain=performance_gain,
        bottleneck=bottleneck,
        cost_estimate=cost_estimate,
        optimizations_applied=optimizations,
        index_suggestions=index_suggestions,
        query_plan=query_plan,
        rows_scanned=rows_scanned,
    )


# ── Helper Functions ────────────────────────────────────────────


def _detect_bottleneck(ast, schema_context) -> Bottleneck | None:
    """Detect the primary performance bottleneck."""
    tables = extract_tables(ast)
    joins = extract_joins(ast)

    # Check for missing indexes on large tables
    if schema_context:
        for table in schema_context:
            if table.approximate_rows and table.approximate_rows > 100000:
                if not table.indexes:
                    return Bottleneck(
                        type="sequential_scan",
                        table=table.name,
                        description=(
                            f"Sequential scan on {table.name} (~{table.approximate_rows:,} rows). "
                            f"No indexes defined — every query scans the entire table."
                        ),
                    )

    # Check for subqueries
    if has_subqueries(ast):
        return Bottleneck(
            type="correlated_subquery",
            description=(
                "Correlated subqueries may execute once per row of the outer query, "
                "causing O(n²) behavior on large tables."
            ),
        )

    # Check for multiple joins without indexes
    if len(joins) >= 2:
        return Bottleneck(
            type="multiple_joins",
            description=(
                f"Query joins {len(joins)} tables. Without proper indexes on join "
                f"columns, the database may use nested loop joins with O(n×m) complexity."
            ),
        )

    # Check for full table scan on any table
    if tables and not schema_context:
        return Bottleneck(
            type="potential_full_scan",
            table=tables[0],
            description=(
                f"Without schema information, we assume a sequential scan on {tables[0]}. "
                f"Add your table schema for more accurate analysis."
            ),
        )

    return None


def _estimate_rows_scanned(ast, schema_context, optimizations) -> RowsScanned | None:
    """Estimate rows scanned before and after optimization."""
    tables = extract_tables(ast)

    if not schema_context:
        if tables:
            return RowsScanned(
                before=f"Full scan on {', '.join(tables)}",
                after="Reduced with optimizations" if optimizations else "No change",
                description="Add schema context for detailed row estimates",
            )
        return None

    total_rows = sum(
        t.approximate_rows or 10000
        for t in schema_context
        if t.name in tables
    )

    # Estimate filtered rows
    where = ast.find_all(type(ast).find) if hasattr(ast, 'find') else []
    has_filter = ast.find(type(ast)) is not None if hasattr(ast, 'find') else False

    # Simplified estimate: WHERE reduces by ~90%, LIMIT caps output
    from sqlglot import exp as e
    where_clause = ast.find(e.Where)
    limit_clause = ast.find(e.Limit)

    after_rows = total_rows
    if where_clause:
        after_rows = int(total_rows * 0.1)  # WHERE typically filters 90%
    if limit_clause and limit_clause.this:
        try:
            limit_val = int(limit_clause.this.sql())
            after_rows = min(after_rows, limit_val)
        except (ValueError, AttributeError):
            pass

    def _format_rows(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1000:
            return f"{n // 1000}K"
        return str(n)

    return RowsScanned(
        before=f"{_format_rows(total_rows)} rows",
        after=f"{_format_rows(after_rows)} rows",
        description=f"{_format_rows(total_rows)} → {_format_rows(after_rows)} with filters applied",
    )


# ── Run with Uvicorn ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
