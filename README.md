# ⚡ QueryForge — Rule-Based SQL Query Optimizer

> A web application that parses SQL queries, detects inefficient patterns, suggests optimizations, shows the optimized query, and explains why each optimization helps — with an interactive query execution plan visualization.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16+-000000?style=flat-square&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-27%20passing-brightgreen?style=flat-square)

---

## 📖 Table of Contents

- [What Does This Project Do?](#-what-does-this-project-do)
- [Why This Project Matters (For Interviewers)](#-why-this-project-matters)
- [Core Concepts Explained](#-core-concepts-explained)
  - [What is a Query Optimizer?](#what-is-a-query-optimizer)
  - [What is an AST?](#what-is-an-ast-abstract-syntax-tree)
  - [What are Indexes?](#what-are-indexes)
  - [What is a Query Execution Plan?](#what-is-a-query-execution-plan)
  - [What is Cost Estimation?](#what-is-cost-estimation)
- [Architecture](#-architecture)
- [Optimization Rules (Deep Dive)](#-optimization-rules-deep-dive)
- [How the Code Works](#-how-the-code-works)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [API Documentation](#-api-documentation)
- [Project Structure](#-project-structure)
- [Tech Stack](#-tech-stack)
- [Deployment](#-deployment)
- [Running Tests](#-running-tests)
- [Interview Prep Guide](#-interview-prep-guide)

---

## 🎯 What Does This Project Do?

**In one sentence:** Users paste a SQL query → the tool parses it into a tree, runs 12 optimization rules against it, transforms the SQL, and shows exactly what changed and why.

### The Flow

```
User pastes SQL query
        │
        ▼
┌─────────────────┐
│  1. PARSE       │  SQL string → Abstract Syntax Tree (AST)
│     (sqlglot)   │  using the sqlglot library
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. ANALYZE     │  Score complexity (0-100)
│                 │  Detect bottlenecks
│                 │  Generate logical query plan
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. OPTIMIZE    │  Run 12 rules against the AST
│                 │  Some rules REWRITE the AST (e.g., subquery → JOIN)
│                 │  Some rules DETECT anti-patterns (e.g., leading wildcard)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. ESTIMATE    │  Compare cost before vs. after
│     COST        │  Estimate performance improvement
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. RESPOND     │  Return: optimized SQL, complexity score,
│                 │  cost comparison, query plan tree,
│                 │  index suggestions, explanations
└─────────────────┘
```

---

## 💡 Why This Project Matters

This is **not** a CRUD app. It demonstrates understanding of:

| Concept | What It Shows |
|---------|--------------|
| **Compiler design** | Parsing SQL into ASTs, tree traversal, AST transformation |
| **Database internals** | How query planners work, cost-based optimization, index selection |
| **Algorithm design** | Rule-based pattern matching, tree traversal, cost modeling |
| **Software architecture** | Clean separation: parser → optimizer → analyzer → API |
| **Full-stack engineering** | Python backend + TypeScript frontend, API design, deployment |

### What Makes It Different From a CRUD App

A CRUD app says: *"I can use a database."*
This project says: *"I understand how the database works internally."*

Real database optimizers (PostgreSQL, MySQL) use the same two-phase approach:
1. **Rule-based optimization** — apply known transformation rules (what this project does)
2. **Cost-based optimization** — estimate cost of different plans and pick the cheapest (what this project does, simplified)

---

## 📚 Core Concepts Explained

### What is a Query Optimizer?

When you write SQL, you're telling the database **what** data you want, not **how** to get it. The query optimizer figures out the "how."

**Example:**
```sql
SELECT * FROM users WHERE age > 25 AND country = 'US'
```

The database has choices:
- Scan every row and check both conditions? (slow)
- Use an index on `country` first, then filter by `age`? (faster)
- Use an index on `age` first, then filter by `country`? (depends on data)

The optimizer picks the best strategy. Our tool does a simplified version of this — it looks at your SQL and tells you which patterns are inefficient and how to fix them.

---

### What is an AST (Abstract Syntax Tree)?

An AST is a **tree representation** of code. Instead of treating SQL as a string, we parse it into a structured tree that we can analyze and transform.

**This SQL:**
```sql
SELECT name FROM users WHERE age > 25
```

**Becomes this tree:**
```
         Select
        /      \
    Column     Where
    (name)       |
      |        GT (>)
    Table      /    \
   (users)  Column  Literal
            (age)    (25)
```

**Why do we need this?** You can't reliably analyze or transform SQL as a string — regex breaks on edge cases. With an AST, you can:
- Walk the tree to find patterns (e.g., "is there a subquery?")
- Transform nodes (e.g., replace a subquery with a JOIN)
- Generate valid SQL back from the modified tree

We use the **sqlglot** library for parsing. It supports PostgreSQL, MySQL, and SQLite dialects.

---

### What are Indexes?

An index is like a **book's table of contents**. Without it, finding data requires reading every page (full table scan). With it, you jump directly to the right page.

**Without index (Full Table Scan):**
```
Table: users (1,000,000 rows)
Query: WHERE country = 'US'

Database must check ALL 1,000,000 rows → O(n)
```

**With index on `country`:**
```
Index: B-Tree on users(country)

Database looks up 'US' in the B-Tree → O(log n)
Then fetches only matching rows (~50,000)
```

**Types of indexes this tool suggests:**

| Type | Example | When It Helps |
|------|---------|--------------|
| **Single column** | `INDEX(country)` | Filtering on one column |
| **Composite** | `INDEX(country, age)` | Filtering on multiple columns |
| **Covering** | `INDEX(country, age, name)` | When all SELECT + WHERE columns are in the index — database never touches the actual table |

---

### What is a Query Execution Plan?

A query plan is the **step-by-step strategy** the database uses to execute your query. Our tool generates a **logical plan** — a tree showing the operations in order.

**Example plan for:**
```sql
SELECT u.name, COUNT(o.id)
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.country = 'US'
GROUP BY u.name
ORDER BY COUNT(o.id) DESC
LIMIT 20
```

```
Project (u.name, COUNT(o.id))
  └── Limit 20
       └── Sort (COUNT(o.id) DESC)
            └── Hash Aggregate (GROUP BY u.name)
                 └── Filter (u.country = 'US')
                      └── Hash LEFT JOIN (o.user_id = u.id)
                           ├── Sequential Scan on users
                           └── Sequential Scan on orders
```

**Reading bottom-up:** The database scans both tables, joins them, filters for US users, groups by name, sorts by count, takes top 20, and projects the final columns.

**Why this matters:** Seeing the plan reveals bottlenecks. A "Sequential Scan on users (1M rows)" screams "add an index!" A "Nested Loop Join" on large tables means "switch to Hash Join."

---

### What is Cost Estimation?

Cost estimation assigns **relative numbers** to operations so you can compare "before" vs. "after."

**Our cost model:**

| Operation | Relative Cost | Why |
|-----------|:---:|-----|
| Full Table Scan | `100 × (rows / 10K)` | Reads every row — scales linearly |
| Index Scan | `10 × log₂(rows)` | B-tree lookup — scales logarithmically |
| Nested Loop Join | `80 × (rows / 10K)` | O(n × m) — very expensive |
| Hash Join | `30 × (rows / 10K)` | O(n + m) — builds hash table |
| Sort (ORDER BY) | `20 × log₂(rows)` | Merge sort — O(n log n) |
| Aggregate (GROUP BY) | `15` | Hash or sort based |
| Subquery penalty | `50` per subquery | May execute once per outer row |

**Example:** A query scanning 500K rows with a nested loop join might cost `4,000 + 4,000 = 8,000 units`. After optimization (add index + hash join), it might cost `166 + 1,500 = 1,666 units` — a **79% reduction**.

> ⚠️ These are **relative** costs for comparison, not actual milliseconds. Real databases use statistics (histograms, cardinality estimates) for precise cost modeling.

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│                     (Next.js + TypeScript)                    │
│                                                              │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐  │
│  │  Query   │ │   Stats   │ │  Query   │ │  Analysis    │  │
│  │  Editor  │ │   Panel   │ │  Plan    │ │  Tabs        │  │
│  │          │ │           │ │  Tree    │ │  (4 views)   │  │
│  └────┬─────┘ └───────────┘ └──────────┘ └──────────────┘  │
│       │                                                      │
│       │  HTTP POST /api/optimize                             │
│       ▼                                                      │
├──────────────────────────────────────────────────────────────┤
│                        BACKEND                               │
│                     (Python + FastAPI)                        │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────┐   │
│  │   Parser    │──▶│  Optimizer   │──▶│   Analyzer     │   │
│  │  (sqlglot)  │   │  (12 rules)  │   │  (complexity,  │   │
│  │             │   │  (engine)    │   │   plan, cost,  │   │
│  │  SQL → AST  │   │  (cost)     │   │   indexes)     │   │
│  └─────────────┘   └──────────────┘   └────────────────┘   │
│                                                              │
│  Data flow: SQL string → AST → Rule matching → AST          │
│  transform → Cost comparison → JSON response                 │
└──────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

Each module has a **single responsibility**:
- **Parser** — only converts SQL ↔ AST (doesn't know about rules)
- **Optimizer** — only applies rules to ASTs (doesn't know about HTTP)
- **Analyzer** — only scores/plans/suggests (doesn't modify queries)
- **API (main.py)** — only orchestrates the above and handles HTTP

This means you can test each piece independently, swap implementations, or add new rules without touching other modules.

---

## 🔧 Optimization Rules (Deep Dive)

### Rule 1: SELECT * Elimination
**Category:** Query Rewrite | **Impact:** Medium

```sql
-- Before:
SELECT * FROM users WHERE country = 'US'

-- After (with schema context):
SELECT users.id, users.name, users.country FROM users WHERE country = 'US'
```

**Why it matters:** `SELECT *` fetches ALL columns — even blobs, text fields, and columns you don't display. This wastes network bandwidth and prevents **covering index** optimizations. If an index contains all the columns you need, the database can answer the query from the index alone without touching the actual table (called an "index-only scan").

**How it works in code:** The rule checks for `exp.Star` nodes in the AST. If schema context is provided, it replaces the `*` with explicit column references from the table definitions.

---

### Rule 2: Predicate Pushdown
**Category:** Query Rewrite | **Impact:** High

```sql
-- The idea: move filters as close to the data source as possible

-- Before (filter applied AFTER subquery returns all rows):
SELECT * FROM (SELECT * FROM orders WHERE total > 100) sub
WHERE sub.date > '2024-01-01'

-- After (filter pushed INTO the subquery):
SELECT * FROM (SELECT * FROM orders WHERE total > 100 AND date > '2024-01-01') sub
```

**Why it matters:** Without pushdown, the inner query returns ALL rows matching `total > 100`, then the outer query filters again. With pushdown, the database filters both conditions at once, scanning far fewer rows.

**Real-world analogy:** Instead of ordering 1,000 books from a warehouse and then returning the ones you don't want, you tell the warehouse to only ship the ones you need.

---

### Rule 3: Subquery to JOIN Conversion
**Category:** Query Rewrite | **Impact:** High

```sql
-- Before:
SELECT * FROM products
WHERE category_id IN (SELECT id FROM categories WHERE active = 1)

-- After (rewritten by QueryForge):
SELECT * FROM products
JOIN categories ON products.category_id = categories.id
WHERE categories.active = 1
```

**Why it matters:** `IN (SELECT ...)` can cause the database to execute the subquery repeatedly or materialize it into a temporary table. A `JOIN` lets the optimizer choose efficient strategies (hash join, merge join) and use indexes on both tables.

**How it works in code:** The rule finds `exp.In` nodes containing `exp.Subquery` children. It extracts the subquery's table, column, and WHERE conditions, then constructs a new `exp.Join` node and adds it to the main query's FROM clause while moving conditions to the main WHERE.

---

### Rule 4: OR to UNION ALL Conversion
**Category:** Query Rewrite | **Impact:** Medium

```sql
-- Before:
SELECT * FROM products WHERE name = 'iPhone' OR category_id = 5

-- After:
SELECT * FROM products WHERE name = 'iPhone'
UNION ALL
SELECT * FROM products WHERE category_id = 5
```

**Why it matters:** When `OR` connects conditions on **different columns**, the database usually can't use indexes on either column — it falls back to a full table scan. By splitting into `UNION ALL`, each branch can use its own index independently.

**When NOT to use this:** If both conditions are on the **same column** (e.g., `WHERE status = 'active' OR status = 'pending'`), the database handles it fine with a single index. This rule only fires when columns differ.

---

### Rule 5: Redundant DISTINCT Removal
**Category:** Query Rewrite | **Impact:** Low

```sql
-- Before:
SELECT DISTINCT department FROM employees GROUP BY department

-- After (DISTINCT removed):
SELECT department FROM employees GROUP BY department
```

**Why it matters:** `GROUP BY` already guarantees unique results. Adding `DISTINCT` on top forces an extra deduplication pass (sort or hash), wasting CPU for no benefit.

---

### Rule 6: Join Order Optimization
**Category:** Join Optimization | **Impact:** High

```
-- Schema context: users (500K rows), orders (2M rows)
-- Suggestion: Start with users (smaller), then join orders

-- Why: Hash joins build a hash table from one side.
-- Building it from the smaller table (500K) uses 4x less memory
-- than building from the larger table (2M).
```

**Note:** Modern optimizers often handle this automatically, but in complex queries with 3+ joins, explicit ordering can help.

---

### Rule 7: Implicit Type Conversion Detection
**Category:** Anti-pattern | **Impact:** High

```sql
-- Problem (column is INTEGER, value is STRING):
WHERE user_id = '123'

-- Fix:
WHERE user_id = 123
```

**Why it matters:** When types don't match, the database must **cast every row** before comparing. This prevents index usage because the casted value doesn't match the stored index values. A simple type fix can turn a full table scan into an index lookup.

---

### Rule 8: Null-Safe Join
**Category:** Join Optimization | **Impact:** Medium

```sql
-- Before:
SELECT * FROM users u
LEFT JOIN orders o ON o.user_id = u.id

-- After:
SELECT * FROM users u
LEFT JOIN orders o ON o.user_id = u.id AND o.user_id IS NOT NULL
```

**Why it matters:** In LEFT JOINs, the foreign key (`o.user_id`) may be NULL. Adding an explicit `IS NOT NULL` helps the optimizer skip NULL rows during the join, reducing intermediate result size.

---

### Rule 9: Leading Wildcard LIKE Detection
**Category:** Anti-pattern | **Impact:** High

```sql
-- Problem:
WHERE email LIKE '%@gmail.com'

-- This FORCES a full table scan. The database cannot use a
-- B-tree index because it doesn't know where the string starts.
```

**Fix suggestions:**
- PostgreSQL: Use `pg_trgm` extension with GIN index
- MySQL: Use `FULLTEXT` index
- General: Reverse the string and use a suffix index, or use a full-text search engine (Elasticsearch)

---

### Rule 10: Function on Indexed Column
**Category:** Anti-pattern | **Impact:** High

```sql
-- Problem:
WHERE LOWER(email) = 'user@test.com'

-- The database must apply LOWER() to EVERY row before comparing.
-- Even if there's an index on `email`, it can't be used.
```

**Fix:**
```sql
-- Option 1: Create a functional index
CREATE INDEX idx_email_lower ON users(LOWER(email));

-- Option 2: Normalize data at write time
-- Store emails in lowercase when inserting/updating
```

---

### Rule 11: UNION to UNION ALL
**Category:** Query Rewrite | **Impact:** Medium

```sql
-- Before:
SELECT name FROM employees UNION SELECT name FROM contractors

-- After:
SELECT name FROM employees UNION ALL SELECT name FROM contractors
```

**Why:** `UNION` sorts the combined result to remove duplicates. `UNION ALL` skips sorting. If you know there are no duplicates (or don't care), `UNION ALL` is significantly faster on large datasets.

---

### Rule 12: Missing WHERE in UPDATE/DELETE
**Category:** Anti-pattern (Safety) | **Impact:** High ⚠️

```sql
-- DANGER:
DELETE FROM sessions;
-- This deletes EVERY row in the table!
```

This is a safety check, not a performance optimization. It warns when `UPDATE` or `DELETE` statements have no `WHERE` clause, which almost always indicates a mistake.

---

## ⚙ How the Code Works

### Backend File-by-File

| File | Purpose | Key Concepts |
|------|---------|-------------|
| [`parser/sql_parser.py`](backend/app/parser/sql_parser.py) | Parse SQL → AST using sqlglot. Extract tables, columns, joins, subqueries. | AST traversal, `exp.Table`, `exp.Column`, `exp.Join` node types |
| [`optimizer/rules.py`](backend/app/optimizer/rules.py) | 12 optimization rules, each with `detect()` and `optimize()` methods. | Strategy pattern, AST pattern matching, AST transformation |
| [`optimizer/engine.py`](backend/app/optimizer/engine.py) | Runs all rules sequentially against the AST. | Pipeline pattern, error isolation |
| [`optimizer/cost.py`](backend/app/optimizer/cost.py) | Assigns relative cost scores to query operations. | Cost modeling, Big-O complexity, logarithmic vs linear scaling |
| [`analyzer/complexity.py`](backend/app/analyzer/complexity.py) | Scores query complexity 0-100 based on structural factors. | Weighted scoring, feature extraction |
| [`analyzer/plan.py`](backend/app/analyzer/plan.py) | Generates a logical query plan tree from the AST. | Tree construction, bottom-up plan building |
| [`analyzer/index_advisor.py`](backend/app/analyzer/index_advisor.py) | Suggests indexes based on WHERE, JOIN, ORDER BY columns. | Index theory, covering indexes, composite indexes |
| [`models.py`](backend/app/models.py) | Pydantic request/response schemas. | Data validation, API contracts |
| [`main.py`](backend/app/main.py) | FastAPI app — orchestrates parse → optimize → analyze → respond. | REST API design, CORS, dependency orchestration |

### Frontend Components

| Component | Purpose |
|-----------|---------|
| `page.tsx` | Main page — assembles all components, manages state |
| `StatsPanel.tsx` | Shows complexity score, performance gain, cost comparison, bottleneck |
| `AnalysisTabs.tsx` | 4-tab view: Optimizations, Index Suggestions, Explain Plan, Diff View |
| `QueryPlan.tsx` | Interactive tree visualization of the logical execution plan |
| `SchemaInput.tsx` | Collapsible panel for defining table schemas |
| `HistoryPanel.tsx` | Slide-out sidebar with past queries (localStorage) |
| `PixelProgress.tsx` | Retro pixel-art progress bar (RPG health bar style) |

---

## 🎮 Features

- **12 optimization rules** across 4 categories (query rewrite, join optimization, anti-pattern detection, safety)
- **Actual SQL rewriting** — SubqueryToJoin, NullSafeJoin, OrToUnion transform the AST, not just flag issues
- **Query execution plan visualization** — interactive tree with expandable nodes
- **Cost estimation model** — before/after cost comparison with percentage improvement
- **Complexity scorer** — 0-100 score with factor breakdown
- **Index advisor** — suggests single, composite, and covering indexes with ready-to-run CREATE INDEX statements
- **Schema context** — define tables, columns, indexes, row counts for smarter analysis
- **Side-by-side diff view** — visual comparison of original vs. optimized SQL
- **SQL syntax highlighting** — keywords, functions, strings, comments colored
- **Multi-dialect support** — PostgreSQL, MySQL, SQLite
- **Query history** — saved in localStorage, searchable
- **Retro arcade UI** — CRT scanlines, pixel fonts, neon colors, RPG stat bars
- **Keyboard shortcuts** — Ctrl+Enter to optimize

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.12+** — [download](https://www.python.org/downloads/)
- **Node.js 20+** — [download](https://nodejs.org/)

### 1. Clone
```bash
git clone https://github.com/Yash19Singhal/queryforge.git
cd queryforge
```

### 2. Start the Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# API running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 3. Start the Frontend
```bash
cd frontend
npm install
npm run dev
# App running at http://localhost:3000
```

### 4. Use It
1. Open http://localhost:3000
2. Paste a SQL query (or use the pre-filled example)
3. Click **▶ OPTIMIZE QUERY** (or press Ctrl+Enter)
4. Explore the stats, optimized query, plan tree, and suggestions

### Docker (Optional)
```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

---

## 📡 API Documentation

### `GET /api/health`
Health check.
```json
{ "status": "ok", "version": "1.0.0" }
```

### `POST /api/optimize`
Main endpoint — full optimization pipeline.

**Request:**
```json
{
  "query": "SELECT * FROM users WHERE name LIKE '%john%'",
  "dialect": "postgresql",
  "schema_context": [
    {
      "name": "users",
      "columns": [
        { "name": "id", "data_type": "int", "is_nullable": false },
        { "name": "name", "data_type": "varchar", "is_nullable": true }
      ],
      "indexes": [
        { "name": "pk_users", "columns": ["id"], "is_unique": true }
      ],
      "approximate_rows": 500000
    }
  ]
}
```

**Response:**
```json
{
  "original_query": "SELECT ...",
  "optimized_query": "SELECT ...",
  "dialect": "postgresql",
  "complexity": {
    "score": 42,
    "label": "Moderate",
    "breakdown": [
      { "factor": "Joins", "score": 12, "description": "1 join(s): LEFT JOIN" }
    ]
  },
  "performance_gain": {
    "estimate": "~30% faster",
    "description": "Significant performance improvement with proper indexing"
  },
  "bottleneck": {
    "type": "sequential_scan",
    "table": "users",
    "description": "Sequential scan on users (~500,000 rows)"
  },
  "cost_estimate": {
    "before": 5000.0,
    "after": 1250.0,
    "unit": "relative cost units",
    "improvement_percent": 75.0
  },
  "optimizations_applied": [ ... ],
  "index_suggestions": [ ... ],
  "query_plan": { ... },
  "rows_scanned": { ... }
}
```

### `POST /api/parse`
Parse and validate SQL.
```json
// Request:
{ "query": "SELECT * FROM users", "dialect": "postgresql" }

// Response:
{ "is_valid": true, "tables": ["users"], "columns": ["*"], "query_type": "SELECT" }
```

### `POST /api/format`
Prettify SQL.
```json
// Request:
{ "query": "SELECT * FROM users WHERE id=1", "dialect": "postgresql" }

// Response:
{ "formatted_query": "SELECT\n  *\nFROM users\nWHERE\n  id = 1" }
```

---

## 📁 Project Structure

```
queryforge/
├── backend/                        # Python + FastAPI
│   ├── app/
│   │   ├── main.py                 # FastAPI app, routes, orchestration
│   │   ├── models.py               # Pydantic request/response schemas
│   │   ├── parser/
│   │   │   └── sql_parser.py       # SQL → AST parsing (sqlglot)
│   │   ├── optimizer/
│   │   │   ├── rules.py            # 12 optimization rules
│   │   │   ├── engine.py           # Rule execution engine
│   │   │   └── cost.py             # Cost estimation model
│   │   ├── analyzer/
│   │   │   ├── complexity.py       # Query complexity scorer (0-100)
│   │   │   ├── plan.py             # Logical query plan generator
│   │   │   └── index_advisor.py    # Index suggestion engine
│   │   └── utils/
│   │       └── formatter.py        # SQL formatting
│   ├── tests/
│   │   └── test_optimizer.py       # 27 unit + integration tests
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                       # Next.js + TypeScript
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx          # Root layout + metadata
│   │   │   ├── page.tsx            # Main page (all state + SQL highlighter)
│   │   │   └── globals.css         # Retro arcade CSS theme
│   │   ├── components/
│   │   │   ├── StatsPanel.tsx      # Complexity, performance, cost cards
│   │   │   ├── AnalysisTabs.tsx    # Optimizations, Indexes, Plan, Diff
│   │   │   ├── QueryPlan.tsx       # Interactive plan tree visualization
│   │   │   ├── SchemaInput.tsx     # Table/column/index definition panel
│   │   │   ├── HistoryPanel.tsx    # Query history sidebar
│   │   │   └── PixelProgress.tsx   # RPG-style progress bar
│   │   ├── hooks/
│   │   │   ├── useOptimizer.ts     # API call hook with loading/error state
│   │   │   └── useHistory.ts       # localStorage history management
│   │   ├── lib/
│   │   │   └── api.ts              # HTTP client for backend
│   │   └── types/
│   │       └── index.ts            # TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml              # Local dev (both services)
├── render.yaml                     # Render deployment blueprint
└── README.md                       # You are here
```

---

## 🛠 Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **SQL Parsing** | [sqlglot](https://github.com/tobymao/sqlglot) | Industry-grade SQL parser with multi-dialect support and AST manipulation |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) | Async Python framework with automatic OpenAPI docs and Pydantic validation |
| **Data Validation** | [Pydantic](https://docs.pydantic.dev/) | Type-safe request/response models with automatic serialization |
| **Frontend Framework** | [Next.js 16](https://nextjs.org/) | React framework with App Router, SSR, and TypeScript support |
| **Styling** | Vanilla CSS | Custom retro arcade theme with CSS custom properties — no utility framework needed |
| **Deployment** | [Render](https://render.com/) / Docker | Free tier hosting with one-click deploy via render.yaml |

---

## 🌐 Deployment

### Deploy to Render (Recommended)

1. Push to GitHub
2. Go to [render.com/blueprints](https://render.com/blueprints)
3. Connect your repository
4. Render auto-detects `render.yaml` and deploys both services:
   - `queryforge-api` (Python backend)
   - `queryforge-frontend` (Next.js frontend)
5. Update the frontend's `NEXT_PUBLIC_API_URL` environment variable to point to the backend URL

### Deploy with Docker

```bash
docker-compose up --build
```

---

## 🧪 Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

**27 tests** covering:
- SQL parsing (11 tests) — parse, validate, extract tables/columns/joins
- Optimization rules (6 tests) — detection and transformation
- Complexity scoring (2 tests) — simple vs. complex queries
- Query plan generation (2 tests) — plan tree structure
- API endpoints (6 tests) — health, parse, format, optimize with/without schema

---

## 🎤 Interview Prep Guide

### Questions You Will Be Asked (And How to Answer)

---

**Q: "Walk me through what happens when a user clicks Optimize."**

A: *"The frontend sends a POST to `/api/optimize` with the SQL string, dialect, and optional schema context. The backend:*
1. *Parses the SQL into an AST using sqlglot*
2. *Scores complexity by walking the AST and counting joins, subqueries, aggregations*
3. *Runs 12 optimization rules — each rule's `detect()` method checks for a pattern in the AST, and if found, `optimize()` transforms the AST or returns a suggestion*
4. *Compares cost before/after using a simplified cost model*
5. *Generates a logical query plan tree*
6. *Runs the index advisor to suggest missing indexes*
7. *Returns everything as a structured JSON response"*

---

**Q: "Is this using AI/LLMs?"**

A: *"No — this is a rule-based optimizer, which is actually how real database optimizers work. PostgreSQL's planner uses rule-based transformations (like predicate pushdown and subquery flattening) before cost-based plan selection. Each rule is a deterministic pattern match on the AST. This is more reliable and explainable than an LLM — every optimization can be traced to a specific rule with a specific reason."*

---

**Q: "How does the cost estimation work?"**

A: *"It's a simplified relative cost model. Each operation gets a base cost: full table scan is O(n), index scan is O(log n), hash join is O(n+m), nested loop is O(n×m). If schema context is provided with row counts, costs scale accordingly. The model compares the original and optimized AST costs and returns a percentage improvement. It's not as precise as PostgreSQL's EXPLAIN ANALYZE (which uses runtime statistics), but it demonstrates understanding of how query planners evaluate execution strategies."*

---

**Q: "How do the rules actually transform the SQL?"**

A: *"Rules that can safely auto-rewrite modify the AST directly. For example, SubqueryToJoin finds `exp.In` nodes containing `exp.Subquery`, extracts the inner table and join column, constructs a new `exp.Join` node, adds it to the main query, and moves the inner WHERE conditions to the outer WHERE. Then sqlglot regenerates valid SQL from the modified AST. Rules where auto-rewriting would be unsafe (like WildcardLikePattern) just flag the issue and explain the fix."*

---

**Q: "What's the difference between your optimizer and PostgreSQL's?"**

A: *"PostgreSQL does two things: (1) rule-based logical optimization (predicate pushdown, subquery flattening — similar to what I built), and (2) cost-based physical optimization (choosing between sequential scan vs. index scan, nested loop vs. hash join, based on statistics about actual data distribution). My tool does (1) plus a simplified version of (2). The main thing I'm missing is runtime statistics — PostgreSQL tracks histograms, null ratios, and correlation data per column to make precise cardinality estimates."*

---

**Q: "Why sqlglot instead of writing your own parser?"**

A: *"Writing a SQL parser from scratch would require implementing a full grammar for each dialect — PostgreSQL alone has thousands of grammar rules. sqlglot is an industry-standard library (used by companies like Airbnb and Databricks) that handles all edge cases: CTEs, window functions, dialect-specific syntax, quoted identifiers, etc. It also provides a clean AST with typed expression nodes (`exp.Select`, `exp.Join`, `exp.Where`) that I can pattern-match against. Building the parser wasn't the goal — building the optimization logic was."*

---

**Q: "How would you extend this?"**

A: *"Three directions: (1) Add more rules — CTE optimization, join elimination, materialized view suggestions. (2) Improve cost estimation — integrate with a real database to get actual EXPLAIN output and compare with my estimates. (3) Add query history analytics — track which optimization rules fire most often across queries to identify systemic schema issues."*

---

**Q: "What design patterns did you use?"**

A: *"Strategy Pattern for optimization rules — each rule is a class with a common interface (detect/optimize), and the engine iterates through all registered rules. Pipeline Pattern for the main flow (parse → optimize → analyze → respond). Factory Pattern for query plan node creation. Observer Pattern for the frontend state (React hooks with effect-based updates). The architecture follows Single Responsibility — parser doesn't know about HTTP, optimizer doesn't know about the API layer."*

---

### Key Terms to Know

| Term | Definition |
|------|-----------|
| **AST** | Abstract Syntax Tree — tree representation of parsed code |
| **B-tree index** | Balanced tree data structure databases use for O(log n) lookups |
| **Covering index** | An index that contains all columns needed to satisfy a query (no table access needed) |
| **Cardinality** | Number of unique values in a column — affects index effectiveness |
| **Cost-based optimization** | Choosing execution plans by estimating their cost using data statistics |
| **Full table scan (Seq Scan)** | Reading every row in a table — O(n) |
| **Hash join** | Join strategy that builds a hash table from one side — O(n+m) |
| **Nested loop join** | Join strategy that checks every pair of rows — O(n×m) |
| **Predicate pushdown** | Moving filter conditions as close to data sources as possible |
| **Query plan** | The step-by-step strategy a database uses to execute a query |
| **Rule-based optimization** | Applying known transformation rules to improve queries |
| **Selectivity** | Fraction of rows a condition matches — low selectivity = good for indexes |

---

## 📝 License

MIT

---

*Built by [Yash Singhal](https://github.com/Yash19Singhal)*
