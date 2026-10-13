#!/usr/bin/env python3
"""Global water vapour in the air (total column water vapour) from Copernicus ERA5 monthly averages.

Total column water vapour is all the water vapour above one square metre of ground, from the surface to the top of
the atmosphere, in kg/m². 1 kg/m² is a 1 mm layer of liquid water if it all condensed at once ("precipitable water").

Source: "ERA5 monthly averaged data on single levels from 1940 to present" (DOI 10.24381/cds.f17050d7), variable
total_column_water_vapour, the same dataset build_era5_monthly.py uses for air temperature.

Output
  data/era5_tcwv_monthly.csv   month, then the cos(latitude)-weighted mean over each region, in kg/m²:
                               world, nh, sh, tropics (23.5S-23.5N), nhmid (northern mid-latitudes, 30-60N)

Each run fetches only what is missing: whole years in chunks of CHUNK years, then the months of the current year
(the last 3 are fetched again when a new month appears, because the early-release data can still be revised).
A region added later (nhmid) is filled in for the past by downloading only its own latitude band.
Needs ~/.cdsapirc. ERA5_BUDGET_MIN limits the run time (default 300 minutes); the next run continues.
"""
import csv, os, shutil, tempfile, time, zipfile
from datetime import date, timedelta

import numpy as np

DATASET = "reanalysis-era5-single-levels-monthly-means"
VAR = "total_column_water_vapour"
REGIONS = {"world": (-90, 90), "nh": (0, 90), "sh": (-90, 0), "tropics": (-23.5, 23.5), "nhmid": (30, 60)}
BASE = ("world", "nh", "sh", "tropics")   # a month counts as present once these are; later columns are back-filled
CSVF = "data/era5_tcwv_monthly.csv"
FIRST, CHUNK = 1940, 5
BUDGET = float(os.environ.get("ERA5_BUDGET_MIN", "300")) * 60


def load():
    rows = {}
    if os.path.exists(CSVF):
        for r in csv.DictReader(open(CSVF)):
            rows[r["month"]] = {k: float(r[k]) for k in REGIONS if r.get(k)}
    rows = {m: v for m, v in rows.items() if all(k in v for k in BASE)}
    return rows


def save(rows):
    with open(CSVF + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["month", *REGIONS])
        for m in sorted(rows):
            if all(k in rows[m] for k in BASE):
                w.writerow([m, *[f"{rows[m][k]:.4f}" if k in rows[m] else "" for k in REGIONS]])
    os.replace(CSVF + ".tmp", CSVF)


