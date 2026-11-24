# HRRR-Zarr probe

run 2026-11-24 15:09 UTC

## sfc .zmetadata: HTTP 200, 903209 bytes
1360 arrays
## prs .zmetadata: HTTP 200, 3635520 bytes
5664 arrays

## chunk index
HTTP 200
- .zattrs: {}
- chunk_id/.zarray: shape=[1799, 1059] chunks=[225, 265] dtype=|O comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- chunk_id/.zattrs: {"_ARRAY_DIMENSIONS": ["x", "y"]}
- chunk_x/.zarray: shape=[1799] chunks=[1799] dtype=<i4 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- chunk_x/.zattrs: {"_ARRAY_DIMENSIONS": ["x"]}
- chunk_y/.zarray: shape=[1059] chunks=[1059] dtype=<i4 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- chunk_y/.zattrs: {"_ARRAY_DIMENSIONS": ["y"]}
- in_chunk_x/.zarray: shape=[1799] chunks=[1799] dtype=<i4 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- in_chunk_x/.zattrs: {"_ARRAY_DIMENSIONS": ["x"]}
- in_chunk_y/.zarray: shape=[1059] chunks=[1059] dtype=<i4 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- in_chunk_y/.zattrs: {"_ARRAY_DIMENSIONS": ["y"]}
- index_x/.zarray: shape=[1799] chunks=[1799] dtype=<i4 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- index_x/.zattrs: {"_ARRAY_DIMENSIONS": ["x"]}
- index_y/.zarray: shape=[1059] chunks=[1059] dtype=<i4 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- index_y/.zattrs: {"_ARRAY_DIMENSIONS": ["y"]}
- latitude/.zarray: shape=[1059, 1799] chunks=[133, 450] dtype=<f8 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- latitude/.zattrs: {"_ARRAY_DIMENSIONS": ["y", "x"]}
- longitude/.zarray: shape=[1059, 1799] chunks=[133, 450] dtype=<f8 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- longitude/.zattrs: {"_ARRAY_DIMENSIONS": ["y", "x"]}
- x/.zarray: shape=[1799] chunks=[1799] dtype=<f8 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- x/.zattrs: {"_ARRAY_DIMENSIONS": ["x"]}
- y/.zarray: shape=[1059] chunks=[1059] dtype=<f8 comp={'blocksize': 0, 'clevel': 5, 'cname': 'lz4', 'id': 'blosc', 'shuffle': 1}
- y/.zattrs: {"_ARRAY_DIMENSIONS": ["y"]}
lat shape (1059, 1799), range 21.14..52.62; lon range -134.10..-60.92
chunk_x first/last [0 0 0]..[11 11 11], in_chunk_x [0 1 2]..[146 147 148]; chunk_y [0 0 0]..[7 7 7]

## site grid points
| site | iy | ix | chunk | grid lat | grid lon | km off |
|---|---|---|---|---|---|---|
| North Side | 634 | 495 | 4.3 | 40.4758 | -111.8845 | 0.64 |
| South Side | 633 | 494 | 4.3 | 40.4450 | -111.9140 | 1.60 |
| Burn Side | 643 | 503 | 4.3 | 40.7488 | -111.6532 | 1.78 |
| Cherry | 635 | 497 | 4.3 | 40.5108 | -111.8200 | 0.63 |
| Grandeur | 642 | 499 | 4.3 | 40.7056 | -111.7883 | 0.82 |
| The V | 650 | 499 | 4.3 | 40.9186 | -111.8324 | 1.36 |
| Francis Peak | 654 | 499 | 4.3 | 41.0252 | -111.8546 | 1.41 |
| Inspo | 626 | 501 | 4.3 | 40.2876 | -111.6310 | 1.56 |
| Jupiter | 638 | 505 | 4.3 | 40.6238 | -111.5557 | 1.73 |
| Horse Heaven | 598 | 491 | 3.3 | 39.4999 | -111.8267 | 1.20 |
| Monroe Peak | 564 | 478 | 3.3 | 38.5391 | -112.0879 | 1.30 |
| Junction | 555 | 469 | 3.3 | 38.2608 | -112.3445 | 1.57 |
| Poverty Ridge | 564 | 475 | 3.3 | 38.5263 | -112.1901 | 1.48 |
| Cove | 567 | 479 | 3.3 | 38.6233 | -112.0702 | 1.45 |
| Edna | 560 | 470 | 3.3 | 38.3982 | -112.3381 | 1.47 |
| Oakley Ridge | 640 | 514 | 4.3 | 40.7137 | -111.2502 | 1.05 |
| Wire | 644 | 499 | 4.3 | 40.7589 | -111.7993 | 1.30 |
| Mahogany | 631 | 499 | 4.3 | 40.4126 | -111.7280 | 1.64 |
| Wales | 598 | 495 | 3.3 | 39.5166 | -111.6886 | 1.21 |
| Castleton Tower | 557 | 557 | 3.3 | 38.6573 | -109.3542 | 1.44 |
| Ken's Lake | 551 | 554 | 3.3 | 38.4864 | -109.4302 | 0.94 |

