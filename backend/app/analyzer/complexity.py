"""
Query Complexity Scorer.

Scores SQL queries on a 0-100 scale based on structural complexity factors.
"""

from sqlglot import exp
from app.models import ComplexityResult, ComplexityBreakdown
from app.parser.sql_parser import (
    extract_joins,
    has_subqueries,
    has_group_by,
    has_order_by,
    has_distinct,
    has_having,
    has_window_functions,
    is_select_star,
)


def score_complexity(ast: exp.Expression) -> ComplexityResult:
    """
    Score the complexity of a SQL query (0-100).
    Higher score = more complex query.
    """
    breakdown: list[ComplexityBreakdown] = []
    total = 0

    # ── Joins (+12 per join) ────────────────────────────────────
    joins = extract_joins(ast)
    if joins:
        join_score = min(len(joins) * 12, 36)
        total += join_score
        join_types = [j["type"] for j in joins]
        breakdown.append(
            ComplexityBreakdown(
                factor="Joins",
                score=join_score,
                description=f"{len(joins)} join(s): {', '.join(join_types)}",
            )
        )

    # ── Subqueries (+18 per subquery) ───────────────────────────
    if has_subqueries(ast):
        subquery_count = len(list(ast.find_all(exp.Subquery)))
        sub_score = min(subquery_count * 18, 36)
        total += sub_score
        breakdown.append(
            ComplexityBreakdown(
                factor="Subqueries",
                score=sub_score,
                description=f"{subquery_count} subquery(ies) — consider converting to JOINs",
            )
        )

    # ── Aggregations (+8) ───────────────────────────────────────
    if has_group_by(ast):
        total += 8
        breakdown.append(
            ComplexityBreakdown(
                factor="Aggregation",
                score=8,
                description="GROUP BY requires sorting/hashing all rows",
            )
        )

    # ── HAVING (+10) ────────────────────────────────────────────
    if has_having(ast):
        total += 10
        breakdown.append(
            ComplexityBreakdown(
                factor="HAVING clause",
                score=10,
                description="Post-aggregation filtering adds processing overhead",
            )
        )

    # ── ORDER BY (+6) ───────────────────────────────────────────
    if has_order_by(ast):
        total += 6
        breakdown.append(
            ComplexityBreakdown(
                factor="Sorting",
                score=6,
                description="ORDER BY requires sorting the result set",
            )
        )

    # ── DISTINCT (+7) ───────────────────────────────────────────
    if has_distinct(ast):
        total += 7
        breakdown.append(
            ComplexityBreakdown(
                factor="DISTINCT",
                score=7,
                description="Deduplication requires sorting or hashing",
            )
        )

    # ── Window Functions (+15) ──────────────────────────────────
    if has_window_functions(ast):
        window_count = len(list(ast.find_all(exp.Window)))
        w_score = min(window_count * 15, 30)
        total += w_score
        breakdown.append(
            ComplexityBreakdown(
                factor="Window Functions",
                score=w_score,
                description=f"{window_count} window function(s) — requires partitioning and sorting",
            )
        )

    # ── CASE expressions (+5 each) ──────────────────────────────
    case_count = len(list(ast.find_all(exp.Case)))
    if case_count:
        c_score = min(case_count * 5, 15)
        total += c_score
        breakdown.append(
            ComplexityBreakdown(
                factor="CASE expressions",
                score=c_score,
                description=f"{case_count} CASE expression(s)",
            )
        )

    # ── Nested depth bonus ──────────────────────────────────────
    max_depth = _measure_depth(ast)
    if max_depth > 2:
        depth_score = min((max_depth - 2) * 5, 15)
        total += depth_score
        breakdown.append(
            ComplexityBreakdown(
                factor="Nesting depth",
                score=depth_score,
                description=f"Query nesting depth: {max_depth} levels",
            )
        )

    # ── Base complexity for any query ───────────────────────────
    total += 5  # Every query has at least a base complexity

    # Cap at 100
    total = min(total, 100)

    # Determine label
    if total <= 20:
        label = "Simple"
    elif total <= 45:
        label = "Moderate"
    elif total <= 70:
        label = "Complex"
    else:
        label = "Very Complex"

    return ComplexityResult(score=total, label=label, breakdown=breakdown)


def _measure_depth(node: exp.Expression, current_depth: int = 0) -> int:
    """Measure the maximum nesting depth of subqueries."""
    max_d = current_depth
    for child in node.iter_expressions():
        if isinstance(child, (exp.Subquery, exp.Select)):
            d = _measure_depth(child, current_depth + 1)
            max_d = max(max_d, d)
        else:
            d = _measure_depth(child, current_depth)
            max_d = max(max_d, d)
    return max_d
