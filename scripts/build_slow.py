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
  fossil  Global Carbon Project fossil CO2 emissions (Andrew & Peters, Zenodo; the dataset behind the yearly Global
        Carbon Budget): the newest version's "MtCO2_flat" CSV, row "Global" (world total, including international
        shipping and aviation). Released once a year, in October-November.
        -> data/fossil_co2_global.csv  year, total, coal, oil, gas, cement, flaring, other (million tonnes CO2)
  ph    Hawaii Ocean Time-series (HOT), Station ALOHA (22.75N, 158W): surface (0-30 m) seawater pH, total scale,
        at in situ temperature, about monthly since 1988 (HOT_surface_CO2.txt, Dore et al. 2009, updated).
        -> data/hot_surface_ph.csv  date, ph_calc, ph_meas (calculated from DIC and alkalinity; measured directly)
  blossom  Kyoto cherry blossom: peak bloom date of the mountain cherry (Prunus jamasakura) at Arashiyama, from 812.
        Compiled by Yasuyuki Aono (Aono and Kazui 2008; Aono and Saito 2010; recent years from a local newspaper),
        as kept up to date by the George Mason University cherry blossom prediction competition on GitHub.
        -> data/kyoto_cherry_blossom.csv  year, date, doy (day of the year)
  crops FAOSTAT crops and livestock products (QCL), world yields of maize, wheat, rice and soybeans, tonnes per
        hectare, from 1961; released once a year (around December, for the year before last).
        -> data/fao_crop_yields_world.csv  year, maize, wheat, rice, soybeans
  trees Global Forest Watch / University of Maryland (Hansen et al.) annual tree cover loss by dominant driver, world,
        hectares at 30% canopy cover, from 2001; released once a year (spring). Taken from Our World in Data's copy,
        because GFW's own API needs a key and its download links change with each release.
        -> data/tree_cover_loss_world.csv  year, total, wildfire (hectares; OWID publishes the total and the wildfire
           part as separate charts)
