"""Verified CSV-to-database publishing for Heat Map reference data.

The Heat Map stays CSV-led until a province has a published release whose
database snapshot matches a clean ingestion of the committed CSV files.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from . import ingest
from .db import (
    BusinessAreaReference,
    ChargerCompetitor,
    DistrictNodeReference,
    HeatmapExclusionReference,
    HotZoneReference,
    POIReference,
    ReferenceDatasetRelease,
    create_session_factory,
)


REFERENCE_LAYERS = (
    (
        "pois",
        POIReference,
        "poi_id",
        ("poi_id", "province", "district", "name", "category", "lat", "lon", "demand_role", "radius_km", "weight", "verification_status", "confidence", "active"),
    ),
    (
        "competitors",
        ChargerCompetitor,
        "station_id",
        ("station_id", "province", "district", "name", "network", "operator", "lat", "lon", "plug_count", "gun_count", "max_kw", "status", "verification_status", "confidence", "active"),
    ),
    (
        "business_areas",
        BusinessAreaReference,
        "business_area_id",
        ("business_area_id", "province", "name", "area_type", "center_lat", "center_lon", "radius_km", "demand_pool_conservative", "demand_pool_base", "demand_pool_upside", "location_type", "confidence", "active"),
    ),
    (
        "heatmap_exclusions",
        HeatmapExclusionReference,
        "exclusion_id",
        ("exclusion_id", "province", "name", "center_lat", "center_lon", "radius_km", "exclusion_type", "confidence", "reason", "active"),
    ),
    (
        "hot_zones",
        HotZoneReference,
        "zone_id",
        ("zone_id", "province", "name", "center_lat", "center_lon", "radius_km", "heat_rank", "demand_pool_conservative", "demand_pool_base", "demand_pool_upside", "competition_pressure", "confidence", "active"),
    ),
    (
        "district_nodes",
        DistrictNodeReference,
        "node_id",
        ("node_id", "province", "district_name", "name", "node_type", "lat", "lon", "radius_km", "confidence_multiplier", "confidence", "active"),
    ),
)


def _normalise_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 7)
    return value


def _snapshot(session, province: str) -> dict[str, dict[str, dict[str, Any]]]:
    snapshot: dict[str, dict[str, dict[str, Any]]] = {}
    for layer, model, id_field, fields in REFERENCE_LAYERS:
        records: dict[str, dict[str, Any]] = {}
        for row in session.query(model).filter_by(province=province).all():
            key = str(getattr(row, id_field))
            records[key] = {field: _normalise_value(getattr(row, field)) for field in fields}
        snapshot[layer] = records
    return snapshot


def _source_manifest(slug: str) -> dict[str, Any]:
    patterns = (
        f"aadt_{slug}_seed.csv",
        f"poi_{slug}_seed.csv",
        f"poi_{slug}_city_seed.csv",
        f"competitors_{slug}_seed.csv",
        f"competitors_{slug}_detailed.csv",
        f"competitors_{slug}_google_verified.csv",
        f"business_areas_{slug}.csv",
        f"heatmap_exclusions_{slug}.csv",
        f"hot_zones_{slug}.csv",
        f"district_nodes_{slug}.csv",
    )
    files = []
    for name in patterns:
        path = ingest.DATA_DIR / name
        if path.exists():
            content = path.read_bytes()
            files.append({"name": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return {"files": files, "file_count": len(files)}


def _dataset_version(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _expected_snapshot(slug: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Build the exact DB shape expected from current CSV without touching target DB."""
    province = ingest.SLUG_TO_NAME.get(slug, slug)
    factory = create_session_factory("sqlite:///:memory:")
    with factory() as session:
        source_map = ingest.seed_reference_sources(session)
        ingest.ingest_province(session, source_map, slug)
        session.flush()
        return _snapshot(session, province)


def _deactivate_stale_ingest_rows(session, province: str, expected: dict[str, dict[str, dict[str, Any]]]) -> dict[str, int]:
    """Retire only obsolete CSV-managed rows; preserve admin-created records."""
    deactivated: dict[str, int] = {}
    for layer, model, id_field, _fields in REFERENCE_LAYERS:
        ids = set(expected[layer])
        count = 0
        for row in session.query(model).filter_by(province=province, updated_by="ingest").all():
            if str(getattr(row, id_field)) not in ids and row.active:
                row.active = False
                count += 1
        deactivated[layer] = count
    session.flush()
    return deactivated


