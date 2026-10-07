#!/usr/bin/env python3
"""Sea-ice volume for the Arctic and Antarctic from Copernicus Marine.

--source glorys   Monthly volume from Mercator's GLORYS12 reanalysis (1993 to ~2-3 months ago).
                  Their real-time system is not used: it runs clearly lower than the reanalysis.
--source cs2smos   Weekly volume (every Monday) from the CryoSat-2 + SMOS satellite thickness product.
                  Only the cold season has data (Arctic Oct-Apr, Antarctic roughly Apr-Oct); empty days
                  are stored with a blank volume and coverage 0 so they are not fetched again.
                  Copernicus only keeps a rolling window of this near-real-time data online, so the
                  cache file IS the history: rows are never deleted.

Volume = sum over grid cells of thickness x concentration x cell area. Thickness in these products
is the thickness of the ice where there is ice, so multiplying by concentration gives the amount
of ice per cell. Output in thousand km3; ice area (sum of concentration x cell area) in million km2.

Login: environment variables COPERNICUSMARINE_SERVICE_USERNAME / _PASSWORD (GitHub secrets).
Progress is saved after every year (glorys) or every few weeks (cs2smos), so a run that is cut
short continues where it stopped next time.
"""
import argparse, csv, os, sys, time
from datetime import date

import numpy as np

R = 6371.0                                          # Earth radius, km
POLES = {"north": (40.0, 90.0),                     # 40N includes the Sea of Okhotsk ice
         "south": (-80.0, -50.0)}                   # GLORYS ends at 80S; sea ice never reaches 50S

GLORYS_MY = "cmems_mod_glo_phy_my_0.083deg_P1M-m"
GLORYS_ANFC = "cmems_mod_glo_phy_anfc_0.083deg_P1M-m"
CS2SMOS = {"north": "esa_obs-si_arc_phy-sit_nrt_l4-multi_P1D-m",
           "south": "esa_obs-si_ant_phy-sit_nrt_l4-multi_P1D-m"}
CS_VARS = ["sea_ice_thickness", "sea_ice_concentration", "sea_ice_thickness_uncertainty"]


# ---------- helpers ----------
def retry(what, fn, tries=4):
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            print(f"  {what} failed ({e}); retry {attempt + 1}", flush=True)
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"{what} failed after {tries} tries")


def open_ds(dataset_id, variables, pole):
    import copernicusmarine as cm
    lo, hi = POLES[pole]
    # Copernicus stores each dataset twice: chunked as maps ("geo-series") and as long series per
    # location ("time-series"). We always read whole maps, so force the map layout; otherwise the
    # tool may pick the time-series copy and download years of data to get one day.
    return retry(f"open {dataset_id}", lambda: cm.open_dataset(
        dataset_id=dataset_id, variables=variables, service="arco-geo-series",
        minimum_latitude=lo, maximum_latitude=hi))


def cell_area(lat, lon):
    """km2 per cell of a regular latitude-longitude grid (spacing may be uneven)."""
    if lat.ndim != 1 or lon.ndim != 1:
        raise RuntimeError("expected a latitude-longitude grid; this dataset uses another projection")
    dlat = np.deg2rad(np.abs(np.gradient(lat)))
    dlon = np.deg2rad(np.abs(np.gradient(lon)))
    return R ** 2 * (np.cos(np.deg2rad(lat)) * dlat)[:, None] * dlon[None, :]


def frac(c):
    c = np.nan_to_num(np.asarray(c, dtype="float64"))
    return c / 100.0 if c.max() > 1.5 else c        # some products give percent, some a fraction


def vol(h, c, area):
    """thousand km3: thickness m -> km (/1e3), km3 -> thousand km3 (/1e3)."""
    return float((np.nan_to_num(np.asarray(h, dtype="float64")) * c * area).sum()) / 1e6


def iso(t):
    return str(np.datetime_as_string(np.datetime64(t, "D")))


