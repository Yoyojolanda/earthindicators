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
   (year, mass change in Gt, uncertainty in Gt). Uncertainty: the cells' random uncertainties combined as the
   square root of the sum of squares, as random errors add up.
"""
import csv, glob, json, os, sys, tempfile, urllib.request, zipfile

DATASET = "derived-gridded-glacier-mass-change"
OUT, SRC = "data/glaciers_global.csv", "data/glaciers_source.txt"


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
    return [xr.open_dataset(f) for f in files]


def describe(ds):
    print(f"  dims {dict(ds.sizes)}", flush=True)
    for v in ds.data_vars:
        a = ds[v].attrs
        print(f"    {v} {ds[v].dims} units={a.get('units')!r} long_name={a.get('long_name')!r}", flush=True)


def pick(ds, want_unc):
    """The 'total' mass change variable (or its uncertainty), not the 'specific' (per square metre) one."""
    for v in ds.data_vars:
        txt = (v + " " + str(ds[v].attrs.get("long_name", ""))).lower()
        if "total" in txt and ("uncertainty" in txt or "error" in txt or "_unc" in txt) == want_unc:
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


def main():
    import numpy as np
    cfg = cds_cfg()
    f = form(cfg)
    req = choose(f.get("inputs", {}))
    version = json.dumps({k: v for k, v in req.items() if "version" in k}, sort_keys=True)
    print(f"request: { {k: (v if not isinstance(v, list) or len(v) < 6 else f'{len(v)} values') for k, v in req.items()} }", flush=True)
    if os.path.exists(OUT) and os.path.exists(SRC) and open(SRC).read().strip() == version:
        print("same product version as last time: nothing new", flush=True)
        return
    from ecmwf.datastores import Client
    client = Client(url=cfg["url"], key=cfg["key"], progress=False)
    path = os.path.join(tempfile.mkdtemp(), "glaciers")
    client.retrieve(DATASET, req, path)
    rows = {}
    for ds in open_all(path):
        describe(ds)
        tv, uv = pick(ds, False), pick(ds, True)
        if tv is None:
            raise SystemExit("no 'total' mass change variable found; see the variables listed above")
        k = to_gt(ds[tv])
        tdim = next((d for d in ds[tv].dims if d not in ("lat", "lon", "latitude", "longitude")), None)
        space = [d for d in ds[tv].dims if d != tdim]
        tot = (ds[tv].sum(space, skipna=True) * k)
        unc = (np.sqrt((ds[uv] ** 2).sum(space, skipna=True)) * to_gt(ds[uv])) if uv else None
        times = ds[tdim].values if tdim else [ds.attrs.get("year")]
        for i, t in enumerate(times):
            y = int(str(t)[:4])
            rows[y] = (float(tot.values[i] if tdim else tot.values),
                       float(unc.values[i] if tdim else unc.values) if unc is not None else None)
    if len(rows) < 30:
        raise SystemExit(f"only {len(rows)} years found; not saving")
    with open(OUT + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["year", "mass_change_gt", "uncertainty_gt"])
        for y in sorted(rows):
            m, u = rows[y]; w.writerow([y, f"{m:.1f}", "" if u is None else f"{u:.1f}"])
    os.replace(OUT + ".tmp", OUT)
    open(SRC, "w").write(version + "\n")
    print(f"saved {len(rows)} years ({min(rows)}-{max(rows)}); last: {max(rows)} {rows[max(rows)][0]:.0f} Gt", flush=True)


if __name__ == "__main__":
    sys.exit(main())