def compare_reference_snapshot(session, slug: str, expected: dict[str, dict[str, dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Compare CSV-derived expected rows with the managed rows in a target DB."""
    province = ingest.SLUG_TO_NAME.get(slug, slug)
    expected = expected or _expected_snapshot(slug)
    actual = _snapshot(session, province)
    layer_results: dict[str, Any] = {}
    passed = True

    for layer, model, id_field, fields in REFERENCE_LAYERS:
        expected_rows = expected[layer]
        actual_rows = actual[layer]
        expected_ids = set(expected_rows)
        managed_rows = {
            str(getattr(row, id_field)): row
            for row in (
                session.query(model)
                .filter_by(province=province, updated_by="ingest")
                .filter(model.active.is_(True))
                .all()
            )
        }
        managed_ids = set(managed_rows)
        missing = sorted(expected_ids - managed_ids)
        extra = sorted(managed_ids - expected_ids)
        mismatched = []
        for record_id in sorted(expected_ids & managed_ids):
            actual_row = actual_rows[record_id]
            changes = [field for field in fields if expected_rows[record_id].get(field) != actual_row.get(field)]
            if changes:
                mismatched.append({"id": record_id, "fields": changes})

        admin_only = sorted(
            str(getattr(row, id_field))
            for row in session.query(model).filter_by(province=province).all()
            if getattr(row, "updated_by", None) != "ingest" and str(getattr(row, id_field)) not in expected_ids
        )
        layer_passed = not missing and not extra and not mismatched
        passed = passed and layer_passed
        layer_results[layer] = {
            "passed": layer_passed,
            "expected_count": len(expected_ids),
            "managed_db_count": len(managed_ids),
            "missing_ids": missing,
            "extra_ingest_ids": extra,
            "mismatches": mismatched[:20],
            "admin_only_ids": admin_only,
        }

    return {"province": province, "province_slug": slug, "passed": passed, "layers": layer_results}


def sync_province_reference(
    session,
    slug: str,
    *,
    publish: bool = False,
    actor: str = "reference_sync",
) -> dict[str, Any]:
    """Ingest one province, verify parity, and optionally publish DB-first mode."""
    if slug not in ingest.SLUG_TO_NAME:
        raise ValueError(f"Unknown province slug: {slug}")

    province = ingest.SLUG_TO_NAME[slug]
    manifest = _source_manifest(slug)
    expected = _expected_snapshot(slug)
    if not any(expected[layer] for layer, *_rest in REFERENCE_LAYERS):
        raise ValueError(f"No Heat Map reference CSV files found for {slug}")

    source_map = ingest.seed_reference_sources(session)
    ingest.ingest_province(session, source_map, slug)
    deactivated = _deactivate_stale_ingest_rows(session, province, expected)
    parity = compare_reference_snapshot(session, slug, expected)
    parity["deactivated_ingest_rows"] = deactivated

    version = _dataset_version(manifest)
    release = (
        session.query(ReferenceDatasetRelease)
        .filter_by(province_slug=slug, dataset_version=version)
        .first()
    )
    if release is None:
        release = ReferenceDatasetRelease(
            province=province,
            province_slug=slug,
            dataset_version=version,
            manifest_json=json.dumps(manifest, ensure_ascii=True, sort_keys=True),
            parity_json="{}",
        )
        session.add(release)

    release.manifest_json = json.dumps(manifest, ensure_ascii=True, sort_keys=True)
    release.parity_json = json.dumps(parity, ensure_ascii=True, sort_keys=True)
    release.parity_passed = bool(parity["passed"])
    release.status = "published" if publish and parity["passed"] else ("verified" if parity["passed"] else "failed")
    release.published_by = actor if release.status == "published" else None
    release.published_at = datetime.utcnow() if release.status == "published" else None
    session.flush()

    return {
        "province": province,
        "province_slug": slug,
        "dataset_version": version,
        "release_id": release.id,
        "status": release.status,
        "parity": parity,
    }


def published_release_status(session, slug: str) -> dict[str, Any] | None:
    release = (
        session.query(ReferenceDatasetRelease)
        .filter_by(province_slug=slug, status="published", parity_passed=True)
        .order_by(ReferenceDatasetRelease.published_at.desc(), ReferenceDatasetRelease.id.desc())
        .first()
    )
    if release is None:
        return None
    return {
        "province": release.province,
        "province_slug": release.province_slug,
        "dataset_version": release.dataset_version,
        "status": release.status,
        "parity_passed": release.parity_passed,
        "published_by": release.published_by,
        "published_at": release.published_at.isoformat() if release.published_at else None,
    }
