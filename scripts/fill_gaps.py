"""Fill holes in the 850/700/500 mb columns from the sfc store, which carries those levels too.

The prs store is missing some stretches (early January 2023, for example). The rating only uses
850, 700 and 500 mb, so those are the columns worth filling.

usage: python scripts/fill_gaps.py [YYYY-MM ...]   (no args = every month on disk)
"""
import glob
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import hrrr  # noqa: E402

COLS = {}
for p in (850, 700, 500):
    for short, var in (("T", "TMP"), ("TD", "DPT"), ("U", "UGRD"), ("V", "VGRD"), ("Z", "HGT")):
        COLS[f"{short}{p}"] = (f"{p}mb", var)


def fill(month, points):
    path = f"data/hrrr/{month}.parquet"
    df = pd.read_parquet(path)
    gap_times = sorted(df.loc[df[list(COLS)].isna().any(axis=1), "time"].unique())
    if not gap_times:
        return 0
    times = [pd.Timestamp(t).tz_localize("UTC").to_pydatetime() for t in gap_times]
    chunks = sorted({p["chunk"] for p in points})
    jobs = [(t, c, ch) for t in times for c in COLS for ch in chunks]

    def work(job):
        t, c, ch = job
        lev, var = COLS[c]
        return job, hrrr.fetch(hrrr.anl_url("sfc", t, lev, var, ch))

    filled = 0
    idx = {(r.time, r.site): i for i, r in enumerate(df[["time", "site"]].itertuples(index=False))}
    with ThreadPoolExecutor(32) as ex:
        for (t, c, ch), a in ex.map(work, jobs):
            if a is None:
                continue
            tt = pd.Timestamp(t).tz_localize(None)
            for p in points:
                if p["chunk"] != ch:
                    continue
                i = idx.get((tt, p["id"]))
                if i is not None and np.isnan(df.at[i, c]):
                    df.at[i, c] = a[p["iy"] % 150, p["ix"] % 150]
                    filled += 1
    df.to_parquet(path, compression="zstd", index=False)
    return filled


def main(months):
    points = json.load(open("data/gridpoints.json"))
    if not months:
        months = [os.path.basename(f)[:7] for f in sorted(glob.glob("data/hrrr/[0-9]*.parquet"))]
    for m in months:
        n = fill(m, points)
        if n:
            print(m, "filled", n, "values")


if __name__ == "__main__":
    main(sys.argv[1:])
