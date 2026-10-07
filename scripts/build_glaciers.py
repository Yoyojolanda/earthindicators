#!/usr/bin/env python3
"""World glacier mass change per year, from the Copernicus gridded glacier product (produced by WGMS).

Dataset: "Glacier mass change gridded data from 1976 to present derived from the Fluctuations of Glaciers
Database" (CDS id derived-gridded-glacier-mass-change, doi:10.24381/cds.ba597449): annual glacier mass change
on a 0.5-degree grid, per hydrological year.

What this script does:
1. Reads the dataset's request form from the CDS API and picks: the newest product version, all years, all
   variables. If that version is already in data/glaciers_source.txt (and the CSV exists), it stops: nothing new.
2. Downloads it with the same CDS key as the ERA5 workflows (~/.cdsapirc, written by the workflow).
3. Prints the file layout (variables, dimensions, units), so the log shows exactly what came in.
4. Adds up the total mass change of all grid cells for each year -> data/glaciers_global.csv
   (year, hydrological year, mass change in Gt, uncertainty in Gt). Uncertainty: the cells' random uncertainties combined as the
   square root of the sum of squares, as random errors add up.
5. Also adds up, separately, the glaciers around Greenland and those south of 60 S (around Antarctica). NASA's GRACE
   totals for Greenland and Antarctica measure the gravity of the whole region, so they already include these glaciers;
   the land-ice sea-level chart subtracts them from the glacier bar so they are not counted twice.
   Greenland area: north of 59 N, east of a line through Davis Strait, Baffin Bay and Nares Strait (which separates it
   from Baffin and Ellesmere Island), and west of 30 W below 67.5 N (which leaves out Iceland) or of 10 W further north.
"""
import csv, glob, json, os, sys, tempfile, urllib.request, zipfile

DATASET = "derived-gridded-glacier-mass-change"
OUT, SRC = "data/glaciers_global.csv", "data/glaciers_source.txt"
COLS = ["year", "hydrological_year", "mass_change_gt", "uncertainty_gt", "greenland_periphery_gt", "antarctic_periphery_gt"]
# (longitude, latitude) along Davis Strait, Baffin Bay and Nares Strait: Greenland lies east of this line
WEST_EDGE = [(-58, 59), (-58, 70), (-66, 74), (-75, 76.5), (-74, 78.3), (-70, 79.5), (-65.5, 81), (-61.5, 82), (-56, 83), (-50, 90)]


def greenland(lat, lon):
    """True for grid cells in the Greenland region (lat, lon in degrees; lon -180..180), as numpy arrays."""
    import numpy as np
    xs, ys = zip(*WEST_EDGE)
    west = np.interp(lat, ys, xs)
    east = np.where(lat < 67.5, -30.0, -10.0)
    return (lat >= 59) & (lon > west) & (lon < east)


def cds_cfg():
    cfg = {}
    for line in open(os.path.expanduser("~/.cdsapirc")):
        if ":" in line:
            k, v = line.split(":", 1); cfg[k.strip()] = v.strip()
    return cfg


def form(cfg):
    url = f"{cfg['url'].rstrip('/')}/retrieve/v1/processes/{DATASET}"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": cfg["key"]})
    return json.load(urllib.request.urlopen(req, timeout=60))


def choose(inputs):
    """One value (or all values) for every field of the request form."""
    req = {}
    for name, spec in inputs.items():
        sch = spec.get("schema", {})
        enum = sch.get("enum") or sch.get("items", {}).get("enum") or []
        many = sch.get("type") == "array"
        print(f"  form field {name}: {'several' if many else 'one'} of {enum[:8]}{' ...' if len(enum) > 8 else ''}", flush=True)
        if not enum:
            continue
        if "format" in name:
            req[name] = next((v for v in ("zip", "netcdf") if v in enum), enum[0])
        elif "version" in name:
            req[name] = sorted(enum)[-1]                 # newest version
        else:
            req[name] = list(enum) if many else enum[-1]
    return req


def open_all(path):
    """Returns (file name, dataset) pairs."""
    import xarray as xr
    print(f"  downloaded {os.path.getsize(path):,} bytes; zip: {zipfile.is_zipfile(path)}", flush=True)
    files = [path]
    if zipfile.is_zipfile(path):
        d = tempfile.mkdtemp()
        def unpack(z, where):                            # also unpacks zips inside the zip
            z.extractall(where)
            for n in z.namelist():
                print(f"    in zip: {n}", flush=True)
                q = os.path.join(where, n)
                if zipfile.is_zipfile(q):
                    unpack(zipfile.ZipFile(q), q + "_unzipped")
        unpack(zipfile.ZipFile(path), d)
        files = sorted(f for f in glob.glob(os.path.join(d, "**", "*"), recursive=True)
                       if os.path.isfile(f) and not zipfile.is_zipfile(f)
                       and f.lower().rsplit(".", 1)[-1] in ("nc", "nc4", "netcdf", "cdf", "h5"))
    print(f"  {len(files)} data file(s): {[os.path.basename(f) for f in files[:5]]}{' ...' if len(files) > 5 else ''}", flush=True)
    return [(os.path.basename(f), xr.open_dataset(f)) for f in files]


