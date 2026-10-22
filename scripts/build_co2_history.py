#!/usr/bin/env python3
"""CO2 over Earth's history, for the "CO2 through Earth's history" chart on co2.html.

Both records are finished studies that will not change, so they are downloaded once and kept in data/;
run with --refetch to download them again.

  icecore   Bereiter et al. 2015 (GRL 42, 542-549, doi:10.1002/2014GL061957): the Antarctic ice-core CO2 composite,
            800,000 years up to the 2000s (the youngest part from Law Dome). From NOAA NCEI paleoclimatology.
            -> data/co2_icecore_bereiter2015.csv  age_bp (years before 1950), year_ce, co2_ppm, sd_ppm
  cenozoic  CenCO2PIP Consortium (Hönisch et al.) 2023 (Science 382, eadi5177, doi:10.1126/science.adi5177): CO2 over
            the last 66 million years from all reviewed proxy records (boron isotopes and alkenones in marine shells
            and algae, plant stomata, soil carbonates and more), combined in one statistical curve at 500,000-year steps.
            The consortium's file holds ln(CO2) quantiles; converted here to ppm.
            -> data/co2_cenozoic_cenco2pip2023.csv  age_ma (million years ago), p2_5, p25, p50, p75, p97_5 (ppm)
"""
import csv, io, math, os, sys, urllib.request

ICE_URL = "https://www.ncei.noaa.gov/pub/data/paleo/icecore/antarctica/antarctica2015co2composite.txt"
CENO_URL = "https://raw.githubusercontent.com/SPATIAL-Lab/CenoCO2/v1.0/out/500kyrCO2.csv"
OUT_I, OUT_C = "data/co2_icecore_bereiter2015.csv", "data/co2_cenozoic_cenco2pip2023.csv"


def get(url):
    print("downloading", url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "earthindicators.org data update"})
    return urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")


def icecore():
    rows = []
    for line in get(ICE_URL).splitlines():
        if line.startswith("#"):
            continue
        p = line.split()
        try:
            age, co2 = float(p[0]), float(p[1])
            sd = float(p[2]) if len(p) > 2 else float("nan")
        except (ValueError, IndexError):
            continue
        if -100 <= age <= 900000 and 150 <= co2 <= 450:
            rows.append((age, co2, sd))
    rows.sort()
    if len(rows) < 1500 or rows[-1][0] < 790000:
        sys.exit(f"ice-core file looks incomplete ({len(rows)} rows); nothing written")
    with open(OUT_I, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["age_bp", "year_ce", "co2_ppm", "sd_ppm"])
        for a, c, s in rows:
            w.writerow([f"{a:g}", f"{1950 - a:g}", f"{c:.2f}", "" if math.isnan(s) else f"{s:.2f}"])
    print(f"wrote {OUT_I}: {len(rows)} samples, {rows[0][0]:g} to {rows[-1][0]:g} years before 1950")


def cenozoic():
    rd = list(csv.reader(io.StringIO(get(CENO_URL))))
    head, body = rd[0], rd[1:]
    if [h.strip() for h in head] != ["ages", "2.5%", "25%", "50%", "75%", "97.5%"]:
        sys.exit(f"unexpected columns in the CenCO2PIP file: {head}")
    rows = sorted((float(r[0]), *[math.exp(float(x)) for x in r[1:6]]) for r in body if r)
    if len(rows) < 120:
        sys.exit("CenCO2PIP file looks incomplete; nothing written")
    with open(OUT_C, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["age_ma", "p2_5", "p25", "p50", "p75", "p97_5"])
        for r in rows:
            w.writerow([f"{r[0]:g}"] + [f"{v:.1f}" for v in r[1:]])
    print(f"wrote {OUT_C}: {len(rows)} steps, {rows[0][0]:g} to {rows[-1][0]:g} million years ago")


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    refetch = "--refetch" in sys.argv
    for out, fn in ((OUT_C, cenozoic), (OUT_I, icecore)):
        if refetch or not os.path.exists(out):
            fn()
        else:
            print(f"{out} already present; use --refetch to download again")
