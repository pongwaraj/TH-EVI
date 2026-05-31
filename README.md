# TH-EVI: Thailand Electric Vehicle Infrastructure Projection Model

TH-EVI estimates EV charging demand for Thailand locations, with a Chiang Mai
pilot dataset. The project combines EV adoption forecasting, location demand,
station-level demand, hourly load shaping, queue sizing, and validation reports.

## Quick Start

```powershell
pip install -r requirements.txt
python tests\run_demo.py
```

Run the API and local map:

```powershell
python -m th_evi.api
```

Then open `http://localhost:8000`.

## Project Structure

```text
th_evi/
  adoption.py      EV adoption S-curve and fleet accumulation
  location.py      Location and station demand models
  temporal.py      Hourly arrivals and Erlang-C queue sizing
  validation.py    Adoption and station validation report
  constants.py     Thailand and Chiang Mai model assumptions
  data.py          Data loading utilities for DLT, DOH, OSM, population
  api.py           FastAPI endpoints and local static frontend
  static/index.html

data/              Chiang Mai AADT, population, and charger datasets
notebooks/         Analysis notebooks and scripts
tests/             Lightweight model tests and demo runner
```

## Validation

Generate the current validation report:

```powershell
python -m th_evi.validation
```

Current validation coverage:

- Adoption layer is compared against FTI/Autolife annual BEV new passenger-car
  shares for 2023, 2024, and 2025.
- Station layer currently has one confirmed station-day. This is enough to fit
  the single `calibration_factor`, but not enough to estimate out-of-sample
  station error. Collect at least four more station-days before treating station
  validation as robust.

## Tests

Run all tests with pytest:

```powershell
python -m pytest -q
```

The tests can also be run directly if pytest is not installed:

```powershell
python tests\test_adoption.py
python tests\test_location.py
python tests\test_temporal.py
```

## Model Overview

The location model estimates daily charging demand:

```text
EV visits/day = AADT * fleet EV share(year) * charge probability
```

The station model estimates daily sessions from resident, ride-hail, tourist,
and transit components, then optionally applies a single calibrated multiplier.

The temporal layer converts daily sessions into hourly arrivals and uses
Erlang-C queueing to size plugs against explicit service levels such as
`P(wait) <= 10%` and average wait under 10 minutes.

## Data Notes

Tracked datasets include Chiang Mai AADT files, population tables, OSM charging
station data, and `Fuel_NewCar_Apr69.xls`. Large derived datasets and notebook
HTML outputs are ignored, except for `th_evi/static/index.html`, which is kept
as the local frontend for the API.
