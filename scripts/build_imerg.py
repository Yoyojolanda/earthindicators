#!/usr/bin/env python3
"""Extreme rainfall from NASA's IMERG satellite rainfall (water cycle page).

IMERG (Integrated Multi-satellitE Retrievals for GPM, version 07) combines the microwave and infrared measurements of
a whole fleet of satellites, calibrated by the GPM Core Observatory and, in the research-quality "Final" run, by rain
gauges, into rainfall every half hour on a 0.1° grid, since 1998. The daily product is used here:
  Final (GPM_3IMERGDF): with gauge calibration, published about 3.5 months or more after the month
  Late  (GPM_3IMERGDL): about 14 hours after the day, without gauges; used for the days Final does not cover yet,
                        and those days are marked as preliminary (replaced by Final when it arrives)

Read through NASA's OPeNDAP server (DAP4), every 10th grid point (a 1° sample of individual 0.1° cells, ~115 kB a day;
sampling, not averaging, keeps the rainfall of real places, so heavy downpours are not smoothed away), land between
60°S and 60°N (Natural Earth outline, data/land_110m.json). Needs an Earthdata login (~/.netrc).

Per land point:
  rx1   the wettest day of the year (mm), compared with the point's own 2001-2020 average wettest day, in %
  r99   the share of the year's rain that fell on very wet days: days wetter than the point's 99th percentile of wet
        days (at least 1 mm) in 2001-2020 (the ETCCDI index R99pTOT, as a share of the yearly total)
Averaged over the land (weighted by area).
  -> data/imerg_yearly.csv  year, rx1 (%), r99 (%), days, late (days from the Late run, preliminary)
Every day since 1998 is kept, as 1° land samples, in GitHub's Actions cache (IMERG_CACHE), not in the repository; if
the cache is gone, the first run reads 1998 to now again (~10,000 small requests, in parallel).
"""
import csv, io, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import requests

STRIDE = 10
BASE = (2001, 2020)
CACHE = os.environ.get("IMERG_CACHE") or os.path.expanduser("~/imergcache")
OUT = "data/imerg_yearly.csv"
THREADS = int(os.environ.get("IMERG_THREADS") or 8)
S = requests.Session()
import threading
LOCK = threading.Lock()


