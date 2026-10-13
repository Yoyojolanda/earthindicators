#!/usr/bin/env python3
"""Build a Climate-Reanalyzer-style Nino 3.4 daily SST JSON from NOAA OISST v2.1.

The box defaults to Nino 3.4; --lat/--lon/--stride let the same script build other regions
(e.g. world 60S-60N with --lat -60 60 --lon 0 360 --stride 4). Defaults leave Nino 3.4 unchanged.

Source: NOAA PSL OPeNDAP (yearly files, subset to the Nino 3.4 box only).
Output: list of {"name": "<year>", "data": [366 values by day-of-year]} plus
        {"name": "1991-2020", "data": [...]} (day-of-year mean, 5-day circular smoothing).
"""
import argparse, csv, json, os, sys, time
from datetime import date, timedelta

import numpy as np

URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.day.mean.{year}.nc"
LAT, LON = (-5.0, 5.0), (190.0, 240.0)   # 5S-5N, 170W-120W (degrees east)
CLIM = (1991, 2020)
# Once PSL keeps answering 429 (too many requests), later runs of this script in the same job leave it alone.
BUSY_FLAG = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "psl_busy")
SAW_429 = False


def _open(url, engine):
    import xarray as xr
    for attempt in range(4):
        try:
            return xr.open_dataset(url, engine=engine)
        except Exception as e:
            # a busy server answers 429 (too many requests): back off for minutes, not seconds
            global SAW_429
            SAW_429 = SAW_429 or "429" in str(e) or "Too Many Requests" in str(e)
            wait = 60 * 2 ** attempt if "429" in str(e) or "Access failure" in str(e) else 8 * (attempt + 1)
            print(f"  [{engine}] open failed ({e}); retry {attempt+1} in {wait} s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"could not open {url} with {engine}")


def _load(piece):
    for attempt in range(4):
        try:
            return piece.load()
        except Exception as e:
            wait = 60 * 2 ** attempt if "429" in str(e) else 8 * (attempt + 1)
            print(f"    chunk failed ({e}); retry {attempt+1} in {wait} s", flush=True)
            time.sleep(wait)
    raise RuntimeError("chunk failed after retries")


def _fetch_year_engine(url, weighting, engine, chunk=30, lat_box=LAT, lon_box=LON, stride=1, since=None):
    ds = _open(url, engine)
    lat, lon = ds["lat"].values, ds["lon"].values
    li = np.where((lat >= lat_box[0]) & (lat <= lat_box[1]))[0]
    lo = np.where((lon >= lon_box[0]) & (lon <= lon_box[1]))[0]
    # stride > 1 samples every n-th grid point (server-side), to keep large regions fast
    sst = ds["sst"].isel(lat=slice(li.min(), li.max() + 1, stride), lon=slice(lo.min(), lo.max() + 1, stride))
    if since is not None:   # only the days from `since` on (opening the file reads just its metadata)
        times = ds["time"].values.astype("datetime64[D]")
        sst = sst.isel(time=slice(int(np.searchsorted(times, np.datetime64(since))), None))
    out = {}
    for i in range(0, sst.sizes["time"], chunk):
        sub = _load(sst.isel(time=slice(i, i + chunk)))
        if weighting == "cos":
            m = sub.weighted(np.cos(np.deg2rad(sub["lat"]))).mean(("lat", "lon"))
        else:
            m = sub.mean(("lat", "lon"))
        days = m["time"].values.astype("datetime64[D]")
        for d, v in zip(days, m.values):
            if np.isfinite(v):
                out[d.astype(object)] = float(v)
    return out


def fetch_year(year, weighting, url_template=URL, lat_box=LAT, lon_box=LON, stride=1, since=None):
    url = url_template.format(year=year)
    last = None
    for engine in ("netcdf4", "pydap"):
        try:
            return _fetch_year_engine(url, weighting, engine, lat_box=lat_box, lon_box=lon_box, stride=stride, since=since)
        except Exception as e:
            last = e
            print(f"  engine {engine} failed for {year}: {e}", flush=True)
    raise RuntimeError(f"all engines failed for {year}: {last}")


def build_json(daily):
    """daily: {datetime.date: sst}. Returns the list-of-series structure."""
    years = sorted({d.year for d in daily})
    arr = {y: np.full(366, np.nan) for y in years}
    for d, v in daily.items():
        arr[d.year][d.timetuple().tm_yday - 1] = v
    cy = [y for y in range(CLIM[0], CLIM[1] + 1) if y in arr]
    naive = np.nanmean(np.array([arr[y] for y in cy]), axis=0)
    clim = np.mean([np.roll(naive, k) for k in range(-2, 3)], axis=0)
    f = lambda a: [None if not np.isfinite(x) else round(float(x), 3) for x in a]
    out = [{"name": str(y), "data": f(arr[y])} for y in years if y >= 1982]
    out.append({"name": f"{CLIM[0]}-{CLIM[1]}", "data": f(clim)})
    return out


def load_cache(path):
    daily = {}
    if os.path.exists(path):
        with open(path) as fh:
            for row in csv.reader(fh):
                if row and row[0] != "date":
                    daily[date.fromisoformat(row[0])] = float(row[1])
    return daily


def save_cache(path, daily):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "sst"])
        for d in sorted(daily):
            w.writerow([d.isoformat(), f"{daily[d]:.4f}"])


