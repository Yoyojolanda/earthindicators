#!/usr/bin/env python3
"""Overlap test: regional ERA5 air temperature from Google's ARCO-ERA5 copy vs. the Copernicus-based cache.

Before ARCO-ERA5 is used to backfill data/era5_t2_regions_daily.csv, this checks that it gives the same numbers
for days the cache already has. ARCO-ERA5 stores hourly values, so the daily mean is computed here the way
Copernicus's "daily statistics" product does it: the plain mean of the 24 hourly values 00-23 UTC. The regional
averaging is not copied but imported from build_era5_regions.py (region_means), so both use exactly the same
regions, latitude limits and cos(latitude) weights.

Reads only (no account, no queue), writes nothing to the repo; results go to the log and the run's summary.
  ARCO_FROM / ARCO_TO   date range to test, default 2016-01-01 .. 2016-12-31 (must lie inside the cache)
  ARCO_THREADS          parallel reads, default 8
Pass: every region within 0.01 degC on every day.
"""
import os, sys, time
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from build_era5_regions import REGIONS, load_cache, region_means   # the same code the real build uses

ARCO = os.environ.get("ARCO_PATH", "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3")
VAR = "2m_temperature"
D0 = date.fromisoformat(os.environ.get("ARCO_FROM") or "2016-01-01")
D1 = date.fromisoformat(os.environ.get("ARCO_TO") or "2016-12-31")
THREADS = int(os.environ.get("ARCO_THREADS") or "8")
TOL = 0.01


def months(a, b):
    while a <= b:
        nxt = (a.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield a, min(b, nxt - timedelta(days=1))
        a = nxt


def main():
    import dask, xarray as xr
    dask.config.set(scheduler="threads", num_workers=THREADS)
    cache = load_cache()
    ds = xr.open_zarr(ARCO, chunks={"time": 24}, consolidated=True, storage_options={"token": "anon"})
    print(f"ARCO-ERA5: {ARCO}")
    print(f"  data available {ds.attrs.get('valid_time_start', '?')} to {ds.attrs.get('valid_time_stop', '?')}, "
          f"grid {ds.sizes['latitude']} x {ds.sizes['longitude']}", flush=True)
    da = ds[VAR]

    diffs = {k: [] for k in REGIONS}          # ARCO minus cache, per day
    worst = {k: (0.0, None) for k in REGIONS}
    ndays, t_all = 0, time.time()
    for a, b in months(D0, D1):
        t = time.time()
        hourly = da.sel(time=slice(np.datetime64(f"{a}T00:00"), np.datetime64(f"{b}T23:00")))
        nh = hourly.sizes["time"]
        if nh != 24 * ((b - a).days + 1):
            sys.exit(f"{a:%Y-%m}: expected {24 * ((b - a).days + 1)} hourly fields, found {nh}")
        daily = hourly.coarsen(time=24).mean().compute()          # 00-23 UTC mean, like Copernicus
        daily = daily.assign_coords(time=np.arange(np.datetime64(a), np.datetime64(b + timedelta(days=1))))
        got = region_means(daily.to_dataset(name="t2m"))
        n = 0
        for d, vals in got.items():
            if d not in cache:
                continue
            for k, v in vals.items():
                if k in cache[d]:
                    x = v - cache[d][k]; diffs[k].append(x)
                    if abs(x) > abs(worst[k][0]): worst[k] = (x, d)
            n += 1
        ndays += (b - a).days + 1
        dt = time.time() - t
        print(f"  {a:%Y-%m}: {(b - a).days + 1} days in {dt:.0f} s ({dt / ((b - a).days + 1):.1f} s/day), "
              f"{n} compared", flush=True)

    total = time.time() - t_all
    per_day = total / ndays
    lines = [f"ARCO-ERA5 minus cache (Copernicus daily statistics), {D0} to {D1}, tolerance {TOL} degC", "",
             "| region | days | mean | std | largest (date) |", "|---|---|---|---|---|"]
    ok = True
    for k in REGIONS:
        x = np.array(diffs[k])
        if not len(x):
            lines.append(f"| {k} | 0 | | | |"); ok = False; continue
        ok &= bool(np.abs(x).max() <= TOL)
        lines.append(f"| {k} | {len(x)} | {x.mean():+.4f} | {x.std():.4f} | {worst[k][0]:+.4f} ({worst[k][1]}) |")
    span = (date(2015, 1, 1) - date(1991, 1, 1)).days
    lines += ["", f"Speed: {per_day:.1f} s per day; 1991-2014 ({span} days) would take about {span * per_day / 3600:.1f} h "
              f"of reading, 1940-1990 another {(date(1991, 1, 1) - date(1940, 1, 1)).days * per_day / 3600:.1f} h.",
              "", "RESULT: " + ("PASS - ARCO-ERA5 matches the cache" if ok else "FAIL - see differences above")]
    out = "\n".join(lines)
    print("\n" + out)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(out + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
