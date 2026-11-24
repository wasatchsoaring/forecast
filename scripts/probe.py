"""Probe the HRRR-Zarr archive from GitHub Actions.

Writes everything to probe/ so the results can be read from the repo:
  probe/report.md       what worked, timings, site grid points
  probe/sfc_arrays.txt  every array in a sfc analysis store
  probe/prs_arrays.txt  every array in a prs analysis store
  probe/sample.csv      one week of the candidate variables at every site
"""
import json
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numcodecs
import numpy as np
import requests

BASE = "https://hrrrzarr.s3.amazonaws.com"
OUT = "probe"
os.makedirs(OUT, exist_ok=True)
report = []
S = requests.Session()
S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32))


def log(msg=""):
    print(msg, flush=True)
    report.append(str(msg))


def get(url, **kw):
    r = S.get(url, timeout=60, **kw)
    return r


sites = json.load(open("sites.json"))

# 1. list arrays in sfc and prs analysis stores
arrays = {}
for kind in ("sfc", "prs"):
    url = f"{BASE}/{kind}/20240701/20240701_18z_anl.zarr/.zmetadata"
    try:
        r = get(url)
        log(f"## {kind} .zmetadata: HTTP {r.status_code}, {len(r.content)} bytes")
        if r.ok:
            meta = r.json()["metadata"]
            rows = []
            for k, v in meta.items():
                if k.endswith("/.zarray"):
                    p = k[: -len("/.zarray")]
                    rows.append(f"{p}\tshape={v.get('shape')}\tchunks={v.get('chunks')}\tdtype={v.get('dtype')}\tcomp={json.dumps(v.get('compressor'))}")
            rows.sort()
            arrays[kind] = [r_.split("\t")[0] for r_ in rows]
            open(f"{OUT}/{kind}_arrays.txt", "w").write("\n".join(rows) + "\n")
            log(f"{len(rows)} arrays")
    except Exception:
        log(f"{kind} metadata failed:\n```\n{traceback.format_exc()}\n```")

# 2. chunk index grid
log("\n## chunk index")
lat = lon = None
try:
    r = get(f"{BASE}/grid/HRRR_chunk_index.zarr/.zmetadata")
    log(f"HTTP {r.status_code}")
    if r.ok:
        meta = r.json()["metadata"]
        for k, v in meta.items():
            if k.endswith(".zarray"):
                log(f"- {k}: shape={v.get('shape')} chunks={v.get('chunks')} dtype={v.get('dtype')} comp={v.get('compressor')}")
            if k.endswith(".zattrs"):
                log(f"- {k}: {json.dumps(v)[:300]}")
    import s3fs
    import xarray as xr

    fs = s3fs.S3FileSystem(anon=True)
    ds = xr.open_zarr(s3fs.S3Map("hrrrzarr/grid/HRRR_chunk_index.zarr", s3=fs))
    log("```\n" + str(ds) + "\n```")
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    if np.nanmax(lon) > 180:
        lon = np.where(lon > 180, lon - 360, lon)
    log(f"lat shape {lat.shape}, range {np.nanmin(lat):.2f}..{np.nanmax(lat):.2f}; lon range {np.nanmin(lon):.2f}..{np.nanmax(lon):.2f}")
    np.save(f"{OUT}/lat.npy", lat.astype("float32"))
    np.save(f"{OUT}/lon.npy", lon.astype("float32"))
except Exception:
    log(f"chunk index failed:\n```\n{traceback.format_exc()}\n```")

# 3. nearest grid point per site
pts = []
if lat is not None:
    log("\n## site grid points")
    log("| site | iy | ix | chunk | grid lat | grid lon | km off |")
    log("|---|---|---|---|---|---|---|")
    for s in sites:
        d2 = (lat - s["lat"]) ** 2 + ((lon - s["lon"]) * np.cos(np.radians(s["lat"]))) ** 2
        iy, ix = np.unravel_index(np.nanargmin(d2), d2.shape)
        km = np.sqrt(d2[iy, ix]) * 111.2
        ch = f"{iy // 150}.{ix // 150}"
        pts.append((s["id"], int(iy), int(ix), ch))
        log(f"| {s['name']} | {iy} | {ix} | {ch} | {lat[iy, ix]:.4f} | {lon[iy, ix]:.4f} | {km:.2f} |")
    json.dump([dict(id=a, iy=b, ix=c, chunk=d) for a, b, c, d in pts], open(f"{OUT}/gridpoints.json", "w"), indent=1)


