"""Rate every history day for every site, for the percentiles.

reads data/hrrr/*.parquet, writes data/climo.parquet with one row per site per local day:
  best_soar_above_ft   the day's best soarable height over launch, 8 am to 5 pm (what Top 25% / Top 5% compare against)
  best_level           the day's best rating before percentiles (-1 to 2)
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
        h["date"] = h["local"].dt.date
        h = h[(h["local"].dt.hour >= 8) & (h["local"].dt.hour <= 17)]
        g = h.groupby("date")
        day = pd.DataFrame({"hours": g.size(), "best_soar_above_ft": g["soar_above_ft"].max(), "best_level": g["level"].max(),
                            "flyable_hours": g["flyable"].sum(), "best_wstar": g["wstar"].max()}).reset_index()
        day = day[day["hours"] >= 8]
        day.insert(0, "site", sid)
        rows.append(day)
    out = pd.concat(rows, ignore_index=True)
    out["date"] = out["date"].astype(str)
    out.to_parquet("data/climo.parquet", compression="zstd", index=False)
    print(len(files), "months,", len(out), "site-days")
    print(out.groupby("site")["best_soar_above_ft"].describe(percentiles=[.25, .5, .75, .95]).round(0).to_string())


if __name__ == "__main__":
    main()
