#!/usr/bin/env python3
"""Render the clearest available post-event SkySat look at Syabrubesi.

This is a single-date visual review, not a change comparison. Cloud and valley
haze obscure much of the target channel, so the output must not be interpreted
as a mapped flood edge.
"""
import json
import os
import warnings

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import transform
from rasterio.windows import from_bounds


matplotlib.use("Agg")
warnings.filterwarnings("ignore")
os.environ.update(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_MAX_RETRY="4",
)

SOURCE = (
    "/vsicurl/https://data.source.coop/planet/disasterdata/"
    "nepal-flash-flood-2026-08-26/post-event/2026-08-27/items/"
    "20260827_020055_ssc1_u0002/20260827_020055_ssc1_u0002_visual.tif"
)
WEST, SOUTH, EAST, NORTH = 85.3200, 28.1480, 85.3360, 28.1600


def main():
    with open("out/mapdata.json", encoding="utf-8") as source:
        mapdata = json.load(source)

    with rasterio.open(SOURCE) as dataset:
        bounds = transform(
            "EPSG:4326", dataset.crs, [WEST, EAST], [SOUTH, NORTH]
        )
        window = from_bounds(
            bounds[0][0], bounds[1][0], bounds[0][1], bounds[1][1],
            transform=dataset.transform,
        )
        output_width = 1900
        output_height = int(output_width * window.height / window.width)
        image = dataset.read(
            [1, 2, 3], window=window, boundless=True, fill_value=0,
            out_shape=(3, output_height, output_width),
        )

    rgb = np.transpose(image, (1, 2, 0))
    figure, axis = plt.subplots(
        figsize=(13, 13 * output_height / output_width), facecolor="#0c131a"
    )
    axis.set_facecolor("#0c131a")
    axis.imshow(
        rgb, extent=[WEST, EAST, SOUTH, NORTH], aspect="auto",
        interpolation="bilinear",
    )

    for line in mapdata["stem"]:
        segment = [
            (lon, lat) for lon, lat in line
            if WEST - 0.01 < lon < EAST + 0.01
            and SOUTH - 0.01 < lat < NORTH + 0.01
        ]
        if len(segment) > 1:
            axis.plot(
                [point[0] for point in segment],
                [point[1] for point in segment],
                color="#4fc3f7", lw=1.1, ls=(0, (6, 4)), alpha=0.85,
                label="channel mapped in OpenStreetMap before the flood",
            )

    handles, labels = axis.get_legend_handles_labels()
    if handles:
        legend = axis.legend(
            [handles[0]], [labels[0]], loc="lower left", fontsize=9,
            frameon=True, facecolor="#131c25", edgecolor="#2a3844",
            labelcolor="#cfd9e2",
        )
        legend.get_frame().set_alpha(0.9)

    axis.plot(85.3289, 28.1545, "o", ms=7, mfc="none", mec="#ffd166", mew=1.8)
    axis.annotate(
        "Syabrubesi", (85.3289, 28.1545), xytext=(10, 0),
        textcoords="offset points", color="#ffd166", fontsize=11,
        va="center", fontweight="bold",
    )
    axis.set_xlim(WEST, EAST)
    axis.set_ylim(SOUTH, NORTH)
    axis.set_xticks([])
    axis.set_yticks([])
    for spine in axis.spines.values():
        spine.set_color("#2a3844")

    figure.suptitle(
        "Syabrubesi, 27 August 2026 at 02:00 UTC",
        color="#e9eff4", fontsize=16, fontweight="bold", y=0.975,
    )
    figure.text(
        0.5, 0.938,
        "SkySat, 0.79 m, about 23 hours after the flood.",
        ha="center", color="#8394a2", fontsize=10.5,
    )
    figure.text(
        0.5, 0.028,
        "Single date, not a change comparison. Cloud and haze obscure the channel.",
        ha="center", color="#ffb199", fontsize=9.5,
    )
    figure.text(
        0.5, 0.007,
        "Planet Crisis Response via Source Cooperative, CC BY-NC 4.0.",
        ha="center", color="#6b7a88", fontsize=8.5,
    )
    figure.tight_layout(rect=[0, 0.045, 1, 0.925])
    figure.savefig(
        "out/skysat_syabrubesi_detail.jpg", dpi=140,
        facecolor="#0c131a", pil_kwargs={"quality": 88},
    )


if __name__ == "__main__":
    main()
