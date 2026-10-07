# Earth Indicators

Live climate indicators in plain words, at **[earthindicators.org](https://earthindicators.org)**.

Each page shows one of Earth's vital signs, updated automatically from the agencies that measure it:

| Page | Data |
|---|---|
| Global air temperature | Copernicus ERA5 |
| Sea surface temperature | NOAA OISST |
| El Niño (Niño 3.4) | NOAA OISST |
| Ocean heat content | NOAA NCEI |
| Sea level | NASA |
| Sea ice extent | NSIDC Sea Ice Index |
| Sea ice volume | Copernicus Marine (Mercator GLORYS12; CryoSat-2 + SMOS) |
| CO₂ (Mauna Loa) | NOAA Global Monitoring Laboratory |
| Methane | NOAA Global Monitoring Laboratory |
| Earth's energy imbalance | NASA CERES |

**[Common claims, answered](https://earthindicators.org/claims.html)**: short answers to the claims people run into most, using live numbers from the data pages. Every answer has its own link.

## How it works

- Plain HTML, CSS and JavaScript. No build step; GitHub Pages serves the files as they are.
- GitHub Actions workflows (`.github/workflows/`) download fresh data from each agency on a schedule and commit it to `data/`.
- `indicators.js` calculates every live number shown outside the charts, so the front page, the claims page and the "In short" boxes always agree.

## Where the numbers come from

**[How the numbers are made](https://earthindicators.org/methods.html)** gives, for every chart, the exact dataset and version (with DOI), the files downloaded, the processing steps, the code and the checks.

The files in `data/` are of two kinds:

- **Agency files, unchanged**: CO₂ and methane (NOAA GML), ocean heat content (`h22-*.dat`, NOAA NCEI), sea level (NASA-SSH, NOAA LSA), sea ice extent (NSIDC Sea Ice Index v4). Derived numbers (trends, running means, growth rates) are calculated in the browser by each page's own script.
- **Series calculated here** from gridded agency data:
  - `scripts/build_nino34.py`: El Niño and sea surface temperature, area-weighted averages of NOAA OISST v2.1 (`*_daily_sst.csv`, `oisst2.1_*_sst_day.json`).
  - `scripts/build_era5.py` and `build_era5_regions.py`: air temperature from Copernicus ERA5 (`era5_*`). In `era5_t2_global_daily.csv` the `source` column marks each day as Copernicus's published value (`c3s`) or calculated here (`cds`).
  - `scripts/build_seaice_volume.py`: sea ice volume for both poles from Copernicus Marine thickness and concentration grids, model (`seaice_volume_glorys.csv`) and satellite (`seaice_volume_cs2smos.csv`).
  - `scripts/build_ceres.py`: NASA CERES EBAF-TOA Ed4.2.1 global monthly means (`ceres_ebaf_global.csv`), taken from the file's own global-mean variables.

Calculated series are checked against independently published ones; the results are saved as `data/nino34_check.txt`, `data/era5_seam_check.txt` and `data/era5_overlap_check.txt` and shown on the methods page.
