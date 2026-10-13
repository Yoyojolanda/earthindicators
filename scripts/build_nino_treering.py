#!/usr/bin/env python3
"""Winter (Dec-Feb) Nino 3.4 from 1100 to now: tree rings before the thermometer era, measurements after.

Source: Cook, E.R. and Cane, M.A. (2024), Tree Rings Reveal ENSO in the Last Millennium, Geophysical Research
Letters 51, doi:10.1029/2024GL109759; data at NOAA NCEI Paleoclimatology (study 39379). The reconstruction is a
map of December-February sea-surface temperature on about 2,400 grid points of the equatorial Pacific
(10N-10S, 160E-80W). Two versions: R11 (1100-2000, fewer tree-ring records) and R15 (1500-2000, more records and
better skill); as in the paper's own comparisons, R15 is used from 1500 and R11 before. A third file holds the
measured SST on the same grid for 1871-2000.

This script averages each map over the Nino 3.4 box (5S-5N, 170W-120W, weighted by cos(latitude)) and gives
every winter as an anomaly from the measured 1871-2000 mean, the reconstruction's own reference period.

Output: data/nino34_treering.csv   winter (e.g. 1791-92), year (of January), recon (tree rings, degC),
                                   measured (the instrumental grid, 1871-2000, degC)

The files never change, so this runs once (and again only if the output is missing). Run from the repo root.
"""
import csv, io, math, os, sys, urllib.request

BASE = "https://www.ncei.noaa.gov/pub/data/paleo/treering/reconstructions/cook2024/"
FILES = {"r11": "cook2024-R11-ENSO-Rec-1100-2000.txt", "r15": "cook2024-R15-ENSO-Rec-1500-2000.txt",
         "act": "cook2024-ENSO-Act-1871-2000-SST.txt", "ll": "cook2024-ENSO-latlon.txt"}
OUT = "data/nino34_treering.csv"
LAT, LON = (-5.0, 5.0), (-170.0, -120.0)     # Nino 3.4, longitudes in degrees east from -180 to 180


def get(name):
    req = urllib.request.Request(BASE + FILES[name], headers={"User-Agent": "earthindicators.org data update"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8", "replace")


def table(text):
    """NOAA paleo text file: '#' comment lines, then a tab-separated table with a header row."""
    rows = [l.rstrip("\n") for l in text.splitlines() if l.strip() and not l.startswith("#")]
    head = rows[0].split("\t")
    return head, [r.split("\t") for r in rows[1:]]


def points(text):
    """grid point number -> (lat, lon); the coordinate file has a point number, latitude and longitude per row"""
    head, rows = table(text)
    h = [x.strip().lower() for x in head]
    ilat = next(i for i, x in enumerate(h) if x.startswith("lat"))
    ilon = next(i for i, x in enumerate(h) if x.startswith("lon"))
    ipt = next((i for i, x in enumerate(h) if x not in (h[ilat], h[ilon])), None)
    out = {}
    for k, r in enumerate(rows, 1):
        lon = float(r[ilon]); lon = lon - 360 if lon > 180 else lon
        out[str(int(float(r[ipt]))) if ipt is not None else str(k)] = (float(r[ilat]), lon)
    return out


def box_means(text, pts):
    """{year: cos-weighted mean over the Nino 3.4 box}"""
    head, rows = table(text)
    cols = [(j, math.cos(math.radians(pts[c.strip()][0]))) for j, c in enumerate(head)
            if c.strip() in pts and LAT[0] <= pts[c.strip()][0] <= LAT[1] and LON[0] <= pts[c.strip()][1] <= LON[1]]
    if len(cols) < 10:
        sys.exit(f"only {len(cols)} grid points in the Nino 3.4 box; check the coordinate file")
    out = {}
    for r in rows:
        s = w = 0.0
        for j, wt in cols:
            v = r[j].strip()
            if v and v.upper() != "NA":
                s += float(v) * wt; w += wt
        if w:
            out[int(float(r[0]))] = s / w
    return out, len(cols)


def main():
    if os.path.exists(OUT) and "--force" not in sys.argv:
        print(f"{OUT} exists; the source never changes (use --force to rebuild)"); return
    pts = points(get("ll"))
    act, n = box_means(get("act"), pts)
    r11, _ = box_means(get("r11"), pts)
    r15, _ = box_means(get("r15"), pts)
    print(f"{n} grid points in the Nino 3.4 box; measured {min(act)}-{max(act)}, R11 {min(r11)}-{max(r11)}, R15 {min(r15)}-{max(r15)}")
    base = sum(act[y] for y in range(1871, 2001)) / 130
    # which year is a winter filed under? The 1997-98 El Nino is the largest measured winter of the 1990s:
    # under 1998 if the year is January's, under 1997 if it is December's
    jan = act[1998] > act[1997]
    off = 0 if jan else 1                     # add to get the year of January
    print(f"year label = year of {'January' if jan else 'December'} (1997: {act[1997]-base:+.2f}, 1998: {act[1998]-base:+.2f})")
    rec = {**{y: v for y, v in r11.items() if y < 1500}, **r15}
    years = sorted(rec)
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["winter", "year", "recon", "measured"])
        for y in years:
            j = y + off
            w.writerow([f"{j-1}-{str(j)[-2:]}", j, f"{rec[y]-base:.3f}", f"{act[y]-base:.3f}" if y in act else ""])
    pre = sorted(((rec[y] - base, y + off) for y in years if y + off < 1871), reverse=True)[:3]
    print("largest reconstructed winters before 1871:", ", ".join(f"{j-1}-{str(j)[-2:]} {v:+.2f}" for v, j in pre))
    print(f"wrote {OUT}: {len(years)} winters")


if __name__ == "__main__":
    main()
