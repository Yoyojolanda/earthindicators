#!/usr/bin/env python3
"""Daily 2 m air temperature for regions (and the world), computed here from Copernicus ERA5.

Same source and method as data/era5_t2_global_day.json (scripts/build_era5.py): the CDS dataset
"ERA5 post-processed daily statistics" (daily mean of all 24 hourly values, UTC), averaged over each
region with cos(latitude) weights. Regions as defined by Climate Reanalyzer:

  nh         Northern Hemisphere   0 to 90 N
  sh         Southern Hemisphere   0 to 90 S
  arctic     Arctic                66.5 to 90 N
  antarctic  Antarctic             66.5 to 90 S
  tropics    Tropics               23.5 S to 23.5 N
  world      World                 (only used to check this calculation against Copernicus's published series)

Each run first adds the newest days, then spends the remaining time budget filling in history, one month at
a time, going back towards 1940. Progress is saved after every month, so the backfill continues over many runs.

Outputs
  data/era5_t2_regions_daily.csv   cache: date + one column per region
  data/era5_t2_<region>_day.json   [{"name":"<year>","data":[366 values]}, ..., {"name":"1991-2020",...}]
                                   (written once the region's history covers 1991-2020)
  data/era5_overlap_check.txt      this site's world average minus Copernicus's published one, every overlapping day

Needs ~/.cdsapirc (url + key).
"""
import csv, json, os, sys, tempfile, time, zipfile
from datetime import date, timedelta

import numpy as np

DATASET = "derived-era5-single-levels-daily-statistics"
REGIONS = {"nh": (0, 90), "sh": (-90, 0), "arctic": (66.5, 90), "antarctic": (-90, -66.5),
           "tropics": (-23.5, 23.5), "world": (-90, 90)}
PUBLISH = ["nh", "sh", "arctic", "antarctic", "tropics"]
CACHE = "data/era5_t2_regions_daily.csv"
GLOBAL_CACHE = "data/era5_t2_global_daily.csv"       # Copernicus's published series, kept by build_era5.py
OVERLAP = "data/era5_overlap_check.txt"
FIRST = date(1940, 1, 1)
CLIM = (1991, 2020)
LAG, REFETCH = 5, 10
BUDGET = float(os.environ.get("ERA5_BUDGET_MIN", "270")) * 60   # seconds of work per run, leaves time to commit


def load_cache():
    rows = {}
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            for r in csv.DictReader(fh):
                rows[date.fromisoformat(r["date"])] = {k: float(r[k]) for k in REGIONS if r.get(k)}
    return rows


def save_cache(rows):
    with open(CACHE + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["date", *REGIONS])
        for d in sorted(rows):
            w.writerow([d.isoformat(), *[f"{rows[d][k]:.4f}" if k in rows[d] else "" for k in REGIONS]])
    os.replace(CACHE + ".tmp", CACHE)


def open_nc(path):
    import xarray as xr
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        name = [n for n in z.namelist() if n.endswith(".nc")][0]
        with open(path + ".nc", "wb") as fh:
            fh.write(z.read(name))
        path = path + ".nc"
    return xr.open_dataset(path)


def region_means(ds):
    """{date: {region: area-weighted mean in degC}}"""
    var = [v for v in ds.data_vars if ds[v].ndim == 3][0]
    da = ds[var]
    tdim = next(d for d in da.dims if d in ("valid_time", "time", "date"))
    latn = next(d for d in da.dims if d.startswith("lat"))
    lonn = next(d for d in da.dims if d.startswith("lon"))
    lat = ds[latn]
    w = np.cos(np.deg2rad(lat))
    kelvin = float(da.isel({tdim: 0}).mean()) > 150
    out = {}
    for name, (s, n) in REGIONS.items():
        sub = da.where((lat >= s) & (lat <= n), drop=True)
        m = sub.weighted(w.where((lat >= s) & (lat <= n), drop=True)).mean((latn, lonn))
        for t, v in zip(m[tdim].values.astype("datetime64[D]"), m.values):
            if np.isfinite(v):
                out.setdefault(t.astype(object), {})[name] = float(v) - (273.15 if kelvin else 0.0)
    return out


def fetch_month(client, days):
    """Regional means for a list of days within one month; drops the newest days if they are not available yet."""
    days = sorted(days)
    y, mth = days[0].year, days[0].month
    while days:
        req = {"product_type": "reanalysis", "variable": ["2m_temperature"],
               "year": f"{y}", "month": [f"{mth:02d}"], "day": [f"{d.day:02d}" for d in days],
               "daily_statistic": "daily_mean", "time_zone": "utc+00:00", "frequency": "1_hourly"}
        path = os.path.join(tempfile.mkdtemp(), "t2m")
        for attempt in range(3):
            try:
                client.retrieve(DATASET, req).download(path)
                return region_means(open_nc(path))
            except Exception as e:
                msg = str(e)
                print(f"    request failed ({msg[:200]})", flush=True)
                if any(k in msg.lower() for k in ("not available", "no data", "invalid")):
                    break
                time.sleep(30 * (attempt + 1))
        print(f"    retrying without {days[-1]}", flush=True)
        days = days[:-1]
    return {}


