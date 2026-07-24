"""
SQL Formatting Utilities.
"""

from app.parser.sql_parser import format_sql


def prettify_sql(query: str, dialect: str = "postgresql") -> str:
    """Format a SQL query with proper indentation and line breaks."""
    return format_sql(query, dialect)
