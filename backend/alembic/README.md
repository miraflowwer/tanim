# Alembic (PostgreSQL/PostGIS)

backend/alembic/versions/0001_entities.py enables PostGIS, creates the
SQLAlchemy 2 schema, installs forced tenant policies, and installs append-only
triggers for audit and history tables.

## Commands

~~~bash
cd backend
alembic upgrade head
alembic downgrade base
alembic upgrade head
~~~

DATABASE_URL supplies the real PostgreSQL connection string. Do not commit
credentials. The deployed API role must be a separate non-owner role without
SUPERUSER or BYPASSRLS privileges.

The migration leaves exact farm GPS optional. Municipality and region fields
support planning without coordinates. backend/tests/test_postgres_rls.py
exercises the actual PostgreSQL policies when configured with a disposable
database.
