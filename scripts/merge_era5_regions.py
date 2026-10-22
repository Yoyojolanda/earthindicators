#!/usr/bin/env python3
"""Combine this run's regional ERA5 data with what another run pushed in the meantime, so neither is lost.

Used by the commit step of update-era5-regions.yml:  python scripts/merge_era5_regions.py /tmp/ours
- The repo files (just reset to the latest version on GitHub) are the other run's version.
- The folder holds this run's copies of the daily cache and the open-requests list.
Days present in both: this run's value wins. Open requests: both lists combined, minus months the cache
now has complete. The published JSON files and the overlap check are then rebuilt from the combined cache.
"""
import json, os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_era5_regions as b

ours = sys.argv[1]
rows = b.load_cache()                                   # the other run's days (repo)
n_theirs = len(rows)
mine = os.path.join(ours, os.path.basename(b.CACHE))
if os.path.exists(mine):
    repo_cache, b.CACHE = b.CACHE, mine
    rows.update(b.load_cache())                         # this run's days
    b.CACHE = repo_cache
b.save_cache(rows)

def complete(label):
    if "(" in label:                                    # a partial month, e.g. "2026-10 (1-2)"
        return False
    y, m = map(int, label.split("-"))
    return all(d in rows for d in b.month_days(y, m, date(9999, 1, 1)))

opn = {}
for p in (b.OPEN_FILE, os.path.join(ours, os.path.basename(b.OPEN_FILE))):
    if os.path.exists(p):
        opn.update(json.load(open(p)))
opn = {k: v for k, v in opn.items() if not complete(v.get("label", "0-0"))}
with open(b.OPEN_FILE + ".tmp", "w") as fh:
    json.dump(opn, fh, indent=1, sort_keys=True)
os.replace(b.OPEN_FILE + ".tmp", b.OPEN_FILE)

print(f"merged: {n_theirs} days already on GitHub, {len(rows)} after adding this run's; "
      f"{len(opn)} open requests kept; cache {min(rows)} to {max(rows)}", flush=True)
b.write_jsons(rows)
b.overlap_check(rows)
