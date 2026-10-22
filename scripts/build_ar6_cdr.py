#!/usr/bin/env python3
"""IPCC AR6 pathways redrawn without large-scale CO2 removal (models page, section "Without the carbon-removal assumption").

Inputs are the IIASA AR6 Scenarios Database v1.1 files (free login at data.ece.iiasa.ac.at/ar6, so not fetched here and
not stored in the repo):
  AR6_Scenarios_Database_World_v1.1.csv               yearly emissions, CO2 removal by method, climate diagnostics
  AR6_Scenarios_Database_metadata_indicators_v1.1.xlsx sheet meta_Ch3vetted_withclimate: warming category per pathway

Method, per pathway in categories C1 (1.5 C, no or limited overshoot), C2 (1.5 C after high overshoot), C3 (2 C, >67%):
  * start from the IPCC's own warming: FaIR v1.6.2 median global surface air temperature (GSAT), above 1850-1900
  * "new-method" removal = BECCS (Carbon Sequestration|CCS|Biomass) + direct air capture + enhanced weathering, as
    reported by the pathway; removal by land (Carbon Sequestration|Land Use) is kept as the pathway has it
  * cap that removal at about today's level, 1 million metric tons a year (State of Carbon Dioxide Removal); the CO2 no
    longer removed stays in the air from 2021 on
  * extra warming = cumulative extra CO2 x TCRE, the IPCC AR6 WG1 best estimate of 0.45 C per 1000 billion metric tons
    (likely range 0.27-0.63, written as lo/hi). Warming follows cumulative CO2 with little delay (AR6 WG1 SPM D.1.1),
    so this is a close approximation, not a full rerun of the climate model.
  * the pathways' emission cuts and everything else are left unchanged: this answers "same cuts, but the removal does
    not happen", not "what would the model have chosen without removal"
Second correction ("and with the emissions that actually happened"): each pathway's total CO2 emissions (the IPCC's
harmonized and infilled series, fossil plus land use) for 2020 up to the last measured year are replaced by measured
emissions from the Indicators of Global Climate Change (Lamb et al., in Forster et al. 2026; data/models_outlook.json,
key ghg, fossil plus land-use CO2). The difference adds warming in the same way (TCRE). After the last measured year the
pathway starts late from where emissions really are: its own cuts (emissions before new-method removal, relative to its
2020 level) are applied to the last measured level, shifted by the years lost (2020 -> last measured year). New-method
removal stays capped. This series includes the removal correction and is the main redrawn line.
Methane: the pathways cut methane from 2020 as well, which has not happened either. Each pathway's methane emissions
(the IPCC's infilled series) are moved with the measured change since 2020 (IGCC methane, relative to 2020, so the two
inventories' different levels do not matter) up to the last measured year, then start the pathway's own methane cuts
late in the same way as CO2. Methane does not add up like CO2, so its extra warming comes from the simple climate model
FaIR v1.6.4 (default parameters, with ozone and stratospheric water vapour from methane): each pathway is run twice,
with its own and with the corrected methane (CO2 and N2O from the pathway, other species from RCP2.6), and the
difference is added. Needs: pip install fair==1.6.4.
Years between the pathways' 5- or 10-year steps are interpolated linearly.

Writes data/models_ar6_cdr.json: per category the median across pathways, year by year 2000-2100, of the IPCC warming
and of the redrawn warming (with lo/hi), plus summary numbers per pathway (medians of peaks, of 2100, share of pathways
below 1.5 C in 2100, cumulative new-method removal 2020-2100).

Run from the repo root: python scripts/build_ar6_cdr.py <World csv> <metadata xlsx>
"""
import json, sys
import numpy as np, pandas as pd

WORLD, META = sys.argv[1], sys.argv[2]
CATS = {"C1": "1.5 °C, no or limited overshoot", "C2": "1.5 °C after a high overshoot", "C3": "below 2 °C (at least two in three)"}
CH4 = "AR6 climate diagnostics|Infilled|Emissions|CH4"
N2O = "AR6 climate diagnostics|Infilled|Emissions|N2O"
CO2 = "AR6 climate diagnostics|Infilled|Emissions|CO2"
TEMP = "AR6 climate diagnostics|Surface Temperature (GSAT)|FaIRv1.6.2|50.0th Percentile"
NEW = ["Carbon Sequestration|CCS|Biomass", "Carbon Sequestration|Direct Air Capture", "Carbon Sequestration|Enhanced Weathering"]
CAP = 1.0                      # Mt CO2 a year: new-method removal today, about 1 million t (State of CDR)
TCRE = {"mid": 0.45, "lo": 0.27, "hi": 0.63}   # C per 1000 Gt CO2 (IPCC AR6 WG1)
Y0, Y1 = 2000, 2100

