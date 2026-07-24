"""
Optimization rules for the SQL Query Optimizer.

Each rule implements:
  - detect(ast, schema_context) -> bool : whether this pattern exists
  - optimize(ast, schema_context) -> tuple[ast, OptimizationApplied] : the fix
"""

from abc import ABC, abstractmethod
from typing import Optional
import sqlglot
from sqlglot import exp
from app.models import OptimizationApplied, TableSchema


class OptimizationRule(ABC):
    """Base class for all optimization rules."""

    name: str = "BaseRule"
    category: str = "query_rewrite"
    impact: str = "medium"

    @abstractmethod
    def detect(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> bool:
        """Check if this optimization can be applied."""
        pass

    @abstractmethod
    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        """Apply the optimization and return (new_ast, description)."""
        pass


def _rebuild_ast(sql: str, dialect: str = "postgres") -> Optional[exp.Expression]:
    """Helper to parse SQL back into AST."""
    try:
        parsed = sqlglot.parse(sql, read=dialect)
        return parsed[0] if parsed else None
    except Exception:
        return None


# ── Rule 1: SELECT * Elimination ────────────────────────────────


class SelectStarElimination(OptimizationRule):
    name = "SelectStarElimination"
    category = "query_rewrite"
    impact = "medium"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        return ast.find(exp.Star) is not None

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        # If schema context is provided, replace * with explicit columns
        if schema_context:
            tables = {t.name: t for t in schema_context}
            table_refs = {}
            for table in ast.find_all(exp.Table):
                alias = table.alias or table.name
                table_refs[alias] = table.name

            columns = []
            for alias, table_name in table_refs.items():
                if table_name in tables:
                    for col in tables[table_name].columns:
                        columns.append(f"{alias}.{col.name}")

            if columns:
                new_ast = ast.copy()
                select = new_ast.find(exp.Select)
                if select:
                    new_expressions = []
                    for col_str in columns:
                        parts = col_str.split(".")
                        new_expressions.append(
                            exp.Column(
                                this=exp.to_identifier(parts[1]),
                                table=exp.to_identifier(parts[0]),
                            )
                        )
                    select.set("expressions", new_expressions)
                    return new_ast, OptimizationApplied(
                        rule=self.name,
                        category=self.category,
                        impact=self.impact,
                        description="Replaced SELECT * with explicit column list",
                        explanation=(
                            "SELECT * fetches all columns including ones you don't need, "
                            "increasing I/O and memory usage. Listing only required columns "
                            "reduces data transfer and can enable covering index scans."
                        ),
                    )

        # Without schema — rewrite to add a comment marker showing the issue
        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="SELECT * detected — replace with explicit columns",
            explanation=(
                "SELECT * fetches every column from the table, even ones your "
                "application doesn't use. This wastes I/O bandwidth, prevents "
                "covering index optimizations, and makes your query fragile to "
                "schema changes. Always list the specific columns you need. "
                "Add your table schema in the Schema Context panel to auto-rewrite."
            ),
        )


# ── Rule 2: Predicate Pushdown ──────────────────────────────────


class PredicatePushdown(OptimizationRule):
    name = "PredicatePushdown"
    category = "query_rewrite"
    impact = "high"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        subqueries = list(ast.find_all(exp.Subquery))
        if not subqueries:
            return False
        where = ast.find(exp.Where)
        if not where:
            return False
        return True

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="Filter conditions can be pushed closer to the data source",
            explanation=(
                "Predicate pushdown moves WHERE filters into subqueries or closer "
                "to the base tables. This dramatically reduces the number of rows "
                "processed in intermediate steps, lowering memory usage and improving "
                "execution speed. The database scans fewer rows earlier in the pipeline."
            ),
        )


# ── Rule 3: Subquery to JOIN Conversion ─────────────────────────


