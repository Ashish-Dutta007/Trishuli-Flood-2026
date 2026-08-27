#!/usr/bin/env python3
"""Pre/post Sentinel-2 false colour over the cloud-free downstream reach.

SWIR/NIR/Red: water reads near black, wet sediment dull cyan, vegetation red.
Cloud and cloud shadow are masked from the scene classification layer and drawn
as flat grey, so nothing obscured can be mistaken for change.
"""
import numpy as np, rasterio, warnings, os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
warnings.filterwarnings("ignore")
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="4")

# Asset hrefs come from the STAC catalogue rather than being constructed: the
# files are named by band (B11.tif), not by the STAC key (swir16).
STAC = "https://earth-search.aws.element84.com/v1/search"


def hrefs(scene_ids):
    import json, urllib.request
    body = json.dumps({"collections": ["sentinel-2-l2a"], "ids": scene_ids, "limit": 20}).encode()
    req = urllib.request.Request(STAC, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        feats = json.load(r)["features"]
    return {f["id"]: {k: v["href"] for k, v in f["assets"].items()} for f in feats}
W, S, E, N = 85.09, 27.845, 85.235, 28.06          # clear downstream reach
SCENES = {"12 August, before": ["S2C_45RUM_20260812_0_L2A", "S2C_45RUL_20260812_0_L2A"],
          "27 August, after":  ["S2B_45RUM_20260827_0_L2A", "S2B_45RUL_20260827_0_L2A"]}
ASSETS = None
BANDS = ["swir16", "nir", "red"]
CLOUD = {3, 8, 9, 10}          # shadow, cloud med/high, cirrus


# B11 and SCL are 20 m while B08 and B04 are 10 m, so every band is resampled
# onto one fixed grid rather than inheriting its native window size.
TARGET = (1190, 710)          # rows, cols: the window at roughly 20 m


def read(sid, band):
    url = ASSETS[sid][band]
    with rasterio.open(url) as ds:
        b = transform_bounds("EPSG:4326", ds.crs, W, S, E, N)
        win = from_bounds(*b, transform=ds.transform)
        resample = (rasterio.enums.Resampling.nearest if band == "scl"
                    else rasterio.enums.Resampling.bilinear)
        arr = ds.read(1, window=win, boundless=True, fill_value=0,
                      out_shape=TARGET, resampling=resample)
        return arr.astype("float32")


def compose(parts):
    """Mosaic the tiles that cover the window, preferring valid pixels."""
    stack = {}
    for band in BANDS + ["scl"]:
        layers = [read(sid, band) for sid in parts]
        out = layers[0].copy()
        for l in layers[1:]:
            out = np.where(out <= 0, l, out)
        stack[band] = out
    rgb = np.dstack([stack[b] for b in BANDS])
    scl = stack["scl"]
    mask = np.isin(scl, list(CLOUD))
    return rgb, mask


def stretch(rgb, lo, hi, mask):
    out = np.clip((rgb - lo) / max(hi - lo, 1), 0, 1)
    out[mask] = 0.42                      # flat grey where the view is blocked
    return out


ASSETS = hrefs([sid for parts in SCENES.values() for sid in parts])
print("resolved assets for:", sorted(ASSETS))

# One stretch for both dates. A per-panel stretch would rescale each image
# independently and could manufacture apparent change where there is none.
panels = {label: compose(parts) for label, parts in SCENES.items()}
clear = np.concatenate([r[~m & (r[..., 0] > 0)].ravel() for r, m in panels.values()])
LO, HI = np.nanpercentile(clear, [2, 96])
print(f"shared stretch: {LO:.0f} to {HI:.0f} (from cloud-free pixels of both dates)")

fig, axes = plt.subplots(1, 2, figsize=(15, 8.2), facecolor="#0c131a")
for ax, (label, (rgb, mask)) in zip(axes, panels.items()):
    ax.imshow(stretch(rgb, LO, HI, mask), extent=[W, E, S, N], aspect="auto",
              interpolation="bilinear")
    ax.set_title(f"{label}    ({mask.mean()*100:.0f}% cloud in view)",
                 color="#e9eff4", fontsize=13.5, pad=10, fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color("#2a3844")
    for lon, lat, nm in [(85.1860, 27.9731, "Betrawati"), (85.1465, 27.8953, "Bidur"),
                         (85.1101, 27.8600, "Devighat")]:
        if W < lon < E and S < lat < N:
            ax.plot(lon, lat, "o", ms=5, mfc="none", mec="#ffd166", mew=1.6)
            ax.annotate(nm, (lon, lat), xytext=(7, 0), textcoords="offset points",
                        color="#ffd166", fontsize=9.5, va="center")

fig.suptitle("Trishuli corridor, Sentinel-2 short-wave infrared composite",
             color="#e9eff4", fontsize=16, fontweight="bold", y=0.975)
fig.text(0.5, 0.925, "Water reads dark, wet sediment pale. Grey areas are cloud or cloud shadow, where nothing can be read.",
         ha="center", color="#8394a2", fontsize=10.5)
fig.text(0.5, 0.03, "Copernicus Sentinel-2 L2A via AWS Open Data. Bands 11, 8, 4, identical stretch on both dates. Comparison only, no change detection applied.",
         ha="center", color="#6b7a88", fontsize=8.5)
plt.tight_layout(rect=[0, 0.055, 1, 0.912])
plt.savefig("out/s2_prepost.png", dpi=125, facecolor="#0c131a")
print("wrote out/s2_prepost.png")
