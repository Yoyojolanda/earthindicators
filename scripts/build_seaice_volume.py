#!/usr/bin/env python3
"""Sea-ice volume for the Arctic and Antarctic from Copernicus Marine.

--source glorys   Monthly volume from Mercator's GLORYS12 reanalysis (1993 to ~3 months ago),
                  extended to the latest month with Mercator's real-time analysis ("anfc").
                  Each month records which of the two it came from (src = my / anfc); an anfc month
                  is replaced by the reanalysis value once that becomes available.
--source cs2smos   Weekly volume (every Monday) from the CryoSat-2 + SMOS satellite thickness product.
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
    return retry(f"open {dataset_id}", lambda: cm.open_dataset(
        dataset_id=dataset_id, variables=variables,
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


def run_glorys(path, check_path):
    rows = load_cache(path)
    checks = []
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

        # Real-time analysis: newer months, plus the last 12 overlapping months to check for a jump
        an = open_ds(GLORYS_ANFC, ["sithick", "siconc"], pole)
        an_area = cell_area(an["latitude"].values, an["longitude"].values)
        an_months = [iso(t)[:7] + "-01" for t in an["time"].values]
        overlap = [m for m in an_months if m <= my_end][-12:]
        newer = [m for m in an_months if m > my_end]
        for m in overlap + newer:
            sub = retry(f"load anfc {m}", lambda: an.sel(time=m).load())
            val = glorys_month(sub, an_area)
            if m > my_end:
                rows[(m, pole)] = {"date": m, "pole": pole, "src": "anfc", **val}
            else:
                ref = float(rows[(m, pole)]["volume"])
                checks.append(f"{pole} {m}  reanalysis {ref:7.3f}  real-time {float(val['volume']):7.3f}"
                              f"  diff {float(val['volume']) - ref:+.3f} thousand km3")
        save_cache(path, rows, G_FIELDS)
        print(f"  real-time months added: {len(newer)}", flush=True)

    with open(check_path, "w") as fh:
        fh.write(f"GLORYS seam check, {date.today()}: same months from both systems\n" + "\n".join(checks) + "\n")
    print("\n".join(checks))


# ---------- CryoSat-2 + SMOS (satellite) ----------
C_FIELDS = ["date", "pole", "volume", "volume_unc", "area"]


def run_cs2smos(path, max_days):
    rows = load_cache(path)
    done = 0
    for pole in POLES:
        print(f"== CS2SMOS {pole}", flush=True)
        ds = open_ds(CS2SMOS[pole], CS_VARS, pole)
        area = cell_area(ds["latitude"].values, ds["longitude"].values)
        days = sorted({iso(t) for t in ds["time"].values})
        mondays = [d for d in days if date.fromisoformat(d).weekday() == 0 and (d, pole) not in rows]
        print(f"  online {days[0] if days else '-'} to {days[-1] if days else '-'}; new Mondays: {len(mondays)}", flush=True)
        for n, d in enumerate(mondays, 1):
            if done >= max_days:
                print("  day budget reached; continuing next run", flush=True)
                break
            sub = retry(f"load {d}", lambda: ds.sel(time=d).load())
            if "time" in sub.dims:
                sub = sub.isel(time=0)
            c = frac(sub["sea_ice_concentration"].values)
            rows[(d, pole)] = {"date": d, "pole": pole,
                               "volume": f"{vol(sub['sea_ice_thickness'].values, c, area):.3f}",
                               # errors partly share causes (snow on the ice), so add them up in full:
                               # a cautious, upper-bound uncertainty band
                               "volume_unc": f"{vol(sub['sea_ice_thickness_uncertainty'].values, c, area):.3f}",
                               "area": f"{float((c * area).sum()) / 1e6:.3f}"}
            done += 1
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
        run_glorys("data/seaice_volume_glorys.csv", "data/seaice_volume_seam_check.txt")
    else:
        run_cs2smos("data/seaice_volume_cs2smos.csv", a.max_days)


if __name__ == "__main__":
    sys.exit(main())
