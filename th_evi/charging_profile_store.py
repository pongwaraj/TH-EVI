"""Idempotent, append-only profile snapshots and non-destructive evidence backfill."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .charging_profiles import profile_fingerprint
from .db import ChargerCompetitor, ChargingBehaviorProfileSnapshot
from .constants import PROVINCE_CANONICAL_NAMES, canonical_province_name


def persist_profile_snapshot(session, profile: dict, *, engine_version: str, actor: str) -> dict:
    digest = profile_fingerprint(profile)
    existing = session.query(ChargingBehaviorProfileSnapshot).filter_by(
        province=profile["province"], profile_sha256=digest,
    ).one_or_none()
    created = existing is None
    if created:
        existing = ChargingBehaviorProfileSnapshot(
            province=profile["province"], profile_sha256=digest,
            profile_json=json.dumps(profile, ensure_ascii=True, sort_keys=True),
            engine_version=engine_version, updated_by=actor,
        )
        session.add(existing)
        session.flush()
    if json.loads(existing.profile_json) != profile:
        raise ValueError("Stored profile snapshot does not match its hash")
    return {"id": existing.id, "created": created, "profile_sha256": digest,
            "engine_version": existing.engine_version}


def backfill_competitor_evidence(session, province: str, paths: list[Path]) -> dict:
    """Fill missing evidence only; leave numbers, existing evidence and admin edits intact."""
    source = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("station_id"):
                    target = source.setdefault(row["station_id"], {})
                    for key in ("connector_summary", "power_summary"):
                        if str(row.get(key) or "").strip():
                            target[key] = row[key].strip()
    updated, conflicts, unmatched = [], [], []
    canonical = canonical_province_name(province)
    aliases = {canonical, province} | {name for name, value in PROVINCE_CANONICAL_NAMES.items() if value == canonical}
    for row in session.query(ChargerCompetitor).filter(ChargerCompetitor.province.in_(aliases)).all():
        evidence = source.get(row.station_id)
        if evidence is None:
            unmatched.append(row.station_id)
            continue
        fields = []
        for key, value in evidence.items():
            current = getattr(row, key)
            if not current:
                setattr(row, key, value)
                fields.append(key)
            elif current != value:
                conflicts.append({"station_id": row.station_id, "field": key})
        if fields:
            row.updated_by = "charging_pilot_evidence_backfill"
            updated.append({"station_id": row.station_id, "fields": fields})
    session.flush()
    return {"updated": updated, "preserved_conflicts": conflicts, "no_csv_evidence": unmatched}
