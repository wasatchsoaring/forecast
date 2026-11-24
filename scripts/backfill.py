"""Pull one month of HRRRv4 analyses for every site.

usage: python scripts/backfill.py YYYY-MM
writes data/hrrr/YYYY-MM.parquet (one row per site per hour) and data/hrrr/_status/YYYY-MM.json
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import fill_gaps  # noqa: E402
import hrrr  # noqa: E402

V4_START = datetime(2020, 12, 3, tzinfo=timezone.utc)   # HRRRv4 went operational 2 Dec 2020 12Z
DAY_HOURS = set(range(14, 24)) | {0, 1, 2, 3}            # 8 am to 9 pm in Utah, as UTC hours


def month_hours(month):
    y, m = map(int, month.split("-"))
    t = datetime(y, m, 1, tzinfo=timezone.utc)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    end = min(end, now)
    out = []
    while t < end:
        if t >= V4_START and t.hour in DAY_HOURS:
            out.append(t)
        t += timedelta(hours=1)
    return out


def main(month):
    pts = json.load(open("data/gridpoints.json"))
    hours = month_hours(month)
    t0 = time.time()
    cols, stats = hrrr.extract_hours(hours, pts, threads=32)
    rows = []
    for hi, t in enumerate(hours):
        for j, p in enumerate(pts):
            rows.append([t.replace(tzinfo=None), p["id"]] + [cols[c][hi, j] for c in cols])
    df = pd.DataFrame(rows, columns=["time", "site"] + list(cols))
    df["site"] = df["site"].astype("category")
    for c in cols:
        df[c] = df[c].astype("float32")
    os.makedirs("data/hrrr/_status", exist_ok=True)
    df.to_parquet(f"data/hrrr/{month}.parquet", compression="zstd", index=False)
    stats["gap_filled"] = fill_gaps.fill(month, pts)
    stats.update(month=month, hours=len(hours), seconds=round(time.time() - t0),
                 missing_hours=int(sum(df.groupby("time")["HPBL"].apply(lambda s: s.isna().all()))),
                 bytes=os.path.getsize(f"data/hrrr/{month}.parquet"))
    json.dump(stats, open(f"data/hrrr/_status/{month}.json", "w"), indent=1)
    print(stats)


if __name__ == "__main__":
    main(sys.argv[1])
