#!/usr/bin/env python3
"""Build a Climate-Reanalyzer-style Nino 3.4 daily SST JSON from NOAA OISST v2.1.

The box defaults to Nino 3.4; --lat/--lon/--stride let the same script build other regions
(e.g. world 60S-60N with --lat -60 60 --lon 0 360 --stride 4). Defaults leave Nino 3.4 unchanged.

Source: NOAA PSL OPeNDAP (yearly files, subset to the Nino 3.4 box only).
Output: list of {"name": "<year>", "data": [366 values by day-of-year]} plus
        {"name": "1991-2020", "data": [...]} (day-of-year mean, 5-day circular smoothing).
"""
import argparse, csv, json, os, sys, time
from datetime import date

import numpy as np

URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.day.mean.{year}.nc"
LAT, LON = (-5.0, 5.0), (190.0, 240.0)   # 5S-5N, 170W-120W (degrees east)
CLIM = (1991, 2020)


def _open(url, engine):
    import xarray as xr
    for attempt in range(4):
        try:
            return xr.open_dataset(url, engine=engine)
        except Exception as e:
            print(f"  [{engine}] open failed ({e}); retry {attempt+1}", flush=True)
            time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"could not open {url} with {engine}")


def _load(piece):
    for attempt in range(4):
        try:
            return piece.load()
        except Exception as e:
            print(f"    chunk failed ({e}); retry {attempt+1}", flush=True)
            time.sleep(8 * (attempt + 1))
    raise RuntimeError("chunk failed after retries")


def _fetch_year_engine(url, weighting, engine, chunk=30, lat_box=LAT, lon_box=LON, stride=1):
    ds = _open(url, engine)
    lat, lon = ds["lat"].values, ds["lon"].values
    li = np.where((lat >= lat_box[0]) & (lat <= lat_box[1]))[0]
    lo = np.where((lon >= lon_box[0]) & (lon <= lon_box[1]))[0]
    # stride > 1 samples every n-th grid point (server-side), to keep large regions fast
    sst = ds["sst"].isel(lat=slice(li.min(), li.max() + 1, stride), lon=slice(lo.min(), lo.max() + 1, stride))
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


def fetch_year(year, weighting, url_template=URL, lat_box=LAT, lon_box=LON, stride=1):
    url = url_template.format(year=year)
    last = None
    for engine in ("netcdf4", "pydap"):
        try:
            return _fetch_year_engine(url, weighting, engine, lat_box=lat_box, lon_box=lon_box, stride=stride)
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
    ap.add_argument("--lat", type=float, nargs=2, default=list(LAT), metavar=("S", "N"), help="latitude box (default: Nino 3.4)")
    ap.add_argument("--lon", type=float, nargs=2, default=list(LON), metavar=("W", "E"), help="longitude box in degrees east (default: Nino 3.4)")
    ap.add_argument("--stride", type=int, default=1, help="use every n-th grid point (default 1 = all)")
    ap.add_argument("--compare", help="reference Climate Reanalyzer JSON to compare against")
    ap.add_argument("--check-out", help="write a one-line summary of the comparison to this file")
    a = ap.parse_args()

    daily = {} if a.full else load_cache(a.cache)
    this = date.today().year
    counts = {}
    for d in daily:
        counts[d.year] = counts.get(d.year, 0) + 1
    years = [y for y in range(a.start, this + 1) if y >= this - 1 or counts.get(y, 0) < 360]
    for n, y in enumerate(years, 1):
        print(f"[{n}/{len(years)}] fetching {y} ...", flush=True)
        got = fetch_year(y, a.weighting, a.url_template, tuple(a.lat), tuple(a.lon), a.stride)
        print(f"    {len(got)} days", flush=True)
        if y < this and len(got) < 360:
            sys.exit(f"{y}: only {len(got)} days returned; refusing to continue")
        for d in [d for d in daily if d.year == y]:
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
