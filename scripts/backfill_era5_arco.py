#!/usr/bin/env python3
"""Fill in the regional ERA5 history (data/era5_t2_regions_daily.csv) from Google's ARCO-ERA5 copy.

ARCO-ERA5 is the same ECMWF reanalysis as the Copernicus data the regular build downloads, stored hourly on
Google Cloud: free to read, no account and no queue. The daily mean is the plain mean of the 24 hourly values
00-23 UTC, as in Copernicus's "daily statistics" product; the regional averages come from region_means() in
build_era5_regions.py, so regions and weights are exactly the same. scripts/test_arco_overlap.py checked this
against the cache for 2016: every region within 0.0006 degC on every day.

Each call fills one chunk, newest first, directly below the oldest day in the cache (so the cache never has a
gap), and writes only the new days to $ARCO_OUT/era5_t2_regions_daily.csv. The workflow then adds them to
GitHub with merge_era5_regions.py and calls this again, until 1940 is reached.
  ARCO_FROM     oldest day to fill, default 1940-01-01
  ARCO_YEARS    years per chunk, default 10
  ARCO_OUT      folder for the new days, default /tmp/ours
Exit code 0: a chunk was written; 3: nothing left to fill.
"""
import os, sys, time
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_era5_regions as b

ARCO = os.environ.get("ARCO_PATH", "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3")
FROM = date.fromisoformat(os.environ.get("ARCO_FROM") or "1940-01-01")
YEARS = int(os.environ.get("ARCO_YEARS") or "10")
OUT = os.environ.get("ARCO_OUT") or "/tmp/ours"
THREADS = int(os.environ.get("ARCO_THREADS") or "8")


def main():
    rows = b.load_cache()
    hi = min(rows) - timedelta(1)                       # newest day to fill: just below the cache
    lo = max(FROM, date(hi.year - YEARS + 1, 1, 1))     # chunks end on whole years
    if hi < FROM:
        print(f"nothing to fill: cache already starts {min(rows)}", flush=True)
        sys.exit(3)

    import dask, xarray as xr
    dask.config.set(scheduler="threads", num_workers=THREADS)
    da = xr.open_zarr(ARCO, chunks={"time": 24}, consolidated=True, storage_options={"token": "anon"})["2m_temperature"]
    print(f"filling {lo} to {hi} from ARCO-ERA5", flush=True)

    new, t0 = {}, time.time()
    a = date(hi.year, hi.month, 1)
    while True:                                         # month by month, newest first
        s, e = max(a, lo), min(hi, (a.replace(day=28) + timedelta(4)).replace(day=1) - timedelta(1))
        hourly = da.sel(time=slice(np.datetime64(f"{s}T00:00"), np.datetime64(f"{e}T23:00")))
        n = (e - s).days + 1
        if hourly.sizes["time"] != 24 * n:
            sys.exit(f"{s:%Y-%m}: expected {24 * n} hourly fields, found {hourly.sizes['time']}")
        daily = hourly.coarsen(time=24).mean().compute()
        daily = daily.assign_coords(time=np.arange(np.datetime64(s), np.datetime64(e + timedelta(1))))
        got = b.region_means(daily.to_dataset(name="t2m"))
        if len(got) != n or any(len(v) != len(b.REGIONS) for v in got.values()):
            sys.exit(f"{s:%Y-%m}: incomplete result ({len(got)} of {n} days)")
        new.update(got)
        if s.month == 1:
            print(f"  {s.year} done ({(time.time() - t0) / 60:.1f} min)", flush=True)
        if s <= lo:
            break
        a = (a - timedelta(1)).replace(day=1)

    os.makedirs(OUT, exist_ok=True)
    b.CACHE = os.path.join(OUT, os.path.basename(b.CACHE))   # only the new days; the merge adds them to GitHub's copy
    b.save_cache(new)
    print(f"wrote {len(new)} days ({min(new)} to {max(new)}) to {b.CACHE}", flush=True)


if __name__ == "__main__":
    main()
