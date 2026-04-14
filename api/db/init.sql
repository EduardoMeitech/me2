-- =============================================================================
-- ME2 — PostgreSQL Initialization Script
-- =============================================================================
-- This script runs once when the PostgreSQL container is first created.
-- It is mounted into /docker-entrypoint-initdb.d/ via docker-compose.yml.
--
-- Purpose: Enable required PostgreSQL extensions before Alembic runs migrations.
-- The application schema itself is managed by Alembic — do NOT create tables here.
-- =============================================================================

-- uuid-ossp: Provides uuid_generate_v4() for generating UUIDs.
-- All ME2 tables use UUID primary keys: id UUID DEFAULT gen_random_uuid()
-- While gen_random_uuid() is built into PostgreSQL 13+, uuid-ossp provides
-- additional UUID generation functions (v1, v3, v5) that may be needed for
-- deterministic IDs in multi-tenant scenarios.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pgcrypto: Provides gen_random_uuid() (redundant on PG 13+ but explicit),
-- plus crypt() and gen_salt() which may be used for password hashing at the
-- database level if needed as a fallback to application-level hashing.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- btree_gist: Required for exclusion constraints on time ranges.
-- Used in shift and scheduling tables to prevent overlapping time intervals.
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- =============================================================================
-- Verify extensions loaded correctly
-- =============================================================================
DO $$
BEGIN
    -- Quick sanity check — generate a UUID to confirm uuid-ossp works
    PERFORM uuid_generate_v4();
    RAISE NOTICE 'ME2 init.sql: All extensions loaded successfully.';
END
$$;
