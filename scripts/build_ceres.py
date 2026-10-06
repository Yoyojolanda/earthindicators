#!/usr/bin/env python3
"""Global monthly TOA radiation from NASA CERES EBAF-TOA Ed4.2.1 -> data/ceres_ebaf_global.csv

  build_ceres.py latest            print the download URL of the newest EBAF-TOA file (public CMR search)
  build_ceres.py extract FILE.nc   write the global monthly means CSV from a downloaded file

Columns: month, solar (incoming), asr (absorbed solar = incoming - reflected), olr (outgoing longwave),
net (asr - olr = Earth's energy imbalance), all in W/m2, all-sky.
"""
import csv, json, os, sys, urllib.request

COLLECTION = "C3880497643-LARC_CLOUD"   # CERES_EBAF-TOA_Edition4.2.1
OUT = "data/ceres_ebaf_global.csv"


def latest():
    url = ("https://cmr.earthdata.nasa.gov/search/granules.json"
           f"?collection_concept_id={COLLECTION}&page_size=100")
    feed = json.load(urllib.request.urlopen(url, timeout=60))["feed"]["entry"]
    links = [l["href"] for g in feed for l in g.get("links", [])
             if l.get("href", "").startswith("https://") and l["href"].endswith(".nc")]
    if not links:
        sys.exit("no .nc links found in CMR response")
    # file names end in _200003-YYYYMM.nc: the newest has the latest end month
    print(max(links, key=lambda h: h.rsplit("-", 1)[-1]))


def extract(path):
    import numpy as np, xarray as xr
    ds = xr.open_dataset(path, decode_times=True)
    names = set(ds.variables)
    g = {k: f"g{k}" for k in ("solar_mon", "toa_sw_all_mon", "toa_lw_all_mon")}
    if all(v in names for v in g.values()):
        print("using the file's own global means (geodetic weighting)")
        get = lambda k: ds[g[k]].values
    else:
        print("global-mean variables not found; computing area-weighted means from the 1-degree grid")
        w = np.cos(np.deg2rad(ds["lat"]))
        get = lambda k: ds[k].weighted(w).mean(("lat", "lon")).values
    solar, sw, lw = get("solar_mon"), get("toa_sw_all_mon"), get("toa_lw_all_mon")
    months = ds["time"].values.astype("datetime64[M]").astype(str)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        wr = csv.writer(fh, lineterminator="\n"); wr.writerow(["month", "solar", "asr", "olr", "net"])
        n = 0
        for m, s, r, o in zip(months, solar, sw, lw):
            if np.isfinite([s, r, o]).all():
                asr = s - r
                wr.writerow([m, f"{s:.3f}", f"{asr:.3f}", f"{o:.3f}", f"{asr - o:.3f}"]); n += 1
    print(f"wrote {OUT}: {n} months, {months[0]} to {months[-1]}")
    if n < 250:
        sys.exit("fewer than 250 months; something is wrong")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "latest":
        latest()
    elif len(sys.argv) == 3 and sys.argv[1] == "extract":
        extract(sys.argv[2])
    else:
        sys.exit(__doc__)
