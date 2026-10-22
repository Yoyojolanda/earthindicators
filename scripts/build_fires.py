#!/usr/bin/env python3
"""Weekly CO2 emissions from fires, for the wildfires page: the Global Wildfire Information System (GWIS, run by the
European Commission's Joint Research Centre within Copernicus), from its statistics portal's public API, for the
world, continents, large regions and the countries with the most fire emissions.

GWIS splits every year into 52 weeks counted from 1 January (week 1 = 1-7 January, ..., week 52 = 24-30 December;
31 December is not counted) and publishes each week's emissions per area, in metric tons. The API returns one
calendar year per request.

Output: data/fires_weekly.csv  region, year, w1 ... w52 (thousand metric tons of CO2; empty = not yet published)
        data/fires_status.json  latest week, when new data last arrived, regions
First run downloads every region and year from 2003 (about 400 small requests); later runs fetch only the current
year (and last year, during January, when its last weeks can still arrive), so a run is ~15 requests.
"""
import csv, json, os, sys, time, urllib.request
from datetime import date, timedelta

API = "https://api2.effis.emergency.copernicus.eu/statistics/v2/emissions/"
OUT, STATUS = "data/fires_weekly.csv", "data/fires_status.json"
FIRST = 2003
# (code, name, kind): kind "aoi" = a GWIS region, "country" = an ISO3 country code
REGIONS = [
    ("WORLD", "World", "aoi"),
    ("N_AME", "North America", "aoi"), ("CAN", "Canada", "country"), ("USA", "United States", "country"),
    ("S_AME", "South America", "aoi"), ("BRA", "Brazil", "country"), ("BLA", "Brazil's Legal Amazon", "aoi"),
    ("UN_AFR", "Africa", "aoi"),
    ("UN_EUR", "Europe", "aoi"), ("RUS", "Russia", "country"),
    ("UN_ASI", "Asia", "aoi"), ("IDN", "Indonesia", "country"),
    ("UN_OCE", "Oceania", "aoi"), ("AUS", "Australia", "country"),
    ("AMAP", "The Arctic (AMAP area)", "aoi"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "earthindicators.org data update (GitHub Actions)",
                                               "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            err = e
            print(f"  {url}: {e}; retry {attempt + 1}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {err}")


def weeks(code, kind, year):
    """52 weekly CO2 values (thousand tonnes) or None for weeks not published yet."""
    q = f"weeklyaoi?aoi={code}" if kind == "aoi" else f"weekly?country={code}"
    d = get(f"{API}{q}&year={year}")
    w = [r for r in d.get("emissionsweekly", []) if r.get("plt") == "CO2"]
    w.sort(key=lambda r: r["dt"])
    if len(w) != 52:
        raise RuntimeError(f"{code} {year}: {len(w)} weeks")
    out = [None if r.get("curv") is None else round(r["curv"] / 1000, 1) for r in w]
    if any(v is not None and v < 0 for v in out):
        raise RuntimeError(f"{code} {year}: negative values")
    return out


def main():
    old = {}
    if os.path.exists(OUT):
        with open(OUT) as fh:
            for r in csv.reader(fh):
                if r and r[0] != "region":
                    old[(r[0], int(r[1]))] = [None if v == "" else float(v) for v in r[2:]]
    status = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    today, this = date.today(), date.today().year
    redo = {this} | ({this - 1} if today.month == 1 else set())
    data, fails = dict(old), []
    for code, name, kind in REGIONS:
        for y in range(FIRST, this + 1):
            if (code, y) in old and y not in redo:
                continue
            try:
                v = weeks(code, kind, y)
            except Exception as e:
                print(f"::warning::{e}", flush=True); fails.append(f"{code} {y}"); continue
            if y < this and sum(x is None for x in v) > 2:   # a past year must be complete
                print(f"::warning::{code} {y}: incomplete ({sum(x is None for x in v)} weeks missing)", flush=True)
                fails.append(f"{code} {y}"); continue
            data[(code, y)] = v
        print(f"{name}: {sum(1 for k in data if k[0] == code)} years", flush=True)
    if not data:
        sys.exit("nothing downloaded")
    # the world series must exist for the current year, or the page has nothing new to show
    cur = data.get(("WORLD", this)) or data.get(("WORLD", this - 1))
    if not cur:
        sys.exit("no world series")
    rows = sorted(data.items(), key=lambda kv: ([r[0] for r in REGIONS].index(kv[0][0]) if kv[0][0] in [r[0] for r in REGIONS] else 99, kv[0][1]))
    with open(OUT + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["region", "year"] + [f"w{i}" for i in range(1, 53)])
        for (code, y), v in rows:
            w.writerow([code, y] + ["" if x is None else (f"{x:.1f}".rstrip("0").rstrip(".") if x else "0") for x in v])
    changed = not os.path.exists(OUT) or open(OUT).read() != open(OUT + ".tmp").read()
    os.replace(OUT + ".tmp", OUT)
    wy = this if data.get(("WORLD", this)) and any(x is not None for x in data[("WORLD", this)]) else this - 1
    last = max(i for i, x in enumerate(data[("WORLD", wy)]) if x is not None) + 1
    end = date(wy, 1, 1) + timedelta(days=7 * last - 1)
    status.update({"latest_week": last, "latest_year": wy, "through": end.isoformat(),
                   "new_data": today.isoformat() if changed else status.get("new_data", today.isoformat()),
                   "regions": [{"code": c, "name": n} for c, n, _ in REGIONS], "failed": fails,
                   "source": "https://gwis.jrc.ec.europa.eu/apps/gwis.statistics/seasonaltrend"})
    with open(STATUS, "w") as fh:
        json.dump(status, fh, indent=1)
    print(f"wrote {OUT}: world through week {last} of {wy} (ending {end}); {len(fails)} failed")


if __name__ == "__main__":
    main()
