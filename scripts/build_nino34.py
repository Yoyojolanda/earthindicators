#!/usr/bin/env python3
"""Build a Climate-Reanalyzer-style Nino 3.4 daily SST JSON from NOAA OISST v2.1.

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


def fetch_year(year, weighting):
    import xarray as xr
    url = URL.format(year=year)
    for attempt in range(5):
        try:
            ds = xr.open_dataset(url)
            break
        except Exception as e:  # network hiccups are common on OPeNDAP
            print(f"  open {year} failed ({e}); retry {attempt+1}", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"could not open {url}")
    lat, lon = ds["lat"].values, ds["lon"].values
    li = np.where((lat >= LAT[0]) & (lat <= LAT[1]))[0]
    lo = np.where((lon >= LON[0]) & (lon <= LON[1]))[0]
    sub = ds["sst"].isel(lat=slice(li.min(), li.max() + 1),
                         lon=slice(lo.min(), lo.max() + 1)).load()
    if weighting == "cos":
        sub = sub.weighted(np.cos(np.deg2rad(sub["lat"]))).mean(("lat", "lon"))
    else:
        sub = sub.mean(("lat", "lon"))
    days = sub["time"].values.astype("datetime64[D]")
    out = {}
    for d, v in zip(days, sub.values):
        if np.isfinite(v):
            out[d.astype(object)] = float(v)
    return out


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/oisst2.1_nino3.4_sst_day.json")
    ap.add_argument("--cache", default="data/nino34_daily_sst.csv")
    ap.add_argument("--weighting", choices=["cos", "none"], default="cos")
    ap.add_argument("--start", type=int, default=1982)
    ap.add_argument("--full", action="store_true", help="refetch every year")
    ap.add_argument("--compare", help="reference Climate Reanalyzer JSON to compare against")
    a = ap.parse_args()

    daily = {} if a.full else load_cache(a.cache)
    this = date.today().year
    years = range(a.start, this + 1) if not daily else range(this - 1, this + 1)
    for y in years:
        print(f"fetching {y} ...")
        got = fetch_year(y, a.weighting)
        if y < this and len(got) < 360:
            sys.exit(f"{y}: only {len(got)} days returned; refusing to continue")
        for d in [d for d in daily if d.year == y]:
            del daily[d]
        daily.update(got)
    save_cache(a.cache, daily)
    out = build_json(daily)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"wrote {a.out}; latest day {max(daily)}")
    if a.compare and os.path.exists(a.compare):
        compare(out, a.compare)


if __name__ == "__main__":
    main()
