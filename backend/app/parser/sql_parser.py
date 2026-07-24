"""
SQL Parser module using sqlglot.
Parses SQL queries into structured representations for the optimizer.
"""

import sqlglot
from sqlglot import exp
from typing import Optional


# Map our dialect names to sqlglot dialect names
DIALECT_MAP = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "sqlite": "sqlite",
}


def parse_sql(query: str, dialect: str = "postgresql") -> Optional[exp.Expression]:
    """Parse a SQL query string into a sqlglot AST."""
    sqlglot_dialect = DIALECT_MAP.get(dialect, "postgres")
    try:
        parsed = sqlglot.parse(query, read=sqlglot_dialect)
        if parsed and len(parsed) > 0:
            return parsed[0]
        return None
    except sqlglot.errors.ParseError:
        return None


def validate_sql(query: str, dialect: str = "postgresql") -> tuple[bool, Optional[str]]:
    """Validate a SQL query and return (is_valid, error_message)."""
    sqlglot_dialect = DIALECT_MAP.get(dialect, "postgres")
    try:
        parsed = sqlglot.parse(query, read=sqlglot_dialect)
        if not parsed or len(parsed) == 0:
            return False, "Empty or invalid SQL query"
        return True, None
    except sqlglot.errors.ParseError as e:
        return False, str(e)


def extract_tables(ast: exp.Expression) -> list[str]:
    """Extract all table names from a parsed SQL AST."""
    tables = set()
    for table in ast.find_all(exp.Table):
        table_name = table.name
        if table_name:
            tables.add(table_name)
    return sorted(tables)


def extract_columns(ast: exp.Expression) -> list[str]:
    """Extract all column references from a parsed SQL AST."""
    columns = set()
    for col in ast.find_all(exp.Column):
        col_name = col.name
        table = col.table
        if table:
            columns.add(f"{table}.{col_name}")
        else:
            columns.add(col_name)
    return sorted(columns)


def get_query_type(ast: exp.Expression) -> Optional[str]:
    """Determine the type of SQL query."""
    if isinstance(ast, exp.Select):
        return "SELECT"
    elif isinstance(ast, exp.Insert):
        return "INSERT"
    elif isinstance(ast, exp.Update):
        return "UPDATE"
    elif isinstance(ast, exp.Delete):
        return "DELETE"
    elif isinstance(ast, exp.Create):
        return "CREATE"
    elif isinstance(ast, exp.Drop):
        return "DROP"
    elif isinstance(ast, exp.Alter):
        return "ALTER"
    return "UNKNOWN"


def has_subqueries(ast: exp.Expression) -> bool:
    """Check if the query contains subqueries."""
    # Look for nested SELECT statements (skip the top-level one)
    subqueries = list(ast.find_all(exp.Subquery))
    return len(subqueries) > 0


def extract_joins(ast: exp.Expression) -> list[dict]:
    """Extract join information from the query."""
    joins = []
    for join in ast.find_all(exp.Join):
        join_info = {
            "type": "INNER",
            "table": None,
            "on_condition": None,
        }
        # Determine join type
        if join.args.get("side"):
            join_info["type"] = join.args["side"].upper() + " JOIN"
        else:
            join_info["type"] = "JOIN"
        if join.args.get("kind"):
            join_info["type"] = join.args["kind"].upper() + " " + join_info["type"]

        # Get the joined table
        table_expr = join.find(exp.Table)
        if table_expr:
            join_info["table"] = table_expr.name

        # Get the ON condition
        on_expr = join.args.get("on")
        if on_expr:
            join_info["on_condition"] = on_expr.sql()

        joins.append(join_info)
    return joins


def extract_where_conditions(ast: exp.Expression) -> list[str]:
    """Extract WHERE clause conditions."""
    conditions = []
    where = ast.find(exp.Where)
    if where:
        # Get individual conditions
        for condition in where.find_all(exp.Condition):
            conditions.append(condition.sql())
        if not conditions:
            conditions.append(where.this.sql())
    return conditions


def extract_aggregations(ast: exp.Expression) -> list[str]:
    """Extract aggregation functions used in the query."""
    aggs = set()
    agg_types = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)
    for agg in ast.find_all(*agg_types):
        aggs.add(agg.sql())
    return sorted(aggs)


def has_group_by(ast: exp.Expression) -> bool:
    """Check if the query has a GROUP BY clause."""
    return ast.find(exp.Group) is not None


def has_order_by(ast: exp.Expression) -> bool:
    """Check if the query has an ORDER BY clause."""
    return ast.find(exp.Order) is not None


def has_distinct(ast: exp.Expression) -> bool:
    """Check if the query uses DISTINCT."""
    select = ast.find(exp.Select)
    if select and select.args.get("distinct"):
        return True
    return ast.find(exp.Distinct) is not None


def has_having(ast: exp.Expression) -> bool:
    """Check if the query has a HAVING clause."""
    return ast.find(exp.Having) is not None


def has_window_functions(ast: exp.Expression) -> bool:
    """Check if the query uses window functions."""
    return ast.find(exp.Window) is not None


def has_limit(ast: exp.Expression) -> bool:
    """Check if the query has a LIMIT clause."""
    return ast.find(exp.Limit) is not None


def is_select_star(ast: exp.Expression) -> bool:
    """Check if the query uses SELECT *."""
    return ast.find(exp.Star) is not None


def format_sql(query: str, dialect: str = "postgresql") -> str:
    """Format/prettify a SQL query."""
    sqlglot_dialect = DIALECT_MAP.get(dialect, "postgres")
    try:
        return sqlglot.transpile(
            query,
            read=sqlglot_dialect,
            write=sqlglot_dialect,
            pretty=True,
        )[0]
    except Exception:
        return query


def transpile_sql(query: str, from_dialect: str, to_dialect: str) -> str:
    """Convert SQL from one dialect to another."""
    from_d = DIALECT_MAP.get(from_dialect, "postgres")
    to_d = DIALECT_MAP.get(to_dialect, "postgres")
    try:
        return sqlglot.transpile(query, read=from_d, write=to_d, pretty=True)[0]
    except Exception:
        return query
