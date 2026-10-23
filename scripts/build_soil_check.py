#!/usr/bin/env python3
"""Satellite check for the soil-moisture drought numbers: ERA5 against NASA's SMAP Level 4, like for like.

The share of the land in drought (root-zone soil moisture below its own 20th percentile for the time of year) is
calculated the same way from both, each against its own 2016-2025 percentiles (the years both cover), so the
different absolute levels of the two products do not matter:
  ERA5  every pentad at the 1° land points of scripts/build_soil.py (from its Actions cache, SOIL_CACHE)
  SMAP  every day's sample of the 9 km EASE grid kept by scripts/build_smap.py (its Actions cache, SMAP_GRID),
        averaged into the same pentads; the EASE grid is equal-area, so no weights are needed
Rules as in build_soil.py: unfrozen soil, enough variation, the driest 20% not pinned at the lower limit.
  -> data/soil_smap_check.csv  date (first day of the pentad), era5, smap (% of the land in drought)
"""
import csv, io, os, sys
from datetime import date

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_soil as b

OUT = "data/soil_smap_check.csv"
BASE = (2016, 2025)


def shares(P, w):
    b.BASE = BASE
    M, Q20, Q40, Q0 = b.thresholds({q: v for q, v in P.items()})
    rows, _ = b.rows_for(P, sorted(P), M, Q20, Q40, Q0, w, persist=1)
    return {q: float(r[1]) for q, r in rows.items()}


def main():
    sc, grid = os.environ.get("SOIL_CACHE"), os.environ.get("SMAP_GRID")
    if not sc or not os.path.exists(sc) or not grid or not os.path.isdir(grid):
        sys.exit("needs both caches (SOIL_CACHE and SMAP_GRID)")
    c = np.load(sc)
    cy, ck, crz, cst = c["y"], c["k"], c["rz"], c["st"]      # read each array once (indexing the npz re-reads it)
    E = {(int(y), int(k)): (crz[n], cst[n].astype("float32")) for n, (y, k) in enumerate(zip(cy, ck)) if y >= 2015}
    # ERA5 point weights: cos(latitude) of the 1° land points (same selection as build_soil.py, from its thresholds file)
    jj = np.load(b.THR)["jj"].astype(int)
    lat_e = 90 - 0.25 * b.STRIDE * jj                        # ARCO-ERA5 latitudes run from 90°N down in 0.25° steps
    se = shares(E, np.cos(np.radians(lat_e)))
    # SMAP, one year file at a time (the whole cache at once does not fit in memory): days -> pentads at the land points
    lat = np.load(os.path.join(grid, "lat.npy"))
    keep = ((lat >= -60) & (lat <= 75)).ravel()
    files = sorted(f for f in os.listdir(grid) if f.endswith(".npz") and f[:4].isdigit())
    z = np.load(os.path.join(grid, files[len(files) // 2]))
    land = keep & (np.isfinite(z["rz"].astype("float32").reshape(len(z["dates"]), -1)).mean(axis=0) > 0.9)
    S = {}
    for f in files:
        z = np.load(os.path.join(grid, f))
        rz = z["rz"].reshape(len(z["dates"]), -1)[:, land].astype("float32")
        st = z["st"].reshape(len(z["dates"]), -1)[:, land].astype("float32")
        st[st == -128] = np.nan
        S.update(b.to_pentads({date.fromisoformat(str(d)): (rz[k], st[k]) for k, d in enumerate(z["dates"])}))
        del z, rz, st
    ss = shares(S, np.ones(int(land.sum())))
    keys = sorted(set(se) & set(ss))
    buf = io.StringIO(); wr = csv.writer(buf, lineterminator="\n"); wr.writerow(["date", "era5", "smap"])
    for q in keys:
        wr.writerow([b.pentad_start(*q).isoformat(), f"{se[q]:.2f}", f"{ss[q]:.2f}"])
    open(OUT + ".tmp", "w").write(buf.getvalue()); os.replace(OUT + ".tmp", OUT)
    a, z = np.array([se[q] for q in keys]), np.array([ss[q] for q in keys])
    print(f"{len(keys)} pentads, {keys[0]} to {keys[-1]}; {int(land.sum())} SMAP points; correlation {np.corrcoef(a, z)[0, 1]:.2f}", flush=True)


if __name__ == "__main__":
    main()
