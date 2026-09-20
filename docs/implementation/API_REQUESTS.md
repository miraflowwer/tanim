# TANIM API request ledger

This ledger records backend contracts needed by the Member 1 and Member 2 clients. Existing in-memory/demo responses remain compatible. When TANIM_RUNTIME_MODE is postgres, production routes use the durable repository and never use the global demo store.

## Implemented contracts

| Contract | Status | Method and path | Authorization and tenant scope | Main response or error states | Evidence |
|---|---|---|---|---|---|
| Organization and member administration | Implemented | GET/PATCH organizations/{org_id}; GET/PATCH/DELETE organizations/{org_id}/members/{member_id} | Membership; org_admin for mutations | organization_required, permission_denied, not_found | production_api.py, repository tests |
| Settings and invitations | Implemented | GET/PATCH organizations/{org_id}/settings; GET/POST organizations/{org_id}/invitations | Tenant membership; org_admin for changes/invites | validation_error, permission_denied, conflict | platform_models.py, OpenAPI |
| Plans and revisions | Implemented | POST/GET/PATCH/DELETE plans; GET/POST plans/{plan_id}/revisions | Tenant membership and farm ownership/role checks | invalid_date_range, conflict, not_found | transactional repository methods |
| Calculation history | Implemented | POST plans/{plan_id}/calculate; GET plans/{plan_id}/calculations; GET calculations/{calculation_id} | Tenant membership | calculation_backend_missing, incomplete provenance, not_found | scripts/grci.py authority and result_json |
| Aggregates and context | Implemented | organizations/{org_id}/aggregates, geo-aggregates, timeline, attention-items, map-data | Coordinator/reviewer/admin for shared views | unavailable and privacy metadata are explicit | privacy-safe response code |
| Evidence and policies | Implemented | GET/POST references; reference transitions; GET/POST policies | Reviewer/org_admin for review and policy writes | invalid_reference_transition, invalid_policy, conflict | review/audit persistence |
| Data-source metadata | Implemented | GET data-sources, detail, versions, freshness | Tenant read; platform read/promotion | no_promoted_version, source_version_not_valid, duplicate_source_version | immutable source indexes |
| Ingestion and promotion | Implemented | POST/GET platform/ingestion, retry, version promotion | Platform authority for global ingestion and promotion | ingestion_validation_failed, ingestion_retry_not_safe, permission_denied | ingestion tests and audit events |
| Notifications and search | Implemented | GET notifications, POST notifications/{id}/read, GET search | Tenant scope; search rate limited | rate_limited, permission_denied, paginated response | Page contract and rate-limit bucket |
| Exports and audit | Implemented | POST/GET exports; GET audit-events with action filter | Tenant; individual exports need reviewer/admin | conflict, permission_denied, paginated response | audit append-only tests |
| Consent and context | Implemented | POST/GET consents, POST consents/withdraw, GET context/prices | Tenant and user-scoped | unavailable source state is explicit | consent repository methods |
| Runtime and observability | Implemented | GET health, readiness, metrics, observability/calculations | Metrics endpoint should be network-restricted by deployment | dependency_unavailable, safe metrics text | db readiness and ops.py |

## Contract rules

- Every collection response is shaped as items, next_cursor, and total when pagination is supported.
- Error responses include a stable code, safe message, and X-Request-ID/request_id.
- Coordinate-bearing data is never returned by the privacy-safe map endpoint; exact farm locations require a separate consented contract.
- Supabase Auth owns login, refresh, recovery, and provider session lifecycle. The backend only validates claims and resolves durable identity.
- scripts/grci.py is the sole trusted calculation authority. Clients never reproduce its formulas.
- New frontend contract requests must include requester, tenant scope, fields, privacy, error states, and an example before implementation.
## Finalized branch evidence

- The production contract is generated from backend.app.main with TANIM_RUNTIME_MODE=postgres.
- openapi/openapi.json is committed and matches scripts/generate_openapi.py --check in CI run 35479436314.
- Stable error envelopes include code, safe message, and request ID; ingestion, source-version, authorization, pagination, readiness, and privacy states are recorded above.
- Remaining client work is explicitly cross-member integration (BLOCK-003), not an undocumented backend contract.