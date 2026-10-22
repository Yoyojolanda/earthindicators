#!/usr/bin/env python3
"""Permafrost, for the slow signals page: two measured records and one modelled one.

Each source is handled on its own, so one failing source never blocks the others, and a failed or incomplete download
never replaces good data. The status of each (how far the data reach, the date new data last arrived) is kept in
data/slow_status.json, next to the other slow signals (keys calm, permos, pfcci).

  calm   Circumpolar Active Layer Monitoring (CALM, George Washington University): the "CALM North summary table", end-of-
         season thaw depth (active-layer thickness) in cm per site and year, measured by probing grids and transects,
         thaw tubes, or inferred from borehole temperatures. Only the Arctic and subarctic lowland sites are used (north
         of 55°N). Each site is compared with its own 2001-2020 average, so sites with very different thaw depths can be
         averaged: the result is how much deeper (or shallower) than normal the ground thawed, in %.
         The table is a web page exported from Excel (one ~0.9 MB page), so it is cheap to re-read every week.
         -> data/permafrost_calm.csv  year, all, alaska, canada, nordic, russia (% deeper than each site's 2001-2020
            average; mean over the sites with data that year), n_all (number of sites), mean_cm (average thaw depth of
            those sites in their reference period, for everyday terms)
  permos Swiss Permafrost Monitoring Network (PERMOS), yearly data publication (zip, CC BY 4.0): ground temperature in
         boreholes in the Swiss Alps, averaged over hydrological years (October-September). For each borehole the
         sensor nearest to 10 m depth (8-12.5 m) is used, in boreholes with at least 15 such years and permafrost (not
         the Gemsstock crest, which has none): below the seasonal swings, so the yearly values show the
         slow warming. The zip (~40 MB) is only downloaded when PERMOS publishes a new one.
         -> data/permafrost_permos.csv  borehole, label, elevation, depth, year, temp
  pfcci  ESA Permafrost Climate Change Initiative (Permafrost_cci), ground temperature for the northern hemisphere,
         yearly means at 10 m depth (CRYOGRID model driven by MODIS land-surface temperature and downscaled ERA5,
         checked against boreholes), 0.01° grid. MODELLED, not measured: the page says so. Each year's file is ~360 MB,
         so the files are downloaded once and reduced here to a 0.5° grid; afterwards only new years (or a new version)
         are downloaded.
         -> data/permafrost_cci_grids.npz  every year's 0.5° grid (int16, 0.01 °C) and the per-year area statistics
            data/permafrost_cci.csv       year, mean_t10 (°C, average over the area that was permafrost in 1997-2006),
                                          area_pf (million km², ground at 10 m below 0 °C), area_warm (million km²,
                                          between -2 and 0 °C: permafrost close to thawing)
            data/permafrost_map.json      the latest year and its change since 1997-2006, for the map
"""
import csv, hashlib, io, json, math, os, re, sys, tempfile, urllib.request, zipfile
from datetime import date

STATUS = "data/slow_status.json"
UA = "earthindicators.org data update (GitHub Actions)"
CALM_URL = "https://www2.gwu.edu/~calm/data/north_files/sheet001.htm"
CALM_PAGE = "https://www2.gwu.edu/~calm/data/north.htm"
PERMOS_PAGE = "https://www.permos.ch/doi/permos-dataset-{y}-1"
CCI_BASE = "https://dap.ceda.ac.uk/neodc/esacci/permafrost/data/ground_temperature/L4/area4/pp/"
BASE_YEARS = (1997, 2006)          # reference decade for the modelled change and the permafrost area mask
STEP = 0.5                         # degrees, the reduced grid


def get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(url, path, timeout=900):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path, "wb") as fh:
        n = 0
        while True:
            b = r.read(1 << 22)
            if not b:
                break
            fh.write(b); n += len(b)
    return n


def write_text(path, text):
    old = open(path).read() if os.path.exists(path) else None
    if text != old:
        with open(path + ".tmp", "w") as fh:
            fh.write(text)
        os.replace(path + ".tmp", path)
    return text != old


