#!/usr/bin/env python3
"""Build a Climate-Reanalyzer-style Nino 3.4 daily SST JSON from NOAA OISST v2.1.

The box defaults to Nino 3.4; --lat/--lon/--stride let the same script build other regions
(e.g. world 60S-60N with --lat -60 60 --lon 0 360 --stride 4). Defaults leave Nino 3.4 unchanged.

Source: NOAA PSL OPeNDAP (yearly files, subset to the Nino 3.4 box only). If PSL fails (it sometimes answers
429 Too Many Requests, or 503 during maintenance), the same days are read from NCEI's daily files instead: NCEI is the original distributor
of OISST v2.1 and PSL repackages its files, on the same 0.25-degree grid.
Output: list of {"name": "<year>", "data": [366 values by day-of-year]} plus
        {"name": "1991-2020", "data": [...]} (day-of-year mean, 5-day circular smoothing).
"""
import argparse, calendar, csv, json, os, re, sys, time, urllib.request
from datetime import date, timedelta

import numpy as np

URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.day.mean.{year}.nc"
LAT, LON = (-5.0, 5.0), (190.0, 240.0)   # 5S-5N, 170W-120W (degrees east)
CLIM = (1991, 2020)
# Once PSL refuses (429 too many requests, 5xx down for maintenance), later runs of this script in the same job
# leave it alone and go straight to NCEI.
BUSY_FLAG = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "psl_busy")
SERVER_DOWN = False
# Signs that the server refused rather than the engine failing. netCDF4 reports a 429 only as "Access failure" and
# a 503 as "DAP server error" (it tries to read the HTML error page as data); pydap names the status code.
REFUSED = ("429", "Too Many Requests", "Access failure", "DAP server error", "Service Unavailable",
           "500", "502", "503", "504", "<html", "<!DOCTYPE")


def refused(e):
    return any(k in str(e) for k in REFUSED)


# Series whose output was rebuilt within this many hours are skipped, so re-running a failed job only redoes
# the series that failed. Scheduled runs are 12 hours apart, so they never skip.
STATE = "data/sst_fetch_state.json"

# Fallback source: one global file per day (~1.6 MB), "_preliminary" in the name until the final version replaces it.
NCEI = "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2.1/access/avhrr/"
NCEI_DIR = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "ncei_oisst")   # shared by every series in a run
_listings = {}


