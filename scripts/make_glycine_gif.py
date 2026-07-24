"""Render a rotating GIF of the v8 Glycine phi/psi surface in the Magma colormap.

Uses ProtNRD's OWN renderer: pulls the exact cached 3D data the Pairwise app draws
from proteins_v8.db and feeds it to v8.callbacks.rendering.create_3D_figure, which
builds the plotly go.Surface. Frames are the real app surface; we spin the scene
camera and export each with plotly/kaleido, then stitch a looping GIF.
"""
import io
import os
import math
import sqlite3

import plotly.io as pio
from PIL import Image

from v8.callbacks.data_fetching import get_plot_key_for_query, fetch_v8_data
from v8.callbacks.rendering import create_3D_figure

DB = os.path.join("data", "proteins_v8.db")
OUT = os.path.expanduser("~/Downloads/glycine_phi_psi_magma_v8.gif")
N_FRAMES = 36
SIZE = 640
INV1, INV2 = "tau_NA", "tau_AC"   # phi, psi == "the glycine structure"
RES1 = "G"                        # Glycine
COLORMAP = "Magma"

plot_key = get_plot_key_for_query(INV1, INV2, offset=0, res1=RES1, res2="Any", pos=0)
conn = sqlite3.connect(DB)
data = fetch_v8_data(conn, plot_key)
conn.close()

fig = create_3D_figure(
    data["figure_data_3d"],
    title="Glycine  φ vs ψ  —  v8  (Magma)",
    uirevision_key="glycine-magma",
    log_scale=False,   # app default: Linear
    colormap=COLORMAP,
    inv1_name=INV1,
    inv2_name=INV2,
    smooth=True,       # app default: show isolated bins
)
fig.update_layout(width=SIZE, height=SIZE, margin=dict(l=0, r=0, b=0, t=40))

# Base camera from rendering.py: eye=(-1.5, -2.5, 1.5). Spin the horizontal
# component around z, holding elevation fixed.
bx, by, bz = -1.5, -2.5, 1.5
r = math.hypot(bx, by)
theta0 = math.atan2(by, bx)

frames = []
for i in range(N_FRAMES):
    ang = theta0 + 2 * math.pi * i / N_FRAMES
    fig.update_layout(scene_camera=dict(
        eye=dict(x=r * math.cos(ang), y=r * math.sin(ang), z=bz)
    ))
    png = fig.to_image(format="png", width=SIZE, height=SIZE, scale=1)
    frames.append(Image.open(io.BytesIO(png)).convert("RGB"))
    print(f"frame {i + 1}/{N_FRAMES}", flush=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=80, loop=0, optimize=True)
print("Saved", OUT, f"({len(frames)} frames)")
