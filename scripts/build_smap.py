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
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np

SHORT = "SPL4SMGP"
OUT = "data/smap_rootzone_monthly.csv"
DAILY = "data/smap_rootzone_daily.csv"
STRIDE, HOUR = 10, "T103000"
THREADS = int(os.environ.get("SMAP_THREADS") or 6)


def granules(d0, d1):
    """{date: OPeNDAP url} for the 10:30 UTC granule of each day."""
    out, page = {}, 1
    while True:
        u = (f"https://cmr.earthdata.nasa.gov/search/granules.json?short_name={SHORT}&page_size=2000&page_num={page}"
             f"&temporal={d0}T00:00:00Z,{d1}T23:59:59Z&readable_granule_name=*{HOUR}*&options%5Breadable_granule_name%5D%5Bpattern%5D=true")
        g = json.loads(urllib.request.urlopen(u, timeout=120).read())["feed"]["entry"]
        for e in g:
            ops = [l["href"] for l in e.get("links", []) if "opendap.earthdata.nasa.gov" in l.get("href", "")]
            if ops and HOUR in e["title"]:
                d = date.fromisoformat(e["title"].split("_")[4][:8][:4] + "-" + e["title"].split("_")[4][4:6] + "-" + e["title"].split("_")[4][6:8])
                out[d] = ops[0]
        if len(g) < 2000:
            return out
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
            if t == 3:
                print(f"  failed {url.rsplit('/', 1)[-1]}: {e}", flush=True)
                return None
            time.sleep(10 * (t + 1))


def day_value(r):
    rz, st = r
    lat = GEO["lat"]
    ok = np.isfinite(rz) & (rz >= 0) & (rz <= 1) & np.isfinite(st) & (st > 273.15) & (lat >= -60) & (lat <= 75)
    return (float(rz[ok].mean()), int(ok.sum())) if ok.sum() > 1000 else None


def main():
    today = date.today()
    daily = {}
    if os.path.exists(DAILY):
        daily = {r[0]: (float(r[1]), int(r[2])) for r in csv.reader(open(DAILY)) if r and r[0][:1].isdigit()}
    start = date.fromisoformat(max(daily)) - timedelta(days=44) if daily else date(2015, 4, 1)
    G = granules(start, today)
    print(f"{len(G)} granules from {start}", flush=True)
    todo = sorted(G)
    t0 = time.time()
    with ThreadPoolExecutor(THREADS) as ex:
        for d, r in zip(todo, ex.map(lambda d: read(G[d]), todo)):
            if r is not None:
                v = day_value(r)
                if v:
                    daily[d.isoformat()] = v
            if len(daily) % 200 == 0:
                print(f"  {d}: {time.time() - t0:.0f} s", flush=True)
    if len(daily) < 30:
        sys.exit("too few days")
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
    print(f"{len(daily)} days; {len(rows)} months, {rows[0][0]} to {rows[-1][0]}; last {rows[-1][1]}", flush=True)


if __name__ == "__main__":
    main()
