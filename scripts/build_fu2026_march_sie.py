"""One-time build of data/models_march_sie_fu2026.csv.

Source: MarchSIE_historical_future.xlsx from github.com/CrystalCYFu/Bayes-paleo-weighting
(Fu, Osman & Aquino-Lopez 2026, Nature Geoscience, doi:10.1038/s41561-026-02123-w; CC BY-NC 4.0).
It holds Arctic March sea-ice extent for 27 CMIP5/CMIP6 models: historical runs (1850-2014) and
SSP1-2.6, SSP2-4.5, SSP5-8.5 (2006-2100), each computed on the model's native grid.

Output: per year, the plain (unweighted) model average and the 5th-95th percentile across models,
in million km2, with the number of models. Historical runs 1850-2005, then each scenario from 2005
(2005 repeated so the lines join), each model's historical run used for as long as it lasts.
The paper's paleo-weighted values are NOT in their repository, so they are not in this file.

Usage: python3 scripts/build_fu2026_march_sie.py path/to/MarchSIE_historical_future.xlsx
"""
import csv
import sys

import numpy as np
import openpyxl

src = sys.argv[1]
wb = openpyxl.load_workbook(src, read_only=True)
S = {}
for ws in wb.worksheets:
    rows = list(ws.iter_rows(values_only=True))
    names = rows[0][1:]
    S[ws.title] = {int(r[0]): {m: v / 1e6 for m, v in zip(names, r[1:]) if v is not None}
                   for r in rows[1:] if r[0]}


def merged(k, y):
    # per model: its historical run where it has one, else its scenario run (CMIP5 models switch
    # to their RCP run in 2006, CMIP6 models to their SSP run in 2015)
    d = dict(S[k].get(y, {})) if k != 'historical' else {}
    d.update(S['historical'].get(y, {}))
    return list(d.values())


def stats(v):
    return [round(float(np.mean(v)), 3), round(float(np.percentile(v, 5)), 3),
            round(float(np.percentile(v, 95)), 3), len(v)]


out = []
for y in range(1850, 2101):
    row = [y]
    row += stats(merged('historical', y)) if y <= 2005 else ['', '', '', '']
    for k in ('ssp1', 'ssp2', 'ssp5'):
        row += stats(merged(k, y)) if y >= 2005 else ['', '', '', '']
    out.append(row)

hdr = ['year']
for k in ('hist', 'ssp126', 'ssp245', 'ssp585'):
    hdr += [f'{k}_mean', f'{k}_p5', f'{k}_p95', f'{k}_n']
with open('data/models_march_sie_fu2026.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(hdr)
    w.writerows(out)
print(len(out), 'years written')
