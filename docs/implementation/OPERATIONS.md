# TANIM operations runbook

## Startup and readiness

- Set the explicit runtime mode and managed secrets.
- Run the Alembic migration job with a migration-capable role.
- Start the API with the restricted application role.
- Check health, readiness, metrics, and process logs.
- Do not expose metrics publicly; place them behind the platform network or an authenticated scrape path.

Readiness fails closed when PostgreSQL, PostGIS, or the expected Alembic head is unavailable. The API must not silently fall back to the demo store.

## Request telemetry

Every response receives X-Request-ID. The middleware records method, route, status, duration, and non-sensitive identity ids. Structured logs redact bearer tokens, passwords, secrets, cookies, reset links, raw export data, and coordinates. Error envelopes expose stable codes and request ids without SQL, stack traces, claims, or credentials.

Rate limiting uses transactional PostgreSQL buckets and returns rate_limited with a retry hint. Keep an upstream proxy limit as a second layer.

## Database safety

The application role must be separate from table ownership and must have NOSUPERUSER and NOBYPASSRLS. Tenant context is set transaction-locally. Never grant the application role direct migration or ownership privileges. Run wrong-tenant and append-only tests after role changes.

Audit events are append-only. Global source promotion events require platform_admin context. Plan revisions, calculations, reviews, and evidence versions retain history rather than being overwritten.

## Ingestion incident response

1. Inspect the ingestion run and validation summary.
2. If validation_failed, confirm the promoted source version remains current.
3. Fix the provider payload or normalization rule.
4. Retry only with a new idempotency key after the failed run is understood.
5. Promote only after validation and platform authorization.
6. Check source freshness and audit events.

Unknown crops, invalid units/geographies/dates, duplicate rows, critical blanks, negative or non-finite values, and stale periods are rejected.

## Backup and rollback

Follow DEPLOYMENT.md for RPO/RTO and restore rehearsal. Preserve the last good image, database snapshot, migration reference, and frozen web rollback. Record any rollback actor, reason, release, database action, readiness result, and smoke result.