def land_points():
    from matplotlib.path import Path
    lon = -179.95 + STRIDE * 0.1 * np.arange(3600 // STRIDE)
    lat = -89.95 + STRIDE * 0.1 * np.arange(1800 // STRIDE)
    LO, LA = np.meshgrid(lon, lat, indexing="ij")          # IMERG is (lon, lat)
    P = np.column_stack([LO.ravel(), LA.ravel()])
    inside = np.zeros(len(P), bool)
    for r in json.load(open("data/land_110m.json"))["rings"]:
        ring = np.array(r).reshape(-1, 2)
        for sh in (-360, 0, 360):
            inside |= Path(ring + [sh, 0]).contains_points(P)
    inside = inside.reshape(LO.shape) & (np.abs(LA) <= 60)
    ii, jj = np.where(inside)
    return ii, jj, lat[jj]


def cmr_urls(short, d0, d1):
    out, page = {}, 1
    while True:
        u = (f"https://cmr.earthdata.nasa.gov/search/granules.json?short_name={short}&page_size=2000&page_num={page}"
             f"&temporal={d0}T00:00:00Z,{d1}T23:59:59Z")
        g = requests.get(u, timeout=120).json()["feed"]["entry"]
        for e in g:
            ops = [l["href"] for l in e.get("links", []) if "opendap.earthdata.nasa.gov" in l.get("href", "")]
            if ops:
                out[date.fromisoformat(e["time_start"][:10])] = ops[0]
        if len(g) < 2000:
            return out
        page += 1


def fetch(url, ii, jj):
    import netCDF4
    ce = requests.utils.quote(f"/precipitation[0][0:{STRIDE}:3599][0:{STRIDE}:1799]", safe="/[]:")
    for t in range(5):
        try:
            r = S.get(url + ".dap.nc4?dap4.ce=" + ce, timeout=180)
            r.raise_for_status()
            with LOCK:                                  # the netCDF library is not thread-safe: downloads run in
                ds = netCDF4.Dataset("mem.nc", memory=r.content)   # parallel, reading the bytes one at a time
                v = np.ma.filled(ds.variables["precipitation"][0].astype("float32"), np.nan)
                ds.close()
            return v[ii, jj]
        except Exception as e:
            if t == 4:
                print(f"  failed {url.rsplit('/', 1)[-1]}: {e}", flush=True)
                return None
            time.sleep(15 * (t + 1))


def load_year(y, n):
    p = os.path.join(CACHE, f"{y}.npz")
    if os.path.exists(p):
        z = np.load(p)
        if z["v"].shape[1] == n:
            return z["v"].astype("float32"), z["src"].copy()
    days = (date(y + 1, 1, 1) - date(y, 1, 1)).days
    return np.full((days, n), np.nan, "float32"), np.zeros(days, np.int8)     # src: 0 none, 1 Late, 2 Final


def save_year(y, v, src):
    np.savez_compressed(os.path.join(CACHE, f"{y}.npz.tmp.npz"), v=v.astype(np.float16), src=src)
    os.replace(os.path.join(CACHE, f"{y}.npz.tmp.npz"), os.path.join(CACHE, f"{y}.npz"))


def main():
    os.makedirs(CACHE, exist_ok=True)
    ii, jj, plat = land_points()
    n, w = len(ii), np.cos(np.radians(plat))
    print(f"{n} land points", flush=True)
    today = date.today()
    final_end = max(cmr_urls("GPM_3IMERGDF", today - timedelta(days=900), today) or {date(1997, 12, 31): None})
    print(f"Final run through {final_end}", flush=True)
    Y = {}
    t0 = time.time()
    for y in range(1998, today.year + 1):
        v, src = load_year(y, n)
        need_f = [d for d in (date(y, 1, 1) + timedelta(k) for k in range(len(src))) if d <= final_end and src[(d - date(y, 1, 1)).days] < 2]
        need_l = [d for d in (date(y, 1, 1) + timedelta(k) for k in range(len(src))) if final_end < d < today and src[(d - date(y, 1, 1)).days] < 1]
        if need_f or need_l:
            urls = {}
            if need_f:
                urls.update({d: (u, 2) for d, u in cmr_urls("GPM_3IMERGDF", min(need_f), max(need_f)).items() if d in set(need_f)})
            if need_l:
                urls.update({d: (u, 1) for d, u in cmr_urls("GPM_3IMERGDL", min(need_l), max(need_l)).items() if d in set(need_l)})
            ds_ = sorted(urls)
            with ThreadPoolExecutor(THREADS) as ex:
                for d, a in zip(ds_, ex.map(lambda d: fetch(urls[d][0], ii, jj), ds_)):
                    if a is not None:
                        k = (d - date(y, 1, 1)).days
                        v[k] = a; src[k] = urls[d][1]
            save_year(y, v, src)
            print(f"  {y}: {len(ds_)} days read, {time.time() - t0:.0f} s", flush=True)
        Y[y] = (v, src)
    # 2001-2020: each point's average wettest day and 99th percentile of wet days
    base = [y for y in range(BASE[0], BASE[1] + 1) if (Y[y][1] == 2).sum() >= 360]
    rx_base = np.nanmean(np.stack([np.nanmax(Y[y][0], axis=0) for y in base]), axis=0)
    wet = np.concatenate([Y[y][0] for y in base])
    wet = np.where(wet >= 1, wet, np.nan)
    p99 = np.nanpercentile(wet, 99, axis=0)
    ok = np.isfinite(rx_base) & (rx_base >= 5) & np.isfinite(p99)        # leave out the driest places (deserts)
    rows = []
    for y in sorted(Y):
        v, src = Y[y]
        days = int((src > 0).sum())
        if days < 30:
            continue
        rx = np.nanmax(v, axis=0)
        tot = np.nansum(v, axis=0)
        big = np.nansum(np.where(v > p99, v, 0), axis=0)
        m = ok & np.isfinite(rx) & (tot > 0)
        rx1 = float(np.sum(w[m] * (rx[m] / rx_base[m] - 1) * 100) / w[m].sum())
        r99 = float(np.sum(w[m] * big[m]) / np.sum(w[m] * tot[m]) * 100)          # share of all the land's rain
        rows.append([y, f"{rx1:.2f}", f"{r99:.2f}", days, int((src == 1).sum())])
    buf = io.StringIO(); wr = csv.writer(buf, lineterminator="\n"); wr.writerow(["year", "rx1", "r99", "days", "late"]); wr.writerows(rows)
    open(OUT + ".tmp", "w").write(buf.getvalue()); os.replace(OUT + ".tmp", OUT)
    print(f"{len(rows)} years; {int(ok.sum())} land points counted; last {rows[-1]}", flush=True)


if __name__ == "__main__":
    main()
