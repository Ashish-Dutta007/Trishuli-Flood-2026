#!/usr/bin/env python3
"""Two-panel before/after of OSM building coverage during the HOT campaign."""
import json, math, warnings
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
warnings.filterwarnings("ignore")
Image.MAX_IMAGE_PIXELS = None

CUT = "2026-08-26"
meta = json.load(open("out/base_meta.json"))
RI = [m for m in meta if m["svc"] == "imagery"][0]
img = Image.open("out/base_imagery_z13.jpg").convert("RGB")
W, S, E, N = RI["W"], RI["S"], RI["E"], RI["N"]
mx = lambda lon: (lon + 180) / 360
my = lambda lat: (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2
mW, mE, mN, mS = mx(W), mx(E), my(N), my(S)

feats = json.load(open("data/hot_live/buildings.geojson"))["features"]
def centroid(g):
    c = g["coordinates"]
    while isinstance(c[0][0], list): c = c[0]
    a = np.array(c, dtype=float)
    return a[:, 0].mean(), a[:, 1].mean()
old, new = [], []
for f in feats:
    ts = (f["properties"].get("timestamp") or "")[:10]
    try: p = centroid(f["geometry"])
    except Exception: continue
    (new if ts >= CUT else old).append(p)
old = np.array(old); new = np.array(new)

# crop imagery to the mapped corridor
allpts = np.vstack([old, new])
pad = 0.012
w, e = allpts[:,0].min()-pad, allpts[:,0].max()+pad
s, n = allpts[:,1].min()-pad, allpts[:,1].max()+pad
def px(lon, lat):
    return ((mx(lon)-mW)/(mE-mW)*img.size[0], (my(lat)-mN)/(mS-mN)*img.size[1])
x0,y0 = px(w,n); x1,y1 = px(e,s)
crop = img.crop((int(x0),int(y0),int(x1),int(y1)))

fig, axes = plt.subplots(1, 2, figsize=(15, 8.6), facecolor="#0c131a")
# Framing matters: this is map coverage, not built structures. "Before/after" on a
# flood story reads as buildings having increased, which is the opposite of the truth.
titles = [f"Recorded in OpenStreetMap before 26 Aug   ({len(old):,})",
          f"Recorded now, after two days of mapping   ({len(feats):,})"]
# pre-existing buildings are styled identically in both panels, so the only
# visual difference between them is what the campaign added
PRE = (old, "#cfd9e2", 7, 0.6, "mapped before 26 Aug")
for ax, title, sets in zip(axes, titles,
                           [[PRE], [PRE, (new, "#ff5c33", 9, 0.95, "digitised 26 to 27 Aug")]]):
    ax.imshow(crop, extent=[w,e,s,n], aspect="auto")
    for pts, col, sz, al, lab in sets:
        if len(pts): ax.scatter(pts[:,0], pts[:,1], s=sz, c=col, alpha=al,
                                linewidths=0, label=lab, zorder=3)
    ax.set_xlim(w,e); ax.set_ylim(s,n)
    ax.set_title(title, color="#e9eff4", fontsize=14, pad=11, fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color("#2a3844")
    leg = ax.legend(loc="lower left", frameon=True, fontsize=9.5, facecolor="#131c25",
                    edgecolor="#2a3844", labelcolor="#b4c2ce")
    leg.get_frame().set_alpha(0.9)

fig.suptitle("Volunteers are mapping the Bhote Koshi to Trishuli corridor",
             color="#e9eff4", fontsize=16.5, fontweight="bold", y=0.977)
fig.text(0.5, 0.928,
         "Existing buildings digitised from satellite imagery. This is map coverage improving, not new construction.",
         ha="center", color="#ffb199", fontsize=11)
fig.text(0.5, 0.045,
         "83 mappers, 350 changesets, 40,565 edits across 5 HOT Tasking Manager projects, 26 to 27 August 2026",
         ha="center", color="#8394a2", fontsize=10.5)
fig.text(0.5, 0.017,
         "Data: OpenStreetMap contributors (ODbL) via HOT raw-data-api  |  Imagery: Esri, Vantor, Earthstar Geographics",
         ha="center", color="#6b7a88", fontsize=8.5)
plt.tight_layout(rect=[0, 0.07, 1, 0.915])
plt.savefig("out/hot_before_after.png", dpi=125, facecolor="#0c131a")
print("wrote out/hot_before_after.png")
print(f"  before {len(old):,} | new {len(new):,} | total {len(feats):,}")
