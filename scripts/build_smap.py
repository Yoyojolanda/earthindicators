#!/usr/bin/env python3
"""Root-zone soil moisture from NASA's SMAP satellite (Level 4), as a check on ERA5 (water cycle page).

SMAP (since March 2015) measures the microwave glow of the top ~5 cm of soil. The Level-4 product (SPL4SMGP)
feeds those measurements into NASA's land model every 3 hours, which carries the information down to the root zone
(0-100 cm, the same depth as the ERA5 numbers on the page). So it is also a model estimate, but one steered by a
satellite that sees soil moisture directly, and independent of ERA5.

Read through NASA's OPeNDAP server, one 3-hourly field a day (10:30 UTC; root-zone moisture changes slowly), every
10th point of the 9 km EASE-Grid 2.0 (about a 90 km sample; that grid is equal-area, so no area weights are needed),
land between 60°S and 75°N where the top soil layer is not frozen. Needs an Earthdata login (~/.netrc).
  -> data/smap_rootzone_monthly.csv  month, rz (average root-zone soil moisture, m³/m³), days (days with data),
     points (average number of points that counted)
The first run reads every day since April 2015 (~4,000 small requests, in parallel); later runs read only the
newest 45 days.
"""
import csv, io, json, os, sys, time, urllib.request
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta

import numpy as np

SHORT = "SPL4SMGP"
OUT = "data/smap_rootzone_monthly.csv"
DAILY = "data/smap_rootzone_daily.csv"
STRIDE, HOUR = 10, "T103000"
THREADS = int(os.environ.get("SMAP_THREADS") or 6)
GRID = os.environ.get("SMAP_GRID")       # optional: every day's sampled grid, kept in GitHub's Actions cache


def granules(d0, d1):
    """{date: OPeNDAP url} for the 10:30 UTC granule of each day."""
    out, page = {}, 1
    while True:
        u = (f"https://cmr.earthdata.nasa.gov/search/granules.json?short_name={SHORT}&page_size=2000&page_num={page}"
             f"&temporal={d0}T00:00:00Z,{d1}T23:59:59Z&readable_granule_name=*{HOUR}*&options%5Breadable_granule_name%5D%5Bpattern%5D=true")
        g = json.loads(urllib.request.urlopen(u, timeout=120).read())["feed"]["entry"]
        for e in g:
            # the OPeNDAP address is built from the granule's own title: for older granules the link stored in CMR
            # points to a name that no longer exists (404)
            ops = [f"https://opendap.earthdata.nasa.gov/collections/{e['collection_concept_id']}/granules/{e['title']}"]
            if HOUR in e["title"]:
                st = e["title"].split("_")[4]
                d = date(int(st[:4]), int(st[4:6]), int(st[6:8]))
                # some days have an older and a reprocessed version (Vv8010 and Vv8012): keep the newest
                if d not in out or e["title"].split("_")[5] > out[d][1]:
                    out[d] = (ops[0], e["title"].split("_")[5])
        if len(g) < 2000:
            return {d: v[0] for d, v in out.items()}
        page += 1


GEO = {}


def read(url):
    import netCDF4
    for t in range(4):
        try:
            ds = netCDF4.Dataset(url)
            name = lambda key: next(k for k in ds.variables if k.endswith(key))
            if "lat" not in GEO:
                GEO["lat"] = np.asarray(ds.variables[name("cell_lat")][::STRIDE, ::STRIDE])
            rz = np.ma.filled(ds.variables[name("sm_rootzone")][..., ::STRIDE, ::STRIDE].astype("float32"), np.nan).squeeze()
            st = np.ma.filled(ds.variables[name("soil_temp_layer1")][..., ::STRIDE, ::STRIDE].astype("float32"), np.nan).squeeze()
            ds.close()
            return rz, st
        except Exception as e:
            if t == 3 or "does not identify a granule" in str(e) or "404" in str(e):
                print(f"  failed {url.rsplit('/', 1)[-1]}: {str(e)[:200]}", flush=True)
                return None
            time.sleep(10 * (t + 1))


def day_value(r):
    rz, st = r
    lat = GEO["lat"]
    ok = np.isfinite(rz) & (rz >= 0) & (rz <= 1) & np.isfinite(st) & (st > 273.15) & (lat >= -60) & (lat <= 75)
    return (float(rz[ok].mean()), int(ok.sum())) if ok.sum() > 1000 else None


def one_day(url):
    """(global value or None, root-zone grid as float16, soil temperature in whole °C as int8) for one day."""
    r = read(url)
    if r is None:
        return None
    rz, st = r
    return day_value(r), rz.astype(np.float16), np.clip(np.nan_to_num(np.round(st - 273.15), nan=-128), -128, 127).astype(np.int8)


