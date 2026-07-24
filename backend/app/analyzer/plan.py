"""
Logical Query Plan Generator.

Builds a tree representation of how the database would logically
execute the query — used for visualization in the frontend.
"""

import uuid
from sqlglot import exp
from app.models import QueryPlanNode, TableSchema
from app.parser.sql_parser import extract_tables


def _make_id() -> str:
    return str(uuid.uuid4())[:8]


def generate_query_plan(
    ast: exp.Expression, schema_context: list[TableSchema]
) -> QueryPlanNode:
    """
    Generate a logical query plan tree from a parsed SQL AST.
    Returns the root node of the plan tree.
    """
    if isinstance(ast, exp.Select):
        return _plan_select(ast, schema_context)

    # For non-SELECT queries, return a simple plan
    return QueryPlanNode(
        id=_make_id(),
        type="Execute",
        label=type(ast).__name__.upper(),
        details={"sql": ast.sql()},
    )


def _plan_select(
    select: exp.Expression, schema_context: list[TableSchema]
) -> QueryPlanNode:
    """Build plan tree for a SELECT statement."""
    row_counts = {t.name.lower(): t.approximate_rows or 10000 for t in schema_context}

    # Start from the bottom: scans → joins → filters → aggregates → sorts → project

    # ── 1. Table Scans ──────────────────────────────────────────
    scan_nodes: list[QueryPlanNode] = []
    tables = extract_tables(select)
    for table_name in tables:
        rows = row_counts.get(table_name.lower(), 10000)

        # Determine scan type
        scan_type = "Sequential Scan"
        where = select.find(exp.Where)
        if where and schema_context:
            where_cols = [c.name for c in where.find_all(exp.Column)]
            for ts in schema_context:
                if ts.name.lower() == table_name.lower():
                    for idx in ts.indexes:
                        if any(c in idx.columns for c in where_cols):
                            scan_type = "Index Scan"
                            break

        scan_nodes.append(
            QueryPlanNode(
                id=_make_id(),
                type="Scan",
                label=f"{scan_type} on {table_name}",
                details={
                    "table": table_name,
                    "scan_type": scan_type,
                    "estimated_rows": rows,
                },
                estimated_cost=float(rows) if scan_type == "Sequential Scan" else float(rows) * 0.1,
            )
        )

    # ── 2. Joins ────────────────────────────────────────────────
    current_node = scan_nodes[0] if scan_nodes else None

    joins = list(select.find_all(exp.Join))
    scan_idx = 1
    for join in joins:
        join_table = join.find(exp.Table)
        join_type = "JOIN"
        side = join.args.get("side", "")
        if side:
            join_type = f"{str(side).upper()} JOIN"

        on_condition = ""
        on_expr = join.args.get("on")
        if on_expr:
            on_condition = on_expr.sql()

        right_scan = scan_nodes[scan_idx] if scan_idx < len(scan_nodes) else QueryPlanNode(
            id=_make_id(),
            type="Scan",
            label=f"Scan on {join_table.name if join_table else '?'}",
            details={},
        )
        scan_idx += 1

        children = []
        if current_node:
            children.append(current_node)
        children.append(right_scan)

        current_node = QueryPlanNode(
            id=_make_id(),
            type="Join",
            label=f"Hash {join_type}",
            details={
                "join_type": join_type,
                "condition": on_condition,
                "strategy": "Hash Join",
            },
            children=children,
        )

    # ── 3. Filter (WHERE) ──────────────────────────────────────
    where = select.find(exp.Where)
    if where and current_node:
        condition_text = where.this.sql() if where.this else ""
        current_node = QueryPlanNode(
            id=_make_id(),
            type="Filter",
            label="Filter",
            details={"condition": condition_text},
            children=[current_node],
        )

    # ── 4. Aggregate (GROUP BY) ─────────────────────────────────
    group = select.find(exp.Group)
    if group and current_node:
        group_cols = [col.sql() for col in group.find_all(exp.Column)]
        current_node = QueryPlanNode(
            id=_make_id(),
            type="Aggregate",
            label="Hash Aggregate",
            details={"group_by": group_cols},
            children=[current_node],
        )

    # ── 5. Having ───────────────────────────────────────────────
    having = select.find(exp.Having)
    if having and current_node:
        current_node = QueryPlanNode(
            id=_make_id(),
            type="Filter",
            label="Having Filter",
            details={"condition": having.this.sql() if having.this else ""},
            children=[current_node],
        )

    # ── 6. Sort (ORDER BY) ──────────────────────────────────────
    order = select.find(exp.Order)
    if order and current_node:
        order_exprs = [o.sql() for o in order.find_all(exp.Ordered)]
        current_node = QueryPlanNode(
            id=_make_id(),
            type="Sort",
            label="Sort",
            details={"order_by": order_exprs},
            children=[current_node],
        )

    # ── 7. Limit ────────────────────────────────────────────────
    limit = select.find(exp.Limit)
    if limit and current_node:
        limit_val = limit.this.sql() if limit.this else "?"
        current_node = QueryPlanNode(
            id=_make_id(),
            type="Limit",
            label=f"Limit {limit_val}",
            details={"limit": limit_val},
            children=[current_node],
        )

    # ── 8. Project (SELECT columns) ─────────────────────────────
    select_exprs = select.args.get("expressions", [])
    columns = [e.sql() for e in select_exprs]

    root = QueryPlanNode(
        id=_make_id(),
        type="Project",
        label="Project",
        details={"columns": columns},
        children=[current_node] if current_node else [],
    )

    return root