class SubqueryToJoin(OptimizationRule):
    name = "SubqueryToJoin"
    category = "query_rewrite"
    impact = "high"

    def _find_in_subqueries(self, ast: exp.Expression) -> list:
        """Find WHERE x IN (SELECT ...) patterns."""
        results = []
        for in_expr in ast.find_all(exp.In):
            query = in_expr.args.get("query")
            if query is not None:
                results.append(in_expr)
        return results

    def _find_exists_subqueries(self, ast: exp.Expression) -> list:
        """Find WHERE EXISTS (SELECT ...) patterns."""
        return list(ast.find_all(exp.Exists))

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        return len(self._find_in_subqueries(ast)) > 0 or len(
            self._find_exists_subqueries(ast)
        ) > 0

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        in_subqueries = self._find_in_subqueries(ast)

        if in_subqueries:
            # Actually rewrite: WHERE col IN (SELECT sub_col FROM sub_table WHERE cond)
            # → JOIN sub_table ON col = sub_table.sub_col WHERE cond
            new_ast = ast.copy()

            for in_expr in list(new_ast.find_all(exp.In)):
                query_node = in_expr.args.get("query")
                if query_node is None:
                    continue

                # Find the subquery SELECT inside the Subquery node
                subquery = query_node.find(exp.Select) if not isinstance(query_node, exp.Select) else query_node
                if subquery is None:
                    continue

                # Get left column (the column being compared with IN)
                left_col = in_expr.this

                # Get subquery select column
                sub_expressions = subquery.args.get("expressions", [])
                if not sub_expressions:
                    continue
                sub_col = sub_expressions[0]

                # Get subquery FROM table
                sub_from = subquery.find(exp.From)
                if not sub_from:
                    continue
                sub_table = sub_from.find(exp.Table)
                if not sub_table:
                    continue

                sub_table_name = sub_table.name
                sub_table_alias = sub_table.alias or sub_table_name

                # Get subquery WHERE conditions
                sub_where = subquery.find(exp.Where)

                # Build the JOIN ON condition: left_col = sub_table.sub_col
                sub_col_name = sub_col.name if hasattr(sub_col, 'name') else str(sub_col)
                join_condition = exp.EQ(
                    this=left_col.copy(),
                    expression=exp.Column(
                        this=exp.to_identifier(sub_col_name),
                        table=exp.to_identifier(sub_table_alias),
                    )
                )

                # Create the JOIN node
                join_node = exp.Join(
                    this=sub_table.copy(),
                    on=join_condition,
                )

                # Add the JOIN to the main query's FROM clause
                main_select = new_ast if isinstance(new_ast, exp.Select) else new_ast.find(exp.Select)
                if main_select:
                    existing_joins = main_select.args.get("joins", [])
                    if isinstance(existing_joins, list):
                        existing_joins.append(join_node)
                    else:
                        existing_joins = [join_node]
                    main_select.set("joins", existing_joins)

                # Move subquery WHERE conditions to the main WHERE
                if sub_where and sub_where.this:
                    main_where = new_ast.find(exp.Where)
                    if main_where and main_where.this:
                        # Replace the IN expression with the sub_where condition
                        # First, remove the IN from the main WHERE
                        in_parent = in_expr.parent
                        if isinstance(in_parent, exp.And):
                            # Replace the AND node: keep the other side + add sub condition
                            other_side = in_parent.right if in_parent.left is in_expr else in_parent.left
                            new_condition = exp.And(
                                this=other_side,
                                expression=sub_where.this.copy(),
                            )
                            in_parent.replace(new_condition)
                        else:
                            # The IN is the only WHERE condition
                            main_where.set("this", sub_where.this.copy())
                    else:
                        # No main WHERE, create one from sub conditions
                        in_expr.replace(sub_where.this.copy())
                else:
                    # No sub WHERE — just remove the IN expression
                    main_where = new_ast.find(exp.Where)
                    if main_where:
                        in_parent = in_expr.parent
                        if isinstance(in_parent, exp.And):
                            other_side = in_parent.right if in_parent.left is in_expr else in_parent.left
                            in_parent.replace(other_side)
                        else:
                            # IN was the only condition, remove WHERE entirely
                            main_where.pop()

            return new_ast, OptimizationApplied(
                rule=self.name,
                category=self.category,
                impact=self.impact,
                description="Converted IN (SELECT ...) subquery to JOIN",
                explanation=(
                    "Subqueries with IN execute the inner query for potential "
                    "re-evaluation. Converting to a JOIN allows the optimizer to "
                    "choose hash joins or merge joins, which are typically much "
                    "faster. JOINs also enable better use of indexes on both tables."
                ),
            )

        # EXISTS subqueries — suggest only (complex to auto-rewrite safely)
        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="EXISTS subquery can be rewritten as a JOIN",
            explanation=(
                "EXISTS subqueries execute the inner query once per outer row in "
                "the worst case (correlated subquery). Rewriting as a JOIN gives "
                "the query planner more freedom to pick efficient join strategies."
            ),
        )