## candidate variables
present: surface/HGT, surface/HPBL, surface/SHTFL, surface/LHTFL, surface/GUST, surface/CAPE, surface/CIN, surface/DSWRF, surface/PRES, 10m_above_ground/UGRD, 10m_above_ground/VGRD, 80m_above_ground/UGRD, 80m_above_ground/VGRD, 2m_above_ground/TMP, 2m_above_ground/DPT, 2m_above_ground/RH, cloud_base/HGT, cloud_base/PRES, cloud_ceiling/HGT, cloud_top/HGT, entire_atmosphere/REFC, entire_atmosphere/LTNG, entire_atmosphere/TCDC, low_cloud_layer/LCDC, middle_cloud_layer/MCDC, high_cloud_layer/HCDC, level_of_adiabatic_condensation_from_sfc/HGT, 700mb/TMP, 700mb/UGRD, 700mb/VGRD, 700mb/HGT, 700mb/DPT, 850mb/TMP, 850mb/UGRD, 850mb/VGRD, 850mb/HGT, 500mb/TMP, 500mb/UGRD, 500mb/VGRD, 500mb/HGT, surface/PRATE, surface/CPOFP, surface/VIS
missing: 700mb/VVEL, surface/APCP

## terrain check: HRRR 3 km terrain under each launch vs the launch elevation
| site | launch ft | HRRR terrain ft |
|---|---|---|
| North Side | 5100 | 5268 |
| South Side | 5148 | 4716 |
| Burn Side | None | 6823 |
| Cherry | 7110 | 6668 |
| Grandeur | 6308 | 5680 |
| The V | 6344 | 6708 |
| Francis Peak | 9154 | 7921 |
| Inspo | 6667 | 6225 |
| Jupiter | 9980 | 9164 |
| Horse Heaven | 7538 | 7193 |
| Monroe Peak | 11171 | 9792 |
| Junction | 8100 | 9402 |
| Poverty Ridge | 6900 | 6524 |
| Cove | 8700 | 7698 |
| Edna | 11680 | 9561 |
| Oakley Ridge | 7815 | 7189 |
| Wire | 7136 | 5834 |
| Mahogany | 8783 | 7308 |
| Wales | None | 7808 |
| Castleton Tower | 6234 | 4801 |
| Ken's Lake | None | 5244 |

## one-week timing test
unique chunks for all sites: ['3.3', '4.3']
91 hours x 123 vars x 2 chunks = 22386 requests
bytes by file: sfc 200.6 MB, prs 242.9 MB
took 57 s, 443.4 MB, 392 req/s
failures: entire_atmosphere/LTNG (404): 182; surface/CPOFP (404): 182; surface/PRATE (404): 182
extrapolated to 6 years of the same hours: 5.0 h, 138.7 GB
wrote probe/sample.csv

## archive coverage spot checks (surface/HPBL, chunk of first site)
- 2016-01-15 20Z: HTTP 404
- 2016-07-15 20Z: HTTP 404
- 2017-01-15 20Z: HTTP 200
- 2017-07-15 20Z: HTTP 200
- 2018-01-15 20Z: HTTP 200
- 2018-07-15 20Z: HTTP 200
- 2019-01-15 20Z: HTTP 200
- 2019-07-15 20Z: HTTP 200
- 2020-01-15 20Z: HTTP 200
- 2020-07-15 20Z: HTTP 200
- 2021-01-15 20Z: HTTP 200
- 2021-07-15 20Z: HTTP 200
- 2022-01-15 20Z: HTTP 200
- 2022-07-15 20Z: HTTP 200
- 2023-01-15 20Z: HTTP 200
- 2023-07-15 20Z: HTTP 200
- 2024-01-15 20Z: HTTP 200
- 2024-07-15 20Z: HTTP 200
- 2025-01-15 20Z: HTTP 200
- 2025-07-15 20Z: HTTP 200
- 2026-01-15 20Z: HTTP 200
- 2026-07-15 20Z: HTTP 200
- latest check 2026-11-24 12Z: HTTP 200
- latest check 2026-11-24 09Z: HTTP 200
- latest check 2026-11-24 03Z: HTTP 200
- latest check 2026-11-23 15Z: HTTP 200
