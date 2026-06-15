# KMZ Competitor Audit Summary

Source file:
- `C:\Users\Lenovo\Downloads\DC EV Charging Station Thailand - Piyamate Wisanuvej.kmz`

Generated artifacts:
- [dc_ev_kmz_extracted.csv](D:/Work/TH-EVI/artifacts/dc_ev_kmz_extracted.csv)
- [dc_ev_kmz_candidate_additions.csv](D:/Work/TH-EVI/artifacts/dc_ev_kmz_candidate_additions.csv)
- [extract_kmz_competitors.py](D:/Work/TH-EVI/artifacts/extract_kmz_competitors.py)

## What was done

- Parsed the KMZ and extracted `3,007` placemarks from `doc.kml`
- Compared extracted stations against current TH-EVI competitor files
- Used a conservative duplicate rule:
  - same province
  - existing point within `0.35 km`
- Kept only rows that look new to our current modeled province set

## Candidate additions found

Total candidate additions for currently modeled provinces: `354`

Top provinces by missing competitor rows:

| Province | Candidate additions |
| --- | ---: |
| สมุทรปราการ | 74 |
| นครราชสีมา | 62 |
| ระยอง | 40 |
| เชียงใหม่ | 33 |
| ขอนแก่น | 31 |
| อุบลราชธานี | 18 |
| เชียงราย | 18 |
| ลำปาง | 17 |
| อุดรธานี | 15 |
| พิษณุโลก | 12 |

## Recommended use

Do **not** import all `354` rows directly into the live competition layer in one pass.

Safer workflow:

1. Use `dc_ev_kmz_candidate_additions.csv` as a staging file
2. Review by province
3. Promote only the rows that are:
   - exact named public stations
   - not obviously duplicated by brand / location
   - strategically relevant to our heat-map provinces
4. Keep imported rows as:
   - `verification_status = public_listing_needs_operator_verification`
   - `confidence = medium`

## Good near-term promotion candidates

The KMZ appears especially useful for expanding:

- `เชียงใหม่`
- `เชียงราย`
- `ลำปาง`
- `พิษณุโลก`
- `ระยอง`
- `สมุทรปราการ`
- `นครราชสีมา`

These provinces either:
- already matter in active TH-EVI analysis, or
- show meaningful coverage gaps versus the KMZ list.

## Notes

- The KMZ is strongest as a **public DC charger discovery source**
- It is weaker on:
  - exact gun count
  - exact max kW
  - live availability / access rules
- For that reason, this round improves completeness as **staging + audit-ready data**, not as blind live import.
