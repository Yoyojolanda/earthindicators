#!/usr/bin/env python3
"""Monthly world temperature from four independent records, for the "five records" chart on the air page
(the fifth, Copernicus ERA5, comes from data/era5_t2_regions_monthly.csv).

  gistemp   NASA GISTEMP v4, land-ocean index               data.giss.nasa.gov
  noaa      NOAA GlobalTemp (newest version), land-ocean    ncei.noaa.gov
  hadcrut   Met Office / UEA HadCRUT5, analysis             metoffice.gov.uk
  berkeley  Berkeley Earth, global land and ocean (high-resolution product)

Each is saved as published, on its own baseline; the page puts them all on one footing (each month minus that
record's own 1991-2020 average for the month, plus 0.88 °C). Output: data/temp_records_monthly.csv
(month, gistemp, noaa, hadcrut, berkeley) and data/temp_records_source.txt (the exact files used).

A record that fails to download, or fails the checks below, keeps its previous values, so one source having a bad
day never empties the chart. The script exits with an error only when every record failed.
"""
import csv, io, os, re, sys, time, urllib.request
from datetime import date

OUT, SRC = "data/temp_records_monthly.csv", "data/temp_records_source.txt"
UA = {"User-Agent": "earthindicators.org data update (https://earthindicators.org)"}


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e_:
            e = e_
            print(f"  {url}: {e}; retry {attempt + 1}", flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"download failed: {url} ({e})")


def gistemp():
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    out = {}
    for row in csv.reader(io.StringIO(get(url))):
        if row and re.fullmatch(r"\d{4}", row[0].strip()):
            y = int(row[0])
            for m in range(1, 13):
                v = row[m].strip() if m < len(row) else ""
                if v and "*" not in v:
                    out[f"{y}-{m:02d}"] = float(v)
    return out, url


def noaa():
    base = "https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/"
    # version folders, linked as "v6.1/" or with the full path
    vers = sorted(set(re.findall(r'href="(?:[^"]*/)?v(\d+(?:\.\d+)*)/?"', get(base))), key=lambda v: [int(x) for x in v.split(".")])
    if not vers:
        raise RuntimeError("no versions listed")
    for v in reversed(vers):      # newest version that has a monthly global land-ocean series
        d = f"{base}v{v}/access/timeseries/"
        try:
            names = re.findall(r'(aravg\.mon\.land_ocean\.90S\.90N\.v[\d.]+?\.(\d{6})\.asc)', get(d))
        except RuntimeError:
            continue
        if names:
            fn = max(names, key=lambda n: n[1])[0]
            out = {}
            for line in get(d + fn).splitlines():
                p = line.split()
                if len(p) >= 3 and re.fullmatch(r"\d{4}", p[0]) and re.fullmatch(r"\d{1,2}", p[1]):
                    v_ = float(p[2])
                    if v_ > -900:
                        out[f"{int(p[0])}-{int(p[1]):02d}"] = v_
            return out, d + fn
    raise RuntimeError(f"no time series file found (versions {vers})")


def hadcrut():
    # newest version named on the HadCRUT5 pages (HadCRUT.5.2.0.0 in 2026); its global monthly analysis series
    site = "https://www.metoffice.gov.uk/hadobs/hadcrut5/"
    seen = set(["5.2.0.0"])
    for page in (site, site + "data/download.html", site + "data/versions/"):
        try:
            seen |= set(re.findall(r"HadCRUT\.(\d+\.\d+\.\d+\.\d+)", get(page)))
        except RuntimeError:
            pass
    errs = []
    for v in sorted(seen, key=lambda v: [int(x) for x in v.split(".")], reverse=True):
        url = f"{site}data/HadCRUT.{v}/analysis/diagnostics/HadCRUT.{v}.analysis.summary_series.global.monthly.csv"
        try:
            text = get(url)
        except RuntimeError as e:
            errs.append(v); continue
        out = {}
        for row in csv.reader(io.StringIO(text)):
            if row and re.fullmatch(r"\d{4}-\d{2}", row[0].strip()) and len(row) > 1 and row[1].strip():
                out[row[0].strip()] = float(row[1])
        if out:
            return out, url
    raise RuntimeError(f"no HadCRUT5 file found (tried {errs})")