"""
import csv, hashlib, io, json, os, sys, tempfile, urllib.request
from datetime import date, datetime, timedelta

STATUS = "data/slow_status.json"
AMOC_URL = "https://rapid.ac.uk/sites/default/files/rapid_data/moc_transports.nc"
FOSSIL_RECORD = "17417124"   # one known version (2025v15); its "concept" id leads to the newest version
HOT_URL = "https://hahana.soest.hawaii.edu/hot/hotco2/HOT_surface_CO2.txt"
BLOSSOM_URL = "https://raw.githubusercontent.com/GMU-CherryBlossomCompetition/peak-bloom-prediction/main/data/kyoto.csv"
FAO_URLS = ["https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip",
            "https://fenixservices.fao.org/faostat/static/bulkdownloads/Production_Crops_Livestock_E_All_Data_(Normalized).zip"]
TREES_URL = "https://ourworldindata.org/grapher/tree-cover-loss.csv?v=1&csvType=full&useColumnShortNames=false"
FIRE_URL = "https://ourworldindata.org/grapher/tree-cover-loss-from-wildfires.csv?v=1&csvType=full&useColumnShortNames=false"
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


def fossil():
    known = json.loads(get(f"https://zenodo.org/api/records/{FOSSIL_RECORD}"))
    concept = known.get("conceptrecid") or known.get("parent", {}).get("id")
    try:
        rec = json.loads(get(f"https://zenodo.org/api/records/{concept}/versions/latest"))
    except Exception as e:
        print(f"  fossil: newest version not found ({e}); using {FOSSIL_RECORD}", flush=True); rec = known
    title = rec.get("metadata", {}).get("title", "")
    if "fossil" not in title.lower():
        raise RuntimeError(f"newest version is not the fossil CO2 dataset: {title!r}")
    files = rec.get("files") or []
    if isinstance(files, dict):
        files = list((files.get("entries") or {}).values())
    keys = [f.get("key") or f.get("filename") for f in files]
    key = next((k for k in keys if k and "mtco2" in k.lower() and "flat" in k.lower() and k.lower().endswith(".csv")), None)
    print(f"  fossil: Zenodo record {rec.get('id')} (concept {concept}), {title!r}, version {rec.get('metadata', {}).get('version')}; files {keys}", flush=True)
    if not key:
        raise RuntimeError("no *_MtCO2_flat.csv in the newest version")
    raw = get(f"https://zenodo.org/records/{rec['id']}/files/{key}?download=1", 300).decode("utf-8-sig")
    rd = csv.DictReader(io.StringIO(raw))
    print(f"  fossil: columns {rd.fieldnames}", flush=True)
    iso = next((c for c in rd.fieldnames if c.lower().startswith("iso")), None)
    cols = ["Total", "Coal", "Oil", "Gas", "Cement", "Flaring", "Other"]
    num = lambda v: f"{float(v):.1f}" if v not in (None, "", "NA") else ""
    rows = [[int(r["Year"])] + [num(r.get(c)) for c in cols] for r in rd
            if r.get("Country") == "Global" or (iso and r.get(iso) == "WLD")]
    rows = sorted(r for r in rows if r[1])
    if len(rows) < 200 or not (30000 < float(rows[-1][1]) < 50000):
        raise RuntimeError(f"incomplete or implausible: {len(rows)} years, last {rows[-1] if rows else None}")
    print(f"  fossil: {len(rows)} years, {rows[0][0]} to {rows[-1][0]}, latest {rows[-1][1]} Mt CO2", flush=True)
    write_csv("data/fossil_co2_global.csv", ["year", "total", "coal", "oil", "gas", "cement", "flaring", "other"], rows)
    return {"through": str(rows[-1][0]), "first": str(rows[0][0]), "version": str(rec.get("metadata", {}).get("version")),
            "source": f"https://doi.org/10.5281/zenodo.{rec['id']}", "file": key}


def ph():
    txt = get(HOT_URL).decode("latin-1")
    lines = [l.rstrip("\r") for l in txt.split("\n")]
    hi = next(i for i, l in enumerate(lines) if "date" in l.lower() and "ph" in l.lower())
    head = [h.strip() for h in lines[hi].split("\t")]
    print(f"  ph: columns {head}", flush=True)
    low = [h.lower().replace(" ", "") for h in head]
    find = lambda *w: next((i for i, h in enumerate(low) if all(x in h for x in w)), None)
    di, ci, mi = find("date"), find("ph", "calc", "insitu"), find("ph", "meas", "insitu")
    if di is None or ci is None:
        raise RuntimeError("date or calculated in situ pH column not found")
    def val(p, i):
        try:
            v = float(p[i]) if i is not None and i < len(p) else None
        except ValueError:
            return ""
        return f"{v:.4f}" if v is not None and 7.6 < v < 8.4 else ""
    ki = find("days")
    def when(p):
        d = p[di]
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y", "%m%d%y"):
            try:
                return datetime.strptime(d.zfill(6) if fmt == "%m%d%y" else d, fmt).date().isoformat()
            except ValueError:
                continue
        try:                                   # "days": days since 1 October 1988, the start of HOT
            return (date(1988, 10, 1) + timedelta(days=float(p[ki]))).isoformat() if ki is not None else None
        except (ValueError, IndexError):
            return None
    data = [l for l in lines[hi + 1:] if l.strip()]
    print(f"  ph: first data lines {data[:3]}", flush=True)
    rows = []
    for l in data:
        p = [x.strip() for x in l.split("\t")]
        if len(p) <= max(di, ci):
            continue
        d = when(p)
        if not d or not "1988" <= d[:4] <= str(date.today().year):
            continue
        c, m = val(p, ci), val(p, mi)
        if c or m:
            rows.append([d, c, m])
    rows.sort()
    if len(rows) < 200:
        raise RuntimeError(f"only {len(rows)} usable rows")
    print(f"  ph: {len(rows)} cruises, {rows[0][0]} to {rows[-1][0]}; last {rows[-1]}", flush=True)
    write_csv("data/hot_surface_ph.csv", ["date", "ph_calc", "ph_meas"], rows)
    return {"through": rows[-1][0][:7], "first": rows[0][0][:7], "source": HOT_URL}


def blossom():
    rows = []
    for r in csv.DictReader(io.StringIO(get(BLOSSOM_URL).decode("utf-8-sig"))):
        try:
            y, d, n = int(r["year"]), r["bloom_date"].strip(), int(float(r["bloom_doy"]))
        except (KeyError, ValueError):
            continue
        if 60 <= n <= 140:
            rows.append([y, d, n])
    rows.sort()
    if len(rows) < 700 or rows[0][0] > 900:
        raise RuntimeError(f"incomplete: {len(rows)} years")
    print(f"  blossom: {len(rows)} years, {rows[0][0]} to {rows[-1][0]}; last {rows[-1]}", flush=True)
    write_csv("data/kyoto_cherry_blossom.csv", ["year", "date", "doy"], rows)
    return {"through": str(rows[-1][0]), "first": str(rows[0][0]), "source": BLOSSOM_URL}


def crops():
    import zipfile
    raw, used = None, None
    for u in FAO_URLS:
        try:
            raw, used = get(u, 600), u; break
        except Exception as e:
            print(f"  crops: {u} failed ({e})", flush=True)
    if raw is None:
        raise RuntimeError("no FAOSTAT download worked")
    z = zipfile.ZipFile(io.BytesIO(raw))
    name = next(n for n in z.namelist() if n.lower().endswith(".csv") and "all_data" in n.lower())
    print(f"  crops: {len(raw):,} bytes from {used}; reading {name}", flush=True)
    want = {"maize": ("maize (corn)", "maize"), "wheat": ("wheat",), "rice": ("rice", "rice, paddy"), "soybeans": ("soya beans", "soybeans")}
    vals, units = {}, set()
    with z.open(name) as fh:
        rd = csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"))
        for r in rd:
            if r.get("Area") != "World" or r.get("Element") != "Yield":
                continue
            item = r.get("Item", "").lower()
            crop = next((k for k, keys in want.items() if item in keys), None)     # exact names: not "Maize, green"
            if not crop:
                continue
            u = r.get("Unit", "").lower(); units.add(u)
            f = {"kg/ha": 1e-3, "hg/ha": 1e-4, "t/ha": 1.0, "100 g/ha": 1e-4}.get(u)
            if f is None or not r.get("Value"):
                continue
            vals.setdefault(int(r["Year"]), {})[crop] = float(r["Value"]) * f
    print(f"  crops: units {units}", flush=True)
    rows = [[y] + [f"{vals[y][c]:.3f}" if c in vals[y] else "" for c in want] for y in sorted(vals)]
    if len(rows) < 55 or not all(rows[-1][1:]) or not (3 < float(rows[-1][1]) < 10):
        raise RuntimeError(f"incomplete or implausible: {len(rows)} years, last {rows[-1] if rows else None}")
    print(f"  crops: {len(rows)} years, {rows[0][0]} to {rows[-1][0]}; last {rows[-1]} t/ha", flush=True)
    write_csv("data/fao_crop_yields_world.csv", ["year", *want], rows)
    return {"through": str(rows[-1][0]), "first": str(rows[0][0]), "source": used}


def owid_world(url, tag):
    """{year: value} for the World row of a one-indicator Our World in Data chart."""
    rd = csv.DictReader(io.StringIO(get(url).decode("utf-8-sig")))
    cols = [c for c in rd.fieldnames if c not in ("Entity", "Code", "Year", "World region according to OWID")]
    print(f"  trees: {tag} columns {rd.fieldnames}", flush=True)
    out = {}
    for r in rd:
        if r.get("Entity") == "World" and r.get(cols[0]) not in (None, ""):
            out[int(r["Year"])] = float(r[cols[0]])
    return out


def trees():
    tot = owid_world(TREES_URL, "total")
    try:
        fire = owid_world(FIRE_URL, "wildfire")
    except Exception as e:
        print(f"  trees: wildfire part not available ({e})", flush=True); fire = {}
    rows = [[y, f"{tot[y]:.0f}", f"{fire[y]:.0f}" if y in fire else ""] for y in sorted(tot)]
    if len(rows) < 20 or not (5e6 < tot[max(tot)] < 1e8):
        raise RuntimeError(f"incomplete or implausible: {len(rows)} years")
    print(f"  trees: {len(rows)} years, {rows[0][0]} to {rows[-1][0]}; last {rows[-1]} ha", flush=True)
    write_csv("data/tree_cover_loss_world.csv", ["year", "total", "wildfire"], rows)
    return {"through": str(rows[-1][0]), "first": str(rows[0][0]), "source": "Global Forest Watch, via Our World in Data"}


def main():
    os.makedirs("data", exist_ok=True)
    status = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    files = {"amoc": "data/amoc_rapid_monthly.csv", "rli": "data/redlist_index_world.csv",
             "fossil": "data/fossil_co2_global.csv", "ph": "data/hot_surface_ph.csv",
             "blossom": "data/kyoto_cherry_blossom.csv", "crops": "data/fao_crop_yields_world.csv", "trees": "data/tree_cover_loss_world.csv"}
    failed = []
    for key, fn in (("amoc", amoc), ("rli", rli), ("fossil", fossil), ("ph", ph),
                    ("blossom", blossom), ("crops", crops), ("trees", trees)):
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
    return 1 if len(failed) == len(files) else 0


if __name__ == "__main__":
    sys.exit(main())
