"""Back up and publish only the Chiang Mai pilot profile/evidence to Neon.

Dry-run by default. Existing station power/counts and non-Chiang Mai data are
not rewritten. Secrets are read from an ignored env file, never printed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from th_evi.area_engine import METHOD
from th_evi.charging_profiles import profile_for_province
from th_evi.charging_profile_store import backfill_competitor_evidence, persist_profile_snapshot
from th_evi.db import ChargingBehaviorProfileSnapshot


def load_database_url(path: Path) -> str:
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            values[key.strip()] = json.loads(value)
        except json.JSONDecodeError:
            values[key.strip()] = value.strip().strip("\"'")
    for key in ("TH_EVI_DB_URL", "DATABASE_URL", "POSTGRES_URL"):
        value = values.get(key)
        if isinstance(value, str) and value.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            return value.replace("postgres://", "postgresql+psycopg://", 1).replace("postgresql://", "postgresql+psycopg://", 1)
    raise ValueError("No Postgres URL found in the supplied env file")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.vercel.production")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    url = load_database_url(args.env_file)
    if not (make_url(url).host or "").endswith(".neon.tech"):
        raise ValueError("Refusing an unexpected production database host")
    profile = profile_for_province("Chiang Mai")
    if not profile or not profile.get("spatial_pilot_enabled") or profile.get("spatial_energy_enabled"):
        raise ValueError("Expected the reviewed screening-only Chiang Mai pilot profile")
    province = profile["province"]
    engine = create_engine(url, connect_args={"connect_timeout": 15})
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '10s'"))
        conn.execute(text("SET LOCAL statement_timeout = '60s'"))
        rows = [dict(row) for row in conn.execute(text(
            "SELECT * FROM charger_competitors WHERE province IN (:province, 'Chiang Mai') ORDER BY id"
        ), {"province": province}).mappings()]
        summary = {"mode": "apply" if args.apply else "dry_run", "province": province,
                   "competitor_rows": len(rows), "profile_engine": METHOD}
        if not rows:
            raise ValueError("Expected existing Chiang Mai station records; refusing an empty target")
        if not args.apply:
            print(json.dumps(summary, ensure_ascii=True))
            return
        backup = ROOT / "tmp" / ("chiang_mai_pilot_db_backup_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        backup.parent.mkdir(parents=True, exist_ok=True)
        profiles = []
        if inspect(conn).has_table(ChargingBehaviorProfileSnapshot.__tablename__):
            profiles = [dict(row) for row in conn.execute(text(
                "SELECT * FROM charging_behavior_profile_snapshots WHERE province=:province"
            ), {"province": province}).mappings()]
        backup.write_text(json.dumps({"competitors": rows, "profiles": profiles}, ensure_ascii=True, default=str, indent=2), encoding="utf-8")
        ChargingBehaviorProfileSnapshot.__table__.create(conn, checkfirst=True)
        for field in ("connector_summary", "power_summary"):
            conn.execute(text(f'ALTER TABLE charger_competitors ADD COLUMN IF NOT EXISTS "{field}" TEXT'))
        with Session(bind=conn, join_transaction_mode="create_savepoint") as session:
            summary["profile"] = persist_profile_snapshot(session, profile, engine_version=METHOD, actor="codex_production_publish")
            summary["evidence"] = backfill_competitor_evidence(session, province, [
                ROOT / "data" / f"competitors_chiang_mai_{suffix}.csv"
                for suffix in ("seed", "detailed", "google_verified")
            ])
            session.commit()
        after = [dict(row) for row in conn.execute(text(
            "SELECT * FROM charger_competitors WHERE province IN (:province, 'Chiang Mai') ORDER BY id"
        ), {"province": province}).mappings()]
        unchanged = set(rows[0]) - {"connector_summary", "power_summary", "updated_at", "updated_by"} if rows else set()
        if len(after) != len(rows) or any(
            any(old[key] != new[key] for key in unchanged) for old, new in zip(rows, after)
        ):
            raise ValueError("Unexpected competitor data changes; transaction rolled back")
        summary["backup"] = str(backup)
        summary["preserved_original_station_numbers"] = True
    engine.dispose()
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
