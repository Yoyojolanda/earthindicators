#!/usr/bin/env python3
"""Soil moisture and flash droughts from ERA5 (water cycle page).

Root-zone soil moisture: the water in the top meter of soil, where most plant roots are. ERA5 has four soil layers;
the top three (0-7, 7-28 and 28-100 cm) are averaged by thickness. ERA5 calculates soil moisture with its land-surface
model, driven by the reanalysis weather (rain, sun, heat, wind) and corrected by weather observations: it is a model
estimate, not a measurement.

Source: Google's ARCO-ERA5 copy (the same ECMWF data as Copernicus, hourly, free, no queue), one value a day at
12 UTC (soil water in the root zone changes slowly), on a 1° sample of the 0.25° grid (every 4th point), land only
(land-sea mask >= 0.5) between 60°S and 75°N. Days are averaged into pentads: 73 five-day periods a year (29 February
joins the pentad of 28 February).

Per point and pentad, from 1991-2020 (pooling each pentad with the one before and after, so 90 values): the average,
and the 20th and 40th percentiles. Then for every pentad since 1950:
  drought  share of the land with root-zone soil moisture below its 20th percentile for the time of year (a common
           threshold for agricultural drought, e.g. the U.S. Drought Monitor's "moderate drought")
  flash    share of the land where a flash drought starts in that pentad: soil moisture falls from above the 40th
           percentile to below the 20th within 4 pentads (20 days) or less, the definition of Ford and Labosier
           (2017, Agricultural and Forest Meteorology 247, 414-423); counted in the pentad it first drops below the 20th
  anom     soil moisture compared with normal: sum over the land of (value - normal) / sum of normal, in %
A point and pentad only count while the soil is not frozen (ERA5 soil temperature 7-28 cm above 0 °C) and the soil
moisture there varies enough for percentiles to mean something (40th minus 20th percentile at least 0.002 m³/m³;
this leaves out ice sheets and the driest deserts). Shares are of the land that counts in that pentad, by area.

Outputs
  data/soil_pentad.csv   date (first day of the pentad), drought, flash, anom (%), land (million km² that counted)
  data/soil_yearly.csv   year, flash_area (% of the land that counted that year where at least one flash drought
                         started), drought (average of the pentads' drought shares), pentads (complete pentads)
  data/soil_thresholds.npz  the 1991-2020 normals and percentiles per point and pentad (kept, so later runs only
                         read the last 100 days)
The first run reads 1950 to now once (about 112,000 hourly fields, roughly an hour). Later runs read the last
100 days and recalculate the last 15 pentads.
"""
import csv, io, os, sys, time
from datetime import date, timedelta

import numpy as np

ARCO = os.environ.get("ARCO_PATH", "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3")
FIRST, BASE = 1950, (1991, 2020)
STRIDE, LATS = 4, (-60, 75)
VARS = ["volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2", "volumetric_soil_water_layer_3", "soil_temperature_level_2"]
WGT = np.array([7, 21, 72], "float32") / 100
THR = "data/soil_thresholds.npz"
PCSV, YCSV = "data/soil_pentad.csv", "data/soil_yearly.csv"
THREADS = int(os.environ.get("ARCO_THREADS") or "16")
MIN_SPREAD = 0.002


