from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "out" / "align_check2.jpg"
TARGET = Path("/mnt/shared/docker/climascope/app/static/trishuli/social-card.png")


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


canvas = Image.new("RGB", (1200, 630), "#edf1f4")
source = Image.open(SOURCE).convert("RGB")

# Keep the full mapped corridor visible in the right-hand image field.
scale = max(680 / source.width, 630 / source.height)
source = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
left = max(0, (source.width - 680) // 2)
source = source.crop((left, 0, left + 680, 630))
source = ImageEnhance.Contrast(source).enhance(1.05)
canvas.paste(source, (520, 0))

draw = ImageDraw.Draw(canvas)
draw.rectangle((0, 0, 520, 630), fill="#f8fafb")
draw.rectangle((0, 0, 8, 630), fill="#0f6f8c")
draw.text((50, 54), "INTERACTIVE GEOSPATIAL NOTE", font=font(17, True), fill="#0b5266")
draw.multiline_text((50, 103), "Bhote Koshi-\nTrishuli flood", font=font(48, True), fill="#131c25", spacing=4)
draw.multiline_text(
    (50, 238),
    "First post-event channel evidence,\nsource records, rainfall screening\nand the observations needed next.",
    font=font(23),
    fill="#3b4956",
    spacing=8,
)
draw.rectangle((50, 375, 457, 456), fill="#f2e3c6")
draw.text((68, 387), "60 TO 120 M MEDIAN WETTED WIDTH", font=font(14, True), fill="#6f480c")
draw.text((68, 420), "40 OF 46 CLEAR TRANSECTS WIDER", font=font(14, True), fill="#6f480c")
draw.text((50, 490), "Ashish Dutta  |  Geospatial researcher", font=font(18, True), fill="#131c25")
draw.text((50, 523), "Version 0.4  |  27 August 2026", font=font(16), fill="#697785")
draw.text((50, 576), "climascope.hutton.ac.uk/trishuli", font=font(16, True), fill="#0b5266")
draw.rectangle((520, 596, 1200, 630), fill="#131c25")
draw.text(
    (535, 605),
    "SENTINEL-2  |  USGS  |  Nepal DHM  |  Copernicus DEM",
    font=font(12),
    fill="#f8fafb",
)

TARGET.parent.mkdir(parents=True, exist_ok=True)
canvas.save(TARGET, optimize=True)
print(TARGET)