def describe(ds):
    print(f"  dims {dict(ds.sizes)}", flush=True)
    for v in ds.data_vars:
        a = ds[v].attrs
        print(f"    {v} {ds[v].dims} units={a.get('units')!r} long_name={a.get('long_name')!r}", flush=True)


def pick(ds, want_unc):
    """The total mass change in gigatonnes (or its uncertainty), not the specific one (metres of water per area).
    In the files: glacier_mass_change_gt and uncertainty_gt, both with units 'gt'."""
    for v in ds.data_vars:
        txt = (v + " " + str(ds[v].attrs.get("long_name", ""))).lower()
        is_gt = str(ds[v].attrs.get("units", "")).lower().replace(" ", "") in ("gt", "gigatonnes") or v.lower().endswith("_gt")
        if is_gt and ("uncertainty" in txt or "error" in txt) == want_unc:
            return v
    return None


def to_gt(da):
    u = str(da.attrs.get("units", "")).lower().replace(" ", "")
    if u in ("gt", "gigatonnes", "gt/yr", "gtyr-1", "gta-1"):
        return 1.0
    if u.startswith("kg"):
        return 1e-12
    if u.startswith("t") and "gt" not in u:
        return 1e-9
    raise SystemExit(f"unknown unit {u!r} for {da.name}; check the log above and set the conversion")


def xr_greenland(la, lo):
    import xarray as xr
    a, b = xr.broadcast(la, lo)
    return xr.DataArray(greenland(a.values, b.values), dims=a.dims, coords=a.coords)


def main():
    import numpy as np
    cfg = cds_cfg()
    f = form(cfg)
    req = choose(f.get("inputs", {}))
    version = json.dumps({k: v for k, v in req.items() if "version" in k}, sort_keys=True)
    print(f"request: { {k: (v if not isinstance(v, list) or len(v) < 6 else f'{len(v)} values') for k, v in req.items()} }", flush=True)
    same_cols = os.path.exists(OUT) and open(OUT).readline().strip().split(",") == COLS
    if same_cols and os.path.exists(SRC) and open(SRC).read().strip() == version:
        print("same product version as last time: nothing new", flush=True)
        return
    from ecmwf.datastores import Client
    client = Client(url=cfg["url"], key=cfg["key"], progress=False)
    path = os.path.join(tempfile.mkdtemp(), "glaciers")
    client.retrieve(DATASET, req, path)
    import re
    rows, shown = {}, False
    for fname, ds in open_all(path):
        if not shown:
            describe(ds); shown = True                 # every file has the same layout: show the first one
        tv, uv = pick(ds, False), pick(ds, True)
        if tv is None:
            raise SystemExit("no mass change variable in gigatonnes found; see the variables listed above")
        k = to_gt(ds[tv])
        tdim = next((d for d in ds[tv].dims if d not in ("lat", "lon", "latitude", "longitude")), None)
        space = [d for d in ds[tv].dims if d != tdim]
        tot = (ds[tv].sum(space, skipna=True) * k)
        latn = next(d for d in space if d.startswith("lat")); lonn = next(d for d in space if d.startswith("lon"))
        la, lo = ds[latn], ((ds[lonn] + 180) % 360) - 180
        gmask = xr_greenland(la, lo)
        gp = float((ds[tv].where(gmask).sum(space, skipna=True) * k).values.sum())
        ap = float((ds[tv].where(la < -60).sum(space, skipna=True) * k).values.sum())
        unc = (np.sqrt((ds[uv] ** 2).sum(space, skipna=True)) * to_gt(ds[uv])) if uv else None
        # one file per hydrological year, e.g. ...-2022-23.nc4 = October 2022 to September 2023 (north);
        # labelled by the year it ends in (2023), as WGMS does when it calls 2023 the record year
        m = re.search(r"(\d{4})-(\d{2})\.", fname)
        if not m:
            raise SystemExit(f"no hydrological year in file name {fname}")
        y = int(m.group(1)) + 1
        rows[y] = (f"{m.group(1)}-{m.group(2)}", float(tot.values.sum()), float(unc.values.sum()) if unc is not None else None, gp, ap)
        ds.close()
    if len(rows) < 30:
        raise SystemExit(f"only {len(rows)} years found; not saving")
    with open(OUT + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(COLS)
        for y in sorted(rows):
            h, m, u, gp, ap = rows[y]; w.writerow([y, h, f"{m:.1f}", "" if u is None else f"{u:.1f}", f"{gp:.1f}", f"{ap:.1f}"])
    os.replace(OUT + ".tmp", OUT)
    open(SRC, "w").write(version + "\n")
    big = min(rows, key=lambda y: rows[y][1])
    print(f"saved {len(rows)} years ({rows[min(rows)][0]} to {rows[max(rows)][0]}); latest {rows[max(rows)][1]:.0f} Gt; "
          f"largest loss {rows[big][0]}: {rows[big][1]:.0f} Gt", flush=True)
    rec = [rows[y] for y in rows if y >= 2003]
    av = lambda i: sum(r[i] for r in rec) / len(rec)
    print(f"average per year since 2002-03: all glaciers {av(1):.0f} Gt, around Greenland {av(3):.0f} Gt, "
          f"south of 60 S {av(4):.0f} Gt (published estimates: roughly -30 to -45 and -5 to -15)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