meta = pd.read_excel(META, sheet_name="meta_Ch3vetted_withclimate")
meta = meta[meta.Category.isin(CATS)][["Model", "Scenario", "Category"]]
parts = [c[c.Variable.isin([TEMP, CO2, CH4, N2O] + NEW)] for c in pd.read_csv(WORLD, chunksize=100000)]
d = pd.concat(parts).merge(meta, on=["Model", "Scenario"])
yrs = [str(y) for y in range(1995, Y1 + 1)]
key = ["Model", "Scenario", "Category"]


def wide(v):
    x = d[d.Variable == v].set_index(key)[yrs].astype(float)
    return x.T.interpolate(limit_area="inside").T


T = wide(TEMP).dropna(subset=[str(Y1)])
new = sum(wide(v).reindex(T.index).fillna(0) for v in NEW)
extra = (new - CAP).clip(lower=0)
extra.loc[:, [y for y in yrs if int(y) <= 2020]] = 0
cum = extra.cumsum(axis=1) / 1000.0            # Gt CO2
R = {k: T + cum * t / 1000.0 for k, t in TCRE.items()}
G = json.load(open("data/models_outlook.json"))["ghg"]
meas = {str(y): (G["co2_fossil"][i] + G["co2_land"][i]) * 1000 for i, y in enumerate(G["years"]) if y >= 2020}   # Mt
MY = sorted(meas)
# late start: from the year after the last measured one, the pathway's own cuts (its emissions before new-method
# removal, relative to its 2020 level) are applied to the last measured level, as if the pathway had started then
LAG = int(MY[-1]) - 2020
em = wide(CO2).reindex(T.index)
gross = em + new.reindex(em.index).fillna(0)                 # emissions without the new-method removal
late = pd.DataFrame(index=T.index, columns=yrs, dtype=float)
for y in yrs:
    yi = int(y)
    if yi < 2020: late[y] = em[y]
    elif str(yi) in meas: late[y] = meas[str(yi)]
    else: late[y] = meas[MY[-1]] * gross[str(yi - LAG)] / gross["2020"] - np.minimum(new[str(yi - LAG)], CAP)
gap = (late - em).fillna(0)
gap.loc[:, [y for y in yrs if int(y) < 2020]] = 0
gcum = gap.cumsum(axis=1) / 1000.0
R2 = {k: T + gcum * t / 1000.0 for k, t in TCRE.items()}

# methane: measured change since 2020, then the pathway's own cuts started late; extra warming from FaIR
# FaIR 1.6.4 predates numpy 2: some forcing functions return 1-element arrays that numpy 2 won't put into a scalar slot
import importlib, pkgutil, functools, fair.forcing as FF
def _sq(f):
    @functools.wraps(f)
    def g(*a, **k):
        r = f(*a, **k)
        return r.item() if isinstance(r, np.ndarray) and r.size == 1 else r
    return g
for m in pkgutil.iter_modules(FF.__path__):
    mod = importlib.import_module("fair.forcing." + m.name)
    for n in dir(mod):
        f = getattr(mod, n)
        if callable(f) and getattr(f, "__module__", "") == mod.__name__: setattr(mod, n, _sq(f))
from fair.forward import fair_scm
from fair.RCPs import rcp26
from fair.ancil import natural
mch4 = {str(y): G["ch4"][i] for i, y in enumerate(G["years"]) if y >= 2020}
ch4, n2o = wide(CH4).reindex(T.index), wide(N2O).reindex(T.index)
ch4c = ch4.copy()
for y in yrs:
    yi = int(y)
    if str(yi) in mch4: ch4c[y] = ch4["2020"] * mch4[str(yi)] / mch4["2020"]
    elif yi > int(MY[-1]): ch4c[y] = ch4["2020"] * mch4[MY[-1]] / mch4["2020"] * ch4[str(yi - LAG)] / ch4["2020"]
base = rcp26.Emissions.emissions[:2100 - 1765 + 1].copy()    # 1765-2100, RCP2.6 background
iy = 2015 - 1765


def run(co2, me, no):
    e = base.copy()
    e[iy:, 1], e[iy:, 2] = co2 / 3664.0, 0.0                # Mt CO2 -> Gt C, all in the fossil column
    e[iy:, 3], e[iy:, 4] = me, no / 1000.0 * 28.0 / 44.0   # Mt CH4; kt N2O -> Mt N2
    return fair_scm(emissions=e, natural=natural.Emissions.emissions[:len(e)], F_volcanic=0.0, F_solar=0.0)[2]   # no volcanoes or solar cycle: only the difference is used


