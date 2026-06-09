"""Migrate data from local SQLite to Neon Postgres.

Reads all rows from data/th_evi.sqlite3 and inserts them into
the Neon Postgres database specified by DATABASE_URL in .env.local.

Usage: python migrate_sqlite_to_postgres.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env_file() -> None:
    """Load .env.local into os.environ (no dotenv dependency)."""
    env_path = PROJECT_ROOT / ".env.local"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Don't overwrite existing env vars (priority for Vercel/Railway/etc.)
        if key not in os.environ:
            os.environ[key] = value


def get_postgres_columns(engine, table: str) -> set[str]:
    """Get set of column names that exist in a Postgres table."""
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :t
            """),
            {"t": table},
        ).fetchall()
    return {r[0] for r in rows}


def coerce_value_for_pg(value, col_name: str, all_cols: list[str]) -> object:
    """Coerce SQLite value to be Postgres-compatible.

    - Boolean columns (boolean in PG): int 0/1 -> False/True
    - JSON-serialize unsupported types
    """
    if value is None:
        return None
    # Heuristic: column name ends with _id, _at, _url, _note, _by, active, etc.
    # Better: check if the column is boolean in PG by comparing column types
    # We can't easily do that here, so use the type check passed in
    return value


def main() -> int:
    load_env_file()

    # Force Postgres mode
    from th_evi.db import get_database_url

    pg_url = get_database_url()
    if pg_url.startswith("sqlite"):
        print("ERROR: DATABASE_URL not set or still points to sqlite.")
        print("Set DATABASE_URL in .env.local first.")
        return 1

    print(f"Postgres URL: {pg_url[:60]}...")

    # Local SQLite
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    sqlite_path = PROJECT_ROOT / "data" / "th_evi.sqlite3"
    if not sqlite_path.exists():
        print(f"ERROR: SQLite not found at {sqlite_path}")
        return 1

    sqlite_url = f"sqlite:///{sqlite_path.as_posix()}"
    print(f"SQLite URL:  {sqlite_url}")

    sqlite_engine = create_engine(
        sqlite_url, connect_args={"check_same_thread": False}
    )
    pg_engine = create_engine(pg_url)

    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)

    # Get list of tables (alphabetical, but FK-aware order required)
    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        ).fetchall()
        tables = [r[0] for r in rows]
    print(f"\nFound {len(tables)} tables: {tables}")

    # Order tables to respect FKs (parents first)
    fk_order = [
        "reference_sources",
        "candidate_sites",
        "site_assumptions",
        "competitors",
        "analysis_runs",
        "analysis_results",
        "ev_models",
        "ev_registrations",
        "ev_bookings",
        "ev_fleet_mix",
        "province_ingestion_runs",
        "aadt_segments",
        "charger_competitors",
        "poi_reference",
        "hot_zone_reference",
        "business_area_reference",
        "district_node_reference",
        "district_population",
        "heatmap_exclusion_reference",
    ]
    ordered = [t for t in fk_order if t in tables]
    extras = [t for t in tables if t not in fk_order]
    ordered.extend(extras)
    print(f"Migration order: {ordered}")

    # First, ensure schema is created on Postgres
    from th_evi.db import Base, create_session_factory
    print("\n--- Creating schema on Postgres (if not exists) ---")
    Base.metadata.create_all(pg_engine)
    print("OK")

    # Truncate all Postgres tables (clean slate, respects FKs with CASCADE)
    print("\n--- Truncating existing Postgres data ---")
    with pg_engine.begin() as conn:
        # Use CASCADE to handle FKs
        for t in reversed(ordered):
            try:
                conn.execute(text(f'TRUNCATE TABLE "{t}" RESTART IDENTITY CASCADE'))
            except Exception as e:
                # If table doesn't exist yet, skip
                pass
    print("OK")

    # Migrate each table
    total_rows = 0
    with SqliteSession() as src, PgSession() as dst:
        for table in ordered:
            print(f"\n--- {table} ---")
            # Get Postgres columns to filter SQLite columns that don't exist
            try:
                pg_cols = get_postgres_columns(pg_engine, table)
            except Exception:
                pg_cols = set()

            # Read all rows as dicts
            try:
                src_rows = src.execute(text(f"SELECT * FROM {table}")).mappings().all()
            except Exception as e:
                print(f"  SKIP: {e}")
                continue

            if not src_rows:
                print(f"  Empty (0 rows)")
                continue

            # Filter columns: keep only those that exist in Postgres
            first_row = dict(src_rows[0])
            if pg_cols:
                kept_cols = [c for c in first_row.keys() if c in pg_cols]
                skipped = [c for c in first_row.keys() if c not in pg_cols]
                if skipped:
                    print(f"  Skipping PG-missing columns: {skipped}")
            else:
                kept_cols = list(first_row.keys())

            if not kept_cols:
                print(f"  No matching columns")
                continue

            # Convert to list of dicts (with only kept columns)
            rows_dict = [{k: r[k] for k in kept_cols} for r in src_rows]

            # Coerce types: bool fields, datetime, etc.
            import json
            import datetime
            cleaned_rows = []
            for r in rows_dict:
                new_r = {}
                for k, v in r.items():
                    if v is None:
                        new_r[k] = None
                    elif isinstance(v, bool):
                        new_r[k] = v
                    elif isinstance(v, (str, int, float)):
                        new_r[k] = v
                    elif isinstance(v, (datetime.datetime, datetime.date)):
                        new_r[k] = v
                    elif isinstance(v, bytes):
                        new_r[k] = v.decode("utf-8", errors="ignore")
                    else:
                        try:
                            json.dumps(v)
                            new_r[k] = v
                        except (TypeError, ValueError):
                            new_r[k] = str(v)
                cleaned_rows.append(new_r)

            # Cast any int 0/1 in boolean-like columns to real booleans
            # (SQLite doesn't enforce types — bool columns can hold 0/1)
            for r in cleaned_rows:
                for k in list(r.keys()):
                    if r[k] in (0, 1) and k in (
                        "active", "roadside_frontage", "inside_parking_structure",
                        "dc_fast", "same_corridor", "is_anchor", "is_active"
                    ):
                        r[k] = bool(r[k])

            # Build INSERT with only kept columns
            cols = kept_cols
            col_list = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(f":{c}" for c in cols)

            # Insert one at a time to handle per-row errors gracefully
            inserted = 0
            for row in cleaned_rows:
                try:
                    dst.execute(
                        text(f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'),
                        row,
                    )
                    inserted += 1
                except Exception as e:
                    err_msg = str(e).split('\n')[0]
                    print(f"  ⚠ row {row.get('id', '?')}: {err_msg[:120]}")
                    dst.rollback()
            dst.commit()
            print(f"  Inserted {inserted}/{len(cleaned_rows)} rows")
            total_rows += inserted

    print(f"\n=== Migration complete: {total_rows} total rows ===")

    # Verify
    print("\n--- Verify row counts ---")
    with pg_engine.connect() as conn:
        for t in ordered:
            try:
                n = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                # Compare with SQLite
                with sqlite_engine.connect() as sconn:
                    sn = sconn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                match = "✅" if n == sn else "❌"
                print(f"  {match} {t:30s} SQLite={sn:>5} | Postgres={n:>5}")
            except Exception as e:
                print(f"  ⚠ {t}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