def cache_load():
    """{date: (rz, st)} from the grid cache (one file a year), and the grid's latitudes."""
    out = {}
    if not GRID or not os.path.isdir(GRID):
        return out, None
    lat = np.load(os.path.join(GRID, "lat.npy")) if os.path.exists(os.path.join(GRID, "lat.npy")) else None
    for f in sorted(os.listdir(GRID)):
        if f.endswith(".npz") and f[:4].isdigit():
            z = np.load(os.path.join(GRID, f))
            ds, rz, st = z["dates"], z["rz"], z["st"]          # read each array once (indexing the npz re-reads it)
            for k, d in enumerate(ds):
                out[date.fromisoformat(str(d))] = (rz[k], st[k])
    return out, lat


def cache_save(grids):
    os.makedirs(GRID, exist_ok=True)
    if "lat" in GEO:
        np.save(os.path.join(GRID, "lat.npy"), GEO["lat"])
    for y in sorted({d.year for d in grids}):
        ds = sorted(d for d in grids if d.year == y)
        np.savez_compressed(os.path.join(GRID, f"{y}.tmp.npz"), dates=np.array([d.isoformat() for d in ds]),
                            rz=np.stack([grids[d][0] for d in ds]), st=np.stack([grids[d][1] for d in ds]))
        os.replace(os.path.join(GRID, f"{y}.tmp.npz"), os.path.join(GRID, f"{y}.npz"))


def save(daily):
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(["date", "rz", "points"])
    for k in sorted(daily):
        w.writerow([k, f"{daily[k][0]:.5f}", daily[k][1]])
    open(DAILY + ".tmp", "w").write(buf.getvalue()); os.replace(DAILY + ".tmp", DAILY)
    by = {}
    for k, (v, n) in daily.items():
        by.setdefault(k[:7], []).append((v, n))
    rows = [[m, f"{np.mean([x[0] for x in by[m]]):.5f}", len(by[m]), f"{np.mean([x[1] for x in by[m]]):.0f}"] for m in sorted(by) if len(by[m]) >= 20]
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(["month", "rz", "days", "points"]); w.writerows(rows)
    open(OUT + ".tmp", "w").write(buf.getvalue()); os.replace(OUT + ".tmp", OUT)
    return rows


def main():
    today = date.today()
    budget = float(os.environ.get("SMAP_BUDGET_MIN") or 150) * 60     # stop in time and save; the next run continues
    daily = {}
    if os.path.exists(DAILY):
        daily = {r[0]: (float(r[1]), int(r[2])) for r in csv.reader(open(DAILY)) if r and r[0][:1].isdigit()}
    grids, lat = cache_load()
    if lat is not None:
        GEO["lat"] = lat
    recent = date.fromisoformat(max(daily)) - timedelta(days=44) if daily else date(2015, 4, 1)
    G = granules(date(2015, 4, 1) if GRID else recent, today)
    # the newest 45 days always (preliminary values get updated), and any day missing from the grid cache
    todo = sorted(d for d in G if d >= recent or (GRID and d not in grids) or d.isoformat() not in daily)
    print(f"{len(G)} granules; {len(todo)} to read; {len(grids)} days in the grid cache", flush=True)
    if GRID and "lat" not in GEO and G:
        read(G[max(G)])                             # the grid's latitudes, from one granule
    t0, n = time.time(), 0
    # separate processes, not threads: the netCDF/HDF5 library crashes when several threads use it at once.
    # Days come back in date order; progress is saved every 100 days, so a stopped run loses little.
    import multiprocessing
    with ProcessPoolExecutor(THREADS, mp_context=multiprocessing.get_context("spawn")) as ex:
        for d, r in zip(todo, ex.map(one_day, [G[d] for d in todo], chunksize=4)):
            n += 1
            if r is not None:
                v, rz, st = r
                if v:
                    daily[d.isoformat()] = v
                if GRID:
                    grids[d] = (rz, st)
            if n % 100 == 0:
                save(daily)
                if GRID:
                    cache_save({q: v for q, v in grids.items() if q.year == d.year or q.year == d.year - 1})
                print(f"  {d}: {n} of {len(todo)}, {time.time() - t0:.0f} s", flush=True)
            if time.time() - t0 > budget:
                print(f"  time budget reached at {d}; the next run continues from here", flush=True)
                ex.shutdown(wait=False, cancel_futures=True)
                break
    if len(daily) < 30:
        sys.exit("too few days")
    rows = save(daily)
    if GRID:
        cache_save(grids)
    print(f"{len(daily)} days; {len(rows)} months, {rows[0][0]} to {rows[-1][0]}; last {rows[-1][1]}", flush=True)


if __name__ == "__main__":
    main()
