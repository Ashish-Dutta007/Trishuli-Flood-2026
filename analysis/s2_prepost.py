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

# The public figure zooms to the readable downstream reach. At full-corridor
# scale a 60--120 m channel is only a few display pixels and the result is hard
# to see without GIS experience.
VW, VS, VE, VN = 85.11, 27.855, 85.205, 27.995
fig = plt.figure(figsize=(15, 9), facecolor="#0c131a")
gs = fig.add_gridspec(3, 2, height_ratios=[0.14, 1, 0.27], hspace=0.10, wspace=0.025)
head = fig.add_subplot(gs[0, :]); head.axis("off")
head.text(0, 0.76, "The readable downstream channel is wider after the event",
          color="#e9eff4", fontsize=19, fontweight="bold", va="center")
head.text(0, 0.31, "Same place, scale and image stretch  |  Bidur to Betrawati",
          color="#9ad6ea", fontsize=11.5, va="center")

axes = [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
for ax, (label, (rgb, mask)) in zip(axes, panels.items()):
    ax.imshow(stretch(rgb, LO, HI, mask), extent=[W, E, S, N], aspect="auto",
              interpolation="bilinear")
    ax.set_xlim(VW, VE); ax.set_ylim(VS, VN)
    r0 = max(0, int((N - VN) / (N - S) * mask.shape[0]))
    r1 = min(mask.shape[0], int((N - VS) / (N - S) * mask.shape[0]))
    c0 = max(0, int((VW - W) / (E - W) * mask.shape[1]))
    c1 = min(mask.shape[1], int((VE - W) / (E - W) * mask.shape[1]))
    view_cloud = mask[r0:r1, c0:c1].mean() * 100
    ax.set_title(f"{label}    ({view_cloud:.0f}% cloud / shadow)",
                 color="#e9eff4", fontsize=13, pad=9, fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color("#2a3844")
    for lon, lat, nm in [(85.1860, 27.9731, "Betrawati"), (85.1465, 27.8953, "Bidur"),
                         (85.1101, 27.8600, "Devighat")]:
        if W < lon < E and S < lat < N:
            ax.plot(lon, lat, "o", ms=5, mfc="none", mec="#ffd166", mew=1.6)
            ax.annotate(nm, (lon, lat), xytext=(7, 0), textcoords="offset points",
                        color="#ffd166", fontsize=9.5, va="center")
    ax.annotate("Follow the river ribbon", xy=(85.135, 27.914), xytext=(85.122, 27.945),
                color="#e9eff4", fontsize=9.5, fontweight="bold",
                arrowprops={"arrowstyle": "->", "color": "#e9eff4", "lw": 1.4},
                bbox={"boxstyle": "round,pad=0.25", "fc": "#0c131a", "ec": "#2a3844", "alpha": .9})

summary = fig.add_subplot(gs[2, :]); summary.axis("off")
summary.text(0, .90, "MEDIAN WETTED WIDTH ACROSS 46 CLEAR CROSS-SECTIONS",
             color="#9ad6ea", fontsize=10.5, fontweight="bold", transform=summary.transAxes)
for y, label, width, colour in [(.60, "12 AUG", 60, "#5cb9d6"),
                                (.30, "27 AUG", 120, "#e8776b")]:
    summary.text(.02, y, label, color="#b4c2ce", fontsize=11, fontweight="bold",
                 va="center", transform=summary.transAxes)
    x0, x1 = .13, .13 + width / 120 * .36
    summary.plot([x0, x1], [y, y], color=colour, lw=11, solid_capstyle="butt",
                 transform=summary.transAxes, clip_on=False)
    summary.text(x1 + .015, y, f"{width} m", color="#e9eff4", fontsize=14,
                 fontweight="bold", va="center", transform=summary.transAxes)
summary.text(.67, .55, "40 OF 46", color="#e9eff4", fontsize=19, fontweight="bold",
             transform=summary.transAxes)
summary.text(.67, .32, "cross-sections were wider after", color="#b4c2ce", fontsize=11,
             transform=summary.transAxes)
summary.text(.98, .04, "Dark = water  |  Pale pink = wet sediment  |  Grey = no reading through cloud",
             color="#8394a2", fontsize=9.5, ha="right", transform=summary.transAxes)
fig.text(0.5, 0.012, "Copernicus Sentinel-2 L2A, bands 11/8/4. Comparison only; not a mapped flood extent.",
         ha="center", color="#6b7a88", fontsize=8.5)
plt.subplots_adjust(left=.025, right=.975, top=.975, bottom=.045)
plt.savefig("out/s2_prepost.png", dpi=125, facecolor="#0c131a")
print("wrote out/s2_prepost.png")