# ── Rule 4: OR to UNION Conversion ──────────────────────────────


class OrToUnion(OptimizationRule):
    name = "OrToUnion"
    category = "query_rewrite"
    impact = "medium"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        where = ast.find(exp.Where)
        if not where:
            return False

        or_exprs = list(where.find_all(exp.Or))
        if not or_exprs:
            return False

        for or_expr in or_exprs:
            left_cols = {c.name for c in or_expr.left.find_all(exp.Column)} if hasattr(or_expr, 'left') else set()
            right_cols = {c.name for c in or_expr.right.find_all(exp.Column)} if hasattr(or_expr, 'right') else set()
            if left_cols and right_cols and left_cols != right_cols:
                return True

        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        # Actually rewrite: SELECT ... WHERE a = 1 OR b = 2
        # → SELECT ... WHERE a = 1 UNION ALL SELECT ... WHERE b = 2
        new_ast = ast.copy()
        where = new_ast.find(exp.Where)
        if not where:
            return ast, None

        or_expr = where.find(exp.Or)
        if not or_expr:
            return ast, None

        left_cond = or_expr.left
        right_cond = or_expr.right

        # Create two copies of the query with different WHERE clauses
        query1 = ast.copy()
        query2 = ast.copy()

        # Set WHERE for query1 to left condition
        where1 = query1.find(exp.Where)
        if where1:
            where1.set("this", left_cond.copy())

        # Set WHERE for query2 to right condition
        where2 = query2.find(exp.Where)
        if where2:
            where2.set("this", right_cond.copy())

        # Remove ORDER BY and LIMIT from individual queries (apply to outer)
        for q in [query1, query2]:
            order = q.find(exp.Order)
            if order:
                order.pop()
            limit = q.find(exp.Limit)
            if limit:
                limit.pop()

        # Build UNION ALL
        union = exp.Union(this=query1, expression=query2, distinct=False)

        return union, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="Rewrote OR conditions on different columns to UNION ALL",
            explanation=(
                "When OR connects conditions on different columns (e.g., "
                "WHERE a.col1 = 1 OR b.col2 = 2), the database often cannot "
                "use indexes efficiently and falls back to a full table scan. "
                "Splitting into two queries with UNION ALL allows each branch to "
                "use its own index independently."
            ),
        )


# ── Rule 5: Redundant DISTINCT Removal ──────────────────────────


class RedundantDistinct(OptimizationRule):
    name = "RedundantDistinct"
    category = "query_rewrite"
    impact = "low"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        select = ast.find(exp.Select)
        if not select:
            return False

        has_distinct = select.args.get("distinct") is not None or ast.find(exp.Distinct) is not None
        if not has_distinct:
            return False

        # GROUP BY already guarantees uniqueness
        group = ast.find(exp.Group)
        if group:
            return True

        # Selecting a unique/primary key column
        if schema_context:
            for table_schema in schema_context:
                for idx in table_schema.indexes:
                    if idx.is_unique:
                        select_cols = {c.name for c in ast.find_all(exp.Column)}
                        if all(c in select_cols for c in idx.columns):
                            return True

        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        # Actually remove DISTINCT from the AST
        new_ast = ast.copy()
        select = new_ast.find(exp.Select)
        if select:
            select.set("distinct", None)

        return new_ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="Removed redundant DISTINCT — results are already unique",
            explanation=(
                "When a query uses GROUP BY or selects a unique/primary key, "
                "the results are inherently unique. Adding DISTINCT forces the "
                "database to perform an extra deduplication step (sort + compare "
                "or hash), wasting CPU and memory for no benefit."
            ),
        )


# ── Rule 6: Join Order Optimization ─────────────────────────────


