"""Side-by-side of the mask region: original, SDXL one-shot, Flux Fill.

No high-frequency metric here. That metric was shown to be invalid for
removals - it rewards texture density, so a regenerated bird outscores a
clean removal. Judgement is by eye on the sheet.
"""
import os, sys
import numpy as np
from PIL import Image

SENT = os.path.expanduser("~/git/RapidRAW-AI-Connector/cache/sent")
full = np.array(Image.open(f"{SENT}/last_sent_mask.png").split()[-1]) > 127

RUNS = [("original", f"{SENT}/last_sent_image.jpg"),
        ("SDXL one-shot 1280", "bird_desc_1280.png")]
RUNS += [(l, p) for l, p in zip(sys.argv[1::2], sys.argv[2::2])]

ys, xs = np.where(full)
pad = 120
y0, y1 = max(0, ys.min()-pad), ys.max()+pad
x0, x1 = max(0, xs.min()-pad), xs.max()+pad

tiles, W = [], 1100
for label, p in RUNS:
    if not os.path.exists(p):
        print(f"MISSING {p}"); continue
    im = Image.open(p).convert("RGB").crop((x0, y0, x1, y1))
    im = im.resize((W, int(W * im.height / im.width)), Image.LANCZOS)
    tiles.append((label, im))

h = tiles[0][1].height
sheet = Image.new("RGB", (W, h * len(tiles)), (20, 20, 20))
for i, (_, im) in enumerate(tiles):
    sheet.paste(im, (0, i * h))
sheet.save("flux_compare.png")
print("flux_compare.png  top to bottom: " + " / ".join(l for l, _ in tiles))
