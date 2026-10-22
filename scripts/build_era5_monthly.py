#!/usr/bin/env python3
"""Monthly 2 m air temperature from Copernicus ERA5 monthly averages: regional means and yearly 2-degree maps.

Copernicus stores ERA5 monthly averages ready-made (dataset "ERA5 monthly averaged data on single levels",
DOI 10.24381/cds.f17050d7): the mean of all hourly values in each month. Unlike the daily statistics, they need
no on-demand calculation, so the whole record since 1940 can be downloaded in a few requests.

Outputs
  data/era5_t2_regions_monthly.csv   month, then one column per region (same regions and cos(latitude) weighting
                                     as build_era5_regions.py), in degC
  data/era5_t2_annual_2deg.bin       yearly mean maps, complete years only: int16 little-endian, degC x 100,
                                     years x 90 latitudes (north to south) x 180 longitudes (from 0 E eastwards)
  data/era5_t2_annual_2deg.json      what is in the .bin: years, grid, scale
  data/era5_monthly_check.txt        world yearly means from these monthly averages vs Copernicus's published daily series

Each run fetches only what is missing: whole years for the maps, plus the newest months (the last 3 are fetched
again when a new month appears, because the early-release data can still be revised). Needs ~/.cdsapirc.
"""
import calendar, csv, json, os, shutil, sys, tempfile, time, zipfile
from datetime import date, timedelta

import numpy as np

DATASET = "reanalysis-era5-single-levels-monthly-means"
REGIONS = {"nh": (0, 90), "sh": (-90, 0), "arctic": (66.5, 90), "antarctic": (-90, -66.5),
           "tropics": (-23.5, 23.5), "world": (-90, 90)}
CSVF = "data/era5_t2_regions_monthly.csv"
BIN, META = "data/era5_t2_annual_2deg.bin", "data/era5_t2_annual_2deg.json"
CHECK = "data/era5_monthly_check.txt"
GLOBAL_DAILY = "data/era5_t2_global_daily.csv"
FIRST, CHUNK, DEG = 1940, 5, 2                     # years per request, map cell size
NLAT, NLON = 180 // DEG, 360 // DEG
BUDGET = float(os.environ.get("ERA5_BUDGET_MIN", "300")) * 60


def load_csv():
    rows = {}
    if os.path.exists(CSVF):
        for r in csv.DictReader(open(CSVF)):
            rows[r["month"]] = {k: float(r[k]) for k in REGIONS if r.get(k)}
    return rows


def save_csv(rows):
    with open(CSVF + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["month", *REGIONS])
        for m in sorted(rows):
            w.writerow([m, *[f"{rows[m][k]:.4f}" for k in REGIONS]])
    os.replace(CSVF + ".tmp", CSVF)


def load_maps():
    if not os.path.exists(META):
        return {}
    meta = json.load(open(META))
    arr = np.fromfile(BIN, dtype="<i2").reshape(len(meta["years"]), NLAT, NLON)
    return {y: arr[i] for i, y in enumerate(meta["years"])}


def save_maps(maps):
    years = sorted(maps)
    np.stack([maps[y] for y in years]).astype("<i2").tofile(BIN + ".tmp")
    os.replace(BIN + ".tmp", BIN)
    json.dump({"years": years, "nlat": NLAT, "nlon": NLON, "lat_north_edge": 90, "lon_west_edge": 0, "deg": DEG,
               "scale": 0.01, "units": "degC", "missing": -32768,
               "note": "Yearly mean 2 m temperature (mean of the 12 ERA5 monthly averages, weighted by days), cos(latitude)-weighted into 2-degree cells. Row 0 = 90-88N, column 0 = 0-2E."},
              open(META, "w"), separators=(",", ":"))


def fetch(client, years, months):
    """Download monthly mean 2 m temperature; returns an xarray DataArray (degC) with a time dimension."""
    import xarray as xr
    req = {"product_type": ["monthly_averaged_reanalysis"], "variable": ["2m_temperature"],
           "year": [str(y) for y in years], "month": [f"{m:02d}" for m in months], "time": ["00:00"],
           "data_format": "netcdf", "download_format": "unarchived"}
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "t2m")
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
        da = da.rename({tdim: "time"})
        if float(da.isel(time=0).mean()) > 150:
            da = da - 273.15
        return da
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def region_means(da):
    latn = next(d for d in da.dims if d.startswith("lat")); lonn = next(d for d in da.dims if d.startswith("lon"))
    lat = da[latn]; w = np.cos(np.deg2rad(lat))
    out = {}
    for name, (s, n) in REGIONS.items():
        sel = (lat >= s) & (lat <= n)
        m = da.where(sel, drop=True).weighted(w.where(sel, drop=True)).mean((latn, lonn))
        for t, v in zip(m["time"].values.astype("datetime64[M]").astype(str), m.values):
            out.setdefault(t, {})[name] = float(v)
    return out


