"""Database-backed rule overrides for environments with persistent storage.

The shipped IPS JSON files remain the curated baseline. When a database URL is
configured, this module stores *overrides* and *new rules* in PostgreSQL. The loader
merges those rows over the JSON baseline by ``rule_id`` so local development can keep
using plain JSON files while serverless deployments can persist admin edits externally.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Tuple

SCHEMA_SQL = """
create table if not exists ips_rule_overrides (
  rule_id text primary key,
  source_file text not null,
  rule_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
"""


def database_url() -> str | None:
    for key in (
        "RULE_STORE_DATABASE_URL",
        "POSTGRES_URL_NON_POOLING",
        "DATABASE_URL",
        "POSTGRES_URL",
        "POSTGRES_PRISMA_URL",
    ):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return None


def is_enabled() -> bool:
    return database_url() is not None


def _connect():
    import psycopg

    return psycopg.connect(database_url(), autocommit=True, connect_timeout=5)


def ensure_schema() -> None:
    if not is_enabled():
        return
    with _connect() as conn:
        conn.execute(SCHEMA_SQL)


@lru_cache(maxsize=1)
def _load_cached() -> Tuple[Tuple[Dict[str, Any], ...], Tuple[str, ...]]:
    if not is_enabled():
        return tuple(), tuple()

    try:
        ensure_schema()
        with _connect() as conn:
            rows = conn.execute(
                """
                select rule_id, source_file, rule_json
                from ips_rule_overrides
                order by rule_id
                """
            ).fetchall()
    except Exception as exc:  # pragma: no cover - environment-specific
        return tuple(), (f"database rule store unavailable ({exc})",)

    rules: List[Dict[str, Any]] = []
    problems: List[str] = []
    for rule_id, source_file, rule_json in rows:
        if not isinstance(rule_json, dict):
            problems.append(f"database[{rule_id}]: rule_json must be an object")
            continue
        merged = dict(rule_json)
        merged["rule_id"] = rule_id
        merged["_source_file"] = source_file or "database"
        rules.append(merged)
    return tuple(rules), tuple(problems)


def load_overrides() -> List[Dict[str, Any]]:
    return list(_load_cached()[0])


def load_problems() -> List[str]:
    return list(_load_cached()[1])


def save_rule(rule: Dict[str, Any], source_file: str) -> None:
    if not is_enabled():
        raise RuntimeError("database rule store is not enabled")

    from psycopg.types.json import Jsonb

    ensure_schema()
    payload = {k: v for k, v in rule.items() if not k.startswith("_")}
    with _connect() as conn:
        conn.execute(
            """
            insert into ips_rule_overrides (rule_id, source_file, rule_json)
            values (%s, %s, %s)
            on conflict (rule_id) do update
            set source_file = excluded.source_file,
                rule_json = excluded.rule_json,
                updated_at = now()
            """,
            (rule["rule_id"], source_file, Jsonb(payload)),
        )
    reload()


def reload() -> None:
    _load_cached.cache_clear()