def write_csv(path, header, rows):
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(header); w.writerows(rows)
    return write_text(path, buf.getvalue())


# ---------------------------------------------------------------- CALM: thaw depth, measured
def calm_region(lat, lon):
    if lat < 55:
        return None                                       # mountain sites (Tien Shan, Mongolia, Alps) left out
    if -170 < lon < -140.99:
        return "alaska"
    if -140.99 <= lon < -60:
        return "canada"
    if -60 <= lon < 40:
        return "nordic"                                   # Greenland, Svalbard, Scandinavia
    return "russia"                                       # incl. Chukotka west of 170°W


def calm_value(s):
    s = re.sub(r"\[[^\]]*\]", "", s).strip()
    if not s or s[0] in "<>-" or "inactive" in s.lower():
        return None
    s = s.replace("*", "").replace("?", "").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return v if 1 <= v <= 2000 else None


def calm():
    html = get(CALM_URL).decode("windows-1252", "replace")
    cell = lambda c: re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", c)).replace("\xa0", " ").strip()
    rows = [[cell(c) for c in re.findall(r"<td.*?</td>", r, re.S)] for r in re.findall(r"<tr.*?</tr>", html, re.S)]
    # the year header is the row that starts LAT, LONG, 1990, ... (wide year columns narrower than "1993" show ###)
    head = next(r for r in rows if len(r) > 3 and r[0].upper() == "LAT" and re.fullmatch(r"\d{4}", r[2]))
    ylab = []
    for c in head[2:]:
        if not c:
            break
        ylab.append(c)
    y0 = int(ylab[0]); years = list(range(y0, y0 + len(ylab)))
    named = [(i, int(c)) for i, c in enumerate(ylab) if re.fullmatch(r"\d{4}", c)]
    if any(y != y0 + i for i, y in named):
        raise ValueError(f"CALM year columns not consecutive: {ylab}")
    sites = {}
    for r in rows:
        if len(r) < 5 + len(years) or not re.fullmatch(r"[A-Za-z]{1,3}\d{1,3}[A-Za-z]?", r[0]):
            continue
        try:
            lat, lon = float(r[2]), float(r[3])
        except ValueError:
            continue
        reg = calm_region(lat, lon)
        if not reg:
            continue
        vals = {y: calm_value(r[5 + k]) for k, y in enumerate(years)}
        vals = {y: v for y, v in vals.items() if v is not None}
        if r[0] not in sites:
            sites[r[0]] = (reg, vals)
    print(f"  calm: {len(rows)} table rows, {len(sites)} sites north of 55°N, years {years[0]}-{years[-1]}", flush=True)
    # each site against its own 2001-2020 average (at least 12 years in that window, and at least 15 years in all)
    rel, ref = {}, {}
    for code, (reg, vals) in sites.items():
        rv = [v for y, v in vals.items() if 2001 <= y <= 2020]
        if len(rv) < 12 or len(vals) < 15:
            continue
        m = sum(rv) / len(rv)
        ref[code] = m
        rel[code] = (reg, {y: (v / m - 1) * 100 for y, v in vals.items()})
    print(f"  calm: {len(rel)} sites with a usable 2001-2020 reference", flush=True)
    if len(rel) < 40:
        raise ValueError(f"only {len(rel)} usable CALM sites")
    out = []
    regions = ["alaska", "canada", "nordic", "russia"]
    for y in years:
        here = [(c, reg, d[y]) for c, (reg, d) in rel.items() if y in d]
        if len(here) < 10:
            continue
        row = [y, f"{sum(v for _, _, v in here) / len(here):.1f}"]
        for g in regions:
            gv = [v for _, reg, v in here if reg == g]
            row.append(f"{sum(gv) / len(gv):.1f}" if len(gv) >= 4 else "")
        row += [len(here), f"{sum(ref[c] for c, _, _ in here) / len(here):.0f}"]
        out.append(row)
    # the newest year counts only once most sites have reported it (the table fills in through the autumn)
    while len(out) > 6:
        recent = sorted(r[6] for r in out[-6:-1])[2]
        if out[-1][6] >= 0.6 * recent:
            break
        print(f"  calm: {out[-1][0]} left out for now ({out[-1][6]} sites, usually ~{recent})", flush=True)
        out.pop()
    write_csv("data/permafrost_calm.csv", ["year", "all"] + regions + ["n_all", "mean_cm"], out)
    print(f"  calm: {out[0][0]}-{out[-1][0]}, last year {out[-1][1]}% from {out[-1][6]} sites", flush=True)
    return {"through": out[-1][0], "sites": len(rel), "source": CALM_PAGE}


