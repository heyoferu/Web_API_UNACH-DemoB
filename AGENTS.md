# AGENTS.md

This file provides guidance for AI coding agents working in this repository.

## Project Overview

FastAPI + SQLModel + PostgreSQL REST API (Python 3.10+). Based on the
[full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template).
Package manager is **uv** (Astral). Entry point: `app/main.py`.

## Build & Run Commands

```bash
# Install dependencies
uv sync

# Run the server (dev)
fastapi dev app/main.py

# Run migrations + seed superuser (done automatically on container start)
bash scripts/prestart.sh

# Create a new Alembic migration after model changes
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Test Commands

```bash
# Run full test suite with coverage
bash scripts/test.sh

# Run a single test file
coverage run -m pytest tests/api/routes/test_users.py

# Run a single test by name
coverage run -m pytest tests/api/routes/test_users.py -k "test_create_user_new_email"

# Run pytest directly (without coverage)
pytest tests/
pytest tests/crud/test_user.py::test_create_user -v
```

Tests use `TestClient` against a real PostgreSQL database configured via `.env`.
The `tests/conftest.py` provides session-scoped fixtures: `db`, `client`,
`superuser_token_headers`, and `normal_user_token_headers`.

## Lint & Format Commands

```bash
# Lint (runs all three checks in order)
bash scripts/lint.sh
# Equivalent to:
#   mypy app
#   ruff check app
#   ruff format app --check

# Auto-fix lint issues and reformat
bash scripts/format.sh
# Equivalent to:
#   ruff check app scripts --fix
#   ruff format app scripts
```

Always run `bash scripts/format.sh` before committing.

## Code Style Guidelines

### Python Version & Typing

- Target: Python 3.10+. Use modern syntax (no `from __future__ import annotations`).
- Use `X | None` instead of `Optional[X]`. Never import `Optional`.
- Annotate return types on every function. Use `-> Any` when `response_model=` is
  set on the route decorator; use concrete types otherwise.
- Use `uuid.UUID` (not `from uuid import UUID`). IDs are always UUIDs.
- Dependency injection aliases use `Annotated`: `SessionDep`, `CurrentUser`, `TokenDep`.

### Imports

- **Absolute imports only** (`from app.core.config import settings`). No relative imports.
- Order enforced by ruff/isort: (1) stdlib, (2) third-party, (3) local `app.*`.
- Separate each group with a blank line.

### Naming Conventions

| Element             | Convention         | Examples                                       |
|---------------------|--------------------|-------------------------------------------------|
| Functions/variables | `snake_case`       | `create_user`, `db_user`, `user_in`             |
| Classes             | `PascalCase`       | `User`, `UserCreate`, `UserPublic`              |
| Constants           | `UPPER_SNAKE_CASE` | `ALGORITHM`, `DUMMY_HASH`                       |
| Schema models       | `{Entity}{Purpose}`| `UserCreate`, `ItemPublic`, `UsersPublic`       |
| DB object variables | `db_` prefix       | `db_user`, `db_item`, `db_obj`                  |
| Input model vars    | `_in` suffix       | `user_in`, `item_in`                            |
| Files               | `snake_case.py`    | `crud.py`, `security.py`                        |
| Route files         | plural resource    | `users.py`, `items.py`                          |

### Error Handling

- Raise `HTTPException` directly with integer status codes and plain string `detail`:
  ```python
  raise HTTPException(status_code=400, detail="Incorrect email or password")
  ```
- Status code conventions: `400` (validation/business logic), `403` (authorization),
  `404` (not found), `409` (conflict/duplicate).
- Fail-fast pattern: raise immediately, no broad try/except in route handlers.
- `B904` is ignored in ruff — `raise HTTPException(...)` inside `except` blocks does
  not require `from e`.

### Endpoint Patterns

- Each route file creates its own `APIRouter` with prefix and tags:
  ```python
  router = APIRouter(prefix="/users", tags=["users"])
  ```
- Use `response_model=` on decorators for serialization, return `-> Any` from handler.
- Use `dependencies=[Depends(get_current_active_superuser)]` on decorators for
  authorization-only guards (when the return value is not needed).
- Inject DB session as `session: SessionDep` and auth user as `current_user: CurrentUser`.
- Use keyword-only args with `*`: `def create_user(*, session: SessionDep, ...) -> Any:`
- Route handlers are **synchronous** (`def`, not `async def`).
- Short imperative docstrings: `"""Create new user."""`
- Pagination: `skip: int = 0, limit: int = 100` as query params.
- List responses use wrapper models: `UsersPublic(data=users, count=count)`.
- Deletion returns `Message(message="X deleted successfully")`.

### CRUD Layer

- Pure functions in `app/crud.py` (no classes). Accept `Session` + model DTOs.
- Simple operations (get by id, delete) can be done inline in routes with `session.get()`.
- Complex operations (create with password hash, authenticate) go in `crud.py`.
- CRUD functions use keyword-only arguments.

### Models & Schemas

- All models and DTOs live in `app/models.py` (single file).
- SQLModel tables use `table=True`. Schemas (DTOs) inherit from base models.
- Base classes define shared fields; `Public` schemas exclude sensitive data.
- `hashed_password` must never appear in API response schemas.

### Ruff Configuration

Enabled rules: `E`, `W`, `F`, `I`, `B`, `C4`, `UP`, `ARG001`, `T201`.
Ignored: `E501` (line length handled by formatter), `B008` (allows `Depends()` in
defaults), `W191`, `B904`.
Default line length is 88 (ruff format default). No `print()` calls allowed (`T201`).

### mypy

Strict mode enabled. Excludes `venv`, `.venv`, `alembic`.

## Architecture Layers

```
app/main.py              → FastAPI app, CORS, Sentry, mounts api_router
app/api/main.py          → Aggregates all sub-routers under /api/v1
app/api/routes/*.py      → Endpoint handlers (controllers)
app/api/deps.py          → Dependency injection (DB session, auth)
app/crud.py              → Data access functions
app/models.py            → SQLModel ORM tables + Pydantic schemas
app/core/config.py       → Settings from .env (pydantic-settings)
app/core/db.py           → SQLAlchemy engine, init_db() seeder
app/core/security.py     → JWT creation, password hashing (Argon2/bcrypt)
app/utils.py             → Email sending, password reset tokens
app/alembic/             → Database migrations
tests/                   → Pytest suite (conftest.py has shared fixtures)
```

## Key Files to Know

- **Add a new endpoint**: create or edit a file in `app/api/routes/`, register it
  in `app/api/main.py`.
- **Add a new model**: edit `app/models.py`, then run `alembic revision --autogenerate`.
- **Change auth logic**: edit `app/api/deps.py` and `app/core/security.py`.
- **Environment config**: `.env` file, parsed by `app/core/config.py`.
