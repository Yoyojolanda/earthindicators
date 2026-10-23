#!/usr/bin/env python3
"""Observed coral bleaching, from the Global Coral Bleaching Database (for the coral reefs page).

van Woesik and Kratochwill 2022, "A global coral-bleaching database, 1980-2020", Scientific Data 9, 20
(doi:10.1038/s41597-022-01121-y); data at BCO-DMO, dataset 773466 (doi:10.26008/1912/bco-dmo.773466).
34,846 surveys at 14,405 sites in 93 countries, compiled from Reef Check, AGRRA, the Florida Reef Resilience Program,
Donner et al., McClanahan et al., Safaie et al. and Kumagai et al. Each survey gives the percentage of corals that were
bleached (some sources report categories, given as their midpoints, e.g. 11-50% as 30.5).

The database is a fixed compilation (it ends in 2020 and is not updated), so it is downloaded once; delete the output
to download it again.
  -> data/coral_bleaching_obs.csv  year, surveys (with a bleaching value), any (% of surveys with bleached corals),
     severe (% of surveys where more than half of the corals were bleached), mean (average % of corals bleached),
     atlantic, pacific, indian (% of surveys with bleaching per ocean, Red Sea and Arabian Gulf counted as Indian;
     empty when fewer than 30 surveys)
"""
import csv, io, os, sys, urllib.request
from collections import defaultdict

URL = "https://datadocs.bco-dmo.org/dataset/773466/file/B11vA82u7y2Owp/global_bleaching_environmental.csv"
OUT = "data/coral_bleaching_obs.csv"


def main():
    if os.path.exists(OUT):
        print(f"{OUT} exists; the database is not updated, nothing to do", flush=True)
        return
    req = urllib.request.Request(URL, headers={"User-Agent": "earthindicators.org data update (GitHub Actions)"})
    raw = urllib.request.urlopen(req, timeout=600).read().decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(raw)))
    print(f"{len(rows)} rows", flush=True)
    ocean = {"Atlantic": "atlantic", "Pacific": "pacific", "Indian": "indian", "Red Sea": "indian", "Arabian Gulf": "indian"}
    Y, O = defaultdict(list), defaultdict(lambda: defaultdict(list))
    seen = set()
    for r in rows:
        try:
            y, v = int(r["Date_Year"]), float(r["Percent_Bleaching"])
        except (ValueError, KeyError):
            continue
        key = (r.get("Sample_ID"), r.get("Site_ID"), y)          # one value per survey
        if key in seen:
            continue
        seen.add(key)
        Y[y].append(v)
        if r.get("Ocean_Name") in ocean:
            O[y][ocean[r["Ocean_Name"]]].append(v)
    out = []
    for y in sorted(Y):
        v = Y[y]
        if len(v) < 100:                                         # too few surveys to say anything for the year
            continue
        pc = lambda a: f"{100 * sum(1 for x in a if x > 0) / len(a):.1f}" if len(a) >= 30 else ""
        out.append([y, len(v), pc(v), f"{100 * sum(1 for x in v if x > 50) / len(v):.1f}", f"{sum(v) / len(v):.1f}",
                    pc(O[y]["atlantic"]), pc(O[y]["pacific"]), pc(O[y]["indian"])])
    if len(out) < 15:
        sys.exit(f"only {len(out)} years with enough surveys")
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["year", "surveys", "any", "severe", "mean", "atlantic", "pacific", "indian"]); w.writerows(out)
    for r in out:
        print(*r, flush=True)


if __name__ == "__main__":
    main()
