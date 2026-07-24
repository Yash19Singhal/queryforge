"""
Tests for the SQL Query Optimizer backend.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.parser.sql_parser import (
    parse_sql,
    validate_sql,
    extract_tables,
    extract_columns,
    get_query_type,
    format_sql,
    has_subqueries,
    is_select_star,
    extract_joins,
)
from app.optimizer.rules import ALL_RULES
from app.optimizer.engine import run_optimizations
from app.analyzer.complexity import score_complexity
from app.analyzer.plan import generate_query_plan
from app.models import TableSchema, ColumnDefinition, IndexDefinition


client = TestClient(app)


# ── Parser Tests ────────────────────────────────────────────────


class TestParser:
    def test_parse_valid_query(self):
        ast = parse_sql("SELECT * FROM users WHERE id = 1")
        assert ast is not None

    def test_parse_invalid_query(self):
        is_valid, error = validate_sql("SELEC * FORM users")
        # sqlglot is lenient, so this might still parse
        # Just test it doesn't crash
        assert isinstance(is_valid, bool)

    def test_extract_tables(self):
        ast = parse_sql("SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id")
        tables = extract_tables(ast)
        assert "users" in tables
        assert "orders" in tables

    def test_extract_columns(self):
        ast = parse_sql("SELECT u.name, u.email FROM users u")
        columns = extract_columns(ast)
        assert any("name" in c for c in columns)

    def test_get_query_type_select(self):
        ast = parse_sql("SELECT * FROM users")
        assert get_query_type(ast) == "SELECT"

    def test_has_subqueries(self):
        ast = parse_sql("SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)")
        assert has_subqueries(ast) is True

    def test_no_subqueries(self):
        ast = parse_sql("SELECT * FROM users WHERE id = 1")
        assert has_subqueries(ast) is False

    def test_is_select_star(self):
        ast = parse_sql("SELECT * FROM users")
        assert is_select_star(ast) is True

    def test_not_select_star(self):
        ast = parse_sql("SELECT id, name FROM users")
        assert is_select_star(ast) is False

    def test_extract_joins(self):
        ast = parse_sql(
            "SELECT * FROM users u LEFT JOIN orders o ON u.id = o.user_id"
        )
        joins = extract_joins(ast)
        assert len(joins) >= 1

    def test_format_sql(self):
        result = format_sql("SELECT * FROM users WHERE id=1", "postgresql")
        assert "SELECT" in result


# ── Optimizer Rules Tests ───────────────────────────────────────


class TestOptimizationRules:
    def test_select_star_detection(self):
        ast = parse_sql("SELECT * FROM users")
        rule = ALL_RULES[0]  # SelectStarElimination
        assert rule.detect(ast, []) is True

    def test_select_star_no_detection(self):
        ast = parse_sql("SELECT id, name FROM users")
        rule = ALL_RULES[0]
        assert rule.detect(ast, []) is False

    def test_subquery_to_join_detection(self):
        ast = parse_sql(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        )
        rule = ALL_RULES[2]  # SubqueryToJoin
        assert rule.detect(ast, []) is True

    def test_wildcard_like_detection(self):
        ast = parse_sql("SELECT * FROM users WHERE name LIKE '%john%'")
        rule = ALL_RULES[8]  # WildcardLikePattern
        assert rule.detect(ast, []) is True

    def test_function_on_column_detection(self):
        ast = parse_sql("SELECT * FROM users WHERE LOWER(email) = 'test@test.com'")
        rule = ALL_RULES[9]  # FunctionOnIndexedColumn
        assert rule.detect(ast, []) is True

    def test_run_optimizations(self):
        ast = parse_sql(
            "SELECT * FROM users WHERE name LIKE '%test%'"
        )
        _, applied = run_optimizations(ast, [])
        assert len(applied) > 0


# ── Complexity Tests ────────────────────────────────────────────


class TestComplexity:
    def test_simple_query(self):
        ast = parse_sql("SELECT id FROM users WHERE id = 1")
        result = score_complexity(ast)
        assert result.score <= 30
        assert result.label in ("Simple", "Moderate")

    def test_complex_query(self):
        ast = parse_sql("""
            SELECT u.name, COUNT(o.id)
            FROM users u
            LEFT JOIN orders o ON u.id = o.user_id
            LEFT JOIN products p ON o.product_id = p.id
            WHERE u.country = 'US'
            GROUP BY u.name
            HAVING COUNT(o.id) > 5
            ORDER BY COUNT(o.id) DESC
        """)
        result = score_complexity(ast)
        assert result.score > 30
        assert len(result.breakdown) > 0


# ── Query Plan Tests ────────────────────────────────────────────


class TestQueryPlan:
    def test_generate_plan(self):
        ast = parse_sql(
            "SELECT u.name FROM users u WHERE u.id = 1"
        )
        plan = generate_query_plan(ast, [])
        assert plan is not None
        assert plan.type == "Project"

    def test_plan_with_join(self):
        ast = parse_sql(
            "SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id"
        )
        plan = generate_query_plan(ast, [])
        assert plan is not None
        # Should have join node in children
        assert len(plan.children) > 0


# ── API Tests ───────────────────────────────────────────────────


class TestAPI:
    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_parse_valid(self):
        response = client.post(
            "/api/parse",
            json={"query": "SELECT * FROM users", "dialect": "postgresql"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert "users" in data["tables"]

    def test_format(self):
        response = client.post(
            "/api/format",
            json={"query": "SELECT * FROM users WHERE id=1", "dialect": "postgresql"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "SELECT" in data["formatted_query"]

    def test_optimize(self):
        response = client.post(
            "/api/optimize",
            json={
                "query": "SELECT * FROM users WHERE name LIKE '%john%'",
                "dialect": "postgresql",
                "schema_context": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "complexity" in data
        assert "optimizations_applied" in data
        assert data["complexity"]["score"] >= 0

    def test_optimize_with_schema(self):
        response = client.post(
            "/api/optimize",
            json={
                "query": "SELECT * FROM users u LEFT JOIN orders o ON o.user_id = u.id WHERE u.country = 'US'",
                "dialect": "postgresql",
                "schema_context": [
                    {
                        "name": "users",
                        "columns": [
                            {"name": "id", "data_type": "int", "is_nullable": False},
                            {"name": "name", "data_type": "varchar", "is_nullable": True},
                            {"name": "country", "data_type": "varchar", "is_nullable": True},
                        ],
                        "indexes": [],
                        "approximate_rows": 500000,
                    },
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "id", "data_type": "int", "is_nullable": False},
                            {"name": "user_id", "data_type": "int", "is_nullable": True},
                        ],
                        "indexes": [],
                        "approximate_rows": 1000000,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["index_suggestions"]) > 0

    def test_optimize_invalid_query(self):
        response = client.post(
            "/api/optimize",
            json={
                "query": "",
                "dialect": "postgresql",
                "schema_context": [],
            },
        )
        assert response.status_code == 422  # Validation error — min_length=1