def load_cache(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as fh:
        return {(r["date"], r["pole"]): r for r in csv.DictReader(fh)}


def save_cache(path, rows, fields):
    tmp = path + ".tmp"                             # write to a temp file first: a crash never
    with open(tmp, "w", newline="") as fh:          # leaves a half-written data file behind
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({f: rows[k].get(f, "") for f in fields})
    os.replace(tmp, path)


# ---------- GLORYS (model) ----------
G_FIELDS = ["date", "pole", "volume", "area", "src"]


def glorys_month(sub, area):
    c = frac(sub["siconc"].values)
    return {"volume": f"{vol(sub['sithick'].values, c, area):.3f}",
            "area": f"{float((c * area).sum()) / 1e6:.3f}"}


def run_glorys(path):
    rows = load_cache(path)
    for pole in POLES:
        print(f"== GLORYS {pole}", flush=True)
        my = open_ds(GLORYS_MY, ["sithick", "siconc"], pole)
        area = cell_area(my["latitude"].values, my["longitude"].values)
        months = [iso(t)[:7] + "-01" for t in my["time"].values]
        my_end = max(months)
        for year in sorted({m[:4] for m in months}):
            need = [m for m in months if m[:4] == year and rows.get((m, pole), {}).get("src") != "my"]
            if not need:
                continue
            sub = retry(f"load {year}", lambda: my.sel(time=slice(f"{year}-01-01", f"{year}-12-31")).load())
            for i, t in enumerate(sub["time"].values):
                m = iso(t)[:7] + "-01"
                rows[(m, pole)] = {"date": m, "pole": pole, "src": "my", **glorys_month(sub.isel(time=i), area)}
            save_cache(path, rows, G_FIELDS)
            print(f"  {year}: {len(need)} months", flush=True)

        print(f"  reanalysis up to {my_end}", flush=True)

    # The real-time system ("anfc") turned out to run 1-4 thousand km3 lower than the reanalysis in
    # the same months (seam check, Oct 2026), so it is not used: remove rows an earlier version added.
    for k in [k for k, r in rows.items() if r.get("src") == "anfc"]:
        del rows[k]
    save_cache(path, rows, G_FIELDS)


# ---------- CryoSat-2 + SMOS (satellite) ----------
C_FIELDS = ["date", "pole", "volume", "volume_unc", "area", "coverage"]
ARCTIC_SEASON = {10, 11, 12, 1, 2, 3, 4}            # summer melt ponds blind the radar (May-September)


def run_cs2smos(path, max_days):
    rows = load_cache(path)
    done = 0
    for pole in POLES:
        print(f"== CS2SMOS {pole}", flush=True)
        ds = open_ds(CS2SMOS[pole], CS_VARS, pole)
        area = cell_area(ds["latitude"].values, ds["longitude"].values)
        days = sorted({iso(t) for t in ds["time"].values})
        if pole == "north":                         # drop summer rows a previous version stored
            for k in [k for k in rows if k[1] == "north" and int(k[0][5:7]) not in ARCTIC_SEASON]:
                del rows[k]
        # new Mondays, plus rows from the previous version that have no coverage value yet
        mondays = [d for d in days if date.fromisoformat(d).weekday() == 0
                   and not rows.get((d, pole), {}).get("coverage")
                   and (pole == "south" or int(d[5:7]) in ARCTIC_SEASON)]
        print(f"  online {days[0] if days else '-'} to {days[-1] if days else '-'}; new Mondays: {len(mondays)}", flush=True)
        for n, d in enumerate(mondays, 1):
            if done >= max_days:
                print("  day budget reached; continuing next run", flush=True)
                break
            t0 = time.time()
            sub = retry(f"load {d}", lambda: ds.sel(time=d).load())
            if "time" in sub.dims:
                sub = sub.isel(time=0)
            c = frac(sub["sea_ice_concentration"].values)
            h = np.asarray(sub["sea_ice_thickness"].values, dtype="float64")
            # coverage: share of the ice-covered area (concentration >= 15%) that has a thickness value.
            # Cells without one count as zero in the volume, so low coverage means too low a volume.
            ice = c >= 0.15
            ice_area = float((area * ice).sum())
            cov = float((area * (ice & np.isfinite(h))).sum()) / ice_area if ice_area else 0.0
            if cov == 0.0:                          # no data that day: keep a row so it isn't retried
                rows[(d, pole)] = {"date": d, "pole": pole, "volume": "", "volume_unc": "", "area": "",
                                   "coverage": "0.000"}
                print(f"  {d}: no thickness data", flush=True)
                done += 1
                continue
            rows[(d, pole)] = {"date": d, "pole": pole, "coverage": f"{cov:.3f}",
                               "volume": f"{vol(sub['sea_ice_thickness'].values, c, area):.3f}",
                               # errors partly share causes (snow on the ice), so add them up in full:
                               # a cautious, upper-bound uncertainty band
                               "volume_unc": f"{vol(sub['sea_ice_thickness_uncertainty'].values, c, area):.3f}",
                               "area": f"{float((c * area).sum()) / 1e6:.3f}"}
            done += 1
            print(f"  {d}: {rows[(d, pole)]['volume']} thousand km3, coverage {cov:.0%} ({time.time() - t0:.0f} s)", flush=True)
            if n % 5 == 0:
                save_cache(path, rows, C_FIELDS)
        save_cache(path, rows, C_FIELDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["glorys", "cs2smos"], required=True)
    ap.add_argument("--max-days", type=int, default=200, help="cs2smos: max new days per run")
    a = ap.parse_args()
    os.makedirs("data", exist_ok=True)
    if a.source == "glorys":
        run_glorys("data/seaice_volume_glorys.csv")
    else:
        run_cs2smos("data/seaice_volume_cs2smos.csv", a.max_days)


if __name__ == "__main__":
    sys.exit(main())