def compare(new, ref_path):
    ref = {str(r["name"]): np.array([np.nan if x is None else x for x in r["data"]], float)
           for r in json.load(open(ref_path))}
    if "2026" in ref and "Preliminary" in ref:       # merge reference's preliminary tail
        m = np.isnan(ref["2026"]) & ~np.isnan(ref["Preliminary"]); ref["2026"][m] = ref["Preliminary"][m]
    mine = {r["name"]: np.array([np.nan if x is None else x for x in r["data"]], float) for r in new}
    print("\nComparison with reference (mean abs / max abs difference, degC):")
    worst = 0
    for k in sorted(mine):
        if k in ref:
            both = ~np.isnan(mine[k]) & ~np.isnan(ref[k])
            if both.any():
                dd = np.abs(mine[k][both] - ref[k][both]); worst = max(worst, dd.max())
                if not k.isdigit() or int(k) % 5 == 0 or int(k) >= 2024:
                    print(f"  {k}: mean {dd.mean():.4f}  max {dd.max():.4f}  (n={both.sum()})")
    print(f"  worst single-day difference: {worst:.4f}")
    # one-line summary for the methods page (every overlapping day, all years)
    d = np.concatenate([mine[k][b] - ref[k][b] for k in mine if k.isdigit() and k in ref
                        for b in [~np.isnan(mine[k]) & ~np.isnan(ref[k])] if b.any()])
    days = [int(k) for k in mine if k.isdigit() and k in ref]
    a = np.abs(d)
    return (f"This site's daily values minus Climate Reanalyzer's, {len(d)} overlapping days ({min(days)}-{max(days)}): "
            f"mean {d.mean():+.4f} degC; {np.mean(a < 0.0015) * 100:.1f}% of days within 0.001 degC; "
            f"{int(np.sum(a > 0.02))} days differ by more than 0.02 degC (largest {a.max():.3f} degC).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/oisst2.1_nino3.4_sst_day.json")
    ap.add_argument("--cache", default="data/nino34_daily_sst.csv")
    ap.add_argument("--weighting", choices=["cos", "none"], default="cos")
    ap.add_argument("--start", type=int, default=1982)
    ap.add_argument("--url-template", default=URL)
    ap.add_argument("--full", action="store_true", help="refetch every year")
    ap.add_argument("--recent-days", type=int, default=30,
                    help="refetch only this many days before the last cached day (OISST replaces its preliminary "
                         "values with final ones after about two weeks); complete earlier years are kept as they are")
    ap.add_argument("--lat", type=float, nargs=2, default=list(LAT), metavar=("S", "N"), help="latitude box (default: Nino 3.4)")
    ap.add_argument("--lon", type=float, nargs=2, default=list(LON), metavar=("W", "E"), help="longitude box in degrees east (default: Nino 3.4)")
    ap.add_argument("--stride", type=int, default=1, help="use every n-th grid point (default 1 = all)")
    ap.add_argument("--compare", help="reference Climate Reanalyzer JSON to compare against")
    ap.add_argument("--check-out", help="write a one-line summary of the comparison to this file")
    a = ap.parse_args()
    if os.path.exists(BUSY_FLAG):
        sys.exit("PSL refused an earlier series in this run (429 Too Many Requests); not asking again until the next run")

    daily = {} if a.full else load_cache(a.cache)
    this = date.today().year
    counts = {}
    for d in daily:
        counts[d.year] = counts.get(d.year, 0) + 1
    # refetch window: the last few weeks before the newest cached day (nothing cached = everything)
    since = max(daily) - timedelta(days=a.recent_days) if daily else None
    jobs = []   # (year, first day to fetch or None for the whole year)
    for y in range(a.start, this + 1):
        if y < this and counts.get(y, 0) >= 360:
            if since is not None and since.year <= y and since <= date(y, 12, 31):
                jobs.append((y, since if since.year == y else None))
        elif y == this and since is not None and since.year == y:
            jobs.append((y, since))
        else:
            jobs.append((y, None))
    for n, (y, first) in enumerate(jobs, 1):
        print(f"[{n}/{len(jobs)}] fetching {y}" + (f" from {first}" if first else "") + " ...", flush=True)
        try:
            got = fetch_year(y, a.weighting, a.url_template, tuple(a.lat), tuple(a.lon), a.stride, since=first)
        except RuntimeError:
            if SAW_429:
                open(BUSY_FLAG, "w").close()
            raise
        print(f"    {len(got)} days", flush=True)
        if first is None and y < this and len(got) < 360:
            sys.exit(f"{y}: only {len(got)} days returned; refusing to continue")
        start = first or date(y, 1, 1)
        for d in [d for d in daily if d.year == y and d >= start]:
            del daily[d]
        daily.update(got)
        save_cache(a.cache, daily)   # checkpoint after every year
    out = build_json(daily)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"wrote {a.out}; latest day {max(daily)}")
    if a.compare and os.path.exists(a.compare):
        msg = compare(out, a.compare)
        print("  " + msg)
        if a.check_out:
            with open(a.check_out, "w") as fh:
                fh.write(msg + "\n")


if __name__ == "__main__":
    main()
