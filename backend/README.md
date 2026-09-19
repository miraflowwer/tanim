# TANIM backend

The production target is FastAPI + SQLAlchemy 2 + Alembic on PostgreSQL/PostGIS.
The deterministic in-memory store remains a development/demo adapter until the
route repository adapter is wired.

## Runtime modes

Set the mode explicitly in deployment:

~~~powershell
cd backend
$env:TANIM_RUNTIME_MODE = "inmemory"
$env:ALLOW_DEV_AUTH = "true"
uvicorn app.main:app --reload
~~~

Development mode uses seeded data and dev:user:role:org tokens only when
ALLOW_DEV_AUTH=true. It must never be enabled in production.

An omitted runtime mode fails closed as PostgreSQL. Production also requires a database URL:

~~~powershell
cd backend
$env:TANIM_RUNTIME_MODE = "postgres"
$env:DATABASE_URL = "postgresql+psycopg://user:password@host/tanim"
alembic upgrade head
uvicorn app.main:app
~~~

PostgreSQL mode requires PostGIS. The readiness endpoint checks database and
PostGIS availability. Core API routes return a structured unavailable response
until their SQLAlchemy repository adapter is wired; this prevents the
in-memory adapter from being presented as production persistence or RLS.

## Migrations and tenant isolation

alembic/versions/0001_entities.py enables PostGIS, creates the SQLAlchemy
schema, installs forced row-level security policies, and adds append-only
triggers for audit, calculation, revision, and review history. Deploy the API
with a separate non-owner PostgreSQL role that has neither SUPERUSER nor
BYPASSRLS.

Mechanism-level RLS tests are in tests/test_postgres_rls.py. Set
TANIM_TEST_DATABASE_URL to the application role and
TANIM_RLS_ADMIN_DATABASE_URL to a disposable setup role; if only
DATABASE_URL is supplied, the test creates a temporary non-privileged role
through the disposable admin connection.

## Layout

- app/main.py — FastAPI API contract and development adapter routes.
- ../scripts/grci.py — framework-independent authoritative calculation domain; app/grci.py only re-exports it.
- app/schemas.py — strict request schemas and domain-compatible response contracts.
- app/models.py — SQLAlchemy/PostGIS persistence model.
- app/db.py — explicit runtime mode, readiness, and tenant session context.
- alembic/ — PostgreSQL/PostGIS schema and RLS migration.
- tests/ — domain, API, authorization, and PostgreSQL mechanism tests (run against a disposable PostGIS service in CI).

OpenAPI is generated from the FastAPI app with
python scripts/generate_openapi.py --check.
