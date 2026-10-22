#!/usr/bin/env python3
"""Marine heatwaves: the share of the ocean (60°S-60°N) in a marine heatwave each day, since 1982, for the SST page.

Definition (Hobday et al. 2016, Progress in Oceanography 141, 227-238; the standard one): at a point of the ocean, a
marine heatwave is a spell of at least 5 days in a row warmer than the 90th percentile for that time of year (the
"threshold"); spells separated by 2 days or less count as one. Threshold and climatology are calculated per point and
day of the year from 1991-2020, pooling the days within ±5 days of the date, then smoothed with a 31-day running mean.
Categories (Hobday et al. 2018, Oceanography 31(2)): how far above normal, in multiples of the gap between the
threshold and normal: 1-2× moderate, 2-3× strong, 3-4× severe, 4× and more extreme.

Source: NOAA OISST v2.1 daily (0.25°) from NOAA PSL's OPeNDAP server, every 8th grid point (a 2° sample, as a
lighter load than the full grid; heatwaves are usually hundreds of km across), 60°S-60°N. Points and days where
the threshold is below -1.2 °C (sea ice season) are never counted as in a heatwave.

The first run downloads 1982 to now once (about 700 MB in pieces) and saves the 1991-2020 threshold and climatology
(data/mhw_threshold.npz). After that, each run only downloads the last 75 days and rewrites the last 50: OISST's
preliminary values become final after about two weeks, and a heatwave's first days are only known once it has
lasted 5 days.

  -> data/mhw_daily.csv  date, share (% of the ocean area in a heatwave), moderate, strong, severe, extreme (% each;
     they add up to share)
"""
import csv, io, os, sys, time
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_nino34 import _open, _load   # same retry and back-off handling as the other OISST series

URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.day.mean.{year}.nc"
LAT = (-60, 60)
STRIDE = 8
BASE = (1991, 2020)
THR_FILE = "data/mhw_threshold.npz"
OUT = "data/mhw_daily.csv"
WINDOW, KEEP = 75, 50
ICE_T = -1.2


def fetch(year, since=None):
    """(list of dates, float32 array [day, lat, lon]) for one yearly file, from `since` on."""
    ds = None
    for engine in ("netcdf4", "pydap"):
        try:
            ds = _open(URL.format(year=year), engine); break
        except Exception as e:
            print(f"  {year}: {engine} failed ({e})", flush=True)
    if ds is None:
        raise RuntimeError(f"could not open {year}")
    lat = ds["lat"].values
    li = np.where((lat >= LAT[0]) & (lat <= LAT[1]))[0]
    sst = ds["sst"].isel(lat=slice(li.min(), li.max() + 1, STRIDE), lon=slice(0, None, STRIDE))
    times = ds["time"].values.astype("datetime64[D]")
    if since is not None:
        k = int(np.searchsorted(times, np.datetime64(since)))
        sst, times = sst.isel(time=slice(k, None)), times[k:]
    parts = [np.asarray(_load(sst.isel(time=slice(i, i + 30))).values, "float32") for i in range(0, sst.sizes["time"], 30)]
    arr = np.concatenate(parts) if parts else np.zeros((0, sst.sizes["lat"], sst.sizes["lon"]), "float32")
    return [t.astype(object) for t in times], arr, sst["lat"].values


def idx366(d):
    """Day of the year on a 366-day calendar: 28 Feb = 58, 29 Feb = 59, 1 Mar = 60 in every year."""
    k = d.timetuple().tm_yday - 1
    leap = d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)
    return k + 1 if (not leap and k >= 59) else k


def circ_smooth(a, n=31):
    """Running mean along axis 0 (366 days), wrapping round the year."""
    h = n // 2
    ext = np.concatenate([a[-h:], a, a[:h]])
    c = np.cumsum(np.concatenate([np.zeros((1,) + a.shape[1:]), ext]), axis=0)
    return (c[n:] - c[:-n]) / n


def thresholds(dates, T):
    """Climatology and 90th-percentile threshold per (366-day index, point) from the base period."""
    years = sorted({d.year for d in dates if BASE[0] <= d.year <= BASE[1]})
    B = np.full((len(years), 366, T.shape[1]), np.nan, "float32")
    for i, d in enumerate(dates):
        if BASE[0] <= d.year <= BASE[1]:
            B[d.year - years[0], idx366(d)] = T[i]
    clim = np.empty((366, T.shape[1]), "float32"); thr = np.empty_like(clim)
    for k in range(366):
        w = B[:, [(k + j) % 366 for j in range(-5, 6)]].reshape(-1, T.shape[1])
        with np.errstate(all="ignore"):
            clim[k] = np.nanmean(w, axis=0); thr[k] = np.nanpercentile(w, 90, axis=0)
    return circ_smooth(clim), circ_smooth(thr), len(years)


def in_event(e):
    """Days that belong to a heatwave, for one point: runs of >= 5 days above threshold, joined across gaps <= 2."""
    out = np.zeros(len(e), bool)
    if not e.any():
        return out
    d = np.diff(np.concatenate([[0], e.astype(np.int8), [0]]))
    st, en = np.where(d == 1)[0], np.where(d == -1)[0]          # run i covers st[i] .. en[i]-1
    keep = (en - st) >= 5
    st, en = st[keep], en[keep]
    for i in range(len(st)):
        out[st[i]:en[i]] = True
        if i and st[i] - en[i - 1] <= 2:
            out[en[i - 1]:st[i]] = True
    return out