def chunk_url(kind, dt, level, var, chunk):
    d = dt.strftime("%Y%m%d")
    return f"{BASE}/{kind}/{d}/{d}_{dt:%H}z_anl.zarr/{level}/{var}/{level}/{var}/{chunk}"


def read_chunk(url, dtype):
    r = get(url)
    if r.status_code != 200:
        return None, r.status_code, 0
    buf = numcodecs.blosc.decompress(r.content)
    return np.frombuffer(buf, dtype=dtype).reshape(150, 150), 200, len(r.content)


def dtype_for(path):
    meta_dtype = None
    for p in ("surface/PRES", "mean_sea_level/MSLMA", "0C_isotherm/PRES"):
        if path.startswith(p):
            meta_dtype = "<f4"
    return meta_dtype or "<f2"


# 4. orientation check: raw chunk decode vs xarray for terrain height
WANT = [
    "surface/HGT", "surface/HPBL", "surface/SHTFL", "surface/LHTFL", "surface/GUST",
    "surface/CAPE", "surface/CIN", "surface/DSWRF", "surface/PRES",
    "10m_above_ground/UGRD", "10m_above_ground/VGRD",
    "80m_above_ground/UGRD", "80m_above_ground/VGRD",
    "2m_above_ground/TMP", "2m_above_ground/DPT", "2m_above_ground/RH",
    "cloud_base/HGT", "cloud_base/PRES", "cloud_ceiling/HGT", "cloud_top/HGT",
    "entire_atmosphere/REFC", "entire_atmosphere/LTNG", "entire_atmosphere/TCDC",
    "low_cloud_layer/LCDC", "middle_cloud_layer/MCDC", "high_cloud_layer/HCDC",
    "level_of_adiabatic_condensation_from_sfc/HGT",
    "700mb/TMP", "700mb/UGRD", "700mb/VGRD", "700mb/HGT", "700mb/DPT", "700mb/VVEL",
    "850mb/TMP", "850mb/UGRD", "850mb/VGRD", "850mb/HGT",
    "500mb/TMP", "500mb/UGRD", "500mb/VGRD", "500mb/HGT",
    "surface/PRATE", "surface/APCP", "surface/CPOFP", "surface/VIS",
]
have = set(arrays.get("sfc", []))
present = [w for w in WANT if f"{w}/{w.split('/')[0]}/{w.split('/')[1]}" in have or w in have or any(h.startswith(w + "/") for h in have)]
if not have:
    log("no sfc array list, trying every candidate")
    present = list(WANT)
missing = [w for w in WANT if w not in present]
log("\n## candidate variables")
log("present: " + ", ".join(present))
log("missing: " + ", ".join(missing))

if pts:
    try:
        import s3fs
        import xarray as xr

        fs = s3fs.S3FileSystem(anon=True)
        dt = datetime(2024, 7, 1, 18, tzinfo=timezone.utc)
        g = xr.open_zarr(s3fs.S3Map("hrrrzarr/sfc/20240701/20240701_18z_anl.zarr/surface/HGT/surface", s3=fs), consolidated=False)
        log("\n## orientation check (surface/HGT)\n```\n" + str(g)[:1500] + "\n```")
        full = g["HGT"].values.squeeze()
        log(f"xarray HGT shape {full.shape}")
        cache = {}
        log("| site | xarray m | raw chunk m | launch ft | HRRR terrain ft |")
        log("|---|---|---|---|---|")
        for (sid, iy, ix, ch), s in zip(pts, sites):
            if ch not in cache:
                cache[ch] = read_chunk(chunk_url("sfc", dt, "surface", "HGT", ch), "<f2")[0]
            raw = cache[ch][iy % 150, ix % 150] if cache[ch] is not None else float("nan")
            xv = full[iy, ix]
            log(f"| {s['name']} | {xv:.0f} | {raw:.0f} | {s['launch_ft']} | {raw * 3.28084:.0f} |")
    except Exception:
        log(f"orientation check failed:\n```\n{traceback.format_exc()}\n```")

