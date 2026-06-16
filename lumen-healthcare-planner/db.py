"""Database connection module for Lakebase Postgres.

Handles token refresh (OAuth tokens expire after 1 hour).
Refreshes every 15 minutes to stay safe.
"""
import os
import time
import uuid
import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from databricks.sdk import WorkspaceClient

# Lakebase connection config
DB_HOST = os.environ.get("PGHOST", "ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com")
DB_NAME = "healthcare"  # Synced tables are in 'healthcare' db (not databricks_postgres)
DB_USER = os.environ.get("PGUSER", "krish.kilaru@lumenalta.com")  # Databricks user email; injected as PGUSER by app runtime
DB_PORT = int(os.environ.get("PGPORT", 5432))
INSTANCE_NAME = "hackathon-healthcare"

# Schema where synced tables live — synced from dais2026.lakebase_sync_clean via Synced Database Tables
SYNCED_SCHEMA = "lakebase_pg_sync"
# Schema for app-specific user data
APP_SCHEMA = "app_data"

# Token cache
_token_cache = {"token": None, "refreshed_at": 0}
TOKEN_REFRESH_INTERVAL = 900  # 15 minutes

_sdk_client = None


def _get_sdk():
    global _sdk_client
    if _sdk_client is None:
        _sdk_client = WorkspaceClient()
    return _sdk_client


def _get_token():
    """Get or refresh the database credential token."""
    now = time.time()
    if (
        _token_cache["token"] is None
        or now - _token_cache["refreshed_at"] > TOKEN_REFRESH_INTERVAL
    ):
        w = _get_sdk()
        cred = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[INSTANCE_NAME],
        )
        _token_cache["token"] = cred.token
        _token_cache["refreshed_at"] = now
    return _token_cache["token"]


def get_connection():
    """Get a fresh psycopg2 connection with current token."""
    token = _get_token()
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        port=DB_PORT,
        password=token,
        sslmode="require",
        options=f"-c search_path={SYNCED_SCHEMA},{APP_SCHEMA},public",
    )


@contextmanager
def get_cursor():
    """Context manager for database cursor with auto-commit."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql, params=None):
    """Execute a SELECT and return list of dicts."""
    with get_cursor() as cur:
        cur.execute(sql, params)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def execute(sql, params=None):
    """Execute a write statement (INSERT/UPDATE/DELETE)."""
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def init_app_schema():
    """Create app-specific tables for user persistence."""
    ddl = f"""
    CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA};

    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.user_notes (
        id SERIAL PRIMARY KEY,
        facility_id TEXT NOT NULL,
        user_id TEXT NOT NULL DEFAULT 'default',
        note_text TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.user_overrides (
        id SERIAL PRIMARY KEY,
        facility_id TEXT NOT NULL,
        user_id TEXT NOT NULL DEFAULT 'default',
        field_name TEXT NOT NULL,
        override_value TEXT,
        reason TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.shortlists (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT 'default',
        facility_id TEXT NOT NULL,
        track TEXT NOT NULL,
        label TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, facility_id, track)
    );

    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.scenarios (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        track TEXT NOT NULL,
        filters_json JSONB NOT NULL DEFAULT '{{}}',
        results_json JSONB,
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.trust_scores (
        facility_id TEXT PRIMARY KEY,
        overall_score REAL NOT NULL,
        completeness_score REAL,
        verification_score REAL,
        recency_score REAL,
        detail_json JSONB,
        computed_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.trust_overrides (
        id SERIAL PRIMARY KEY,
        facility_id TEXT NOT NULL,
        capability TEXT NOT NULL,
        user_signal TEXT NOT NULL,
        note TEXT DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(facility_id, capability)
    );

    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.review_decisions (
        id SERIAL PRIMARY KEY,
        facility_id TEXT NOT NULL,
        user_id TEXT NOT NULL DEFAULT 'default',
        decision TEXT NOT NULL,
        flag_reason TEXT DEFAULT '',
        note TEXT DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, facility_id)
    );
    """
    with get_cursor() as cur:
        cur.execute(ddl)
