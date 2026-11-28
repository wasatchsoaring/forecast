"""Add sites from sites.json that have no grid point yet, and pull their history into the existing month files.

usage:
  python scripts/add_sites.py points            # give new sites a grid point and HRRR terrain (writes data/gridpoints.json)
  python scripts/add_sites.py months 2021 2022  # pull history for sites missing from those years' month files
"""
import glob
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import backfill  # noqa: E402
import fill_gaps  # noqa: E402
import hrrr  # noqa: E402


def points():
    sites = json.load(open("sites.json"))
    grid = json.load(open("data/gridpoints.json"))
    have = {p["id"] for p in grid}
    lat, lon = np.load("probe/lat.npy"), np.load("probe/lon.npy")
    for s in sites:
        if s["id"] in have:
            continue
        d2 = (lat - s["lat"]) ** 2 + ((lon - s["lon"]) * np.cos(np.radians(s["lat"]))) ** 2
        iy, ix = (int(v) for v in np.unravel_index(np.nanargmin(d2), d2.shape))
        ch = f"{iy // 150}.{ix // 150}"
        a = hrrr.fetch(hrrr.anl_url("sfc", datetime(2024, 7, 1, 18, tzinfo=timezone.utc), "surface", "HGT", ch))
        p = {"id": s["id"], "iy": iy, "ix": ix, "chunk": ch, "terrain_m": round(float(a[iy % 150, ix % 150]), 1)}
        grid.append(p)
        print("added", p)
    json.dump(grid, open("data/gridpoints.json", "w"), indent=1)


def months(years):
    grid = json.load(open("data/gridpoints.json"))
    for f in sorted(glob.glob("data/hrrr/[0-9]*.parquet")):
        month = os.path.basename(f)[:7]
        if years and month[:4] not in years:
            continue
        df = pd.read_parquet(f)
        have = set(df["site"].astype(str).unique())
        new = [p for p in grid if p["id"] not in have]
        if not new:
            continue
        hours = backfill.month_hours(month)
        cols, stats = hrrr.extract_hours(hours, new, threads=32)
        rows = [[t.replace(tzinfo=None), p["id"]] + [cols[c][hi, j] for c in cols] for hi, t in enumerate(hours) for j, p in enumerate(new)]
        add = pd.DataFrame(rows, columns=["time", "site"] + list(cols))
        out = pd.concat([df.assign(site=df["site"].astype(str)), add], ignore_index=True).sort_values(["time", "site"])
        out["site"] = out["site"].astype("category")
        for c in cols:
            out[c] = out[c].astype("float32")
        out.to_parquet(f, compression="zstd", index=False)
        filled = fill_gaps.fill(month, new)
        print(month, "added", [p["id"] for p in new], stats, "gap-filled", filled, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "points":
        points()
    else:
        months(sys.argv[2:])
