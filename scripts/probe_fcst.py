"""Probe the HRRR-Zarr forecast stores (sfc and prs) and their latency."""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
import numpy as np, numcodecs, requests
sys.path.insert(0, os.path.dirname(__file__))
import hrrr

OUT = "probe"; os.makedirs(OUT, exist_ok=True)
rep = []
def log(s=""):
    print(s, flush=True); rep.append(str(s))
S = requests.Session()
now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
log(f"now {now:%Y-%m-%d %HZ}")

# latest available runs
log("\n## latest forecast runs (sfc, surface/HPBL chunk 4.3)")
found = []
for h in range(0, 13):
    t = now - timedelta(hours=h)
    d = t.strftime("%Y%m%d")
    url = f"{hrrr.BASE}/sfc/{d}/{d}_{t:%H}z_fcst.zarr/surface/HPBL/surface/HPBL/0.4.3"
    r = S.get(url, timeout=60)
    log(f"- run {t:%Y-%m-%d %HZ}: HTTP {r.status_code} {len(r.content)} bytes")
    if r.ok:
        found.append(t)

for kind in ("sfc", "prs"):
    for t in found[:6]:
        d = t.strftime("%Y%m%d")
        r = S.get(f"{hrrr.BASE}/{kind}/{d}/{d}_{t:%H}z_fcst.zarr/.zmetadata", timeout=120)
        log(f"\n## {kind} fcst .zmetadata for {t:%Y-%m-%d %HZ}: HTTP {r.status_code}, {len(r.content)} bytes")
        if not r.ok:
            continue
        meta = r.json()["metadata"]
        rows = sorted(k[:-8] + "\t" + json.dumps({x: meta[k].get(x) for x in ("shape", "chunks", "dtype")}) for k in meta if k.endswith("/.zarray"))
        open(f"{OUT}/{kind}_fcst_arrays.txt", "w").write("\n".join(rows) + "\n")
        for want in ("surface/HPBL/surface/HPBL", "surface/HPBL/time", "surface/HPBL/forecast_period", "700mb/TMP/700mb/TMP", "2m_above_ground/TMP/2m_above_ground/TMP"):
            for k in rows:
                if k.startswith(want + "\t"):
                    log(f"- {k}")
        log(f"{len(rows)} arrays")
        break

# decode one sfc and one prs forecast chunk
for kind, lev, var in (("sfc", "surface", "HPBL"), ("sfc", "2m_above_ground", "TMP"), ("prs", "700mb", "TMP")):
    for t in found:
        d = t.strftime("%Y%m%d")
        for ch in ("0.4.3", "4.3"):
            url = f"{hrrr.BASE}/{kind}/{d}/{d}_{t:%H}z_fcst.zarr/{lev}/{var}/{lev}/{var}/{ch}"
            r = S.get(url, timeout=60)
            if r.ok:
                buf = numcodecs.blosc.decompress(r.content)
                log(f"\n{kind} {lev}/{var} run {t:%HZ} chunk {ch}: {len(r.content)} bytes compressed, {len(buf)} raw = {len(buf) / 22500:.1f} values per grid point")
                break
        else:
            continue
        break
open(f"{OUT}/fcst_report.md", "w").write("# HRRR-Zarr forecast probe\n\n" + "\n".join(rep) + "\n")
