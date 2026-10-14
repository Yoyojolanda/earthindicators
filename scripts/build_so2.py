#!/usr/bin/env python3
"""Sulfur dioxide (SO2) emissions for the "Cleaner air" section of eei.html, from CEDS.

CEDS (Community Emissions Data System, Hoesly et al.) is an emissions inventory: emissions are calculated from fuel
use, sulfur content and pollution controls, and checked against national reports. It is published on Zenodo about once
a year. Its aggregate archive is large (~60 MB) and slow to download, so the workflow first asks Zenodo for the newest
version and only downloads when it differs from data/so2_ceds_source.txt.

Writes data/so2_ceds.csv: year, then kt SO2 per year for the world, China, India, the US, the EU and UK, and
international shipping (from 1950).

Usage: python3 scripts/build_so2.py check          -> prints the newest version's archive URL, or nothing if up to date
       python3 scripts/build_so2.py build ZIP VER  -> extracts the series from the downloaded archive
"""
import csv, io, json, sys, urllib.request, zipfile, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'so2_ceds_source.txt'
RECORD = 'https://zenodo.org/api/records/15059443/versions/latest'     # any CEDS record id; "latest" follows new versions
EU_UK = 'aut bel bgr hrv cyp cze dnk est fin fra deu grc hun irl ita lva ltu lux mlt nld pol prt rou svk svn esp swe gbr'.split()
FIRST = 1950

def check():
    d = json.load(urllib.request.urlopen(RECORD, timeout=60))
    ver = d['metadata'].get('version') or str(d['id'])
    old = SRC.read_text().split('\n')[0].strip() if SRC.exists() else ''
    f = next(f for f in d['files'] if f['key'].endswith('_aggregate.zip'))
    if ver != old: print(f['links']['self'], ver)

def rows(z, pattern):
    name = next(n for n in z.namelist() if pattern in n and not n.startswith('__MACOSX') and n.endswith('.csv'))
    r = csv.reader(io.TextIOWrapper(z.open(name), encoding='utf-8'))
    head = next(r)
    years = [int(h[1:]) for h in head[3:]]
    return name, years, list(r)

def build(zpath, ver):
    z = zipfile.ZipFile(zpath)
    _, years, sect = rows(z, 'SO2_CEDS_global_estimates_by_sector_v')
    _, years2, ctry = rows(z, 'SO2_CEDS_estimates_by_country_v')
    assert years == years2
    def total(rs): return [sum(float(r[3 + i] or 0) for r in rs) for i in range(len(years))]
    world = total(sect)
    ship = total([r for r in sect if r[1] == '1A3di_International-shipping'])
    by = {}
    for r in ctry: by.setdefault(r[1].lower(), []).append(r)
    cols = {'world': world, 'china': total(by['chn']), 'india': total(by['ind']), 'usa': total(by['usa']),
            'eu_uk': total([r for c in EU_UK for r in by.get(c, [])]), 'shipping': ship}
    assert max(world) > 100000 and max(ship) > 1000, 'unexpected values'
    out = ROOT / 'data' / 'so2_ceds.csv'
    with open(out, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['year'] + [k + '_kt' for k in cols])
        for i, y in enumerate(years):
            if y >= FIRST: w.writerow([y] + [round(cols[k][i]) for k in cols])
    SRC.write_text(f'{ver}\nCEDS {ver}, Hoesly et al., Zenodo record via {RECORD}\n')
    print('wrote', out, years[0], '-', years[-1], 'world last:', round(world[-1]), 'kt')

if __name__ == '__main__':
    if sys.argv[1] == 'check': check()
    else: build(sys.argv[2], sys.argv[3])