col = [str(y) for y in range(2015, Y1 + 1)]
dch4 = pd.DataFrame(0.0, index=T.index, columns=yrs)
for ix in T.index:
    co2v, nov = em.loc[ix, col].values, n2o.loc[ix, col].values
    t0 = run(co2v, ch4.loc[ix, col].values, nov)
    t1 = run(co2v, ch4c.loc[ix, col].values, nov)
    dch4.loc[ix, col] = (t1 - t0)[iy:]
R2 = {k: v + dch4 for k, v in R2.items()}   # replaces the removal-only correction: includes it
out_yrs = [str(y) for y in range(Y0, Y1 + 1)]
r2 = lambda a: [round(float(v), 3) for v in a]

out = {"years": [Y0, Y1], "cap_mt": CAP, "tcre": TCRE, "measured_years": [int(MY[0]), int(MY[-1])], "measured_last_gt": round(meas[MY[-1]] / 1000, 1), "ch4_change_pct": round((mch4[MY[-1]] / mch4["2020"] - 1) * 100, 1), "delay_years": LAG, "categories": {}}
for c, name in CATS.items():
    o, n = T.xs(c, level="Category"), {k: v.xs(c, level="Category") for k, v in R.items()}
    m = {k: v.xs(c, level="Category") for k, v in R2.items()}
    cn = new.xs(c, level="Category")[[str(y) for y in range(2020, Y1 + 1)]].sum(axis=1) / 1000.0
    out["categories"][c] = {
        "name": name, "n": int(len(o)),
        "ipcc": r2(o[out_yrs].median()), "redrawn": r2(n["mid"][out_yrs].median()),
        "redrawn_lo": r2(n["lo"][out_yrs].median()), "redrawn_hi": r2(n["hi"][out_yrs].median()),
        "measured": r2(m["mid"][out_yrs].median()), "measured_lo": r2(m["lo"][out_yrs].median()), "measured_hi": r2(m["hi"][out_yrs].median()),
        "emissions_gt": {y: round(float(em.xs(c, level="Category")[y].median()) / 1000, 1) for y in ("2025", "2030")},
        "ch4_dt2100": round(float(dch4.xs(c, level="Category")[str(Y1)].median()), 3),
        "ch4_dtpeak": round(float(dch4.xs(c, level="Category").max(axis=1).median()), 3),
        "ch4_mt": {y: round(float(v.xs(c, level="Category")[y].median())) for v, y in ((ch4, "2030"),)},
        "ch4c_mt": {y: round(float(ch4c.xs(c, level="Category")[y].median())) for y in ("2024", "2030")},
        "gap_gt": round(float(gcum.xs(c, level="Category")[MY[-1]].median()), 1),
        "late_gt": round(float((late - em).xs(c, level="Category")[[str(y) for y in range(2020, Y1 + 1)]].sum(axis=1).median() / 1000)),
        "late_em_gt": {y: round(float(late.xs(c, level="Category")[y].median()) / 1000, 1) for y in ("2030", "2050")},
        "peak_measured": round(float(m["mid"].max(axis=1).median()), 2),
        "y2100_measured": {"mid": round(float(m["mid"][str(Y1)].median()), 2), "lo": round(float(m["lo"][str(Y1)].median()), 2), "hi": round(float(m["hi"][str(Y1)].median()), 2)},
        "below15_2100_measured": round(float((m["mid"][str(Y1)] < 1.5).mean()) * 100),
        "below2_peak": {"ipcc": round(float((o.max(axis=1) < 2).mean()) * 100), "measured": round(float((m["mid"].max(axis=1) < 2).mean()) * 100)},
        "removal_gt": {"p5": round(float(cn.quantile(.05))), "median": round(float(cn.median())), "p95": round(float(cn.quantile(.95)))},
        "peak": {"ipcc": round(float(o.max(axis=1).median()), 2), "redrawn": round(float(n["mid"].max(axis=1).median()), 2)},
        "y2100": {"ipcc": round(float(o[str(Y1)].median()), 2), "redrawn": round(float(n["mid"][str(Y1)].median()), 2),
                  "redrawn_lo": round(float(n["lo"][str(Y1)].median()), 2), "redrawn_hi": round(float(n["hi"][str(Y1)].median()), 2)},
        "below15_2100": {"ipcc": round(float((o[str(Y1)] < 1.5).mean()) * 100), "redrawn": round(float((n["mid"][str(Y1)] < 1.5).mean()) * 100)},
    }
json.dump(out, open("data/models_ar6_cdr.json", "w"), ensure_ascii=False, separators=(",", ":"))
for c, v in out["categories"].items():
    print(c, v["n"], v["removal_gt"], v["peak"], v["y2100"], v["below15_2100"], "| measured:", v["gap_gt"], v["peak_measured"], v["y2100_measured"], v["below15_2100_measured"], "ch4:", v["ch4_dtpeak"], v["ch4_dt2100"], v["ch4_mt"], v["ch4c_mt"])
