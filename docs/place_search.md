# Place search

Planning and Advanced Analysis share the place/coordinate control. Typing a name
searches after 350 ms; pasting coordinates retains immediate map navigation.
Name results never move the map until explicitly chosen. Results show a province
and switch the selected Heat Map province before loading its existing model.

`GET /api/place-search?q=...&province=Chiang%20Mai&limit=8` searches shipped POI and
competitor files, published DB overrides, and active saved sites. The province is
a ranking preference, not a filter. Invalid coordinates and inactive published
records are excluded. Reference inventory is cached for 30 seconds and cleared
by reference Admin edits; saved sites are read fresh. Database fallback is marked
`partial`, not confused with an authoritative empty search.

`data/place_search_aliases.json` adds bilingual labels and alternate names to
existing province/kind/ID keys. It is search metadata only. It does not create
POIs, change coordinates, add weights, or modify heat-map/demand calculations.
New places require the normal reference-data verification process.

## Optional external search

Without a provider key, local search is fully available and no external geocoder
is called. Arbitrary businesses not in TH-EVI cannot be guaranteed to appear.

To enable the implemented MapTiler browser adapter, configure
`TH_EVI_MAPTILER_PUBLIC_KEY` locally / in Vercel and restart or redeploy. This is
an intentionally public browser key: create a dedicated search key, restrict it
to the production domain and approved local origins, set usage/billing limits,
and check the applicable commercial terms before enabling it. Never put a private
or unrestricted service credential in this variable.

`GET /api/place-search/config` exposes only this explicitly public key. The
browser calls MapTiler directly with `country=th`, Thai/English language
preferences, autocomplete, and current-map proximity. External content is not
stored in Neon, localStorage, or a server cache; attribution stays visible while
an external result is selected. External calls only supplement fewer than eight
internal matches. A missing/unresolved province is reported rather than loading
another province's heat map as though it matched.

No Google Places or public Nominatim autocomplete integration is used.

Provider documentation:
- https://docs.maptiler.com/cloud/api/geocoding/
- https://docs.maptiler.com/client-js/
- https://operations.osmfoundation.org/policies/nominatim/
- https://developers.google.com/maps/documentation/places/web-service/policies

## Verification

Run `python -m pytest tests -q` and the browser flows with a local server:
`node tests/frontend_place_search.cjs`, `node tests/frontend_coordinate_flow.cjs`.
Set `CHROMIUM_EXECUTABLE_PATH` if a compatible Playwright browser is not installed.
The provider adapter is tested with mocked responses; live Thai POI coverage and
provider account restrictions still need verification when a real key is added.