def coarse(field, lat, lon):
    """cos(latitude)-weighted mean of a 2-D field into DEG-degree cells (NLAT x NLON)."""
    i = np.clip(((90 - lat) // DEG).astype(int), 0, NLAT - 1)
    j = (np.mod(lon, 360) // DEG).astype(int) % NLON
    w = np.repeat(np.cos(np.deg2rad(lat))[:, None], len(lon), 1)
    cell = (i[:, None] * NLON + j[None, :]).ravel()
    ok = np.isfinite(field.ravel())
    s = np.bincount(cell[ok], (field.ravel() * w.ravel())[ok], NLAT * NLON)
    n = np.bincount(cell[ok], w.ravel()[ok], NLAT * NLON)
    with np.errstate(invalid="ignore"):
        return (s / n).reshape(NLAT, NLON)


def year_map(da):
    """Yearly mean map from the 12 months of one year, weighted by days in each month."""
    latn = next(d for d in da.dims if d.startswith("lat")); lonn = next(d for d in da.dims if d.startswith("lon"))
    t = da["time"].values.astype("datetime64[M]").astype(str)
    days = np.array([calendar.monthrange(int(x[:4]), int(x[5:7]))[1] for x in t], float)
    mean = (da.values * days[:, None, None]).sum(0) / days.sum()
    m = coarse(mean, da[latn].values, da[lonn].values)
    return np.where(np.isfinite(m), np.round(m * 100), -32768).astype("<i2")


def check(rows):
    """World yearly means from the monthly averages vs the daily series (Copernicus's published values + this site's)."""
    if not os.path.exists(GLOBAL_DAILY):
        return
    daily = {}
    for r in csv.DictReader(open(GLOBAL_DAILY)):
        daily.setdefault(int(r["date"][:4]), []).append(float(r["temp"]))
    diffs, ys = [], []
    for y in sorted(daily):
        ms = [f"{y}-{m:02d}" for m in range(1, 13)]
        if len(daily[y]) >= 365 and all(m in rows for m in ms):
            d = [calendar.monthrange(y, m)[1] for m in range(1, 13)]
            mon = sum(rows[k]["world"] * n for k, n in zip(ms, d)) / sum(d)
            diffs.append(mon - np.mean(daily[y])); ys.append(y)
    if diffs:
        d = np.array(diffs)
        msg = (f"World yearly averages from ERA5 monthly averages minus those from the daily series, {len(d)} years "
               f"({ys[0]}-{ys[-1]}): mean {d.mean():+.4f} degC, largest difference {np.abs(d).max():.4f} degC.")
        open(CHECK, "w").write(msg + "\n"); print("  " + msg, flush=True)


def main():
    import cdsapi
    t0 = time.time()
    client = cdsapi.Client(quiet=True, progress=False)
    rows, maps = load_csv(), load_maps()
    today = date.today()
    # newest month that should be published (monthly averages appear about 5 days after the month ends)
    last = date(today.year, today.month, 1) - timedelta(1)
    if (today - last).days <= 6:
        last = date(last.year, last.month, 1) - timedelta(1)

    # 1. complete years without a map, in chunks of CHUNK years (these also fill in their months)
    todo = [y for y in range(FIRST, last.year + (1 if last.month == 12 else 0)) if y not in maps]
    for k in range(0, len(todo), CHUNK):
        if time.time() - t0 > BUDGET:
            print("time budget used; the next run continues", flush=True); break
        ys = todo[k:k + CHUNK]
        print(f"years {ys[0]}-{ys[-1]} ...", flush=True)
        da = fetch(client, ys, range(1, 13))
        if da is None:
            print("  no data; stopping here", flush=True); break
        rows.update(region_means(da)); save_csv(rows)
        tm = da["time"].values.astype("datetime64[Y]").astype(int) + 1970
        for y in ys:
            sub = da.isel(time=np.where(tm == y)[0])
            if sub.sizes["time"] == 12:
                maps[y] = year_map(sub)
        save_maps(maps)
        print(f"  saved ({(time.time() - t0) / 60:.0f} min used)", flush=True)

    # 2. months of the current (incomplete) year, plus the last 3 again when a new month has appeared
    want = []
    d = date(last.year, 1, 1)
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
                rows.update(region_means(da)); save_csv(rows)
    check(rows)
    print(f"regional months: {min(rows) if rows else '-'} to {max(rows) if rows else '-'}; maps: "
          f"{min(maps) if maps else '-'}-{max(maps) if maps else '-'}", flush=True)


if __name__ == "__main__":
    main()
