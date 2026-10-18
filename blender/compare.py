"""
Side-by-side: original photo (left) | Blender render (right).
  Blender -b --python compare.py
"""
import bpy, os, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PAIRS = [
    ('IMG_20261016_141426.jpg', 'cam_photo1_final.png', 'photo1_vs_render.png'),
    ('IMG_20261016_141445.jpg', 'cam_photo2_final.png', 'photo2_vs_render.png'),
    ('IMG_20261016_141455.jpg', 'cam_photo3_final.png', 'photo3_vs_render.png'),
]


def load(path, size=None):
    im = bpy.data.images.load(path)
    if size:
        im.scale(*size)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


for photo, render, out in PAIRS:
    r = load(os.path.join(HERE, 'renders', render))
    h, w = r.shape[:2]
    p = load(os.path.join(ROOT, photo), (w, h))
    gap = np.ones((h, 10, 4), dtype=np.float32)
    both = np.concatenate([p, gap, r], axis=1)
    im = bpy.data.images.new(out, both.shape[1], both.shape[0], alpha=True)
    im.pixels.foreach_set(both.ravel())
    im.filepath_raw = os.path.join(HERE, 'compare', out)
    im.file_format = 'PNG'
    im.save()
    print('WROTE', im.filepath_raw)