def month_days(y, m, until):
    d, out = date(y, m, 1), []
    while d.month == m and d <= until:
        out.append(d); d += timedelta(1)
    return out


def write_jsons(rows):
    for r in PUBLISH:
        series = {d: v[r] for d, v in rows.items() if r in v}
        years = sorted({d.year for d in series})
        clim_years = [y for y in range(CLIM[0], CLIM[1] + 1) if y in years and sum(1 for d in series if d.year == y) >= 360]
        if len(clim_years) < CLIM[1] - CLIM[0] + 1:
            print(f"  {r}: history covers {years[0] if years else '-'}-{years[-1] if years else '-'}; not published until 1991-2020 is complete", flush=True)
            continue
        arr = {y: np.full(366, np.nan) for y in years}
        for d, v in series.items():
            arr[d.year][d.timetuple().tm_yday - 1] = v
        naive = np.nanmean(np.array([arr[y] for y in clim_years]), axis=0)
        clim = np.mean([np.roll(naive, k) for k in range(-2, 3)], axis=0)   # 5-day smoothing, as for the world series
        f = lambda a: [None if not np.isfinite(x) else round(float(x), 3) for x in a]
        out = [{"name": str(y), "data": f(arr[y])} for y in years]
        out.append({"name": f"{CLIM[0]}-{CLIM[1]}", "data": f(clim)})
        with open(f"data/era5_t2_{r}_day.json", "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        print(f"  wrote data/era5_t2_{r}_day.json ({years[0]}-{years[-1]})", flush=True)


def overlap_check(rows):
    """Compare this site's own world average with Copernicus's published series on every overlapping day."""
    if not os.path.exists(GLOBAL_CACHE):
        return
    pub = {}
    with open(GLOBAL_CACHE) as fh:
        for r in csv.DictReader(fh):
            if r["source"] == "c3s":
                pub[date.fromisoformat(r["date"])] = float(r["temp"])
    diffs = np.array([rows[d]["world"] - pub[d] for d in sorted(pub) if d in rows and "world" in rows[d]])
    if len(diffs) == 0:
        return
    days = sorted(d for d in pub if d in rows and "world" in rows[d])
    msg = (f"This site's ERA5 world average minus the series published by Copernicus, {len(diffs)} overlapping days "
           f"({days[0]} to {days[-1]}): mean {diffs.mean():+.4f} degC, standard deviation {diffs.std():.4f} degC, "
           f"largest difference {np.abs(diffs).max():.4f} degC.")
    with open(OVERLAP, "w") as fh:
        fh.write(msg + "\n")
    print("  " + msg, flush=True)


def main():
    import cdsapi
    t0 = time.time()
    os.makedirs("data", exist_ok=True)
    rows = load_cache()
    client = cdsapi.Client(quiet=True, progress=False)
    last_ok = date.today() - timedelta(LAG)

    # 1. newest days (plus the last few again: preliminary data can be revised)
    start = (max(rows) - timedelta(REFETCH)) if rows else last_ok - timedelta(40)
    months = {}
    for k in range((last_ok - start).days + 1):
        d = start + timedelta(k); months.setdefault((d.year, d.month), []).append(d)
    for (y, m), days in sorted(months.items()):
        print(f"new: {y}-{m:02d} ({len(days)} days)", flush=True)
        rows.update(fetch_month(client, days)); save_cache(rows)

    # 2. history, newest month first, while the time budget lasts
    while time.time() - t0 < BUDGET:
        first = min(rows)
        prev = date(first.year, first.month, 1) - timedelta(1)
        missing = [d for d in month_days(first.year, first.month, first) if d not in rows]
        if missing:                                    # finish a partly filled month first
            target = missing
        elif prev < FIRST:
            print("history complete back to 1940", flush=True); break
        else:
            target = month_days(prev.year, prev.month, prev)
        print(f"history: {target[0]:%Y-%m} ({(time.time() - t0) / 60:.0f} min used)", flush=True)
        got = fetch_month(client, target)
        if not got:
            print("  no data returned; stopping for this run", flush=True); break
        rows.update(got); save_cache(rows)

    print(f"cache: {min(rows)} to {max(rows)}", flush=True)
    write_jsons(rows)
    overlap_check(rows)


if __name__ == "__main__":
    main()
