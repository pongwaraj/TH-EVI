# TH-EVI: Thailand Electric Vehicle Infrastructure Projection Model
## Inspired by NREL EVI-Pro Methodology

This project estimates EV charging infrastructure demand for any location in Thailand,
projecting 10-15 years forward.

## Quick Start

```bash
pip install -r requirements.txt
jupyter notebook notebooks/01_th_evi_chiang_mai_demo.ipynb
```

## Project Structure

```
th_evi/              # Core model package
├── adoption.py      # EV adoption S-curve forecast
├── location.py      # Location demand estimation
├── catchment.py     # Catchment zone analysis
├── constants.py     # Default parameters (Thailand-specific)
├── data.py          # Data loading utilities (AADT, DLT, etc.)
└── utils.py         # Helper functions
notebooks/           # Jupyter notebooks for analysis & demo
data/                # Raw & processed data (gitignored if large)
tests/               # Unit tests
```

## Data Sources (Planned)

| Source | Data | Status |
|--------|------|--------|
| DLT (กรมขนส่ง) | EV registration by province | 📝 To collect |
| DOH (กรมทางหลวง) | AADT traffic volume | 📝 To collect |
| DOPA (ปกครอง) | Population density | 📝 To collect |
| POI | Destinations (malls, hotels, etc.) | 📝 To collect |
| AOT | Airport traffic | 📝 To collect |

## Model Overview

For a given location (lat, lon) and year:

```
EVs/day = Traffic_Volume × EV_Share(year) × P(charge)
```

Where:
- `Traffic_Volume` = AADT or estimated from population density
- `EV_Share(year)` = S-curve calibrated to Thailand 30@30 policy
- `P(charge)` = probability based on location type & dwell time
