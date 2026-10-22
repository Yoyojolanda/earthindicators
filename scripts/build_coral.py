#!/usr/bin/env python3
"""Coral reef heat stress, for the sea-surface temperature page: how many of the world's coral reef regions are under
bleaching-level heat stress, day by day since 1985.

Source: NOAA Coral Reef Watch (CRW), Daily 5km Regional Virtual Stations: about 220 reef regions worldwide, each a
polygon around a group of reefs, with a daily time series since 1985 (coralreefwatch.noaa.gov/product/vs/). We use the
last column, BAA_7day_max: the highest Bleaching Alert Area level in the region over the past 7 days:
  0 no stress, 1 Bleaching Watch, 2 Bleaching Warning, 3 Alert Level 1 (significant bleaching likely),
  4 Alert Level 2 (severe bleaching and significant mortality likely), 5-7 Alert Levels 3-5 (since CRW v3.1, 2023:
  multi-species mortality likely, up to near-complete mortality).
"Bleaching-level heat stress" = Alert Level 1 or higher, as in CRW's global bleaching reports.

Each station's levels are kept as one string of digits (one per day from 1 January 1985) in data/coral_baa.csv, so the
full files (about 1.3 MB each) are downloaded only once. Later runs fetch only the last ~100 days of each file
(an HTTP range request of a few kB), which also picks up CRW's revisions of recent days.

Output: data/coral_baa.csv          station, name, lat, lon, levels (digits; '-' = no data)
        data/coral_alert_daily.csv  date, stations, watch, warning, alert1, alert2, alert3plus (number of stations at
                                    each level that day; stations = stations with data)
        data/coral_status.json
"""
import csv, json, os, re, sys, time, urllib.request
from datetime import date, timedelta

BASE = "https://coralreefwatch.noaa.gov/product/vs/"
LIST_PAGES = [BASE + "data.php", BASE + "index.php", BASE + "map.php"]
OUT_BAA, OUT_DAILY, STATUS = "data/coral_baa.csv", "data/coral_alert_daily.csv", "data/coral_status.json"
START = date(1985, 1, 1)
TAIL = 9000          # bytes: ~100 days of rows
UA = {"User-Agent": "earthindicators.org data update (GitHub Actions)"}


def fetch(url, tail=None):
    h = dict(UA)
    if tail:
        h["Range"] = f"bytes=-{tail}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
                return r.read().decode("utf-8", "replace"), r.status
        except Exception as e:
            err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {err}")


def stations():
    """Station file names from CRW's pages (links like data/hawaii.txt)."""
    found = set()
    for u in LIST_PAGES:
        try:
            found |= set(re.findall(r"data/([A-Za-z0-9_\-]+)\.txt", fetch(u)[0]))
        except RuntimeError as e:
            print(f"  list page {u}: {e}", flush=True)
    return sorted(found)


def parse(text, head=True):
    """{date: level} from a station file (or from the tail of one: the first, cut line is skipped)."""
    out, meta = {}, {}
    if head:
        m = re.search(r"Name:\s*\n(.+?)\s*\n", text); meta["name"] = m.group(1).strip() if m else ""
        m = re.search(r"Longitude:\s*\n\s*(-?[\d.]+)", text); meta["lon"] = m.group(1) if m else ""
        m = re.search(r"Latitude:\s*\n\s*(-?[\d.]+)", text); meta["lat"] = m.group(1) if m else ""
    for line in text.splitlines():
        p = line.split()
        if len(p) == 10 and re.fullmatch(r"\d{4}", p[0]) and re.fullmatch(r"\d\d", p[1]) and re.fullmatch(r"\d\d", p[2]) and re.fullmatch(r"\d", p[9]):
            try:
                out[date(int(p[0]), int(p[1]), int(p[2]))] = int(p[9])
            except ValueError:
                pass
    return out, meta


def main():
    old = {}
    if os.path.exists(OUT_BAA):
        with open(OUT_BAA) as fh:
            for r in csv.DictReader(fh):
                old[r["station"]] = r
    names = stations()
    print(f"{len(names)} stations listed", flush=True)
    if len(names) < 150:
        if len(old) < 150:
            sys.exit(f"only {len(names)} stations listed and no saved data")
        print("::warning::station list incomplete; updating the saved stations only", flush=True)
        names = sorted(set(names) | set(old))
    today = date.today()
    ndays = (today - START).days + 1
    keep, fails, full = {}, [], 0
    for i, st in enumerate(names):
        rec = old.get(st)
        try:
            if rec and len(rec["levels"]) > 1000:
                text, status = fetch(f"{BASE}data/{st}.txt", tail=TAIL)
                lv, _ = parse(text, head=(status == 200))    # a server that ignores the range sends the whole file
                s = list(rec["levels"].ljust(ndays, "-")[:ndays])
                meta = rec
            else:
                text, _ = fetch(f"{BASE}data/{st}.txt")
                lv, meta = parse(text)
                if len(lv) < 5000:
                    raise RuntimeError(f"only {len(lv)} days")
                s = ["-"] * ndays
                full += 1
                time.sleep(0.5)
            for d, v in lv.items():
                k = (d - START).days
                if 0 <= k < ndays:
                    s[k] = str(v)
            keep[st] = {"station": st, "name": meta.get("name", ""), "lat": meta.get("lat", ""), "lon": meta.get("lon", ""), "levels": "".join(s).rstrip("-")}
        except Exception as e:
            print(f"::warning::{st}: {e}", flush=True); fails.append(st)
            if rec:
                keep[st] = rec
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(names)} ({full} full downloads)", flush=True)
    if len(keep) < 150:
        sys.exit(f"only {len(keep)} stations with data; nothing written")
    with open(OUT_BAA + ".tmp", "w", newline="") as fh:
        w = csv.DictWriter(fh, ["station", "name", "lat", "lon", "levels"], lineterminator="\n")
        w.writeheader(); [w.writerow(keep[k]) for k in sorted(keep)]
    os.replace(OUT_BAA + ".tmp", OUT_BAA)
    # daily counts: every day with data for at least 80% of the stations
    L = [r["levels"] for r in keep.values()]
    last = max(len(s) for s in L)
    rows = []
    for k in range(last):
        c = [0] * 8; n = 0
        for s in L:
            if k < len(s) and s[k] != "-":
                c[int(s[k])] += 1; n += 1
        if n >= 0.8 * len(L):
            rows.append([(START + timedelta(days=k)).isoformat(), n, c[1], c[2], c[3], c[4], sum(c[5:])])
    with open(OUT_DAILY + ".tmp", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["date", "stations", "watch", "warning", "alert1", "alert2", "alert3plus"]); w.writerows(rows)
    os.replace(OUT_DAILY + ".tmp", OUT_DAILY)
    st = {"through": rows[-1][0], "stations": len(keep), "failed": fails, "updated": today.isoformat(),
          "source": BASE}
    json.dump(st, open(STATUS, "w"), indent=1)
    print(f"wrote {OUT_DAILY}: {rows[0][0]} to {rows[-1][0]}, {len(keep)} stations, {full} full downloads, {len(fails)} failed")


if __name__ == "__main__":
    main()