def berkeley():
    # Since 2025 Berkeley Earth updates only its high-resolution (0.25°) product; its global monthly series is here.
    # Anomalies vs 1951-1980; over sea ice, air temperature where ice is present (one series, no second section).
    url = "https://storage.googleapis.com/berkeley-earth-temperature-hr/global/Global_TAVG_monthly.txt"
    out = {}
    for line in get(url).splitlines():
        p = line.split()
        if len(p) >= 3 and not line.lstrip().startswith("%") and re.fullmatch(r"\d{4}", p[0]) and re.fullmatch(r"\d{1,2}", p[1]):
            k = f"{int(p[0])}-{int(p[1]):02d}"
            if k not in out and p[2].lower() != "nan":
                out[k] = float(p[2])
    return out, url


RECORDS = [("gistemp", gistemp, 1880), ("noaa", noaa, 1850), ("hadcrut", hadcrut, 1850), ("berkeley", berkeley, 1850)]


def check(name, s, first):
    """Plausible monthly anomalies, starting when the record does and reaching the last few months."""
    if len(s) < 12 * 100:
        raise ValueError(f"only {len(s)} months")
    if min(s) > f"{first}-12":
        raise ValueError(f"starts {min(s)}, expected {first}")
    t = date.today()
    lag = (t.year * 12 + t.month) - (int(max(s)[:4]) * 12 + int(max(s)[5:]))
    if lag > 5:
        raise ValueError(f"last month {max(s)}, {lag} months old")
    bad = [k for k, v in s.items() if not -4 < v < 4]
    if bad:
        raise ValueError(f"implausible values in {bad[:3]}")
    # 1991-2020 must be complete: the page's baseline
    miss = [f"{y}-{m:02d}" for y in range(1991, 2021) for m in range(1, 13) if f"{y}-{m:02d}" not in s]
    if miss:
        raise ValueError(f"1991-2020 incomplete ({len(miss)} months missing)")


def main():
    old, olds = {}, {}
    if os.path.exists(OUT):
        with open(OUT) as fh:
            for r in csv.DictReader(fh):
                for k, v in r.items():
                    if k != "month" and v != "":
                        old.setdefault(k, {})[r["month"]] = float(v)
    if os.path.exists(SRC):
        for line in open(SRC):
            if ": " in line:
                k, u = line.rstrip("\n").split(": ", 1)
                olds[k] = u
    cols, srcs, ok = {}, {}, 0
    for name, fn, first in RECORDS:
        try:
            s, url = fn()
            check(name, s, first)
            cols[name], srcs[name] = s, url
            ok += 1
            print(f"{name}: {min(s)} to {max(s)}, {len(s)} months ({url})", flush=True)
        except Exception as e:
            print(f"{name}: FAILED ({e}); keeping the previous values", flush=True)
            prev = olds.get(name, "").split(" [")[0]
            cols[name], srcs[name] = old.get(name, {}), f"{prev} [{date.today()}: update failed, previous values kept: {str(e)[:200]}]".strip()
    if not ok:
        sys.exit("every record failed; nothing written")
    months = sorted(set().union(*cols.values()))
    with open(OUT + ".part", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["month"] + [n for n, _, _ in RECORDS])
        for m in months:
            w.writerow([m] + [("%.3f" % cols[n][m]) if m in cols[n] else "" for n, _, _ in RECORDS])
    os.replace(OUT + ".part", OUT)
    with open(SRC, "w") as fh:
        fh.write("# Files used for data/temp_records_monthly.csv (each record as published, on its own baseline)\n")
        for n, _, _ in RECORDS:
            fh.write(f"{n}: {srcs[n]}\n")
    print(f"wrote {OUT}: {months[0]} to {months[-1]}")


if __name__ == "__main__":
    main()
