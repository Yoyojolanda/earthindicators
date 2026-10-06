#!/usr/bin/env python3
"""Daily global-mean 2 m air temperature from Copernicus ERA5.

History: the Copernicus C3S published series (era5_daily_series_2t_global_1940-2024.csv),
         used for every day it marks FINAL.
New days: computed here from the CDS dataset "ERA5 post-processed daily statistics"
         (daily mean of all 24 hourly values, UTC), area-weighted over the whole globe,
         i.e. the same method as the published series.

Outputs
  data/era5_t2_global_daily.csv   date,temp,source   (cache; source = c3s or cds)
  data/era5_t2_global_day.json    [{"name":"1940","data":[366 values]}, ..., {"name":"1991-2020",...}]

Needs ~/.cdsapirc (url + key) for the CDS part.
"""
import csv, json, os, sys, tempfile, time, zipfile
from datetime import date, timedelta
from urllib.request import urlopen

import numpy as np

HIST_URL = "https://sites.ecmwf.int/data/c3sci/era5-daily/data/era5_daily_series_2t_global_1940-2024.csv"
DATASET = "derived-era5-single-levels-daily-statistics"
CACHE = "data/era5_t2_global_daily.csv"
OUT = "data/era5_t2_global_day.json"
SEAM = "data/era5_seam_check.txt"
CLIM = (1991, 2020)
LAG = 5          # ERA5 in the CDS runs about 5 days behind real time
REFETCH = 10     # always recompute the most recent days (preliminary data can be revised)


def load_cache():
    rows = {}
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            for r in csv.DictReader(fh):
                rows[date.fromisoformat(r["date"])] = (float(r["temp"]), r["source"])
    return rows


def save_cache(rows):
    os.makedirs("data", exist_ok=True)
    with open(CACHE, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["date", "temp", "source"])
        for d in sorted(rows):
            w.writerow([d.isoformat(), f"{rows[d][0]:.4f}", rows[d][1]])


def load_history():
    print("downloading Copernicus history series ...", flush=True)
    text = urlopen(HIST_URL, timeout=120).read().decode()
    rows = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or line.startswith("date"):
            continue
        d, t, status = line.split(",")[:3]
        if status.strip().upper() == "FINAL":
            rows[date.fromisoformat(d)] = (float(t), "c3s")
    print(f"  {len(rows)} final days, {min(rows)} to {max(rows)}", flush=True)
    if len(rows) < 30000:
        sys.exit("history series looks incomplete; refusing to continue")
    return rows


def open_nc(path):
    """CDS may deliver a .nc or a .zip containing one; return an xarray Dataset."""
    import xarray as xr
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        name = [n for n in z.namelist() if n.endswith(".nc")][0]
        out = path + ".nc"
        with open(out, "wb") as fh:
            fh.write(z.read(name))
        path = out
    return xr.open_dataset(path)


def global_means(ds):
    """{date: area-weighted global mean in degC} from a daily-mean 2 m temperature file."""
    var = [v for v in ds.data_vars if ds[v].ndim == 3][0]
    tdim = next(d for d in ds[var].dims if d in ("valid_time", "time", "date"))
    latn = next(d for d in ds[var].dims if d.startswith("lat"))
    lonn = next(d for d in ds[var].dims if d.startswith("lon"))
    da = ds[var]
    w = np.cos(np.deg2rad(ds[latn]))
    m = da.weighted(w).mean((latn, lonn))
    kelvin = float(m.mean()) > 150
    out = {}
    for t, v in zip(m[tdim].values.astype("datetime64[D]"), m.values):
        if np.isfinite(v):
            out[t.astype(object)] = float(v) - (273.15 if kelvin else 0.0)
    return out


