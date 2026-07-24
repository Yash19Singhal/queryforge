"""
Index Advisor.

Analyzes query structure and schema to suggest indexes
that would improve query performance.
"""

from sqlglot import exp
from app.models import IndexSuggestion, TableSchema
from app.parser.sql_parser import extract_tables


def suggest_indexes(
    ast: exp.Expression, schema_context: list[TableSchema]
) -> list[IndexSuggestion]:
    """
    Analyze a SQL query and suggest indexes based on:
    - WHERE clause columns
    - JOIN condition columns
    - ORDER BY columns
    - GROUP BY columns
    """
    suggestions: list[IndexSuggestion] = []
    existing_indexes = _collect_existing_indexes(schema_context)
    schema_tables = {t.name.lower(): t for t in schema_context}

    # ── WHERE clause indexes ────────────────────────────────────
    where = ast.find(exp.Where)
    if where:
        where_cols_by_table = _group_columns_by_table(where, ast)
        for table_name, columns in where_cols_by_table.items():
            if _index_exists(table_name, columns, existing_indexes):
                continue

            idx_type = "composite" if len(columns) > 1 else "single"
            col_list = ", ".join(columns)
            idx_name = f"idx_{table_name}_{'_'.join(columns)}"

            suggestions.append(
                IndexSuggestion(
                    table=table_name,
                    columns=columns,
                    type=idx_type,
                    impact="high",
                    rationale=(
                        f"The WHERE clause filters on {col_list} from {table_name}. "
                        f"An index would convert a sequential scan to an index scan, "
                        f"dramatically reducing rows examined."
                    ),
                    create_statement=f"CREATE INDEX {idx_name} ON {table_name}({col_list});",
                )
            )

    # ── JOIN condition indexes ──────────────────────────────────
    for join in ast.find_all(exp.Join):
        on_expr = join.args.get("on")
        if not on_expr:
            continue

        join_table = join.find(exp.Table)
        if not join_table:
            continue

        table_name = join_table.name
        join_cols = [
            c.name
            for c in on_expr.find_all(exp.Column)
            if (c.table == table_name or c.table == join_table.alias)
        ]

        if not join_cols:
            # Try to get columns without table qualifier
            join_cols = [c.name for c in on_expr.find_all(exp.Column)]
            # Filter to only columns that belong to the join table
            if schema_tables.get(table_name.lower()):
                schema_col_names = {
                    c.name for c in schema_tables[table_name.lower()].columns
                }
                join_cols = [c for c in join_cols if c in schema_col_names]

        if join_cols and not _index_exists(table_name, join_cols, existing_indexes):
            col_list = ", ".join(join_cols)
            idx_name = f"idx_{table_name}_{'_'.join(join_cols)}"

            suggestions.append(
                IndexSuggestion(
                    table=table_name,
                    columns=join_cols,
                    type="single" if len(join_cols) == 1 else "composite",
                    impact="high",
                    rationale=(
                        f"An index on {table_name}({col_list}) will convert the join "
                        f"from a sequential scan to an index scan, significantly "
                        f"improving join performance."
                    ),
                    create_statement=f"CREATE INDEX {idx_name} ON {table_name}({col_list});",
                )
            )

    # ── ORDER BY indexes ────────────────────────────────────────
    order = ast.find(exp.Order)
    if order:
        order_cols_by_table = _group_columns_by_table(order, ast)
        for table_name, columns in order_cols_by_table.items():
            if _index_exists(table_name, columns, existing_indexes):
                continue

            # Only suggest if there's no WHERE index already covering these
            col_list = ", ".join(columns)
            idx_name = f"idx_{table_name}_{'_'.join(columns)}_sort"

            suggestions.append(
                IndexSuggestion(
                    table=table_name,
                    columns=columns,
                    type="single" if len(columns) == 1 else "composite",
                    impact="medium",
                    rationale=(
                        f"An index on {table_name}({col_list}) can eliminate the need "
                        f"for a separate sort operation in ORDER BY, returning results "
                        f"in the desired order directly from the index."
                    ),
                    create_statement=f"CREATE INDEX {idx_name} ON {table_name}({col_list});",
                )
            )

    # ── Covering index suggestions ──────────────────────────────
    if schema_context:
        covering = _suggest_covering_indexes(ast, schema_context, existing_indexes)
        suggestions.extend(covering)

    # Deduplicate by (table, columns)
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        key = (s.table, tuple(s.columns))
        if key not in seen:
            seen.add(key)
            unique_suggestions.append(s)

    return unique_suggestions


def _collect_existing_indexes(
    schema_context: list[TableSchema],
) -> dict[str, list[list[str]]]:
    """Collect existing indexes from schema context."""
    indexes: dict[str, list[list[str]]] = {}
    for table in schema_context:
        indexes[table.name.lower()] = [idx.columns for idx in table.indexes]
    return indexes


def _index_exists(
    table_name: str,
    columns: list[str],
    existing_indexes: dict[str, list[list[str]]],
) -> bool:
    """Check if an index already exists for these columns."""
    table_indexes = existing_indexes.get(table_name.lower(), [])
    for idx_cols in table_indexes:
        # Check if the existing index is a prefix match
        if columns == idx_cols[: len(columns)]:
            return True
    return False


def _group_columns_by_table(
    node: exp.Expression, full_ast: exp.Expression
) -> dict[str, list[str]]:
    """Group column references by their table."""
    result: dict[str, list[str]] = {}
    tables = extract_tables(full_ast)

    for col in node.find_all(exp.Column):
        table = col.table or (tables[0] if len(tables) == 1 else "")
        if table:
            if table not in result:
                result[table] = []
            if col.name not in result[table]:
                result[table].append(col.name)

    return result


def _suggest_covering_indexes(
    ast: exp.Expression,
    schema_context: list[TableSchema],
    existing_indexes: dict[str, list[list[str]]],
) -> list[IndexSuggestion]:
    """Suggest covering indexes that include SELECT + WHERE columns."""
    suggestions = []

    where = ast.find(exp.Where)
    if not where:
        return suggestions

    select_node = ast.find(exp.Select)
    if not select_node:
        return suggestions

    # Get WHERE columns and SELECT columns per table
    where_cols_by_table = _group_columns_by_table(where, ast)
    select_cols_by_table = _group_columns_by_table(select_node, ast)

    for table_name, where_cols in where_cols_by_table.items():
        select_cols = select_cols_by_table.get(table_name, [])
        all_cols = where_cols + [c for c in select_cols if c not in where_cols]

        if len(all_cols) <= 1:
            continue

        if _index_exists(table_name, all_cols, existing_indexes):
            continue

        col_list = ", ".join(all_cols)
        idx_name = f"idx_{table_name}_covering"

        suggestions.append(
            IndexSuggestion(
                table=table_name,
                columns=all_cols,
                type="covering",
                impact="high",
                rationale=(
                    f"A covering index on {table_name}({col_list}) includes both "
                    f"the filter columns and the selected columns. This allows "
                    f"index-only scans — the database never needs to access the "
                    f"actual table heap, eliminating random I/O."
                ),
                create_statement=f"CREATE INDEX {idx_name} ON {table_name}({col_list});",
            )
        )

    return suggestions