def fetch(client, years, months, area=None):
    """Download monthly mean total column water vapour; returns an xarray DataArray (kg/m²) with a time dimension."""
    import xarray as xr
    req = {"product_type": ["monthly_averaged_reanalysis"], "variable": [VAR],
           "year": [str(y) for y in years], "month": [f"{m:02d}" for m in months], "time": ["00:00"],
           "data_format": "netcdf", "download_format": "unarchived"}
    if area:
        req["area"] = area   # [north, west, south, east]: download only this band
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tcwv")
        for attempt in range(3):
            try:
                client.retrieve(DATASET, req).download(path); break
            except Exception as e:
                print(f"    request failed ({str(e)[:200]})", flush=True)
                if attempt == 2 or any(k in str(e).lower() for k in ("not available", "no data", "invalid", "none of the data")):
                    return None
                time.sleep(60 * (attempt + 1))
        if zipfile.is_zipfile(path):
            z = zipfile.ZipFile(path); name = [n for n in z.namelist() if n.endswith(".nc")][0]
            open(path + ".nc", "wb").write(z.read(name)); path += ".nc"
        ds = xr.open_dataset(path)
        da = ds[[v for v in ds.data_vars if ds[v].ndim == 3][0]].load()
        ds.close()
        tdim = next(d for d in da.dims if d in ("valid_time", "time", "date"))
        return da.rename({tdim: "time"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def region_means(da, names=REGIONS):
    latn = next(d for d in da.dims if d.startswith("lat")); lonn = next(d for d in da.dims if d.startswith("lon"))
    lat = da[latn]; w = np.cos(np.deg2rad(lat))
    out = {}
    for name in names:
        s, n = REGIONS[name]
        sel = (lat >= s) & (lat <= n)
        m = da.where(sel, drop=True).weighted(w.where(sel, drop=True)).mean((latn, lonn))
        for t, v in zip(m["time"].values.astype("datetime64[M]").astype(str), m.values):
            out.setdefault(t, {})[name] = float(v)
    return out


def main():
    import cdsapi
    t0 = time.time()
    client = cdsapi.Client(quiet=True, progress=False)
    rows = load()
    today = date.today()
    # newest month that should be published (monthly averages appear about 5 days after the month ends)
    last = date(today.year, today.month, 1) - timedelta(1)
    if (today - last).days <= 6:
        last = date(last.year, last.month, 1) - timedelta(1)

    # 1. complete years that are missing any month, CHUNK years per request
    lastfull = last.year if last.month == 12 else last.year - 1
    todo = [y for y in range(FIRST, lastfull + 1) if any(f"{y}-{m:02d}" not in rows for m in range(1, 13))]
    for k in range(0, len(todo), CHUNK):
        if time.time() - t0 > BUDGET:
            print("time budget used; the next run continues", flush=True); break
        ys = todo[k:k + CHUNK]
        print(f"years {ys[0]}-{ys[-1]} ...", flush=True)
        da = fetch(client, ys, range(1, 13))
        if da is None:
            print("  no data; stopping here", flush=True); break
        for m, v in region_means(da).items():
            rows.setdefault(m, {}).update(v)
        save(rows)
        print(f"  saved ({(time.time() - t0) / 60:.0f} min used)", flush=True)

    # 2. months of the current year, plus the last 3 again when a new month has appeared
    want, d = [], date(last.year, 1, 1)
    while d <= last:
        want.append(f"{d:%Y-%m}"); d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    if want and want[-1] not in rows:
        recent = sorted(set([m for m in want if m not in rows] + sorted(rows)[-3:]))
        by_year = {}
        for m in recent:
            by_year.setdefault(int(m[:4]), []).append(int(m[5:]))
        for y, ms in sorted(by_year.items()):
            print(f"months {y}: {ms}", flush=True)
            da = fetch(client, [y], ms)
            if da is not None:
                for m, v in region_means(da).items():
                    rows.setdefault(m, {}).update(v)
                save(rows)

    # 3. regions added later: fill the past from a download of just their latitude band (CHUNK years per request)
    for name in [k for k in REGIONS if k not in BASE]:
        s, n = REGIONS[name]
        miss = sorted({int(m[:4]) for m, v in rows.items() if name not in v})
        full = [y for y in miss if y < last.year]
        jobs = [(full[k:k + CHUNK], range(1, 13)) for k in range(0, len(full), CHUNK)]
        if last.year in miss:
            jobs.append(([last.year], range(1, last.month + 1)))   # the current year on its own: no unpublished months
        for ys, months in jobs:
            if time.time() - t0 > BUDGET:
                print("time budget used; the next run continues", flush=True); break
            print(f"{name}: years {ys[0]}-{ys[-1]} ...", flush=True)
            da = fetch(client, ys, months, area=[n, -180, s, 180])
            if da is None:
                print("  no data; stopping here", flush=True); break
            for m, v in region_means(da, [name]).items():
                if m in rows:
                    rows[m].update(v)
            save(rows)
            print(f"  saved ({(time.time() - t0) / 60:.0f} min used)", flush=True)
    print(f"months: {min(rows) if rows else '-'} to {max(rows) if rows else '-'} ({len(rows)})", flush=True)


if __name__ == "__main__":
    main()
