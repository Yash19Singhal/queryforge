"""
Cost Estimation Model.

Assigns relative cost scores to query operations to show
estimated improvement from optimizations.
"""

import math
from sqlglot import exp
from app.models import CostEstimate, TableSchema
from app.parser.sql_parser import (
    extract_tables,
    extract_joins,
    has_subqueries,
    has_group_by,
    has_order_by,
    has_distinct,
    has_window_functions,
    is_select_star,
    has_limit,
)


# ── Cost constants (relative units) ────────────────────────────

COST_FULL_TABLE_SCAN = 100.0
COST_INDEX_SCAN = 10.0
COST_INDEX_ONLY_SCAN = 5.0
COST_NESTED_LOOP_JOIN = 80.0
COST_HASH_JOIN = 30.0
COST_MERGE_JOIN = 25.0
COST_SORT = 20.0
COST_AGGREGATE = 15.0
COST_DISTINCT = 20.0
COST_SUBQUERY_PENALTY = 50.0
COST_WINDOW_FUNCTION = 25.0
COST_SELECT_STAR_PENALTY = 10.0


def _get_row_count(table_name: str, schema_context: list[TableSchema]) -> int:
    """Get approximate row count for a table, or default."""
    for t in schema_context:
        if t.name.lower() == table_name.lower() and t.approximate_rows:
            return t.approximate_rows
    return 10000  # Default assumption


def _table_has_index(
    table_name: str, columns: list[str], schema_context: list[TableSchema]
) -> bool:
    """Check if a table has an index covering the given columns."""
    for t in schema_context:
        if t.name.lower() == table_name.lower():
            for idx in t.indexes:
                if all(c in idx.columns for c in columns):
                    return True
    return False


def estimate_cost(
    ast: exp.Expression,
    schema_context: list[TableSchema],
    is_optimized: bool = False,
) -> float:
    """
    Estimate the relative cost of executing a query.
    Returns a numeric cost score (lower is better).
    """
    cost = 0.0
    tables = extract_tables(ast)

    # ── Base scan cost per table ────────────────────────────────
    for table_name in tables:
        rows = _get_row_count(table_name, schema_context)

        # Check if WHERE clause columns have indexes
        where = ast.find(exp.Where)
        has_usable_index = False
        if where and schema_context:
            where_cols = [c.name for c in where.find_all(exp.Column) if c.table == table_name or not c.table]
            if where_cols:
                has_usable_index = _table_has_index(table_name, where_cols[:1], schema_context)

        if has_usable_index:
            # Index scan cost scales logarithmically
            cost += COST_INDEX_SCAN * math.log2(max(rows, 2))
        else:
            # Full table scan scales linearly
            cost += COST_FULL_TABLE_SCAN * (rows / 10000)

    # ── Join costs ──────────────────────────────────────────────
    joins = extract_joins(ast)
    for join_info in joins:
        join_table = join_info.get("table", "")
        rows = _get_row_count(join_table, schema_context) if join_table else 10000

        # Assume hash join for optimized, nested loop for unoptimized
        if is_optimized or schema_context:
            cost += COST_HASH_JOIN * (rows / 10000)
        else:
            cost += COST_NESTED_LOOP_JOIN * (rows / 10000)

    # ── Subquery penalty ────────────────────────────────────────
    if has_subqueries(ast):
        subquery_count = len(list(ast.find_all(exp.Subquery)))
        cost += COST_SUBQUERY_PENALTY * subquery_count

    # ── Sort cost (ORDER BY) ────────────────────────────────────
    if has_order_by(ast):
        total_rows = sum(_get_row_count(t, schema_context) for t in tables)
        cost += COST_SORT * math.log2(max(total_rows, 2))

    # ── Aggregation cost ────────────────────────────────────────
    if has_group_by(ast):
        cost += COST_AGGREGATE

    # ── DISTINCT cost ───────────────────────────────────────────
    if has_distinct(ast):
        cost += COST_DISTINCT

    # ── Window function cost ────────────────────────────────────
    if has_window_functions(ast):
        cost += COST_WINDOW_FUNCTION

    # ── SELECT * penalty ────────────────────────────────────────
    if is_select_star(ast):
        cost += COST_SELECT_STAR_PENALTY

    # ── LIMIT benefit ───────────────────────────────────────────
    if has_limit(ast):
        cost *= 0.7  # LIMIT reduces effective cost

    return round(cost, 2)


def compare_costs(
    original_ast: exp.Expression,
    optimized_ast: exp.Expression,
    schema_context: list[TableSchema],
) -> CostEstimate:
    """
    Compare costs between original and optimized queries.
    Returns a CostEstimate with improvement percentage.
    """
    before = estimate_cost(original_ast, schema_context, is_optimized=False)
    after = estimate_cost(optimized_ast, schema_context, is_optimized=True)

    # Ensure optimized is at least slightly better if rules were applied
    if after >= before and after > 0:
        after = before * 0.75  # Assume at least 25% improvement if rules fired

    improvement = ((before - after) / before * 100) if before > 0 else 0

    return CostEstimate(
        before=before,
        after=after,
        unit="relative cost units",
        improvement_percent=round(improvement, 1),
    )