# ---------------------------------------------------------------- PERMOS: borehole temperatures, measured
def permos(old):
    zips = set()
    for y in range(date.today().year + 1, 2024, -1):
        try:
            h = get(PERMOS_PAGE.format(y=y)).decode("utf-8", "replace")
        except Exception:
            continue
        zips |= set(re.findall(r'/fileadmin/Files/data/(PERMOS-DOI-\d{4}-\d{2}\.zip)', h))
    if not zips:
        raise ValueError("no PERMOS data publication found")
    name = max(zips)
    if old.get("zip") == name and os.path.exists("data/permafrost_permos.csv"):
        print(f"  permos: {name} already used", flush=True)
        return dict(old)
    raw = get("https://www.permos.ch/fileadmin/Files/data/" + name, 900)
    z = zipfile.ZipFile(io.BytesIO(raw))
    pick = lambda stem: next(n for n in z.namelist() if re.search(r"/Data/" + stem + r"_\d{8}\.csv$", n) and "__MACOSX" not in n)
    read = lambda stem: list(csv.DictReader(io.StringIO(z.read(pick(stem)).decode("utf-8-sig", "replace"))))
    bh, site, T = read("borehole"), read("site"), read("bht_hyear")
    sname = {s["id"]: s["name"] for s in site}
    meta = {b["id"]: b for b in bh}
    print(f"  permos: {name}, {len(raw):,} bytes; {len(bh)} boreholes, {len(T)} yearly values", flush=True)
    by = {}
    for r in T:
        try:
            if int(r["count"]) < 11:                       # at least 11 of the 12 months
                continue
            by.setdefault(r["borehole_id"], {}).setdefault(float(r["depth"]), {})[int(r["time"])] = float(r["temp"])
        except (ValueError, KeyError):
            continue
    rows, last = [], 0
    for bid, depths in by.items():
        cand = [d for d in depths if 8 <= d <= 12.5]
        if not cand:
            continue
        d = min(cand, key=lambda x: (abs(x - 10), -len(depths[x])))
        ser = depths[d]
        b = meta.get(bid, {})
        if len(ser) < 15 or max(ser) < date.today().year - 4 or "no permafrost" in (b.get("pf_thick") or "").lower():
            continue
        label = f"{sname.get(b.get('site_id'), '?')} ({b.get('name', bid)})".replace(",", " ")
        elev = b.get("h", "")
        elev = f"{float(elev):.0f}" if elev else ""
        for y in sorted(ser):
            rows.append([b.get("name", bid), label, elev, f"{d:g}", y, f"{ser[y]:.3f}"])
        last = max(last, max(ser))
    if len(rows) < 100:
        raise ValueError(f"only {len(rows)} PERMOS values")
    rows.sort(key=lambda r: (r[0], r[4]))
    write_csv("data/permafrost_permos.csv", ["borehole", "label", "elevation", "depth", "year", "temp"], rows)
    print(f"  permos: {len({r[0] for r in rows})} boreholes, through hydrological year {last}", flush=True)
    return {"through": last, "zip": name, "source": "https://www.permos.ch/doi/permos-dataset-" + name[11:15] + "-1"}


