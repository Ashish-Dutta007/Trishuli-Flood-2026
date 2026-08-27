# Trishuli-Flood-2026

Open analysis of the 26 August 2026 flood in the Bhote Koshi and Trishuli
corridor, Rasuwa and Nuwakot districts, Nepal.

Published pages:

- Interactive map: https://climascope.hutton.ac.uk/trishuli
- Evolving research note: https://climascope.hutton.ac.uk/trishuli/report

This repository holds the code behind those pages. It is a working research
effort, not an official assessment, damage survey or emergency product.

## What the scripts do

Every source below is public and none of these scripts needs an API key.

| Script | Purpose |
| --- | --- |
| `dem_corridor.py` | Slope, relief and channel gradient along the river from the Copernicus DEM, read windowed over HTTP. Produces `outputs/reach_metrics.csv`. |
| `terrain_layers.py` | Hillshade and a banded slope overlay, warped onto the basemap grid. |
| `fetch_tiles.py` | Stitches Esri basemap tiles for offline figures. |
| `corridor_cloud.py` | Reads the Sentinel-2 scene classification along the channel, so cloud is judged over the river rather than by the tile average. |
| `s2_prepost.py` | Pre and post short-wave infrared composite. One stretch is computed across both dates; a per-date stretch can manufacture apparent change. |
| `channel_width.py` | Wetted area and cross-section widths from MNDWI, comparing only pixels cloud-free on both dates, at three thresholds. |
| `skysat_detail.py` | Reviews the sharpest Planet Crisis Response view at Syabrubesi and labels it as a single-date, cloud-and-haze-limited observation. |
| `refresh_osm_extract.py` | Re-cuts the corridor from HOT raw-data-api, which tracks OSM minutely. It rejects the export clipping boundary and implausibly small feature counts before replacing a snapshot. |
| `hot_changesets.py` | Counts the mapping campaign from public OSM changesets. |
| `hot_before_after.py` | Renders map coverage before and after the campaign. |
| `poll_copernicus.py` | Watches the Copernicus catalogue for the first post-event scene. Idempotent, safe under cron. |
| `rebuild_mapdata.py`, `build_mapdata.py`, `build_payload.py` | Build the data the published pages read. |

## Data sources

- Copernicus Sentinel-1 and Sentinel-2, and Copernicus DEM GLO-30 (ESA / European Union)
- Sentinel-2 L2A COGs via AWS Open Data (Element 84 Earth Search)
- OpenStreetMap contributors, ODbL, via HOT raw-data-api and HDX
- Nepal COD-AB administrative boundaries, Survey Department of Nepal and UN RCO, CC BY-IGO
- USGS and EMSC earthquake catalogues
- Open-Meteo forecast and elevation APIs
- Planet Crisis Response imagery via Source Cooperative, CC BY-NC 4.0
- Esri World Imagery and related services for basemap context

Volunteers mapping this corridor through the HOT Tasking Manager have added
several thousand buildings since the flood. The exposure layers build on their
work: https://tasks.hotosm.org/projects/62904

## Limits

The mapped seismic source is a location, not a collapse outline. Terrain metrics
are descriptive, not hazard probabilities. The channel-width comparison measures
a difference between two dates and does not attribute it to a cause; both dates
fall in the monsoon. No flood extent is published, and no casualty or damage
figures are derived here. The available sub-metre SkySat view is not used for
change mapping because cloud and valley haze obscure the target channel.

## Contributing

Corrections, field observations, gauge records and post-event imagery are
welcome, through issues or by email to meashishdutta@gmail.com.

## Licence

Code is MIT. Data retrieved by these scripts stays under the licence of its
source, listed above.

## Reproducing

Each script is standalone and writes into `data/` and `out/`, both gitignored.
Run them from the repository root with the dependencies in `requirements.txt`.
