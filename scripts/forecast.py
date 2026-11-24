"""Pull the latest HRRR forecasts for every site.

Uses the newest 48-hour run (00/06/12/18Z) and lays the newest hourly run (18 hours) over the hours it covers.
Writes data/forecast.parquet with the same columns as the history files, plus run and lead hour.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numcodecs
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import hrrr  # noqa: E402

COLS = dict(hrrr.SFC)
for p in (850, 700, 500):
    for short, var in (("T", "TMP"), ("TD", "DPT"), ("U", "UGRD"), ("V", "VGRD"), ("Z", "HGT")):
        COLS[f"{short}{p}"] = (f"{p}mb", var)


def store(run):
    d = run.strftime("%Y%m%d")
    return f"{hrrr.BASE}/sfc/{d}/{d}_{run:%H}z_fcst.zarr"


def exists(run):
    r = hrrr._session.get(f"{store(run)}/surface/HPBL/surface/HPBL/0.4.3", timeout=60)
    return r.status_code == 200


def latest_runs(now):
    """Newest available run of any hour, and newest available 48-hour run."""
    newest = longest = None
    t = now.replace(minute=0, second=0, microsecond=0)
    for h in range(0, 30):
        run = t - timedelta(hours=h)
        if newest is not None and run.hour % 6:
            continue
        if exists(run):
            newest = newest or run
            if run.hour % 6 == 0:
                longest = run
                break
    return newest, longest


def decode(raw, meta):
    comp = meta.get("compressor")
    buf = numcodecs.blosc.decompress(raw) if comp else raw
    return np.frombuffer(buf, dtype=meta["dtype"])


def lead_hours(run, meta_all):
    key = "surface/HPBL/forecast_period"
    m = meta_all[key + "/.zarray"]
    attrs = meta_all.get(key + "/.zattrs", {})
    raw = hrrr._session.get(f"{store(run)}/{key}/0", timeout=60).content
    v = decode(raw, m).astype("float64")
    units = str(attrs.get("units", ""))
    if "hour" in units:
        return v
    if "minute" in units:
        return v / 60
    if "second" in units:
        return v / 3600
    if np.nanmax(v) > 1e9:      # nanoseconds
        return v / 3.6e12
    return v


def pull_run(run, points):
    meta_all = json.loads(hrrr._session.get(f"{store(run)}/.zmetadata", timeout=120).content)["metadata"]
    leads = lead_hours(run, meta_all)
    chunks = sorted({p["chunk"] for p in points})
    out = {c: np.full((len(leads), len(points)), np.nan, dtype="float32") for c in COLS}

    def work(job):
        c, ch = job
        lev, var = COLS[c]
        key = f"{lev}/{var}/{lev}/{var}"
        m = meta_all.get(key + "/.zarray")
        if m is None:
            return c, ch, None
        r = hrrr._session.get(f"{store(run)}/{key}/0.{ch}", timeout=120)
        if r.status_code != 200:
            return c, ch, None
        a = decode(r.content, m).reshape(m["chunks"])
        return c, ch, a

    with ThreadPoolExecutor(24) as ex:
        for c, ch, a in ex.map(work, [(c, ch) for c in COLS for ch in chunks]):
            if a is None:
                print("missing", run, c, ch)
                continue
            for j, p in enumerate(points):
                if p["chunk"] == ch:
                    out[c][:, j] = a[: len(leads), p["iy"] % 150, p["ix"] % 150]
    rows = []
    for li, lead in enumerate(leads):
        valid = run + timedelta(hours=float(lead))
        for j, p in enumerate(points):
            rows.append([valid.replace(tzinfo=None), p["id"], run.replace(tzinfo=None), int(round(lead))] + [out[c][li, j] for c in COLS])
    return pd.DataFrame(rows, columns=["time", "site", "run", "lead"] + list(COLS))


def main():
    points = json.load(open("data/gridpoints.json"))
    now = datetime.now(timezone.utc)
    newest, longest = latest_runs(now)
    print("newest run", newest, "newest 48 h run", longest)
    frames = []
    if longest is not None:
        frames.append(pull_run(longest, points))
    if newest is not None and newest != longest:
        frames.append(pull_run(newest, points))
    df = pd.concat(frames)
    # newest run wins for any valid time it covers
    df = df.sort_values(["time", "site", "run"]).drop_duplicates(["time", "site"], keep="last")
    for c in COLS:
        df[c] = df[c].astype("float32")
    os.makedirs("data", exist_ok=True)
    df.to_parquet("data/forecast.parquet", compression="zstd", index=False)
    json.dump({"newest_run": str(newest), "long_run": str(longest), "pulled": now.isoformat(timespec="minutes"),
               "valid_from": str(df["time"].min()), "valid_to": str(df["time"].max())},
              open("data/forecast_meta.json", "w"), indent=1)
    print(df.groupby("run").size(), df["time"].min(), df["time"].max())


if __name__ == "__main__":
    main()
