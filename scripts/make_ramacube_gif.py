"""Render a rotating GIF of RamaCube's own 3D figure.

Loads the exact plotly figure embedded in https://moracore.github.io/RamaCube/
(default Full Rama view, shipped colormap), spins the scene camera a full turn,
and stitches a looping GIF. Same idea as make_glycine_gif.py, but the figure is
RamaCube's rather than ProtNRD's.
"""
import io
import os
import json
import math

import plotly.io as pio
from PIL import Image

FIG_JSON = "/tmp/ramacube_fig.json"
OUT = os.path.expanduser("~/Downloads/ramacube_full_rama.gif")
N_FRAMES = 36
SIZE = 640

fig = pio.from_json(json.dumps(json.load(open(FIG_JSON))))

# RamaCube ships mode buttons via layout.updatemenus; strip them so they don't
# render into the static frames.
fig.layout.updatemenus = None
fig.update_layout(width=SIZE, height=SIZE, margin=dict(l=0, r=0, b=0, t=40))

# Spin the default plotly camera (eye ~1.25 on each axis) around z.
r = math.hypot(1.25, 1.25)
z = 1.25

frames = []
for i in range(N_FRAMES):
    ang = math.atan2(1.25, 1.25) + 2 * math.pi * i / N_FRAMES
    fig.update_layout(scene_camera=dict(
        eye=dict(x=r * math.cos(ang), y=r * math.sin(ang), z=z)
    ))
    png = fig.to_image(format="png", width=SIZE, height=SIZE, scale=1)
    frames.append(Image.open(io.BytesIO(png)).convert("RGB"))
    print(f"frame {i + 1}/{N_FRAMES}", flush=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=80, loop=0, optimize=True)
print("Saved", OUT, f"({len(frames)} frames)")
