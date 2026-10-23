#!/usr/bin/env python3
"""Water stored on land, from the GRACE and GRACE-FO satellites (water cycle page).

GRACE (2002-2017) and GRACE-FO (since 2018) measure tiny changes in Earth's gravity from month to month; most of them
come from water moving around: rain soaking into the ground, groundwater pumped up, lakes and reservoirs filling,
snow and glaciers melting. NASA JPL turns them into "total water storage": the change in all water on and under the
land (soil, groundwater, surface water, snow and ice), as a layer of water in cm, on a 0.5° grid (3° mascons).

Source: JPL GRACE/GRACE-FO mascon solution RL06.3 version 4, Coastal Resolution Improvement (CRI) filter, one
netCDF file with every month (~45 MB), PO.DAAC collection TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4. Needs an
Earthdata login (~/.netrc). The file is only downloaded when NASA publishes a newer one (about monthly).

Average over all land between 60°S and 90°N except Greenland (land_mask from the file; Antarctica south of 60°S and
Greenland, whose ice is on the land ice page, left out), weighted by area; glaciers elsewhere are included.
  -> data/grace_tws_monthly.csv  date (middle of the month), mm (water layer over that land, compared with the
     2004-2009 average, as JPL's file), gt (the same in billion metric tons; 1 mm over 1 km² = 0.001 Gt)
     data/grace_tws_source.txt   the file used
"""
import csv, io, json, os, sys, tempfile, urllib.request
from datetime import date, timedelta

import numpy as np

SHORT = "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"
OUT, SRC = "data/grace_tws_monthly.csv", "data/grace_tws_source.txt"


def newest():
    u = f"https://cmr.earthdata.nasa.gov/search/granules.json?short_name={SHORT}&sort_key=-start_date&page_size=5"
    g = json.loads(urllib.request.urlopen(u, timeout=60).read())["feed"]["entry"]
    for e in g:
        for l in e.get("links", []):
            h = l.get("href", "")
            if h.startswith("https://archive.podaac") and h.endswith(".nc"):
                return h
    raise RuntimeError("no mascon grid file found in CMR")


def download(url, path):
    import requests                                    # follows the Earthdata login redirects with ~/.netrc
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(path, "wb") as fh:
            for b in r.iter_content(1 << 22):
                fh.write(b)


def is_greenland(lat, lon):
    """A box around Greenland (59-84°N, 75-10°W) without Iceland; it clips a little of Ellesmere Island too."""
    lon = np.where(lon > 180, lon - 360, lon)
    return (lat >= 59) & (lon >= -75) & (lon <= -10) & ~((lat < 67) & (lon > -30))


def main():
    url = newest()
    old = open(SRC).read().strip() if os.path.exists(SRC) else ""
    if old == url and os.path.exists(OUT):
        print(f"already used: {url.rsplit('/', 1)[-1]}", flush=True)
        return
    import xarray as xr
    p = os.path.join(tempfile.mkdtemp(), "m.nc")
    download(url, p)
    ds = xr.open_dataset(p)
    print(f"{url.rsplit('/', 1)[-1]}: {os.path.getsize(p) / 1e6:.0f} MB; variables {list(ds.data_vars)}", flush=True)
    lwe = ds["lwe_thickness"]                          # cm
    lat, lon = ds["lat"].values, ds["lon"].values
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    land = ds["land_mask"].values > 0.5 if "land_mask" in ds else np.isfinite(lwe.isel(time=0).values)
    keep = land & (LA >= -60) & ~is_greenland(LA, LO)
    d = np.radians(abs(lat[1] - lat[0]))
    area = (6371.0 * d) ** 2 * np.cos(np.radians(LA))         # km² per cell
    A = area[keep].sum()
    rows = []
    for k, t in enumerate(ds["time"].values):
        v = lwe.isel(time=k).values
        ok = keep & np.isfinite(v)
        if ok.sum() < 0.98 * keep.sum():
            continue
        mm = 10 * float((v[ok] * area[ok]).sum() / area[ok].sum())
        day = str(np.datetime_as_string(t, unit="D"))
        rows.append([day, f"{mm:.2f}", f"{mm * A / 1e3:.0f}"])
    if len(rows) < 150:
        sys.exit(f"only {len(rows)} months")
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(["date", "mm", "gt"]); w.writerows(rows)
    open(OUT + ".tmp", "w").write(buf.getvalue()); os.replace(OUT + ".tmp", OUT)
    open(SRC, "w").write(url + "\n")
    print(f"{len(rows)} months, {rows[0][0]} to {rows[-1][0]}; land counted {A / 1e6:.1f} million km²; last {rows[-1][1]} mm", flush=True)


if __name__ == "__main__":
    main()
