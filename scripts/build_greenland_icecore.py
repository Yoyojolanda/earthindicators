#!/usr/bin/env python3
"""Greenland summit temperature over the last 4,000 years: two GISP2 ice-core reconstructions plus a modern tail.

The ice-core records are finished studies that will not change, so they are downloaded once and kept in data/;
run with --refetch to download them again. The modern tail is cut from this site's own yearly ERA5 maps
(data/era5_t2_annual_2deg.bin, made by build_era5_monthly.py) every time, so it grows by itself each January.

  kobashi  Kobashi et al. 2011 (GRL 38, L21501, doi:10.1029/2011GL049444): snow temperature at the GISP2 site
           from argon and nitrogen isotopes in air bubbles, one value a year from 2000 BCE, with 1-sigma
           uncertainty up to 1950. Values after 1950 have no uncertainty in the file; the page does not use them.
           -> data/gisp2_kobashi2011.csv  year (CE, negative = BCE), temp_c, sd_c
  alley    Alley 2000 (Quat. Sci. Rev. 19, 213-226): central Greenland temperature from oxygen isotopes in GISP2 ice,
           the record behind the widely shared "GISP2" chart. Ages are thousands of years before 1950; the youngest
           value is 0.0951 ka, about the year 1855. Only the last ~4,050 years are kept.
           -> data/gisp2_alley2000.csv  age_ka (thousand years before 1950), year (CE), temp_c
  era5     ERA5 yearly mean 2 m air temperature in the 2-degree cell 72-74N, 38-40W, which contains Summit Station
           and the GISP2 drill site (72.6N, 38.5W).
           -> data/greenland_summit_era5.csv  year, t2_c
"""
import csv, io, json, os, sys, urllib.request

NOAA = "https://www.ncei.noaa.gov/pub/data/paleo/icecore/greenland/summit/gisp2/isotopes/"
KOBASHI_URL = NOAA + "gisp2-temperature2011.txt"
ALLEY_URL = NOAA + "gisp2_temp_accum_alley2000.txt"
BIN, META = "data/era5_t2_annual_2deg.bin", "data/era5_t2_annual_2deg.json"
OUT_K, OUT_A, OUT_E = "data/gisp2_kobashi2011.csv", "data/gisp2_alley2000.csv", "data/greenland_summit_era5.csv"
SUMMIT = (72.58, -38.46)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "earthindicators.org data update"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("latin-1")


def write_csv(path, header, rows):
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(header); w.writerows(rows)
    new = buf.getvalue()
    if not os.path.exists(path) or open(path).read() != new:
        open(path, "w").write(new); print(f"  wrote {path} ({len(rows)} rows)")
    else:
        print(f"  {path} unchanged")


def kobashi():
    rows = []
    for line in get(KOBASHI_URL).splitlines():
        p = line.split()
        if len(p) < 3 or not p[0].lstrip("-").isdigit():
            continue
        try:
            t = float(p[1])
        except ValueError:
            continue
        sd = "" if p[2].lower() == "n/a" else f"{float(p[2]):.2f}"
        rows.append([int(p[0]), f"{t:.2f}", sd])
    rows.sort()
    if len(rows) < 3900 or rows[0][0] > -1990 or rows[-1][0] < 1950:
        raise RuntimeError(f"Kobashi file looks incomplete: {len(rows)} rows")
    write_csv(OUT_K, ["year", "temp_c", "sd_c"], rows)


def alley():
    rows, on = [], False
    for line in get(ALLEY_URL).splitlines():
        if "Age" in line and "Temperature" in line:          # the temperature table (the accumulation table follows)
            on = True; continue
        if not on:
            continue
        p = line.split()
        if len(p) == 2:
            try:
                age, t = float(p[0]), float(p[1])
            except ValueError:
                if rows: break
                continue
            if age > 4.06: break
            rows.append([f"{age:.4f}", round(1950 - age * 1000), f"{t:.4f}"])
        elif rows:
            break
    if len(rows) < 350 or float(rows[0][0]) > 0.1:
        raise RuntimeError(f"Alley file looks incomplete: {len(rows)} rows")
    write_csv(OUT_A, ["age_ka", "year", "temp_c"], rows)


def era5():
    import numpy as np
    m = json.load(open(META))
    a = np.fromfile(BIN, "<i2").reshape(len(m["years"]), m["nlat"], m["nlon"])
    i = int((m["lat_north_edge"] - SUMMIT[0]) // m["deg"])
    j = int(((SUMMIT[1] - m["lon_west_edge"]) % 360) // m["deg"])
    rows = [[y, f"{v * m['scale']:.2f}"] for y, v in zip(m["years"], a[:, i, j]) if v != m["missing"]]
    write_csv(OUT_E, ["year", "t2_c"], rows)


def main():
    refetch = "--refetch" in sys.argv
    ok = True
    for path, fn in ((OUT_K, kobashi), (OUT_A, alley)):
        if refetch or not os.path.exists(path):
            try:
                fn()
            except Exception as e:
                print(f"  {path}: {e}", file=sys.stderr); ok = False
    era5()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
