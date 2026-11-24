"""Rate every history day for every site, for the percentiles.

reads data/hrrr/*.parquet, writes data/climo.parquet (one row per site per local day)
"""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import rate  # noqa: E402


def main():
    files = sorted(glob.glob("data/hrrr/[0-9]*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["site"] = df["site"].astype(str)
    rows = []
    for sid, x in df.groupby("site"):
        if sid not in rate.SITES:
            continue
        x = x.sort_values("time").reset_index(drop=True)
        h = rate.hourly(x, sid)
        for d in rate.daily(h, sid):
            if d["hours"] < 10:          # skip days with missing hours
                continue
            rows.append({"site": sid, "date": d["date"], "score": d["score"], "soarable_hours": d["soarable_hours"],
                         "above_ft": d.get("above_ft"), "wstar": d.get("wstar"), "max_top_ft": d.get("max_top_ft")})
    out = pd.DataFrame(rows)
    out.to_parquet("data/climo.parquet", compression="zstd", index=False)
    print(len(files), "months,", len(out), "site-days")
    print(out.groupby("site")["score"].describe().round(2).to_string())


if __name__ == "__main__":
    main()
