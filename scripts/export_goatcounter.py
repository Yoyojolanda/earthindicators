"""Daily export of the GoatCounter visitor statistics into stats/ (public, like the dashboard).

Each run exports only the page views since the previous run (GoatCounter numbers every page view;
the last exported number is kept in stats/last_hit_id.txt) and adds them to one file per month, stats/goatcounter-YYYY-MM.csv.
Two columns are dropped before saving: the full browser identification string and the session ID.
Needs the secret GOATCOUNTER_TOKEN (a GoatCounter API token with export permission).
Run from the repo root: python scripts/export_goatcounter.py"""
import csv, gzip, io, json, os, sys, time, urllib.error, urllib.request
from datetime import date

SITE = "https://yoyojolanda.goatcounter.com"
TOKEN = os.environ.get("GOATCOUNTER_TOKEN", "")
OUT = "stats"
LAST = os.path.join(OUT, "last_hit_id.txt")
DROP = {"useragent", "user agent", "session"}          # not needed for statistics, so not published

def api(method, path, body=None, raw=False):
    req = urllib.request.Request(SITE + "/api/v0" + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:                   # show GoatCounter's own explanation, not just the code
        sys.exit(f"{method} {path} failed: HTTP {e.code} {e.reason}\n{e.read().decode('utf-8', 'replace')[:2000]}")
    return data if raw else json.loads(data)

def main():
    if not TOKEN:
        sys.exit("GOATCOUNTER_TOKEN is not set")
    os.makedirs(OUT, exist_ok=True)
    last = int(open(LAST).read().strip()) if os.path.exists(LAST) else 0
    api("GET", "/me")                                     # checks the token before starting (logs are public: print nothing personal)
    print("token accepted")

    exp = api("POST", "/export", {"format": "csv", "start_from_hit_id": last})   # only page views after the last exported one
    for _ in range(60):                                   # wait up to 10 minutes for the export to be ready
        if exp.get("finished_at"):
            break
        time.sleep(10)
        exp = api("GET", f"/export/{exp['id']}")
    else:
        sys.exit("export did not finish in time")

    # print the export's status (no personal data in these fields), to make any problem visible in the log
    print("export:", {k: exp.get(k) for k in ("id", "format", "start_from_hit_id", "last_hit_id", "num_rows", "size", "error")})
    if exp.get("error"):
        sys.exit("GoatCounter reported an error with the export")
    data = api("GET", f"/export/{exp['id']}/download", raw=True)
    if data[:2] == b"\x1f\x8b":                           # the download is gzipped
        data = gzip.decompress(data)

    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    if len(rows) < 2:                                     # only a header (or nothing): no new page views
        print("no new page views since the last export"); return
    head, body = rows[0], rows[1:]
    keep = [i for i, h in enumerate(head) if h.strip().lower().lstrip("0123456789,") not in DROP]
    dcol = next((i for i, h in enumerate(head) if h.strip().lower() == "date"), None)
    # add each page view to the file of the month it happened in: stats/goatcounter-YYYY-MM.csv
    by_month = {}
    for r in body:
        m = r[dcol][:7] if dcol is not None and dcol < len(r) and len(r[dcol]) >= 7 else f"{date.today():%Y-%m}"
        by_month.setdefault(m, []).append(r)
    for m, rs in sorted(by_month.items()):
        name = os.path.join(OUT, f"goatcounter-{m}.csv")
        new_file = not os.path.exists(name)
        with open(name, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow([head[i] for i in keep])
            for r in rs:
                w.writerow([r[i] for i in keep if i < len(r)])
        print(f"added {len(rs)} page views to {name}")
    if exp.get("last_hit_id"):
        open(LAST, "w").write(str(exp["last_hit_id"]))

if __name__ == "__main__":
    main()
