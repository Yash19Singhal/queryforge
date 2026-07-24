"""
Optimization Engine — applies all optimization rules to a parsed SQL query.
"""

from sqlglot import exp
from app.models import OptimizationApplied, TableSchema
from app.optimizer.rules import ALL_RULES


def run_optimizations(
    ast: exp.Expression,
    schema_context: list[TableSchema],
) -> tuple[exp.Expression, list[OptimizationApplied]]:
    """
    Run all optimization rules against the AST.
    Returns the (possibly modified) AST and a list of applied optimizations.
    """
    current_ast = ast.copy()
    applied: list[OptimizationApplied] = []

    for rule in ALL_RULES:
        try:
            if rule.detect(current_ast, schema_context):
                new_ast, optimization = rule.optimize(current_ast, schema_context)
                if optimization:
                    applied.append(optimization)
                    if new_ast is not current_ast:
                        current_ast = new_ast
        except Exception:
            # Skip rules that error — don't break the whole optimization
            continue

    return current_ast, applied
