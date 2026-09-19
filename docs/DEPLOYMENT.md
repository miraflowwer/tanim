# TANIM deployment and rollback

TANIM has two deliberately separate deployment paths. The frozen hackathon path is web/ plus api/ and scripts/service.py. The durable target is app/ plus backend/app/ on PostgreSQL/PostGIS. This branch does not authorize production cutover.

## Durable service configuration

Use a managed secret store. Required environment variables are:

- TANIM_RUNTIME_MODE=postgres
- DATABASE_URL
- SUPABASE_JWKS_URL over HTTPS, or SUPABASE_JWT_SECRET
- SUPABASE_JWT_ISSUER and SUPABASE_JWT_AUDIENCE when configured by Supabase
- A separate non-owner application role without SUPERUSER or BYPASSRLS

Recommended operational variables are TANIM_RATE_LIMIT_PER_MINUTE, TANIM_BODY_LIMIT_BYTES, TANIM_INGESTION_MAX_AGE_DAYS, TANIM_MAP_MIN_GROUP_SIZE, and TANIM_FORCE_HSTS=true behind HTTPS. Never set ALLOW_DEV_AUTH in staging or production. Secrets, bearer tokens, passwords, coordinates, and raw export content must not appear in logs.

The backend image is provider-neutral. Build it from repository root with backend/Dockerfile, inject environment at runtime, run the migration job, then start the API process. No provider-specific SDK is required by the service boundary.

## Migration and readiness

1. Back up the target database and verify the backup before migration.
2. Run upgrade head in staging and run the PostgreSQL test suite.
3. Run upgrade, downgrade base, and upgrade head on a disposable database in CI.
4. For production, prefer a forward migration fix for destructive changes. Use downgrade only when its data implications have been rehearsed.
5. Route traffic only after GET /api/v1/readiness returns ready with PostGIS and migration 0002_platform_durability.
6. Keep the previous image and the last known good migration reference available.

## Backup and recovery targets

- Target RPO: no more than 24 hours.
- Target RTO: no more than 4 hours.
- Backups: encrypted, access-controlled, environment-separated, with retention recorded by the operator.
- Restore rehearsal: at least quarterly on an isolated staging database; restore the backup, verify schema, run representative calculations, run tenant/RLS checks, measure RTO, and record the result.
- A failed or unverified backup blocks production promotion.

## Preview smoke

For every preview, verify:

- GET /api/v1/health returns service health and the expected runtime
- GET /api/v1/readiness is either ready or explicitly unavailable with a dependency code
- Production OpenAPI contains the durable routes and external-auth-only session contract
- A Supabase token resolves to a provisioned user and membership
- Wrong-tenant reads and writes are denied
- Ingestion validation rejects a bad row without changing the promoted version
- Desktop and mobile frontend smoke uses privacy-safe map data and no exact coordinates

## Ingestion operations

The lifecycle is fetch, validate, normalize, version, stage, promote, monitor. Failed validation records a run error and leaves the current promoted version unchanged. Promotion is platform-only and emits an audit event. Retrying is allowed only for failed or validation_failed runs and is idempotent by key.

## Frozen web rollback

Do not remove web/, api/, or scripts/service.py as part of a durable backend release. If the durable preview or production deployment must be withdrawn, redeploy the last known good frozen web build and keep the durable database untouched. A future cutover must be a separate reviewed change with data migration, rollback, privacy review, and mobile/desktop smoke evidence.