#!/usr/bin/env python3
"""Northern Hemisphere snow cover, for the sea-ice page: weekly snow-covered land area since October 1966.

Source: NOAA Climate Data Record of Northern Hemisphere Snow Cover Extent (Robinson et al., Rutgers University Global
Snow Lab, distributed by NOAA NCEI): weekly maps on an 88×88 grid, from the charts that analysts draw from satellite
images. This is the same record as Rutgers' own snow cover tables (whose server does not answer automated requests
from GitHub). NCEI publishes one file with the whole record, renamed each week as it grows; it is downloaded only when a new
version appears (about once a week, ~25 MB).

Area: for each week, the area of the grid cells that are snow covered and land, summed. Greenland is counted as
land (as in Rutgers' "nhland" series, whose numbers this reproduces closely; checked by --check).
Output: data/snow_nh_weekly.csv  week_start, area_km2 (one row per weekly map)
"""
import csv, json, os, re, sys, urllib.request
from datetime import date, datetime, timedelta

import numpy as np

CAT = "https://www.ncei.noaa.gov/thredds/catalog/cdr/snowcover/catalog.xml"
DAP = "https://www.ncei.noaa.gov/thredds/dodsC/cdr/snowcover/{f}"
FILE = "https://www.ncei.noaa.gov/thredds/fileServer/cdr/snowcover/{f}"
OUT, STATUS = "data/snow_nh_weekly.csv", "data/snow_status.json"


def latest_name():
    req = urllib.request.Request(CAT, headers={"User-Agent": "earthindicators.org data update (GitHub Actions)"})
    xml = urllib.request.urlopen(req, timeout=60).read().decode()
    names = re.findall(r'(nhsce_v\d+r\d+_\d{8}_(\d{8})\.nc)', xml)
    if not names:
        raise RuntimeError("no snow cover file in the catalog")
    return max(names, key=lambda n: n[1])[0]


def open_ds(name):
    """The whole file (~25 MB), downloaded once per new version (NCEI's OPeNDAP server refuses the data requests)."""
    import xarray as xr
    path = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), name)
    req = urllib.request.Request(FILE.format(f=name), headers={"User-Agent": "earthindicators.org data update (GitHub Actions)"})
    with urllib.request.urlopen(req, timeout=600) as r, open(path + ".part", "wb") as fh:
        fh.write(r.read())
    os.replace(path + ".part", path)
    return xr.open_dataset(path)


def describe(ds):
    for k, v in ds.variables.items():
        a = {x: v.attrs[x] for x in ("long_name", "units", "flag_values", "flag_meanings", "valid_range") if x in v.attrs}
        print(f"::notice::snow file variable {k} {v.dims} {v.dtype} {a}", flush=True)


def main():
    name = latest_name()
    st = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    if st.get("file") == name and os.path.exists(OUT) and "--force" not in sys.argv:
        print(f"{name} already read; nothing new", flush=True); return
    print(f"file: {name}", flush=True)
    ds = open_ds(name)
    describe(ds)
    sce = "snow_cover_extent" if "snow_cover_extent" in ds else next(v for v in ds.data_vars if "snow" in v.lower() and ds[v].ndim == 3)
    land = next((v for v in ds.data_vars if v.lower() in ("land", "land_mask", "landmask")), None)
    area = next((v for v in ds.data_vars if "area" in v.lower()), None)
    if land is None or area is None:
        sys.exit(f"variables not found (snow {sce}, land {land}, area {area})")
    times = [np.datetime64(t, "D").astype(object) for t in ds["time"].values]
    old = {}
    if os.path.exists(OUT):
        with open(OUT) as fh:
            old = {date.fromisoformat(r["week_start"]): r["area_km2"] for r in csv.DictReader(fh)}
    # land mask: land (1) and, if coded separately, Greenland/ice sheet; water and sea ice are left out
    L = ds[land].values
    fv = ds[land].attrs.get("flag_values"); fm = str(ds[land].attrs.get("flag_meanings", "")).split()
    landvals = [int(v) for v, m in zip(np.atleast_1d(fv), fm) if re.search(r"land|ice_sheet|greenland|lake", m, re.I) and not re.search(r"sea|water|ocean|off", m, re.I)] if fv is not None else [1]
    print(f"::notice::land values used: {landvals} (flags {list(np.atleast_1d(fv)) if fv is not None else None} {fm})", flush=True)
    M = np.isin(L, landvals)
    A = np.nan_to_num(ds[area].values.astype(float))
    # weeks to (re)read: everything new, plus the last 8 saved weeks (late corrections)
    have = sorted(old)
    start = have[-8] if len(have) > 8 else None
    idx = [i for i, t in enumerate(times) if start is None or t >= start]
    out = dict(old)
    for k in range(0, len(idx), 400):
        sub = ds[sce].isel(time=idx[k:k + 400]).values
        for j, i in enumerate(idx[k:k + 400]):
            s = sub[j]
            if not np.isfinite(s).any():
                continue
            out[times[i]] = f"{float(np.sum(A[(s == 1) & M])):.0f}"
    if len(out) < 2500:
        sys.exit(f"only {len(out)} weeks")
    last = max(out)
    v = float(out[last])
    if not (5e5 < v < 6e7) and not (last.month in (7, 8) and v >= 0):
        sys.exit(f"implausible latest value {v} for {last}")
    with open(OUT + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["week_start", "area_km2"])
        for t in sorted(out):
            w.writerow([t.isoformat(), out[t]])
    os.replace(OUT + ".tmp", OUT)
    json.dump({"file": name, "through": last.isoformat(), "read": date.today().isoformat(), "source": FILE.format(f=name)}, open(STATUS, "w"), indent=1)
    print(f"::notice::wrote {OUT}: {min(out)} to {last}, {len(out)} weeks; latest {v / 1e6:.2f} million km²")
    if "--check" in sys.argv:   # Rutgers' published weekly values for a few recent weeks (wkcov.nhland.txt)
        print("::notice::check against Rutgers: " + ", ".join(f"{t}: {float(out[t]) / 1e6:.2f}" for t in sorted(out)[-6:]), flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:   # shown on the job's summary page
        print(f"::error::snow cover: {type(e).__name__}: {e}", flush=True); raise
