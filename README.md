# Wasatch Soaring Forecast

Paragliding forecasts for Wasatch and Utah sites, rated against years of HRRR history.

Live page: https://wasatchsoaring.github.io/forecast/

## How it works

1. **History** (`backfill.yml`, then `daily.yml` every morning). Hourly HRRRv4 analyses from December 2020 on, 8 am to 9 pm Utah time, for every launch. Read from the University of Utah HRRR-Zarr archive on AWS. Stored in `data/hrrr/YYYY-MM.parquet`.
2. **Rating** (`scripts/rate.py`). Per hour: thermal top (boundary layer top, capped at cumulus base), W* thermal strength, wind at launch height, wind in the thermal layer, storms. An hour is soarable when launch wind is inside the club limits in `sites.json`, nothing is storming, and thermals reach 1,000 ft over launch at W* of 1 m/s or more. Ridge sites score on wind in range instead. Every history day gets a score in `data/climo.parquet`.
3. **Forecast** (`forecast.yml`, hourly). Newest 48-hour HRRR run with the newest hourly run laid over it, rated the same way, then ranked against the same site's history within 3 weeks of the date. Top 25% and Top 5% labels come from that rank.
4. **Page** (`scripts/page.html`, built by `scripts/build_site.py`). Published to GitHub Pages and kept on the `gh-pages` branch.

## Files

- `sites.json` launches, elevations, wind limits (UHGPGA, CUASA, or generic where not known yet)
- `data/gridpoints.json` the HRRR grid point and model terrain for each launch
- `probe/` notes from testing the archive

## Changing things

- Add or move a site: edit `sites.json` and `data/gridpoints.json`, delete `data/hrrr/*.parquet`, change `backfill.trigger` and push. The backfill pulls the full history again (about an hour) and re-rates it.
- Re-rate history after changing `rate.py`: push a change to `climo.trigger`.