def _get(url, path=None):
    req = urllib.request.Request(url, headers={"User-Agent": "earthindicators.org data update"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if path:
                with open(path + ".part", "wb") as fh:
                    fh.write(data)
                os.replace(path + ".part", path)
            return data
        except Exception as e:
            wait = 60 * 2 ** attempt if refused(e) else 8 * (attempt + 1)
            print(f"  NCEI {url.rsplit('/', 1)[-1] or url}: {e}; retry {attempt+1} in {wait} s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"NCEI download failed: {url}")


def _ncei_files(ym):
    """{date: file name} for one month folder, the final file where there is one, else the preliminary one."""
    if ym not in _listings:
        html = _get(NCEI + ym + "/").decode("utf-8", "replace")
        files = {}
        for fn, d, pre in re.findall(r'href="(oisst-avhrr-v02r01\.(\d{8})(_preliminary)?\.nc)"', html):
            day = date(int(d[:4]), int(d[4:6]), int(d[6:]))
            if day not in files or not pre:
                files[day] = fn
        _listings[ym] = files
    return _listings[ym]


def fetch_ncei(year, weighting, lat_box=LAT, lon_box=LON, stride=1, since=None, base=NCEI):
    import xarray as xr
    os.makedirs(NCEI_DIR, exist_ok=True)
    d, end, out = since or date(year, 1, 1), min(date(year, 12, 31), date.today()), {}
    while d <= end:
        fn = _ncei_files(f"{d.year}{d.month:02d}").get(d)
        if fn:
            path = os.path.join(NCEI_DIR, fn)
            if not os.path.exists(path):
                _get(base + f"{d.year}{d.month:02d}/" + fn, path)
            with xr.open_dataset(path) as ds:
                sst = ds["sst"].isel(time=0, zlev=0) if "zlev" in ds["sst"].dims else ds["sst"].isel(time=0)
                lat, lon = ds["lat"].values, ds["lon"].values
                li = np.where((lat >= lat_box[0]) & (lat <= lat_box[1]))[0]
                lo = np.where((lon >= lon_box[0]) & (lon <= lon_box[1]))[0]
                sub = sst.isel(lat=slice(li.min(), li.max() + 1, stride), lon=slice(lo.min(), lo.max() + 1, stride)).load()
            m = sub.weighted(np.cos(np.deg2rad(sub["lat"]))).mean(("lat", "lon")) if weighting == "cos" else sub.mean(("lat", "lon"))
            if np.isfinite(float(m)):
                out[d] = float(m)
        d += timedelta(days=1)
    return out


def _open(url, engine):
    import xarray as xr
    for attempt in range(4):
        try:
            return xr.open_dataset(url, engine=engine)
        except Exception as e:
            # a refusing server (429 busy, 5xx down): back off for a minute, not seconds
            global SERVER_DOWN
            SERVER_DOWN = SERVER_DOWN or refused(e)
            if SERVER_DOWN and attempt >= 1:   # still refusing after a minute's pause: let the caller switch to NCEI
                break
            wait = 60 * 2 ** attempt if refused(e) else 8 * (attempt + 1)
            print(f"  [{engine}] open failed ({e}); retry {attempt+1} in {wait} s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"could not open {url} with {engine}")


def _load(piece):
    for attempt in range(4):
        try:
            return piece.load()
        except Exception as e:
            wait = 60 * 2 ** attempt if refused(e) else 8 * (attempt + 1)
            print(f"    chunk failed ({e}); retry {attempt+1} in {wait} s", flush=True)
            time.sleep(wait)
    raise RuntimeError("chunk failed after retries")


def _fetch_year_engine(url, weighting, engine, chunk=30, lat_box=LAT, lon_box=LON, stride=1, since=None, out=None):
    """Fills `out` chunk by chunk, so the days already read survive if a later chunk fails."""
    ds = _open(url, engine)
    lat, lon = ds["lat"].values, ds["lon"].values
    li = np.where((lat >= lat_box[0]) & (lat <= lat_box[1]))[0]
    lo = np.where((lon >= lon_box[0]) & (lon <= lon_box[1]))[0]
    # stride > 1 samples every n-th grid point (server-side), to keep large regions fast
    sst = ds["sst"].isel(lat=slice(li.min(), li.max() + 1, stride), lon=slice(lo.min(), lo.max() + 1, stride))
    if since is not None:   # only the days from `since` on (opening the file reads just its metadata)
        times = ds["time"].values.astype("datetime64[D]")
        sst = sst.isel(time=slice(int(np.searchsorted(times, np.datetime64(since))), None))
    out = {} if out is None else out
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


class PartialFetch(RuntimeError):
    """PSL failed partway; .got holds the days that did arrive."""
    def __init__(self, msg, got):
        super().__init__(msg); self.got = got


def fetch_year(year, weighting, url_template=URL, lat_box=LAT, lon_box=LON, stride=1, since=None):
    url = url_template.format(year=year)
    last, got = None, {}
    for engine in ("netcdf4", "pydap"):
        try:
            return _fetch_year_engine(url, weighting, engine, lat_box=lat_box, lon_box=lon_box, stride=stride,
                                      since=since, out=got)
        except Exception as e:
            last = e
            print(f"  engine {engine} failed for {year}: {e}", flush=True)
            if SERVER_DOWN:   # the server is refusing, not the engine: no point trying the other one
                break
            if got:           # the other engine picks up after the last day that arrived
                since = max(got) + timedelta(days=1)
    raise PartialFetch(f"all engines failed for {year}: {last}", got)


def load_state():
    try:
        with open(STATE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def mark_done(key, latest):
    st = load_state()
    st[key] = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "latest": latest.isoformat()}
    with open(STATE + ".part", "w") as fh:
        json.dump(st, fh, indent=1, sort_keys=True)
    os.replace(STATE + ".part", STATE)


def fresh(key, hours):
    """True if this series was rebuilt less than `hours` ago (by an earlier attempt of the same run)."""
    built = load_state().get(key, {}).get("built")
    if not built or hours <= 0:
        return False
    age = time.time() - calendar.timegm(time.strptime(built, "%Y-%m-%dT%H:%M:%SZ"))
    return age < hours * 3600


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
    ap.add_argument("--skip-if-fresh", type=float, default=float(os.environ.get("SKIP_HOURS", 3)), metavar="HOURS",
                    help="skip when this series was rebuilt less than HOURS ago (0 = never skip; default 3, "
                         "or $SKIP_HOURS)")
    a = ap.parse_args()
    key = os.path.basename(a.cache)
    if not a.full and fresh(key, a.skip_if_fresh):
        print(f"{key} was updated less than {a.skip_if_fresh:g} h ago; nothing to redo", flush=True)
        return
    psl_busy = os.path.exists(BUSY_FLAG)
    if psl_busy:
        print("PSL refused an earlier series in this run; using NCEI's daily files", flush=True)

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
        got, psl_ok = None, False
        if not psl_busy:
            try:
                got = fetch_year(y, a.weighting, a.url_template, tuple(a.lat), tuple(a.lon), a.stride, since=first)
                psl_ok = True
            except PartialFetch as e:
                print(f"    PSL failed ({e}); trying NCEI's daily files"
                      + (f" from {max(e.got) + timedelta(days=1)} ({len(e.got)} days kept from PSL)" if e.got else ""),
                      flush=True)
                if SERVER_DOWN:
                    open(BUSY_FLAG, "w").close(); psl_busy = True
                got = e.got or None
        if not psl_ok:
            # nothing, or only part, came from PSL: NCEI supplies the rest (days PSL did deliver are kept)
            start = max(got) + timedelta(days=1) if got else first
            got = {**(got or {}), **fetch_ncei(y, a.weighting, tuple(a.lat), tuple(a.lon), a.stride, since=start)}
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
    mark_done(key, max(daily))
    if a.compare and os.path.exists(a.compare):
        msg = compare(out, a.compare)
        print("  " + msg)
        if a.check_out:
            with open(a.check_out, "w") as fh:
                fh.write(msg + "\n")


if __name__ == "__main__":
    main()