def metrics(dates, T, clim, thr, w):
    """Per day: % of the ocean area in a heatwave, in total and by category."""
    K = np.array([idx366(d) for d in dates])
    C, H = clim[K], thr[K]
    with np.errstate(invalid="ignore"):
        E = (T > H) & (H >= ICE_T) & np.isfinite(T)
        ratio = (T - C) / np.maximum(H - C, 1e-3)
    ev = np.zeros_like(E)
    for j in range(T.shape[1]):
        ev[:, j] = in_event(E[:, j])
    cat = np.clip(np.floor(np.nan_to_num(ratio, nan=1.0)), 1, 4).astype(np.int8)
    tot = w.sum()
    rows = []
    for i, d in enumerate(dates):
        m = ev[i]
        r = [100 * float(w[m & (cat[i] == c)].sum()) / tot for c in (1, 2, 3, 4)]
        rows.append([d.isoformat(), f"{sum(r):.2f}"] + [f"{x:.2f}" for x in r])
    return rows


def load_rows():
    if not os.path.exists(OUT):
        return {}
    return {r[0]: r for r in csv.reader(open(OUT)) if r and r[0][:1].isdigit()}


def save_rows(rows):
    buf = io.StringIO(); wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(["date", "share", "moderate", "strong", "severe", "extreme"])
    for k in sorted(rows):
        wr.writerow(rows[k])
    with open(OUT + ".tmp", "w") as fh:
        fh.write(buf.getvalue())
    os.replace(OUT + ".tmp", OUT)


def main():
    today = date.today()
    if not os.path.exists(THR_FILE) or not os.path.exists(OUT):
        print("No threshold yet: downloading 1982 to now once", flush=True)
        D, A, lat = [], [], None
        for y in range(1982, today.year + 1):
            t0 = time.time()
            ds, arr, lat = fetch(y)
            D += ds; A.append(arr)
            print(f"  {y}: {len(ds)} days, {time.time() - t0:.0f} s", flush=True)
        A = np.concatenate(A)
        ocean = np.isfinite(A).mean(axis=0) > 0.5                 # points with SST on most days
        jj, ii = np.where(ocean)
        T = A[:, jj, ii]; del A
        clim, thr, ny = thresholds(D, T)
        np.savez_compressed(THR_FILE + ".tmp.npz", clim=np.round(clim * 100).astype(np.int16),
                            thr=np.round(thr * 100).astype(np.int16), jj=jj.astype(np.int16), ii=ii.astype(np.int16),
                            lat=lat.astype("float32"), base=np.array(BASE), stride=STRIDE)
        os.replace(THR_FILE + ".tmp.npz", THR_FILE)
        print(f"Threshold from {ny} base years, {len(jj)} ocean points", flush=True)
        w = np.cos(np.radians(lat[jj]))
        rows = {r[0]: r for r in metrics(D, T, clim, thr, w)}
        save_rows(rows)
        print(f"{len(rows)} days, {min(rows)} to {max(rows)}; last share {rows[max(rows)][1]}%", flush=True)
        return
    z = np.load(THR_FILE)
    clim, thr, jj, ii, lat = z["clim"] / 100.0, z["thr"] / 100.0, z["jj"], z["ii"], z["lat"]
    rows = load_rows()
    start = date.fromisoformat(max(rows)) - timedelta(days=WINDOW - 1)
    D, A = [], []
    for y in range(start.year, today.year + 1):
        try:
            ds, arr, _ = fetch(y, since=start if y == start.year else None)
        except Exception as e:
            if y == today.year and D:          # the new year's file may not exist yet in early January
                print(f"  {y}: {e}", flush=True); break
            raise
        D += ds; A.append(arr)
    T = np.concatenate(A)[:, jj, ii]
    new = metrics(D, T, clim, thr, np.cos(np.radians(lat[jj])))
    cut = (D[0] + timedelta(days=WINDOW - KEEP)).isoformat()
    n = 0
    for r in new:
        if r[0] >= cut:
            n += rows.get(r[0]) != r; rows[r[0]] = r
    save_rows(rows)
    print(f"Updated {len(new)} days from {D[0]} to {D[-1]} ({n} rows changed); last share {rows[max(rows)][1]}%", flush=True)


if __name__ == "__main__":
    # a one-line result in data/mhw_check.txt, so a run can be checked without opening the Actions log
    import traceback
    try:
        main()
        msg = f"ok {date.today()}: " + (open(OUT).read().strip().splitlines()[-1] if os.path.exists(OUT) else "no output")
    except Exception as e:
        msg = f"failed {date.today()}: {e}\n" + traceback.format_exc()[-1500:]
        print(msg, flush=True)
        open("data/mhw_check.txt", "w").write(msg + "\n")
        sys.exit(1)
    open("data/mhw_check.txt", "w").write(msg + "\n")