# ---------------------------------------------------------------- Permafrost_cci: ground temperature at 10 m, modelled
def listing(url):
    h = get(url).decode("utf-8", "replace")
    return [x for x in re.findall(r'href="([^"?]+)"', h) if not x.startswith(("..", "/", "http"))]


def reduce_year(path, np):
    """One yearly file -> 0.5° grid of mean 10 m temperature (NaN where < 25% of the fine cells have a value), and the
    area (km²) with the ground at 10 m below 0 °C and between -2 and 0 °C, from the full 0.01° grid."""
    import netCDF4
    ds = netCDF4.Dataset(path)
    v = ds.variables["T10m"]; v.set_auto_maskandscale(True)
    lat = ds.variables["lat"][:].astype("float64"); lon = ds.variables["lon"][:].astype("float64")
    ny, nx = v.shape[-2:]
    f = int(round(STEP / abs(lat[1] - lat[0])))
    if ny % f or nx % f:
        raise ValueError(f"grid {ny}x{nx} does not divide into {STEP}° blocks")
    flip = lat[0] > lat[-1]
    R = 6371.0; d = math.radians(abs(lat[1] - lat[0]))
    G = np.full((ny // f, nx // f), np.nan, "float32")
    a_pf = a_warm = 0.0
    for j0 in range(0, ny, 600):
        blk = v[0, j0:j0 + 600, :] if v.ndim == 3 else v[j0:j0 + 600, :]
        x = np.ma.filled(blk.astype("float32"), np.nan)
        la = lat[j0:j0 + 600]
        cell = (R * d) ** 2 * np.cos(np.radians(la))[:, None]       # km² of each 0.01° cell
        a_pf += float(np.sum(cell * (x < 0)))
        a_warm += float(np.sum(cell * ((x >= -2) & (x < 0))))
        b = x.reshape(x.shape[0] // f, f, nx // f, f)
        n = np.isfinite(b).sum(axis=(1, 3))
        s = np.nansum(b, axis=(1, 3))
        m = np.where(n >= 0.25 * f * f, s / np.maximum(n, 1), np.nan)
        G[j0 // f:(j0 + x.shape[0]) // f] = m
    ds.close()
    lat0 = float(lat.min()) - abs(lat[1] - lat[0]) / 2 + STEP / 2
    lon0 = float(lon.min()) - abs(lon[1] - lon[0]) / 2 + STEP / 2
    if flip:
        G = G[::-1]
    return G, a_pf / 1e6, a_warm / 1e6, lat0, lon0


def pfcci(old):
    import numpy as np
    vers = sorted(x.rstrip("/") for x in listing(CCI_BASE) if re.fullmatch(r"v\d+\.\d+/", x))
    ver = vers[-1]
    root = CCI_BASE + ver + "/northern_hemisphere/"
    years = sorted(int(x.rstrip("/")) for x in listing(root) if re.fullmatch(r"\d{4}/", x))
    cache = "data/permafrost_cci_grids.npz"
    have = {}
    if os.path.exists(cache) and old.get("version") == ver:
        z = np.load(cache)
        have = {int(y): (z["grids"][k], float(z["area_pf"][k]), float(z["area_warm"][k])) for k, y in enumerate(z["years"])}
        lat0, lon0 = float(z["lat0"]), float(z["lon0"])
    todo = [y for y in years if y not in have]
    print(f"  pfcci: version {ver}, years {years[0]}-{years[-1]}; {len(todo)} to download", flush=True)
    if not todo and os.path.exists("data/permafrost_map.json"):
        return dict(old)
    tmp = tempfile.mkdtemp()
    for y in todo:
        f = next(x for x in listing(root + f"{y}/") if x.endswith(".nc"))
        p = os.path.join(tmp, "y.nc")
        n = download(root + f"{y}/" + f.split("/")[-1], p)
        G, apf, aw, lat0, lon0 = reduce_year(p, np)
        os.remove(p)
        have[y] = (np.where(np.isfinite(G), np.round(G * 100), -32768).astype("int16"), apf, aw)
        print(f"  pfcci: {y}: {n / 1e6:.0f} MB; permafrost (10 m below 0 °C) {apf:.2f} million km², "
              f"-2 to 0 °C {aw:.2f}", flush=True)
    ys = sorted(have)
    if ys != years:
        raise ValueError("years missing after download")
    grids = np.stack([have[y][0] for y in ys])
    np.savez_compressed(cache + ".tmp.npz", years=np.array(ys), grids=grids, area_pf=np.array([have[y][1] for y in ys]),
                        area_warm=np.array([have[y][2] for y in ys]), lat0=lat0, lon0=lon0, step=STEP)
    os.replace(cache + ".tmp.npz", cache)
    T = np.where(grids == -32768, np.nan, grids / 100.0)
    nb = [k for k, y in enumerate(ys) if BASE_YEARS[0] <= y <= BASE_YEARS[1]]
    base = np.nanmean(T[nb], axis=0)
    nlat, nlon = base.shape
    w = np.cos(np.radians(lat0 + STEP * np.arange(nlat)))[:, None] * np.ones((1, nlon))
    mask = np.isfinite(base) & (base < 0)
    rows = []
    for k, y in enumerate(ys):
        ok = mask & np.isfinite(T[k])
        mt = float(np.sum(T[k][ok] * w[ok]) / np.sum(w[ok]))
        rows.append([y, f"{mt:.3f}", f"{have[y][1]:.3f}", f"{have[y][2]:.3f}"])
    write_csv("data/permafrost_cci.csv", ["year", "mean_t10", "area_pf", "area_warm"], rows)
    # the map: one character per grid point, as for the sea-surface maps (sstmap.js); ' ' = no value (sea, ice sheets)
    CH = "".join(c for c in map(chr, range(35, 127)) if c != "\\")
    def enc(a, lo, st):
        q = np.clip(np.round((a - lo) / st), 0, len(CH) - 1)
        return "".join(" " if not np.isfinite(v) else CH[int(i)] for v, i in zip(a.ravel(), np.nan_to_num(q).ravel()))
    L = T[-1]
    mp = {"year": ys[-1], "base": f"{BASE_YEARS[0]}–{BASE_YEARS[1]}", "version": ver,
          "grid": {"lat0": round(lat0, 4), "lon0": round(lon0, 4), "step": STEP, "nlat": nlat, "nlon": nlon},
          "temp": {"lo": -15, "step": .25, "codes": enc(L, -15, .25)},
          "change": {"lo": -2.25, "step": .05, "codes": enc(L - base, -2.25, .05)}}
    write_text("data/permafrost_map.json", json.dumps(mp, separators=(",", ":")))
    print(f"  pfcci: mean 10 m temperature over the 1997-2006 permafrost area {rows[0][1]} -> {rows[-1][1]} °C", flush=True)
    return {"through": ys[-1], "first": ys[0], "version": ver, "source": root}


def main():
    status = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    files = {"calm": ["data/permafrost_calm.csv"], "permos": ["data/permafrost_permos.csv"],
             "pfcci": ["data/permafrost_cci.csv", "data/permafrost_map.json"]}
    digest = lambda fs: hashlib.sha1(b"".join(open(f, "rb").read() for f in fs if os.path.exists(f))).hexdigest()
    failed = []
    for key, fn in (("calm", lambda o: calm()), ("permos", permos), ("pfcci", pfcci)):
        before = digest(files[key])
        old = status.get(key, {})
        try:
            info = fn(old)
        except Exception as e:
            print(f"::warning::{key}: not updated ({str(e)[:300]})", flush=True); failed.append(key); continue
        info["new_data"] = date.today().isoformat() if digest(files[key]) != before else old.get("new_data", date.today().isoformat())
        status[key] = info
    with open(STATUS + ".tmp", "w") as fh:
        json.dump(status, fh, indent=1, sort_keys=True)
    os.replace(STATUS + ".tmp", STATUS)
    return 1 if len(failed) == len(files) else 0


if __name__ == "__main__":
    sys.exit(main())
