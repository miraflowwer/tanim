# TANIM backend

The production target is FastAPI + SQLAlchemy 2 + Alembic on PostgreSQL/PostGIS. Runtime selection is explicit: TANIM_RUNTIME_MODE=inmemory is the seeded demo adapter, while postgres, production, and prod select the durable repository. An omitted mode fails closed to PostgreSQL.

## Runtime configuration

Production requires:

- DATABASE_URL using a PostgreSQL driver and a database with PostGIS enabled
- TANIM_RUNTIME_MODE=postgres
- SUPABASE_JWKS_URL over HTTPS, or SUPABASE_JWT_SECRET for the configured Supabase signing mode
- SUPABASE_JWT_ISSUER and SUPABASE_JWT_AUDIENCE when the issuer/audience are enforced
- A durable users row keyed by provider_subject and organization memberships
- A database role that is not the table owner, is not SUPERUSER, and does not have BYPASSRLS

Development-only variables are TANIM_RUNTIME_MODE=inmemory and ALLOW_DEV_AUTH=true. They must never be enabled in production. Supabase Auth owns login, refresh, recovery, and session lifecycle; the backend exposes auth/session as external-auth-only.

Optional operational variables include TANIM_RATE_LIMIT_PER_MINUTE, TANIM_BODY_LIMIT_BYTES, TANIM_INGESTION_MAX_AGE_DAYS, TANIM_MAP_MIN_GROUP_SIZE, and TANIM_FORCE_HSTS.

## Run and migrate

From the repository root, build the provider-neutral image with the repository root as the Docker build context. The image runs app.main:app with PYTHONPATH including backend.

For a deployment, run alembic -c backend/alembic.ini upgrade head before starting the API. The readiness endpoint requires a successful database connection, PostGIS, and migration head 0002_platform_durability. Do not route production traffic when readiness is false.

## Persistence and security

backend/app/repositories/postgres.py is the production boundary. backend/app/legacy_api.py and app/store.py remain the explicit demo adapter only. Tenant transactions set app.current_org_id, app.current_user_id, and app.current_role locally; PostgreSQL forced RLS is the second enforcement layer after application authorization.

Plan revisions, calculation runs, reviews, audit events, and consent history are append-only or versioned. Data-source versions are immutable payload references with validation status, checksum, staging, and promotion metadata. Historical calculations retain the engine, policy, registry, evidence identifiers, versions, and result JSON used at calculation time.

## Verification

Run the backend test suite with pytest. PostgreSQL mechanism tests require a disposable PostGIS database and exercise migration upgrade/downgrade/upgrade, the restricted application role, wrong-tenant reads/writes, forced RLS, and append-only triggers. Generate or verify the production OpenAPI contract with scripts/generate_openapi.py.