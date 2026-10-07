#!/usr/bin/env bash
# Save the regional ERA5 progress to GitHub in the middle of a run (called every 30 minutes by
# update-era5-regions.yml), so the list of open Copernicus requests on GitHub is never far behind,
# even if a run dies before its final commit step.
# Works in a separate checkout (git worktree) of the latest GitHub version, so the running script's
# own files are never touched; merges this run's data into it with merge_era5_regions.py, then pushes.
set -u
CK=/tmp/era5-checkpoint; OURS=/tmp/era5-ours-checkpoint
rm -rf "$OURS"; mkdir -p "$OURS"
cp data/era5_t2_regions_daily.csv data/era5_open_requests.json "$OURS"/ 2>/dev/null || exit 0
for i in 1 2 3; do
  git fetch -q origin main || exit 0
  git worktree remove -f "$CK" 2>/dev/null; rm -rf "$CK"
  git worktree add -q -f --detach "$CK" origin/main || exit 0
  ( cd "$CK" && python scripts/merge_era5_regions.py "$OURS" > /dev/null && git add data &&
    { git diff --cached --quiet || { git -c user.name="github-actions" -c user.email="actions@users.noreply.github.com" \
        commit -q -m "Regional air temperature: checkpoint" && git push -q origin HEAD:main; }; } )
  ok=$?
  git worktree remove -f "$CK" 2>/dev/null; rm -rf "$CK"
  if [ $ok -eq 0 ]; then echo "checkpoint saved to GitHub ($(date -u +%H:%M) UTC)"; exit 0; fi
  sleep 15                                   # someone else pushed in between: try again on the newer version
done
echo "checkpoint not saved this time; the next one (or the final commit) catches up"