class JoinOrderOptimization(OptimizationRule):
    name = "JoinOrderOptimization"
    category = "join_optimization"
    impact = "high"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        if not schema_context:
            return False

        joins = list(ast.find_all(exp.Join))
        if not joins:
            return False

        row_counts = {t.name: t.approximate_rows for t in schema_context if t.approximate_rows}
        if len(row_counts) < 2:
            return False

        from_table = ast.find(exp.From)
        if from_table:
            main_table = from_table.find(exp.Table)
            if main_table and main_table.name in row_counts:
                for join in joins:
                    join_table = join.find(exp.Table)
                    if join_table and join_table.name in row_counts:
                        if row_counts[main_table.name] > row_counts[join_table.name]:
                            return True

        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        row_counts = {t.name: t.approximate_rows for t in schema_context if t.approximate_rows}

        tables_info = []
        for name, count in sorted(row_counts.items(), key=lambda x: x[1]):
            tables_info.append(f"{name} (~{count:,} rows)")

        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description=f"Consider reordering joins: {' → '.join(tables_info)}",
            explanation=(
                "Starting with the smaller table in a join reduces the size of "
                "intermediate results. When the database processes a join, it "
                "typically builds a hash table from one side — using the smaller "
                "table for this is faster and uses less memory."
            ),
        )


# ── Rule 7: Implicit Type Conversion ────────────────────────────


class ImplicitTypeConversion(OptimizationRule):
    name = "ImplicitTypeConversion"
    category = "anti_pattern"
    impact = "high"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        if not schema_context:
            return False

        col_types = {}
        for table in schema_context:
            for col in table.columns:
                col_types[col.name] = col.data_type.lower()
                col_types[f"{table.name}.{col.name}"] = col.data_type.lower()

        where = ast.find(exp.Where)
        if not where:
            return False

        for eq in where.find_all(exp.EQ):
            col = eq.find(exp.Column)
            lit = eq.find(exp.Literal)
            if col and lit:
                col_name = col.name
                col_type = col_types.get(col_name, None)
                if col_type and col_type in ("int", "integer", "bigint", "smallint"):
                    if lit.is_string:
                        return True
                elif col_type and col_type in ("varchar", "text", "char"):
                    if lit.is_int:
                        return True

        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="Implicit type conversion detected in WHERE clause",
            explanation=(
                "When you compare a column to a value of a different type "
                "(e.g., WHERE integer_col = '123'), the database must convert "
                "every row's value before comparison. This prevents index usage. "
                "Use the correct type for literal values to enable index scans."
            ),
        )


# ── Rule 8: Null-Safe Join ──────────────────────────────────────


class NullSafeJoin(OptimizationRule):
    name = "NullSafeJoin"
    category = "join_optimization"
    impact = "medium"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        for join in ast.find_all(exp.Join):
            side = join.args.get("side", "")
            if side and str(side).upper() in ("LEFT", "RIGHT", "FULL"):
                on = join.args.get("on")
                if on:
                    has_null_check = on.find(exp.Not) is not None and on.find(exp.Is) is not None
                    if not has_null_check:
                        return True
        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        # Actually add IS NOT NULL to the join condition
        new_ast = ast.copy()

        for join in list(new_ast.find_all(exp.Join)):
            side = join.args.get("side", "")
            if not (side and str(side).upper() in ("LEFT", "RIGHT", "FULL")):
                continue

            on = join.args.get("on")
            if not on:
                continue

            # Find the foreign key column from the joined table
            join_table = join.find(exp.Table)
            if not join_table:
                continue

            join_alias = join_table.alias or join_table.name

            # Find column from the joined table in the ON condition
            fk_col = None
            for col in on.find_all(exp.Column):
                if col.table == join_alias:
                    fk_col = col
                    break

            if not fk_col:
                # Try first column from ON condition's EQ expression
                eq = on.find(exp.EQ)
                if eq:
                    for col in eq.find_all(exp.Column):
                        fk_col = col
                        break

            if fk_col:
                # Build: original_on AND fk_col IS NOT NULL
                is_not_null = exp.Not(
                    this=exp.Is(
                        this=fk_col.copy(),
                        expression=exp.Null(),
                    )
                )
                new_on = exp.And(this=on.copy(), expression=is_not_null)
                join.set("on", new_on)

        return new_ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="Added IS NOT NULL check to outer join foreign key column",
            explanation=(
                "In LEFT/RIGHT joins, the foreign key column in the outer table "
                "may contain NULL values. Adding an explicit IS NOT NULL check "
                "in the ON clause helps the optimizer filter out NULL rows early, "
                "reducing the join's intermediate result size."
            ),
        )


# ── Rule 9: Wildcard LIKE Pattern ───────────────────────────────