# 5. one-week timing test, daytime hours only, all present variables
if pts and present:
    log("\n## one-week timing test")
    chunks = sorted({p[3] for p in pts})
    log(f"unique chunks for all sites: {chunks}")
    start = datetime(2024, 7, 1, tzinfo=timezone.utc)
    hours = [start + timedelta(hours=h) for h in range(7 * 24) if (start + timedelta(hours=h)).hour in list(range(14, 24)) + [0, 1, 2]]
    jobs = []
    for dt in hours:
        for w in present:
            lev, var = w.split("/")
            for ch in chunks:
                jobs.append((dt, w, ch, chunk_url("sfc", dt, lev, var, ch)))
    log(f"{len(hours)} hours x {len(present)} vars x {len(chunks)} chunks = {len(jobs)} requests")
    t0 = time.time()
    res = {}
    nbytes = 0
    fails = {}

    def work(j):
        dt, w, ch, url = j
        for attempt in range(3):
            try:
                a, code, n = read_chunk(url, dtype_for(w))
                return j, a, code, n
            except Exception as e:
                err = repr(e)
                time.sleep(1 + attempt)
        return j, None, err, 0

    with ThreadPoolExecutor(32) as ex:
        for (dt, w, ch, url), a, code, n in ex.map(work, jobs):
            nbytes += n
            if a is None:
                fails[(w, str(code))] = fails.get((w, str(code)), 0) + 1
            res[(dt, w, ch)] = a
    el = time.time() - t0
    log(f"took {el:.0f} s, {nbytes / 1e6:.1f} MB, {len(jobs) / el:.0f} req/s")
    if fails:
        log("failures: " + "; ".join(f"{k[0]} ({k[1]}): {v}" for k, v in sorted(fails.items())))
    yrs_hours = 6 * 365 * len(hours) / 7
    log(f"extrapolated to 6 years of the same hours: {el * yrs_hours / len(hours) / 3600:.1f} h, {nbytes * yrs_hours / len(hours) / 1e9:.1f} GB")

    import csv

    with open(f"{OUT}/sample.csv", "w", newline="") as f:
        w_ = csv.writer(f)
        w_.writerow(["time_utc", "site"] + present)
        for dt in hours:
            for (sid, iy, ix, ch) in pts:
                row = []
                for w in present:
                    a = res.get((dt, w, ch))
                    row.append("" if a is None else f"{float(a[iy % 150, ix % 150]):.4g}")
                w_.writerow([dt.strftime("%Y-%m-%dT%H"), sid] + row)
    log("wrote probe/sample.csv")

# 6. availability spot checks across years
log("\n## archive coverage spot checks (surface/HPBL, chunk of first site)")
if pts:
    ch = pts[0][3]
    for dt in [datetime(y, m, 15, 20, tzinfo=timezone.utc) for y in range(2016, 2027) for m in (1, 7)]:
        if dt > datetime.now(timezone.utc):
            continue
        try:
            r = get(chunk_url("sfc", dt, "surface", "HPBL", ch))
            log(f"- {dt:%Y-%m-%d %HZ}: HTTP {r.status_code}")
        except Exception as e:
            log(f"- {dt:%Y-%m-%d %HZ}: {e!r}")
    for dt in [datetime.now(timezone.utc) - timedelta(hours=h) for h in (3, 6, 12, 24)]:
        r = get(chunk_url("sfc", dt.replace(minute=0, second=0, microsecond=0), "surface", "HPBL", ch))
        log(f"- latest check {dt:%Y-%m-%d %HZ}: HTTP {r.status_code}")

open(f"{OUT}/report.md", "w").write("# HRRR-Zarr probe\n\n" + f"run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n\n" + "\n".join(report) + "\n")
