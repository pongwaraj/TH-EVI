"""Shared, uncalibrated POI hierarchy for public-DC opportunity screening.

Weights are relative evidence, not vehicles/day or NREL coefficients. Long
parking duration alone does not imply demand for public DC charging.
"""

from dataclasses import dataclass
from math import isfinite


POI_POLICY_VERSION = "public_dc_poi_hierarchy_v2"
POI_CAPTURE_FACTOR = 0.22


@dataclass(frozen=True)
class POIRule:
    weight: float
    radius_km: float
    tier: str
    role: str


# Tier ordering describes charging relevance, not the size of the institution.
POI_RULES = {
    "airport": POIRule(40, 3.0, "mobility", "destination"),
    "bus_station": POIRule(28, 2.0, "mobility", "destination"),
    "railway_station": POIRule(28, 2.0, "mobility", "destination"),
    "train_station": POIRule(28, 2.0, "mobility", "destination"),
    "transport": POIRule(26, 2.0, "mobility", "destination"),
    "taxi_rank": POIRule(28, 1.8, "mobility", "destination"),
    "border_crossing": POIRule(32, 2.5, "mobility", "corridor"),
    "transport_corridor": POIRule(12, 1.5, "context", "corridor"),
    "shopping_mall": POIRule(38, 2.5, "commercial", "destination"),
    "community_mall": POIRule(30, 2.0, "commercial", "destination"),
    "lifestyle": POIRule(30, 2.0, "commercial", "destination"),
    "supermarket": POIRule(24, 1.6, "commercial", "destination"),
    "hospital": POIRule(14, 1.5, "service", "destination"),
    "university": POIRule(8, 1.5, "service", "support"),
    "hotel": POIRule(8, 1.1, "service", "support"),
    "tourism": POIRule(10, 1.6, "service", "support"),
    "tourism_museum": POIRule(8, 1.2, "service", "support"),
    "recreation": POIRule(8, 1.2, "service", "support"),
    "event_space": POIRule(6, 1.0, "service", "support"),
    "gas_station": POIRule(8, 1.2, "local", "support"),
    "highway_service_area": POIRule(8, 1.2, "local", "corridor"),
    "restaurant_cafe": POIRule(6, 1.1, "local", "support"),
    "retail": POIRule(6, 1.0, "local", "support"),
    "local_market": POIRule(8, 1.0, "local", "support"),
    "market_tourism": POIRule(14, 1.6, "local", "support"),
    "office": POIRule(4, 1.0, "local", "support"),
    "education": POIRule(3, 0.8, "local", "support"),
    "school": POIRule(2, 0.6, "local", "support"),
    "target_site": POIRule(6, 1.0, "local", "support"),
    "city_center": POIRule(10, 1.5, "context", "context"),
    "district_center": POIRule(6, 1.2, "context", "context"),
    "neighborhood_center": POIRule(6, 1.2, "context", "context"),
    "neighborhood_recreation": POIRule(3, 0.8, "local", "support"),
    "hotel_condo": POIRule(3, 0.8, "residential", "support"),
    "apartment": POIRule(3, 0.8, "residential", "support"),
    "condo": POIRule(3, 0.8, "residential", "support"),
    "residential": POIRule(0, 0.5, "residential", "context"),
    "housing_estate": POIRule(0, 0.5, "residential", "context"),
}
UNKNOWN_RULE = POIRule(2, 0.8, "unknown", "support")
POI_CATEGORY_RULES = {name: (rule.weight, rule.radius_km) for name, rule in POI_RULES.items()}


def poi_rule(category):
    return POI_RULES.get(str(category or "").strip(), UNKNOWN_RULE)


def screening_weight(*, model_prior, poi_score, zone_score, business_area_score, district_score):
    """Do not let assumed traffic or overlapping area labels create hotspots.

The legacy traffic estimate is only a prior, capped by POI evidence. Zone,
business and district describe overlapping context: use the largest, bounded
by local activity (or a small coverage-only weight in evidence-poor areas).
"""
    def nonnegative(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, value) if isfinite(value) else 0.0

    activity = nonnegative(poi_score)
    prior = min(nonnegative(model_prior), activity)
    context = min(max(nonnegative(zone_score), nonnegative(business_area_score),
                      nonnegative(district_score)), max(1.0, activity))
    # Convert the legacy capture-adjusted inputs back to relative POI points;
    # otherwise visibility thresholds and competitor pressure use other units.
    components = {"poi_activity": activity / POI_CAPTURE_FACTOR,
                  "bounded_traffic_prior": 0.35 * prior / POI_CAPTURE_FACTOR,
                  "overlap_adjusted_context": 0.35 * context / POI_CAPTURE_FACTOR}
    return {"method": POI_POLICY_VERSION, "weight": sum(components.values()),
            "components": components, "calibrated": False}