class WildcardLikePattern(OptimizationRule):
    name = "WildcardLikePattern"
    category = "anti_pattern"
    impact = "high"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        for like in ast.find_all(exp.Like):
            pattern = like.args.get("expression")
            if pattern and isinstance(pattern, exp.Literal):
                val = pattern.this
                if val.startswith("%"):
                    return True
        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="Leading wildcard in LIKE pattern prevents index usage",
            explanation=(
                "A LIKE pattern starting with % (e.g., '%search_term') forces a "
                "full table scan because the database cannot use a B-tree index "
                "to find matches. Consider using full-text search "
                "(tsvector/GIN in PostgreSQL, FULLTEXT in MySQL) "
                "or a trigram index (pg_trgm) for pattern matching."
            ),
        )


# ── Rule 10: Function on Indexed Column ─────────────────────────


class FunctionOnIndexedColumn(OptimizationRule):
    name = "FunctionOnIndexedColumn"
    category = "anti_pattern"
    impact = "high"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        where = ast.find(exp.Where)
        if not where:
            return False

        func_types = (exp.Lower, exp.Upper, exp.Trim, exp.Cast, exp.Substring, exp.Anonymous)
        for func in where.find_all(*func_types):
            if func.find(exp.Column):
                return True

        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        where = ast.find(exp.Where)
        func_names = set()
        func_types = (exp.Lower, exp.Upper, exp.Trim, exp.Cast, exp.Substring, exp.Anonymous)
        if where:
            for func in where.find_all(*func_types):
                if func.find(exp.Column):
                    func_names.add(type(func).__name__.upper())

        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description=f"Function(s) on column in WHERE clause: {', '.join(func_names) if func_names else 'detected'}",
            explanation=(
                "Wrapping a column in a function (e.g., WHERE LOWER(email) = 'test') "
                "prevents the database from using an index on that column. The database "
                "must apply the function to every row before comparing. Instead, create "
                "a functional/expression index (e.g., CREATE INDEX ON table(LOWER(email))) "
                "or normalize the data at write time."
            ),
        )


# ── Rule 11: UNION ALL vs UNION ─────────────────────────────────


class UnionAllVsUnion(OptimizationRule):
    name = "UnionAllVsUnion"
    category = "query_rewrite"
    impact = "medium"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        for union in ast.find_all(exp.Union):
            if not union.args.get("distinct") is False:
                return True
        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        # Rewrite UNION to UNION ALL
        new_ast = ast.copy()
        for union in new_ast.find_all(exp.Union):
            union.set("distinct", False)

        return new_ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact=self.impact,
            description="Changed UNION to UNION ALL (removes deduplication overhead)",
            explanation=(
                "UNION removes duplicate rows by performing a sort or hash operation "
                "on the combined result set. If you know the results won't have "
                "duplicates (or don't care about them), UNION ALL skips this expensive "
                "deduplication step and can be significantly faster on large datasets."
            ),
        )


# ── Rule 12: Missing WHERE in UPDATE/DELETE ─────────────────────


class MissingWhereClause(OptimizationRule):
    name = "MissingWhereClause"
    category = "anti_pattern"
    impact = "high"

    def detect(self, ast: exp.Expression, schema_context: list[TableSchema]) -> bool:
        if isinstance(ast, (exp.Update, exp.Delete)):
            where = ast.find(exp.Where)
            return where is None
        return False

    def optimize(
        self, ast: exp.Expression, schema_context: list[TableSchema]
    ) -> tuple[exp.Expression, Optional[OptimizationApplied]]:
        if not self.detect(ast, schema_context):
            return ast, None

        query_type = "UPDATE" if isinstance(ast, exp.Update) else "DELETE"
        return ast, OptimizationApplied(
            rule=self.name,
            category=self.category,
            impact="high",
            description=f"⚠️ {query_type} without WHERE clause will affect ALL rows",
            explanation=(
                f"A {query_type} statement without a WHERE clause will modify every "
                f"row in the table. This is almost always unintentional and can cause "
                f"catastrophic data loss. Always add a WHERE clause to limit the scope "
                f"of {query_type} operations."
            ),
        )


# ── All Rules Registry ──────────────────────────────────────────

ALL_RULES: list[OptimizationRule] = [
    SelectStarElimination(),
    PredicatePushdown(),
    SubqueryToJoin(),
    OrToUnion(),
    RedundantDistinct(),
    JoinOrderOptimization(),
    ImplicitTypeConversion(),
    NullSafeJoin(),
    WildcardLikePattern(),
    FunctionOnIndexedColumn(),
    UnionAllVsUnion(),
    MissingWhereClause(),
]