def fetch_days(client, days):
    """Compute global means for a list of days within one month (shrinks the request if the newest days are not yet available)."""
    days = sorted(days)
    y, mth = days[0].year, days[0].month
    while days:
        req = {"product_type": "reanalysis", "variable": ["2m_temperature"],
               "year": f"{y}", "month": [f"{mth:02d}"], "day": [f"{d.day:02d}" for d in days],
               "daily_statistic": "daily_mean", "time_zone": "utc+00:00", "frequency": "1_hourly"}
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "t2m")
        for attempt in range(3):
            try:
                client.retrieve(DATASET, req).download(path)
                return global_means(open_nc(path))
            except Exception as e:
                msg = str(e)
                print(f"    request failed ({msg[:200]})", flush=True)
                if "not available" in msg.lower() or "no data" in msg.lower() or "invalid" in msg.lower():
                    break
                time.sleep(30 * (attempt + 1))
        print(f"    retrying without {days[-1]}", flush=True)
        days = days[:-1]
    return {}


def build_json(rows):
    years = sorted({d.year for d in rows})
    arr = {y: np.full(366, np.nan) for y in years}
    for d, (v, _) in rows.items():
        arr[d.year][d.timetuple().tm_yday - 1] = v
    cy = [y for y in range(CLIM[0], CLIM[1] + 1) if y in arr]
    naive = np.nanmean(np.array([arr[y] for y in cy]), axis=0)
    clim = np.mean([np.roll(naive, k) for k in range(-2, 3)], axis=0)
    f = lambda a: [None if not np.isfinite(x) else round(float(x), 3) for x in a]
    out = [{"name": str(y), "data": f(arr[y])} for y in years]
    out.append({"name": f"{CLIM[0]}-{CLIM[1]}", "data": f(clim)})
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"wrote {OUT}; {min(rows)} to {max(rows)}", flush=True)


def main():
    rows = load_cache()
    if not any(s == "c3s" for _, s in rows.values()):
        rows.update(load_history())
        save_cache(rows)
    hist_end = max(d for d, (_, s) in rows.items() if s == "c3s")

    import cdsapi
    client = cdsapi.Client(quiet=True, progress=False)

    # one-time seam check: compute the last weeks of the history ourselves and compare
    if not os.path.exists(SEAM):
        chk = [d for d in (hist_end - timedelta(k) for k in range(14)) if d.month == hist_end.month]
        print(f"seam check: computing {chk[-1]} to {chk[0]} from the CDS ...", flush=True)
        mine = fetch_days(client, chk)
        diffs = [mine[d] - rows[d][0] for d in chk if d in mine]
        if diffs:
            msg = (f"This site's calculation minus Copernicus's published series, last {len(diffs)} days of the published "
                   f"record (to {hist_end}): mean {np.mean(diffs):+.4f} degC, largest difference {np.max(np.abs(diffs)):.4f} degC.")
            print("  " + msg, flush=True)
            with open(SEAM, "w") as fh:
                fh.write(msg + "\n")
            if abs(np.mean(diffs)) > 0.02:
                print("  WARNING: offset larger than expected; check the method before trusting new days", flush=True)

    last_ok = date.today() - timedelta(LAG)
    have_cds = [d for d, (_, s) in rows.items() if s == "cds"]
    start = max(hist_end, max(have_cds) - timedelta(REFETCH) if have_cds else hist_end) + timedelta(1)
    todo = [start + timedelta(k) for k in range((last_ok - start).days + 1)]
    months = {}
    for d in todo:
        months.setdefault((d.year, d.month), []).append(d)
    print(f"{len(todo)} days to compute in {len(months)} monthly requests", flush=True)
    for n, (ym, days) in enumerate(sorted(months.items()), 1):
        print(f"[{n}/{len(months)}] {ym[0]}-{ym[1]:02d} ({len(days)} days) ...", flush=True)
        got = fetch_days(client, days)
        print(f"    got {len(got)} days", flush=True)
        for d, v in got.items():
            if d > hist_end:
                rows[d] = (v, "cds")
        save_cache(rows)            # checkpoint after every month
        if len(got) < len(days) and ym != max(months):
            print("    incomplete month; stopping here, next run continues", flush=True)
            break
    build_json(rows)


if __name__ == "__main__":
    main()