def pentad(d):
    k = d.timetuple().tm_yday - 1
    leap = d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)
    if leap and k >= 59:
        k -= 1                                    # 29 Feb -> 28 Feb's pentad; later days shift back by one
    return min(72, k // 5)


def pentad_start(y, k):
    d = date(y, 1, 1) + timedelta(days=5 * k)
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    return d + timedelta(days=1) if leap and 5 * k > 58 else d


def open_arco():
    # no dask: a dask graph over the whole store (1.3 million hours, hundreds of variables) does not fit in memory.
    # Fields are read one by one, in parallel threads (read_days).
    import xarray as xr
    return xr.open_zarr(ARCO, chunks=None, consolidated=True, storage_options={"token": "anon"})


def land_points(ds):
    lat = ds["latitude"].values[::STRIDE]; lon = ds["longitude"].values[::STRIDE]
    lsm = ds["land_sea_mask"].sel(time=np.datetime64("2020-01-01T00:00")).values[::STRIDE, ::STRIDE]
    ok = (lsm >= 0.5) & (lat[:, None] >= LATS[0]) & (lat[:, None] <= LATS[1])
    jj, ii = np.where(ok)
    return jj, ii, lat, lon


def last_day(ds):
    """Newest day whose 12 UTC fields have values (ARCO's time axis runs far into the future, empty)."""
    d = date.today()
    for _ in range(200):
        v = ds[VARS[2]].sel(time=np.datetime64(f"{d}T12:00")).values[::40, ::40]
        if np.isfinite(v).any():
            return d
        d -= timedelta(days=1)
    raise RuntimeError("no recent ERA5 day found in ARCO")


def read_days(ds, d0, d1, jj, ii):
    """Root-zone soil moisture and soil temperature (7-28 cm) at 12 UTC, days d0..d1 -> {date: (rz, st)}."""
    from concurrent.futures import ThreadPoolExecutor
    tax = ds["time"].values
    arrs = {v: ds[v] for v in VARS}

    def one(v, d):
        k = int(np.searchsorted(tax, np.datetime64(f"{d}T12:00")))
        for t in range(4):
            try:
                return arrs[v].isel(time=k).values[::STRIDE, ::STRIDE][jj, ii].astype("float32")
            except Exception as e:
                if t == 3:
                    raise
                print(f"  {v} {d}: {e}; retry", flush=True); time.sleep(10 * (t + 1))

    days = [d0 + timedelta(n) for n in range((d1 - d0).days + 1)]
    with ThreadPoolExecutor(THREADS) as ex:
        got = {(v, d): f for v in VARS for d in days for f in [ex.submit(one, v, d)]}
        got = {k: f.result() for k, f in got.items()}
    out = {}
    for d in days:
        rz = (WGT[0] * got[(VARS[0], d)] + WGT[1] * got[(VARS[1], d)] + WGT[2] * got[(VARS[2], d)]).astype("float32")
        if np.isfinite(rz).mean() > 0.9:
            out[d] = (rz, got[(VARS[3], d)] - 273.15)
    return out


def to_pentads(days):
    """{(year, pentad): (mean rz, mean soil temperature, n days)} for complete pentads only."""
    acc = {}
    for d, (rz, st) in days.items():
        k = (d.year, pentad(d))
        if k not in acc:
            acc[k] = [np.zeros_like(rz, "float64"), np.zeros_like(st, "float64"), 0]
        acc[k][0] += rz; acc[k][1] += st; acc[k][2] += 1
    need = lambda y, k: 6 if (k == 11 and y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 5
    return {k: ((v[0] / v[2]).astype("float32"), (v[1] / v[2]).astype("float32")) for k, v in acc.items() if v[2] >= need(*k)}


def thresholds(P):
    """mean, p20, p40 per (pentad, point) from the base years, pooling neighbouring pentads."""
    n = next(iter(P.values()))[0].shape[0]
    M = np.empty((73, n), "float32"); Q20 = np.empty_like(M); Q40 = np.empty_like(M)
    for k in range(73):
        S = np.stack([P[(y, (k + j) % 73)][0] for y in range(BASE[0], BASE[1] + 1) for j in (-1, 0, 1) if (y, (k + j) % 73) in P])
        M[k] = S.mean(0); Q20[k], Q40[k] = np.percentile(S, [20, 40], axis=0)
    return M, Q20, Q40


def rows_for(P, keys, M, Q20, Q40, w):
    """One row per pentad in keys (sorted), using the 4 pentads before each for flash droughts."""
    allk = sorted(P)
    pos = {k: i for i, k in enumerate(allk)}
    out, onset = {}, {}
    for key in keys:
        y, k = key
        rz, st = P[key]
        valid = (st > 0) & ((Q40[k] - Q20[k]) >= MIN_SPREAD) & np.isfinite(rz)
        dry = rz < Q20[k]
        i = pos[key]
        prev = [allk[i - j] for j in range(1, 5) if i - j >= 0]
        if len(prev) == 4 and prev[0] in P:
            p1 = P[prev[0]][0] >= Q20[prev[0][1]]                            # was not yet below the 20th percentile
            wet = np.zeros_like(dry)
            for q in prev:
                wet |= P[q][0] > Q40[q[1]]                                   # above the 40th within the last 4 pentads
            fl = dry & p1 & wet
        else:
            fl = np.zeros_like(dry)
        W = w[valid].sum()
        if W <= 0:
            continue
        out[key] = [pentad_start(y, k).isoformat(), f"{100 * w[valid & dry].sum() / W:.2f}", f"{100 * w[valid & fl].sum() / W:.3f}",
                    f"{100 * (w[valid] * (rz[valid] - M[k][valid])).sum() / (w[valid] * M[k][valid]).sum():.2f}", f"{W:.2f}"]
        onset[key] = valid & fl, valid
    return out, onset


def write(path, header, rows):
    buf = io.StringIO(); wr = csv.writer(buf, lineterminator="\n"); wr.writerow(header); wr.writerows(rows)
    with open(path + ".tmp", "w") as fh:
        fh.write(buf.getvalue())
    os.replace(path + ".tmp", path)


def yearly(prow, flashes):
    """flashes: {year: (union of onset points, union of valid points, weights)}"""
    by = {}
    for r in prow:
        by.setdefault(int(r[0][:4]), []).append(float(r[1]))
    out = []
    for y in sorted(by):
        if y in flashes:
            f, v, w = flashes[y]
            out.append([y, f"{100 * w[f].sum() / w[v].sum():.2f}", f"{np.mean(by[y]):.2f}", len(by[y])])
    return out


def main():
    ds = open_arco()
    jj, ii, lat, lon = land_points(ds)
    w = (np.cos(np.radians(lat[jj])) * (111.2 * STRIDE * 0.25) ** 2 / 1e6).astype("float64")   # million km² per point
    end = last_day(ds)
    print(f"{len(jj)} land points; ERA5 in ARCO through {end}", flush=True)
    if not os.path.exists(THR) or not os.path.exists(PCSV):
        P, t0 = {}, time.time()
        for y in range(FIRST, end.year + 1):
            P.update(to_pentads(read_days(ds, date(y, 1, 1), min(end, date(y, 12, 31)), jj, ii)))
            print(f"  {y}: {time.time() - t0:.0f} s", flush=True)
        M, Q20, Q40 = thresholds(P)
        np.savez_compressed(THR + ".tmp.npz", mean=np.round(M * 1e4).astype(np.int16), p20=np.round(Q20 * 1e4).astype(np.int16),
                            p40=np.round(Q40 * 1e4).astype(np.int16), jj=jj.astype(np.int16), ii=ii.astype(np.int16), stride=STRIDE)
        os.replace(THR + ".tmp.npz", THR)
        M, Q20, Q40 = M.round(4), Q20.round(4), Q40.round(4)     # the same rounding later runs read back
        rows, onset = rows_for(P, sorted(P), M, Q20, Q40, w)
        fl = {}
        for (y, k), (f, v) in onset.items():
            a = fl.setdefault(y, [np.zeros_like(f), np.zeros_like(v), w]); a[0] |= f; a[1] |= v
        prow = [rows[k] for k in sorted(rows)]
        write(PCSV, ["date", "drought", "flash", "anom", "land"], prow)
        np.savez_compressed("data/soil_flash_cur.npz", year=end.year, f=fl[end.year][0], v=fl[end.year][1])
        write(YCSV, ["year", "flash_area", "drought", "pentads"], yearly(prow, {y: tuple(v) for y, v in fl.items()}))
        print(f"{len(prow)} pentads, {prow[0][0]} to {prow[-1][0]}", flush=True)
        return
    z = np.load(THR)
    M, Q20, Q40 = z["mean"] / 1e4, z["p20"] / 1e4, z["p40"] / 1e4
    P = to_pentads(read_days(ds, end - timedelta(days=99), end, jj, ii))
    keys = sorted(P)[4:]
    rows, onset = rows_for(P, keys, M, Q20, Q40, w)
    old = {r[0]: r for r in csv.reader(open(PCSV)) if r and r[0][:1].isdigit()}
    old.update({r[0]: r for r in rows.values()})
    prow = [old[k] for k in sorted(old)]
    write(PCSV, ["date", "drought", "flash", "anom", "land"], prow)
    # the current year's flash-drought area: the union of onsets kept between runs (data/soil_flash_cur.npz),
    # plus the pentads recalculated now
    cur = end.year
    c = np.load("data/soil_flash_cur.npz") if os.path.exists("data/soil_flash_cur.npz") else None
    f0 = c["f"].copy() if c is not None and int(c["year"]) == cur else np.zeros(len(jj), bool)
    v0 = c["v"].copy() if c is not None and int(c["year"]) == cur else np.zeros(len(jj), bool)
    for (y, k), (f, v) in onset.items():
        if y == cur:
            f0 |= f; v0 |= v
    np.savez_compressed("data/soil_flash_cur.npz", year=cur, f=f0, v=v0)
    yr = {r[0]: r for r in csv.reader(open(YCSV)) if r and r[0][:1].isdigit()}
    n = sum(1 for r in prow if r[0][:4] == str(cur))
    mean_d = np.mean([float(r[1]) for r in prow if r[0][:4] == str(cur)])
    if v0.any():
        yr[str(cur)] = [str(cur), f"{100 * w[f0].sum() / w[v0].sum():.2f}", f"{mean_d:.2f}", str(n)]
    write(YCSV, ["year", "flash_area", "drought", "pentads"], [yr[k] for k in sorted(yr)])
    print(f"updated {len(rows)} pentads to {prow[-1][0]}; drought {prow[-1][1]}%", flush=True)


if __name__ == "__main__":
    main()
