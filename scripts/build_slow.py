#!/usr/bin/env python3
"""Slow signals: indicators that are published once a year or less often.

Each source is downloaded, checked and saved on its own, so one failing source never blocks the others, and a
failed or incomplete download never replaces good data. data/slow_status.json records, per indicator, how far the
data reach, where they came from and the date new data last arrived (a change in the content, not just a new download).

  amoc  RAPID 26N AMOC array (rapid.ac.uk): moc_transports.nc, twice-daily transports in Sverdrup (1 Sv =
        1 million m3/s), published every 1-2 years after the moorings are recovered.
        -> data/amoc_rapid_monthly.csv  month, moc_sv, florida_sv, ekman_sv, umo_sv (monthly means of daily means;
           months with fewer than 20 days of data are left out)
  rli   Red List Index (IUCN / BirdLife International) for the world, from the UN SDG database (series ER_RSK_LST,
        indicator 15.5.1); updated once a year.
        -> data/redlist_index_world.csv  year, value, lower, upper (lower/upper: the published uncertainty bounds)
"""
import csv, hashlib, io, json, os, sys, tempfile, urllib.request
from datetime import date

STATUS = "data/slow_status.json"
AMOC_URL = "https://rapid.ac.uk/sites/default/files/rapid_data/moc_transports.nc"
RLI_URL = "https://unstats.un.org/SDGAPI/v1/sdg/Series/Data?seriesCode=ER_RSK_LST&areaCode=1&pageSize=1000"


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "earthindicators.org data update (GitHub Actions)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def write_csv(path, header, rows):
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(header); w.writerows(rows)
    new = buf.getvalue()
    old = open(path).read() if os.path.exists(path) else None
    if new != old:
        with open(path + ".tmp", "w") as fh:
            fh.write(new)
        os.replace(path + ".tmp", path)
    return new != old


def amoc():
    import numpy as np, xarray as xr
    raw = get(AMOC_URL, 300)
    path = os.path.join(tempfile.mkdtemp(), "moc.nc")
    open(path, "wb").write(raw)
    ds = xr.open_dataset(path)
    print(f"  amoc: {len(raw):,} bytes; variables {list(ds.data_vars)}", flush=True)
    pick = lambda pre: next(v for v in ds.data_vars if v.startswith(pre))
    names = {"moc_sv": pick("moc_mar_hc"), "florida_sv": pick("t_gs"), "ekman_sv": pick("t_ek"), "umo_sv": pick("t_umo")}
    tdim = ds[names["moc_sv"]].dims[0]
    daily = ds[list(names.values())].resample({tdim: "1D"}).mean()
    n = daily[names["moc_sv"]].resample({tdim: "MS"}).count()
    monthly = daily.resample({tdim: "MS"}).mean().where(n >= 20, drop=True)
    rows = [[str(t)[:7]] + [f"{float(monthly[v].sel({tdim: t})):.2f}" for v in names.values()] for t in monthly[tdim].values]
    if len(rows) < 200:
        raise RuntimeError(f"only {len(rows)} months")
    m = np.array([float(r[1]) for r in rows])
    if not (5 < m.mean() < 30):
        raise RuntimeError(f"implausible mean AMOC {m.mean():.1f} Sv")
    version = {k: str(v) for k, v in ds.attrs.items() if any(s in k.lower() for s in ("version", "title", "date"))}
    print(f"  amoc: {len(rows)} months, {rows[0][0]} to {rows[-1][0]}, mean {m.mean():.1f} Sv; {version}", flush=True)
    write_csv("data/amoc_rapid_monthly.csv", ["month", *names], rows)
    return {"through": rows[-1][0], "first": rows[0][0], "source": AMOC_URL, "version": version}


def rli():
    js = json.loads(get(RLI_URL))
    data = js.get("data", [])
    print(f"  rli: {len(data)} records; dimensions seen: "
          f"{sorted({k + '=' + str(v) for d in data for k, v in (d.get('dimensions') or {}).items()})[:12]}", flush=True)
    by = {}
    for d in data:
        if str(d.get("geoAreaCode")) != "1" or d.get("value") in (None, "", "NaN"):
            continue
        b = (d.get("dimensions") or {}).get("Bounds", "MP")
        by.setdefault(int(float(d["timePeriodStart"])), {})[b] = float(d["value"])
    rows = [[y, f"{v['MP']:.4f}", f"{v['LB']:.4f}" if "LB" in v else "", f"{v['UB']:.4f}" if "UB" in v else ""]
            for y, v in sorted(by.items()) if "MP" in v]
    if len(rows) < 20 or not all(0 < float(r[1]) <= 1 for r in rows):
        raise RuntimeError(f"incomplete or implausible: {len(rows)} years")
    print(f"  rli: {len(rows)} years, {rows[0][0]} to {rows[-1][0]}, latest {rows[-1][1]}", flush=True)
    write_csv("data/redlist_index_world.csv", ["year", "value", "lower", "upper"], rows)
    return {"through": str(rows[-1][0]), "first": str(rows[0][0]), "source": "UN SDG database, series ER_RSK_LST (indicator 15.5.1)"}


def main():
    os.makedirs("data", exist_ok=True)
    status = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    files = {"amoc": "data/amoc_rapid_monthly.csv", "rli": "data/redlist_index_world.csv"}
    failed = []
    for key, fn in (("amoc", amoc), ("rli", rli)):
        before = hashlib.sha1(open(files[key], "rb").read()).hexdigest() if os.path.exists(files[key]) else None
        try:
            info = fn()
        except Exception as e:
            print(f"::warning::{key}: not updated ({str(e)[:300]})", flush=True); failed.append(key); continue
        after = hashlib.sha1(open(files[key], "rb").read()).hexdigest()
        old = status.get(key, {})
        info["new_data"] = date.today().isoformat() if after != before else old.get("new_data", date.today().isoformat())
        status[key] = info
    with open(STATUS + ".tmp", "w") as fh:
        json.dump(status, fh, indent=1, sort_keys=True)
    os.replace(STATUS + ".tmp", STATUS)
    return 1 if len(failed) == 2 else 0


if __name__ == "__main__":
    sys.exit(main())
