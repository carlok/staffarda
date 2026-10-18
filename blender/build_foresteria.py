"""
Staffarda Abbey guesthouse (foresteria), ground floor -- rough reconstruction from 3 photos.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b --python build_foresteria.py
Out:  foresteria.blend  (next to this script)

Everything is in metres. Room axis = +Y (near end wall y=0, far end wall y=L), X across.
Dimensions were estimated from perspective in the photos (camera height ~1.45 m, ~71 deg
horizontal FOV), so they are plausible, not surveyed.
"""
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(11)

# ------------------------------------------------------------------ parameters
S = 5.4                      # square bay side
NX, NY = 2, 5                # 2 naves, 5 bays long
W, L = NX * S, NY * S
HS = 2.50                    # springing height (column capital / wall corbel top)
R_SIDE = 3.05                # rise of transverse, longitudinal and wall arches
R_DIAG = 3.90                # rise of the diagonal ribs -> keystone at HS + R_DIAG
HK = HS + R_DIAG
DOME = 0.18                  # extra swelling of the web cells
WALL_T = 1.2                 # wall thickness (structural_check.py: >= 0.95 m for the dormitory-floor case)
DOOR_CENTRES = (18.5, 20.1)  # right-wall doorways, along y; kept >= 0.7 m clear of the corbels at y = 16.2 and 21.6
WITH_FURNITURE = os.environ.get('FURNITURE') == '1'   # chairs, tables, extinguishers from the photos -> foresteria_furnished.blend
A_D = S * math.sqrt(2) / 2   # half-span of a diagonal rib

W_TRANS, W_DIAG, W_WALL = 0.56, 0.32, 0.42   # rib widths
D_BELOW_BIG, D_BELOW_DIAG = 0.34, 0.16       # how far ribs hang below the web surface (transverse arch total depth 0.50 m from structural_check.py)
D_BELOW_WALL = 0.14          # wall arches hang this far below the web
D_ABOVE = 0.16               # hidden part of each rib above the web
CORBEL = (0.40, 0.60, 0.65)  # wall corbels: projection, width, height (sized in structural_check.py)
DOOR_W, DOOR_TOP = 1.10, 2.55  # right-wall doorways: width and height of the arched head
CAPITAL_STYLES = ('plain', 'leaf', 'panel', 'teeth')   # columns 1..4 from the entrance end, as in photos 1 and 2
UPLIGHT_W = 120              # watts per uplight (two per capital): vault about as bright as the walls, as in photo 2
FLOOR_BRICK_W = 0.14          # floor bricks are 2:1, 28 x 14 cm, laid in herringbone
SPRINGER_PROFILE = [(0.47, HS), (0.45, HS + 0.18), (0.38, HS + 0.55)]   # (radius, z): low brick block above each capital (round, smooth-shaded)
# splayed arched windows: inner (room side) and outer opening, sill heights z, head heights z, widths
WIN_SIDE = dict(zb_in=1.25, zt_in=3.40, w_in=1.15, zb_out=1.75, zt_out=3.05, w_out=0.42)   # left wall, one per bay
WIN_END = dict(zb_in=1.10, zt_in=3.25, w_in=1.05, zb_out=1.80, zt_out=3.00, w_out=0.40)    # end walls, one per nave
WEB_SINK = 0.12              # plaster cells dip this far where they meet a rib, so rib sides always reach the plaster


# ------------------------------------------------------------------ small helpers
def prof(x, a, r):
    """Height above springing of an arch of half-span a and rise r at offset x from the crown.
    r >= a: two-centred pointed arch. r < a: semi-ellipse."""
    x = abs(x)
    if x >= a:
        return 0.0
    if r >= a:
        xc = (a * a - r * r) / (2 * a)
        rho = a - xc
        return math.sqrt(max(rho * rho - (x - xc) ** 2, 0.0))
    return r * math.sqrt(1 - (x / a) ** 2)


def clustered(n):
    """0..1 with points clustered at both ends (arches are steep there)."""
    return [0.5 - 0.5 * math.cos(math.pi * i / n) for i in range(n + 1)]


def arch_pts(p0, p1, rise, n=40):
    """Points along a pointed arch between p0 and p1 (same height)."""
    p0, p1 = Vector(p0), Vector(p1)
    a = (p1 - p0).length / 2
    mid = (p0 + p1) / 2
    d = (p1 - p0).normalized()
    out = []
    for t in clustered(n):
        x = (t - 0.5) * 2 * a
        q = mid + d * x
        q.z = p0.z + prof(x, a, rise)
        out.append(q)
    return out


def to_obj(name, bm, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def add_box(bm, c, size, rotz=0.0):
    m = Matrix.Translation(c) @ Matrix.Rotation(rotz, 4, 'Z') @ Matrix.Diagonal((size[0], size[1], size[2], 1))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def add_cyl(bm, c, r1, r2, h, seg=24, rotx=0.0, roty=0.0):
    m = Matrix.Translation(c) @ Matrix.Rotation(roty, 4, 'Y') @ Matrix.Rotation(rotx, 4, 'X')
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h, matrix=m)


def lathe(bm, profile, nseg=48, rot=0.0, radial=None, smooth=True, cx=0.0, cy=0.0, cap_top=True, cap_bot=True):
    rings = []
    for (r, z) in profile:
        ring = []
        for k in range(nseg):
            th = 2 * math.pi * k / nseg + rot
            rr = r * (radial(th, z) if radial else 1.0)
            ring.append(bm.verts.new((cx + rr * math.cos(th), cy + rr * math.sin(th), z)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(nseg):
            f = bm.faces.new((a[k], a[(k + 1) % nseg], b[(k + 1) % nseg], b[k]))
            f.smooth = smooth
    if cap_top:
        bm.faces.new(rings[-1][::-1])
    if cap_bot:
        bm.faces.new(rings[0])


# ------------------------------------------------------------------ materials
class NB:
    """tiny node-builder"""

    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        self.m.use_nodes = True
        self.nt = self.m.node_tree
        self.N = self.nt.nodes
        self.bsdf = self.N['Principled BSDF']

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif sock.type == 'RGBA' and len(v) == 3:
            sock.default_value = (*v, 1.0)
        else:
            sock.default_value = v

    def node(self, kind, **props):
        n = self.N.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def coord(self, which='Object'):
        if not hasattr(self, '_tc'):
            self._tc = self.node('ShaderNodeTexCoord')
        return self._tc.outputs[which]

    def noise(self, scale, detail=5, rough=0.55, dist=0.0, vec=None):
        n = self.node('ShaderNodeTexNoise', noise_dimensions='3D')
        self.nt.links.new(vec if vec is not None else self.coord(), n.inputs['Vector'])
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['Distortion'].default_value = dist
        return n.outputs['Fac']

    def ramp(self, fac, stops, interp='LINEAR'):
        n = self.node('ShaderNodeValToRGB')
        n.color_ramp.interpolation = interp
        els = n.color_ramp.elements
        while len(els) > len(stops):
            els.remove(els[-1])
        while len(els) < len(stops):
            els.new(0.5)
        for e, (p, c) in zip(els, stops):
            e.position = p
            e.color = (c, c, c, 1) if isinstance(c, (int, float)) else (*c, 1)
        self.nt.links.new(fac, n.inputs['Fac'])
        return n.outputs['Color']

    def val(self, col_socket):
        n = self.node('ShaderNodeSeparateColor')
        self.nt.links.new(col_socket, n.inputs['Color'])
        return n.outputs['Red']

    def math(self, op, a, b=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        if b is not None:
            self.set(n.inputs[1], b)
        return n.outputs['Value']

    def mix(self, fac, a, b):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type='MIX')
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a)
        self.set(n.inputs[7], b)
        return n.outputs[2]

    def mul(self, a, b, fac=1.0):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY')
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a)
        self.set(n.inputs[7], b)
        return n.outputs[2]

    def bump(self, height, strength=0.3, dist=0.02):
        n = self.node('ShaderNodeBump')
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = dist
        self.nt.links.new(height, n.inputs['Height'])
        return n.outputs['Normal']

    def zcoord(self):
        n = self.node('ShaderNodeSeparateXYZ')
        self.nt.links.new(self.coord(), n.inputs['Vector'])
        return n.outputs['Z']

    def finish(self, color, rough=0.9, normal=None, spec=0.3):
        self.set(self.bsdf.inputs['Base Color'], color)
        self.set(self.bsdf.inputs['Roughness'], rough)
        self.bsdf.inputs['Metallic'].default_value = 0.0
        for nm in ('Specular IOR Level', 'Specular'):
            if nm in self.bsdf.inputs:
                self.bsdf.inputs[nm].default_value = spec
                break
        if normal is not None:
            self.nt.links.new(normal, self.bsdf.inputs['Normal'])
        return self.m


def flat(name, color, rough=0.6, metallic=0.0):
    b = NB(name)
    b.finish(color, rough)
    b.bsdf.inputs['Metallic'].default_value = metallic
    return b.m


def mat_plaster_wall():
    b = NB('plaster_wall')
    cream, ochre = (0.58, 0.46, 0.30), (0.50, 0.37, 0.20)
    big = b.noise(0.30, 6, 0.6)
    mid = b.noise(1.8, 7, 0.55)
    fine = b.noise(28, 4, 0.6)
    tone = b.mix(b.ramp(big, [(0.35, 0), (0.65, 1)]), cream, ochre)
    # weathered grey-green patches where render has flaked / damp creeps up
    worn_mask = b.math('MULTIPLY', b.val(b.ramp(mid, [(0.50, 0), (0.63, 1)])),
                       b.val(b.ramp(big, [(0.36, 0), (0.55, 1)])))
    col = b.mix(worn_mask, tone, (0.33, 0.31, 0.26))
    # exposed brick patches
    bm_ = b.val(b.ramp(b.noise(1.1, 3, 0.5, vec=b.coord('Object')), [(0.70, 0), (0.715, 1)]))
    col = b.mix(bm_, col, (0.30, 0.13, 0.08))
    # damp / grime at the foot of the wall
    z = b.zcoord()
    damp = b.val(b.ramp(z, [(0.0, 0.75), (1.1, 0.0)]))
    col = b.mix(b.math('MULTIPLY', damp, b.val(b.ramp(mid, [(0.3, 0.4), (0.7, 1.0)]))), col, (0.22, 0.20, 0.15))
    col = b.mul(col, b.ramp(fine, [(0.3, 0.8), (0.7, 1.05)]), 0.6)
    return b.finish(col, 0.92, b.bump(fine, 0.35, 0.03))


def mat_plaster_vault():
    b = NB('plaster_vault')
    cream, rosy, ochre = (0.80, 0.66, 0.48), (0.77, 0.57, 0.43), (0.64, 0.46, 0.23)
    big = b.noise(0.45, 6, 0.6, dist=0.5)
    mid = b.noise(2.2, 6, 0.6)
    fine = b.noise(40, 3, 0.6)
    tone = b.mix(b.ramp(big, [(0.30, 0), (0.70, 1)]), cream, rosy)
    stain = b.val(b.ramp(b.noise(0.8, 5, 0.65, dist=0.6), [(0.58, 0), (0.74, 1)]))
    col = b.mix(b.math('MULTIPLY', stain, 0.85), tone, ochre)
    grey = b.val(b.ramp(b.noise(1.6, 4, 0.6), [(0.62, 0), (0.80, 1)]))     # sooty / damp blotches
    col = b.mix(b.math('MULTIPLY', grey, 0.35), col, (0.45, 0.40, 0.34))
    col = b.mul(col, b.ramp(mid, [(0.3, 0.88), (0.7, 1.06)]), 0.8)
    col = b.mul(col, b.ramp(fine, [(0.3, 0.9), (0.7, 1.05)]), 0.7)
    h = b.math('ADD', fine, b.math('MULTIPLY', mid, 0.5))
    return b.finish(col, 0.95, b.bump(h, 0.4, 0.02))


def mat_floor_bricks():
    """old cotto floor: each brick has its own tone (mesh attributes brick_rand / brick_rand2 from floor_bricks()),
    fired-clay mottling, and grey-white dust bloom in large patches, as in photos 1 and 2"""
    b = NB('floor_brick')
    r1 = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='brick_rand').outputs['Fac']
    r2 = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='brick_rand2').outputs['Fac']
    # tan cotto, tuned so the rendered floor matches the colour measured in photos 1 and 2
    # (red:green:blue about 0.42 : 0.34 : 0.24); the room's warm light pushes it redder, so the albedo leans yellow
    tone = b.ramp(r1, [(0.00, (0.44, 0.30, 0.17)),     # dark, reddish
                       (0.15, (0.54, 0.40, 0.22)),     # warmer red-tan
                       (0.45, (0.62, 0.50, 0.28)),     # ordinary faded cotto
                       (0.80, (0.67, 0.58, 0.36)),     # pale, worn
                       (1.00, (0.63, 0.57, 0.40))])    # greyish, dust ground in
    jitter = b.ramp(r2, [(0.0, 0.75), (0.03, 0.75), (0.035, 0.92), (1.0, 1.06)])   # r2 < 0.03: sunken, darker bricks
    col = b.mul(tone, jitter, 1.0)
    mott = b.noise(18, 5, 0.6, dist=0.4)
    col = b.mul(col, b.ramp(mott, [(0.3, 0.82), (0.7, 1.10)]), 1.0)
    wear = b.val(b.ramp(b.noise(9, 5, 0.6, dist=0.6), [(0.52, 0.0), (0.74, 0.65)]))   # pale scuffed patches on the faces
    col = b.mix(wear, col, (0.72, 0.67, 0.49))
    pits = b.ramp(b.noise(140, 2, 0.5), [(0.62, 1.0), (0.70, 0.72)])                   # small dark pits in the clay
    col = b.mul(col, pits, 1.0)
    dust = b.math('MULTIPLY', b.val(b.ramp(b.noise(0.35, 5, 0.6), [(0.30, 0.22), (0.72, 0.80)])),
                  b.val(b.ramp(b.noise(2.5, 4, 0.6), [(0.3, 0.65), (0.7, 1.0)])))
    col = b.mix(dust, col, (0.67, 0.60, 0.41))     # beige dust
    fine = b.noise(70, 4, 0.6)
    col = b.mul(col, b.ramp(fine, [(0.3, 0.90), (0.7, 1.05)]), 0.6)
    return b.finish(col, 0.82, b.bump(fine, 0.25, 0.004))


def mat_floor_mortar():
    b = NB('floor_mortar')
    n = b.noise(6, 4, 0.6)
    col = b.mix(b.ramp(n, [(0.3, 0), (0.7, 1)]), (0.33, 0.29, 0.24), (0.50, 0.44, 0.36))   # dust-filled joints
    return b.finish(col, 0.95)


def mat_brick_rib(use_z=False):
    """brick courses driven by UV.x = metres along the rib (or world Z for horizontal courses)"""
    b = NB('brick_springer' if use_z else 'brick_rib')
    if use_z:
        coord = b.zcoord()
    else:
        uv = b.node('ShaderNodeUVMap', uv_map='UVMap')
        sx = b.node('ShaderNodeSeparateXYZ')
        b.nt.links.new(uv.outputs['UV'], sx.inputs['Vector'])
        coord = sx.outputs['X']
    t = b.math('DIVIDE', coord, 0.085)
    f = b.math('FRACT', t)
    joint = b.val(b.ramp(f, [(0.0, 0.0), (0.05, 0.0), (0.10, 1.0), (0.90, 1.0), (0.95, 0.0), (1.0, 0.0)]))
    wn = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
    b.nt.links.new(b.math('FLOOR', t), wn.inputs['W'])
    rnd = wn.outputs['Value']
    brick = b.ramp(rnd, [(0.0, (0.28, 0.085, 0.045)), (0.45, (0.42, 0.15, 0.075)), (0.75, (0.52, 0.25, 0.13)),
                         (0.92, (0.60, 0.39, 0.25)), (1.0, (0.66, 0.50, 0.36))])   # deep red ... pale buff, as in photo 1
    wash = b.val(b.ramp(b.noise(2.2, 4, 0.5), [(0.4, 0), (0.7, 1)]))
    brick = b.mix(b.math('MULTIPLY', wash, 0.45), brick, (0.40, 0.27, 0.19))
    col = b.mix(joint, (0.74, 0.68, 0.58), brick)   # lime mortar
    h = b.math('ADD', joint, b.math('MULTIPLY', rnd, 0.15))
    return b.finish(col, 0.85, b.bump(h, 0.9, 0.012))


def mat_stone(name, base, alt, rust=True, rust_amt=0.7, rust_col=(0.34, 0.2, 0.1)):
    b = NB(name)
    n1 = b.noise(1.6, 6, 0.6, dist=0.3)
    n2 = b.noise(9, 5, 0.6)
    fine = b.noise(45, 4, 0.6)
    col = b.mix(b.ramp(n1, [(0.35, 0), (0.65, 1)]), base, alt)
    if rust:
        r = b.val(b.ramp(b.noise(3.0, 4, 0.55), [(0.62, 0), (0.78, 1)]))
        col = b.mix(b.math('MULTIPLY', r, rust_amt), col, rust_col)
    col = b.mul(col, b.ramp(n2, [(0.3, 0.6), (0.7, 1.15)]), 0.9)
    h = b.math('ADD', b.math('MULTIPLY', n2, 0.7), fine)
    return b.finish(col, 0.9, b.bump(h, 0.9, 0.03))


def mat_ground():
    b = NB('ground')
    n = b.noise(1.2, 5, 0.6)
    col = b.mix(b.ramp(n, [(0.3, 0), (0.7, 1)]), (0.20, 0.22, 0.10), (0.30, 0.27, 0.15))
    return b.finish(col, 0.95)


MAT = {}


def make_materials():
    MAT['wall'] = mat_plaster_wall()
    MAT['vault'] = mat_plaster_vault()
    MAT['floor'] = mat_floor_mortar()
    MAT['floor_bricks'] = mat_floor_bricks()
    MAT['rib'] = mat_brick_rib()
    MAT['springer'] = mat_brick_rib(use_z=True)
    MAT['col'] = mat_stone('column_stone', (0.58, 0.54, 0.42), (0.70, 0.66, 0.52), rust_amt=0.4, rust_col=(0.30, 0.21, 0.14))   # light warm grey stone (photo 2), faint rust
    MAT['cap_plain'] = mat_stone('capital_plain', (0.46, 0.42, 0.34), (0.56, 0.52, 0.42), rust=False)   # darker, column 1
    MAT['cap_leaf'] = mat_stone('capital_leaf', (0.60, 0.56, 0.45), (0.71, 0.67, 0.55), rust=False)
    MAT['cap_panel'] = mat_stone('capital_panel', (0.61, 0.56, 0.45), (0.72, 0.67, 0.55), rust=False)
    MAT['cap_teeth'] = mat_stone('capital_teeth', (0.69, 0.65, 0.54), (0.79, 0.76, 0.65), rust=False)   # palest, column 4
    MAT['corbel'] = mat_stone('corbel_stone', (0.42, 0.37, 0.28), (0.48, 0.42, 0.32), rust=False)
    MAT['ground'] = mat_ground()
    MAT['iron'] = flat('iron', (0.03, 0.03, 0.03), 0.5, 0.8)
    MAT['wood'] = flat('wood_dark', (0.07, 0.035, 0.018), 0.45)
    MAT['white'] = flat('chair_white', (0.62, 0.62, 0.60), 0.5)
    MAT['blue'] = flat('chair_blue', (0.012, 0.05, 0.16), 0.4)
    MAT['black'] = flat('chair_black', (0.012, 0.012, 0.012), 0.45)
    MAT['red'] = flat('extinguisher', (0.45, 0.015, 0.012), 0.3)
    MAT['lamp'] = flat('lamp_body', (0.7, 0.7, 0.68), 0.5)
    MAT['copper'] = flat('copper_pipe', (0.45, 0.22, 0.10), 0.35, 0.9)
    MAT['glassframe'] = flat('window_frame', (0.02, 0.02, 0.02), 0.5, 0.6)
    MAT['door'] = mat_door_wood()
    MAT['boss'] = mat_stone('boss_stone', (0.55, 0.50, 0.40), (0.60, 0.54, 0.44), rust=False)


# ------------------------------------------------------------------ vault: webs
def smooth01(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def web_object():
    bm = bmesh.new()
    P_W = 1.6
    NU, NV = 26, 16
    us = clustered(NU)
    vs = [1 - math.cos(math.pi / 2 * j / NV) for j in range(NV + 1)]   # dense near v=0 (steep part)
    for bi in range(NX):
        for bj in range(NY):
            x0, y0 = bi * S, bj * S
            x1, y1 = x0 + S, y0 + S
            C = Vector((x0 + S / 2, y0 + S / 2))
            cs = [Vector((x0, y0)), Vector((x1, y0)), Vector((x1, y1)), Vector((x0, y1))]
            for side in range(4):
                ca, cb = cs[side], cs[(side + 1) % 4]
                grid = []
                for u in us:
                    row = []
                    side_xy = ca + (cb - ca) * u
                    zs = HS + prof((u - 0.5) * S, S / 2, R_SIDE)
                    w = abs(2 * u - 1) ** P_W
                    for v in vs:
                        xy = side_xy * (1 - v) + C * v
                        dd = HS + prof((1 - v) * A_D, A_D, R_DIAG)
                        lin = (1 - v) * HS + v * HK
                        z = (1 - v) * zs + v * HK + w * (dd - lin) + DOME * math.sin(math.pi * v) * (1 - w)
                        # dip the plaster along the diagonal ribs (u~0/1) and the side arch (v~0); fade out before the keystone
                        wu = 1 - smooth01(0.06, 0.20, min(u, 1 - u))
                        wv = 1 - smooth01(0.10, 0.30, v)
                        z -= WEB_SINK * max(wu, wv) * (1 - smooth01(0.85, 1.0, v))
                        row.append(bm.verts.new((xy.x, xy.y, z)))
                    grid.append(row)
                for i in range(NU):
                    for j in range(NV):
                        try:
                            f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
                            f.smooth = True
                        except ValueError:
                            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # make sure normals face the room (down)
    for f in bm.faces:
        if f.normal.z > 0.2:
            f.normal_flip()
    return to_obj('vault_webs', bm, MAT['vault'], smooth=True)


# ------------------------------------------------------------------ vault: brick ribs
def add_rib(bm, uvl, pts, bvec, width, d_below, d_above=0.12, rounded=False, plaster_sides=False):
    n = len(pts)
    T = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    sign = 1 if bvec.cross(T[n // 2]).z < 0 else -1
    Nv = [bvec.cross(t) * sign for t in T]
    s_ = [0.0]
    for i in range(1, n):
        s_.append(s_[-1] + (pts[i] - pts[i - 1]).length)
    hw = width / 2
    da = [d_above] * n
    if rounded:   # bull-nosed soffit like the diagonal ribs in photo 3
        arc = [(-hw * math.cos(math.pi * k / 10), d_below * math.sin(math.pi * k / 10)) for k in range(11)]
        runs = [[(-hw, -d_above), (-hw, 0.0)], arc, [(hw, 0.0), (hw, -d_above)]]
    else:
        runs = [[(-hw, -d_above), (-hw, d_below), (hw, d_below), (hw, -d_above)]]
    for run in runs:
        vs_cum = [0.0]
        for k in range(1, len(run)):
            vs_cum.append(vs_cum[-1] + math.hypot(run[k][0] - run[k - 1][0], run[k][1] - run[k - 1][1]))
        rows = []
        for (bo, no) in run:
            if no == -d_above:   # hidden top edge: shallow at the springing (keeps the uplights unblocked), full depth higher up
                rows.append([bm.verts.new(pts[i] + bvec * bo - Nv[i] * da[i]) for i in range(n)])
            else:
                rows.append([bm.verts.new(pts[i] + bvec * bo + Nv[i] * no) for i in range(n)])
        for k in range(len(run) - 1):
            for i in range(n - 1):
                f = bm.faces.new((rows[k][i], rows[k + 1][i], rows[k + 1][i + 1], rows[k][i + 1]))
                f.smooth = rounded
                if plaster_sides and not rounded and k != 1 and pts[i].z > HS + 0.75:   # side faces, above the springer
                    f.material_index = 1                                                  # (lower down the bundle stays brick)
                for lp, uv in zip(f.loops, [(s_[i], vs_cum[k]), (s_[i], vs_cum[k + 1]),
                                            (s_[i + 1], vs_cum[k + 1]), (s_[i + 1], vs_cum[k])]):
                    lp[uvl].uv = uv


def ribs_object():
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    ex, ey = Vector((1, 0, 0)), Vector((0, 1, 0))
    # diagonals
    for bi in range(NX):
        for bj in range(NY):
            x0, y0 = bi * S, bj * S
            x1, y1 = x0 + S, y0 + S
            for p0, p1 in (((x0, y0), (x1, y1)), ((x1, y0), (x0, y1))):
                pts = arch_pts((*p0, HS), (*p1, HS), R_DIAG, 56)
                d = (Vector(p1) - Vector(p0))
                bvec = Vector((-d.y, d.x, 0)).normalized()
                add_rib(bm, uvl, pts, bvec, W_DIAG, D_BELOW_DIAG, D_ABOVE, rounded=True)
    # transverse arches (run along x at y = j*S); end ones are wall arches
    for j in range(NY + 1):
        for i in range(NX):
            pts = arch_pts((i * S, j * S, HS), ((i + 1) * S, j * S, HS), R_SIDE, 48)
            wall = j in (0, NY)
            add_rib(bm, uvl, pts, ey, W_WALL if wall else W_TRANS, D_BELOW_WALL if wall else D_BELOW_BIG, D_ABOVE, plaster_sides=True)
    # longitudinal arches (run along y at x = i*S); outer ones are wall arches
    for i in range(NX + 1):
        for j in range(NY):
            pts = arch_pts((i * S, j * S, HS), (i * S, (j + 1) * S, HS), R_SIDE, 48)
            wall = i in (0, NX)
            add_rib(bm, uvl, pts, ex, W_WALL if wall else W_TRANS, D_BELOW_WALL if wall else D_BELOW_BIG, D_ABOVE, plaster_sides=True)
    ob = to_obj('vault_ribs', bm, MAT['rib'], smooth=True)
    ob.data.materials.append(MAT['vault'])     # slot 1: plastered sides of the big arches
    return ob


def bosses_object():
    bm = bmesh.new()
    for bi in range(NX):
        for bj in range(NY):
            cx, cy = bi * S + S / 2, bj * S + S / 2
            add_cyl(bm, (cx, cy, HK - 0.06), 0.31, 0.27, 0.14, 24)
            # rosette: ring of six petals + centre
            for k in range(6):
                th = k * math.pi / 3
                add_cyl(bm, (cx + 0.15 * math.cos(th), cy + 0.15 * math.sin(th), HK - 0.145), 0.06, 0.055, 0.035, 12)
            add_cyl(bm, (cx, cy, HK - 0.145), 0.055, 0.05, 0.035, 12)
    return to_obj('keystones', bm, MAT['boss'], smooth=False)


# ------------------------------------------------------------------ walls
def hull_cutter(prof_a, prof_b, to3d, da, db):
    bm = bmesh.new()
    verts = []
    for (a, z) in prof_a:
        verts.append(bm.verts.new(to3d(a, z, da)))
    for (a, z) in prof_b:
        verts.append(bm.verts.new(to3d(a, z, db)))
    ret = bmesh.ops.convex_hull(bm, input=verts)
    bmesh.ops.delete(bm, geom=ret['geom_interior'] + ret['geom_unused'], context='VERTS')
    return bm


def arch_outline(c, zb, zt, w, n=14):
    pts = [(c - w / 2, zb), (c + w / 2, zb)]
    zs = zt - w / 2
    pts.append((c + w / 2, zs))
    for k in range(1, n):
        th = math.pi * k / n
        pts.append((c + w / 2 * math.cos(th), zs + w / 2 * math.sin(th)))
    pts.append((c - w / 2, zs))
    return pts


def rect_outline(c, zb, zt, w):
    return [(c - w / 2, zb), (c + w / 2, zb), (c + w / 2, zt), (c - w / 2, zt)]


def circle_outline(c, zc, r, n=28):
    return [(c + r * math.cos(2 * math.pi * k / n), zc + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def wall_slab(name, axis, at, outward, openings):
    """axis 'x': wall plane x=at, runs along y.  axis 'y': plane y=at, runs along x.
    openings: list of (outline_inner, outline_outer, depth_inner_extra)"""
    along = NY if axis == 'x' else NX
    span = along * S

    def p3(a, z, d=0.0):
        # d = depth measured outward from the wall surface
        if axis == 'x':
            return (at + outward * d, a, z)
        return (a, at + outward * d, z)

    pts2 = [(-WALL_T, -0.4), (span + WALL_T, -0.4), (span + WALL_T, HS)]
    for j in reversed(range(along)):
        a0, a1 = j * S, (j + 1) * S
        for t in reversed(clustered(40)):
            x = (t - 0.5) * S
            pts2.append((a0 + t * S, HS + prof(x, S / 2, R_SIDE)))
    pts2.append((-WALL_T, HS))
    dd = [pts2[0]]
    for q in pts2[1:]:
        if abs(q[0] - dd[-1][0]) > 1e-6 or abs(q[1] - dd[-1][1]) > 1e-6:
            dd.append(q)
    pts2 = dd
    bm = bmesh.new()
    vs = [bm.verts.new(p3(a, z)) for a, z in pts2]
    # drop consecutive duplicates (cusp points)
    f = bm.faces.new(vs)
    inward = Vector((-outward, 0, 0)) if axis == 'x' else Vector((0, -outward, 0))
    if f.normal.dot(inward) < 0:
        f.normal_flip()
    ret = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    off = Vector((outward * WALL_T, 0, 0)) if axis == 'x' else Vector((0, outward * WALL_T, 0))
    bmesh.ops.translate(bm, vec=off, verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    ob = to_obj(name, bm, MAT['wall'])
    # openings -> one cutter object, one boolean
    if openings:
        cb = bmesh.new()
        for (pa, pb, d_in) in openings:
            hb = hull_cutter(pa, pb, lambda a, z, d: p3(a, z, d), d_in, WALL_T + 0.1)
            m = bpy.data.meshes.new('tmp')
            hb.to_mesh(m)
            hb.free()
            cb.from_mesh(m)
            bpy.data.meshes.remove(m)
        bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
        cut = to_obj(name + '_cutter', cb)
        mod = ob.modifiers.new('cut', 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cut
        mod.solver = 'EXACT'
        bpy.context.view_layer.objects.active = ob
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.ops.object.modifier_apply(modifier='cut')
        bpy.data.objects.remove(cut, do_unlink=True)
    return ob


def build_walls():
    # left wall (x=0): arched splayed window per bay, plus small lunette window
    left = []
    for j in range(NY):
        c = j * S + S / 2
        ws = WIN_SIDE
        left.append((arch_outline(c, ws['zb_in'], ws['zt_in'], ws['w_in']), arch_outline(c, ws['zb_out'], ws['zt_out'], ws['w_out']), -0.05))
        left.append((rect_outline(c, 4.25, 5.05, 0.80), rect_outline(c, 4.45, 4.90, 0.35), -0.05))
    wall_slab('wall_left', 'x', 0.0, -1, left)

    # right wall (x=W): two doorways near the far end, nothing else
    right = []
    for c in DOOR_CENTRES:
        right.append((arch_outline(c, -0.2, DOOR_TOP, DOOR_W), arch_outline(c, -0.2, DOOR_TOP, DOOR_W), -0.05))
    wall_slab('wall_right', 'x', W, +1, right)

    # end walls: arched window + oculus per nave
    ends = []
    for i in range(NX):
        c = i * S + S / 2
        we = WIN_END
        ends.append((arch_outline(c, we['zb_in'], we['zt_in'], we['w_in']), arch_outline(c, we['zb_out'], we['zt_out'], we['w_out']), -0.05))
        ends.append((circle_outline(c, 4.55, 0.42), circle_outline(c, 4.55, 0.24), -0.05))
    wall_slab('wall_near', 'y', 0.0, -1, ends)
    wall_slab('wall_far', 'y', L, +1, ends)


def window_steps():
    """three stone treads in each arched window embrasure, rising toward the glass as in photo 1.
    They fill the sloped sill the window cutter leaves (inner depth -0.05, outer WALL_T + 0.1)."""
    bm = bmesh.new()
    d_in, d_out = -0.05, WALL_T + 0.1

    def treads(axis, at, outward, c, w):
        sill = lambda d: w['zb_in'] + (w['zb_out'] - w['zb_in']) * (d - d_in) / (d_out - d_in)
        width = lambda d: w['w_in'] + (w['w_out'] - w['w_in']) * (d - d_in) / (d_out - d_in)
        n = 3
        for k in range(n):
            d0, d1 = WALL_T * k / n, WALL_T * (k + 1) / n
            top = sill(d1)
            if k == 0:                       # first tread starts at the sill line, flush with the wall face
                d0, bot = 0.003, sill(0.0)
            else:                            # buried in the wall below the slope
                bot = w['zb_in'] - 0.3
            wd = width(max(d0, 0.0)) + 0.06  # a few cm into the reveals
            dc, dl = (d0 + d1) / 2, d1 - d0
            if axis == 'x':
                add_box(bm, (at + outward * dc, c, (top + bot) / 2), (dl, wd, top - bot))
            else:
                add_box(bm, (c, at + outward * dc, (top + bot) / 2), (wd, dl, top - bot))

    for j in range(NY):
        treads('x', 0.0, -1, j * S + S / 2, WIN_SIDE)
    for i in range(NX):
        c = i * S + S / 2
        treads('y', 0.0, -1, c, WIN_END)
        treads('y', L, +1, c, WIN_END)
    return to_obj('window_steps', bm, MAT['corbel'])


def window_frames():
    bm = bmesh.new()
    # thin black bars across the outer opening of the end-wall and left-wall arched windows
    def frame_x(xp, c, zb, zt, w):
        add_box(bm, (xp, c, (zb + zt - w / 2) / 2), (0.03, 0.025, zt - w / 2 - zb))
        add_box(bm, (xp, c, zb + (zt - w / 2 - zb) * 0.33), (0.03, w, 0.025))
        add_box(bm, (xp, c, zb + (zt - w / 2 - zb) * 0.66), (0.03, w, 0.025))

    def frame_y(yp, c, zb, zt, w):
        add_box(bm, (c, yp, (zb + zt - w / 2) / 2), (0.025, 0.03, zt - w / 2 - zb))
        add_box(bm, (c, yp, zb + (zt - w / 2 - zb) * 0.33), (w, 0.03, 0.025))
        add_box(bm, (c, yp, zb + (zt - w / 2 - zb) * 0.66), (w, 0.03, 0.025))

    for j in range(NY):
        frame_x(-WALL_T + 0.35, j * S + S / 2, 1.78, 3.02, 0.40)
    for i in range(NX):
        c = i * S + S / 2
        frame_y(-WALL_T + 0.35, c, 1.82, 2.98, 0.38)
        frame_y(L + WALL_T - 0.35, c, 1.82, 2.98, 0.38)
    return to_obj('window_frames', bm, MAT['glassframe'])


# ------------------------------------------------------------------ columns, corbels, lamps
def capital(bm, style, cx, cy):
    """the four capitals differ, as in photos 1 and 2. Shaft top at z 2.06, abacus top at HS."""
    th0 = math.pi / 8                                     # abacus corners (octagon rotated by 22.5 degrees)
    lathe(bm, [(0.30, 2.055), (0.33, 2.07), (0.342, 2.095), (0.33, 2.12), (0.315, 2.13)], 48, cx=cx, cy=cy)   # astragal ring
    if style == 'plain':          # round cushion drum under a thick, edge-rounded octagonal slab
        lathe(bm, [(0.315, 2.13), (0.37, 2.15), (0.41, 2.18), (0.44, 2.23), (0.455, 2.28), (0.46, 2.32)], 48, cx=cx, cy=cy)
        lathe(bm, [(0.46, 2.32), (0.545, 2.345), (0.56, 2.37), (0.56, 2.46), (0.545, 2.49), (0.52, HS)], 8,
              rot=th0, smooth=False, cx=cx, cy=cy)
    elif style == 'leaf':         # bell with eight broad leaves curling out under the abacus corners
        prof = [(0.315 + 0.155 * smooth01(0.0, 1.0, t) ** 1.6, 2.13 + 0.21 * t) for t in [i / 16 for i in range(17)]]

        def leaves(th, z):
            s_ = smooth01(2.16, 2.34, z)
            lobe = max(0.0, math.cos(8 * (th - th0))) ** 3
            return 1 + (0.13 * s_ + 0.07 * smooth01(2.29, 2.34, z)) * lobe - 0.045 * s_ * (1 - lobe)
        lathe(bm, prof, 96, radial=leaves, cx=cx, cy=cy)
        lathe(bm, [(0.47, 2.34), (0.56, 2.37), (0.56, 2.48), (0.55, HS)], 8, rot=th0, smooth=False, cx=cx, cy=cy)
    elif style == 'panel':        # flared octagonal bell with flat carved panels
        def octo(th, z):
            ph = (th + math.pi / 8) % (math.pi / 4) - math.pi / 8          # 0 at a face centre, +-22.5 deg at the corners
            o = math.cos(math.pi / 8) / math.cos(ph)                        # circle -> octagon
            return o * (0.965 if abs(ph) < 0.30 and 2.18 < z < 2.31 else 1.0)
        prof = [(0.33 + 0.16 * t ** 1.3, 2.13 + 0.22 * t) for t in [i / 16 for i in range(17)]]
        lathe(bm, prof, 64, radial=octo, smooth=False, cx=cx, cy=cy)
        lathe(bm, [(0.49, 2.35), (0.555, 2.375), (0.555, 2.48), (0.54, HS)], 8, rot=th0, smooth=False, cx=cx, cy=cy)
    else:                         # 'teeth': plain drum, a band of small pointed teeth, thin cornice and slab
        lathe(bm, [(0.315, 2.13), (0.355, 2.145), (0.36, 2.16), (0.36, 2.185), (0.348, 2.19), (0.36, 2.196),
                   (0.36, 2.22), (0.40, 2.225)], 48, cx=cx, cy=cy)

        def teeth(th, z):
            u = (th * 24 / (2 * math.pi)) % 1.0
            w = abs(u - 0.5) * 2                              # 0 on a tooth's centre line, 1 between teeth
            t = (z - 2.225) / 0.065                           # 0 at the bottom of the band, 1 at the top
            return 1.0 if w < 0.15 + 0.85 * t else 0.91      # teeth narrow to points at the bottom
        lathe(bm, [(0.40, 2.225 + 0.065 * i / 13) for i in range(14)], 192, radial=teeth, smooth=False, cx=cx, cy=cy)
        lathe(bm, [(0.40, 2.29), (0.43, 2.30), (0.455, 2.325), (0.46, 2.34)], 48, cx=cx, cy=cy)
        lathe(bm, [(0.46, 2.34), (0.53, 2.36), (0.535, 2.48), (0.525, HS)], 8, rot=th0, smooth=False, cx=cx, cy=cy)


def columns():
    bm_col = bmesh.new()
    bm_iron = bmesh.new()
    bm_lamp = bmesh.new()
    pos = [(S, (k + 1) * S) for k in range(NY - 1)]
    for idx, (cx, cy) in enumerate(pos):
        ph = random.uniform(0, 6.28)
        irr = lambda th, z, ph=ph: 1 + 0.014 * math.sin(3 * th + z * 1.7 + ph) + 0.01 * math.sin(5 * th - 2.1 * z + ph)
        # bulbous round base
        lathe(bm_col, [(0.52, 0.0), (0.55, 0.05), (0.56, 0.12), (0.52, 0.23), (0.42, 0.28), (0.345, 0.30)], 48, cx=cx, cy=cy)
        # shaft, slightly tapering
        lathe(bm_col, [(0.335, 0.30), (0.328, 1.0), (0.318, 1.7), (0.305, 2.06)], 48, radial=irr, cx=cx, cy=cy, cap_top=False, cap_bot=False)
        style = CAPITAL_STYLES[idx]
        bm_cap = bmesh.new()
        capital(bm_cap, style, cx, cy)
        to_obj('capital_%d_%s' % (idx + 1, style), bm_cap, MAT['cap_' + style], smooth=True)
        if idx == 0:   # iron tie band on the first column
            lathe(bm_iron, [(0.336, 0.92), (0.336, 0.98)], 48, cx=cx, cy=cy)
        # two uplight fixtures on the abacus
        for sgn in (-1, 1):
            ang = math.radians(35) if sgn > 0 else math.radians(215)
            lx, ly = cx + 0.46 * math.cos(ang), cy + 0.46 * math.sin(ang)
            add_box(bm_lamp, (lx, ly, HS + 0.045), (0.14, 0.09, 0.09), ang)
    to_obj('column_shafts', bm_col, MAT['col'], smooth=True)
    to_obj('column_iron', bm_iron, MAT['iron'], smooth=True)
    to_obj('lamp_bodies', bm_lamp, MAT['lamp'])
    # uplights
    for (cx, cy) in pos:
        for sgn in (-1, 1):
            ang = math.radians(35) if sgn > 0 else math.radians(215)
            ld = bpy.data.lights.new('uplight', 'SPOT')
            ld.energy = UPLIGHT_W
            ld.color = (1.0, 0.82, 0.58)
            ld.spot_size = math.radians(95)
            ld.spot_blend = 0.7
            ld.shadow_soft_size = 0.05
            lo = bpy.data.objects.new('uplight', ld)
            lo.location = (cx + 0.46 * math.cos(ang), cy + 0.46 * math.sin(ang), HS + 0.12)
            lo.rotation_euler = (math.pi, 0, 0)
            bpy.context.scene.collection.objects.link(lo)


def springers():
    """brick masses where the ribs gather above each capital / corbel"""
    bm = bmesh.new()
    for k in range(NY - 1):
        lathe(bm, SPRINGER_PROFILE, 24, cx=S, cy=(k + 1) * S)
    pts = []
    for j in range(NY + 1):
        pts += [(0.0, j * S, 1), (W, j * S, -1)]
    pts += [(S, 0.0, 2), (S, L, -2)]
    for (x, y, k) in pts:
        if abs(k) == 1:
            add_box(bm, (x + (0.2 if k > 0 else -0.2), y, HS + 0.28), (0.40, 0.56, 0.56))
        else:
            add_box(bm, (x, y + (0.2 if k > 0 else -0.2), HS + 0.28), (0.56, 0.40, 0.56))
    for (x, y, dx, dy) in ((0, 0, 1, 1), (W, 0, -1, 1), (0, L, 1, -1), (W, L, -1, -1)):
        add_box(bm, (x + dx * 0.2, y + dy * 0.2, HS + 0.28), (0.40, 0.40, 0.56))
    return to_obj('springers', bm, MAT['springer'])


def corbels():
    """stone corbels under every spring point; 0.40 x 0.60 x 0.65 m, sized in structural_check.py"""
    P_, W_, H_ = CORBEL
    bm = bmesh.new()
    pts = []
    for j in range(NY + 1):
        pts += [(0.0, j * S, 1), (W, j * S, -1)]
    pts += [(S, 0.0, 2), (S, L, -2)]
    for (x, y, k) in pts:
        off = P_ / 2
        if abs(k) == 1:
            c = (x + (off if k > 0 else -off), y, HS - H_ / 2)
            size = (P_, W_, H_)
        else:
            c = (x, y + (off if k > 0 else -off), HS - H_ / 2)
            size = (W_, P_, H_)
        add_box(bm, c, size)
    for (x, y, dx, dy) in ((0, 0, 1, 1), (W, 0, -1, 1), (0, L, 1, -1), (W, L, -1, -1)):
        add_box(bm, (x + dx * P_ / 2, y + dy * P_ / 2, HS - H_ / 2), (P_, P_, H_))
    return to_obj('corbels', bm, MAT['corbel'])


# ------------------------------------------------------------------ furniture & bits
def chair(name, loc, rotz, mat, scale=1.0):
    bm = bmesh.new()
    lx = Matrix.Rotation(rotz, 4, 'Z')

    def b(off, size):
        add_box(bm, Vector(loc) + lx @ Vector(off), size, rotz)

    sh, sw, sd = 0.45, 0.42, 0.40
    b((0, 0, sh), (sd, sw, 0.035))
    for dx in (-sd / 2 + 0.03, sd / 2 - 0.03):
        for dy in (-sw / 2 + 0.03, sw / 2 - 0.03):
            b((dx, dy, sh / 2), (0.032, 0.032, sh))
    for dy in (-sw / 2 + 0.03, sw / 2 - 0.03):
        b((-sd / 2 + 0.03, dy, sh + 0.2), (0.03, 0.03, 0.42))
    b((-sd / 2 + 0.03, 0, sh + 0.30), (0.025, sw - 0.04, 0.05))
    b((-sd / 2 + 0.03, 0, sh + 0.14), (0.025, sw - 0.04, 0.05))
    return to_obj(name, bm, mat)


def table(name, loc, rotz, size, mat, h=0.76, legs='plain'):
    bm = bmesh.new()
    lx = Matrix.Rotation(rotz, 4, 'Z')

    def b(off, sz):
        add_box(bm, Vector(loc) + lx @ Vector(off), sz, rotz)

    L_, W_ = size
    b((0, 0, h - 0.025), (L_, W_, 0.05))
    if legs == 'plain':
        for dx in (-L_ / 2 + 0.05, L_ / 2 - 0.05):
            for dy in (-W_ / 2 + 0.05, W_ / 2 - 0.05):
                b((dx, dy, (h - 0.05) / 2), (0.05, 0.05, h - 0.05))
    else:   # trestle ends with a stretcher, like the small "fratino" table
        for dx in (-L_ / 2 + 0.12, L_ / 2 - 0.12):
            b((dx, 0, (h - 0.05) / 2), (0.07, W_ * 0.8, h - 0.05))
            b((dx, 0, 0.05), (0.14, W_ * 0.9, 0.07))
        b((0, 0, 0.30), (L_ - 0.3, 0.04, 0.04))
    return to_obj(name, bm, mat)


def furniture():
    chair('chair_white_1', (0.95, 12.30, 0), math.radians(-85), MAT['white'])
    chair('chair_white_2', (1.50, 12.20, 0), math.radians(-100), MAT['white'])
    table('table_dark', (2.45, 12.95, 0), math.radians(8), (1.30, 0.65), MAT['wood'], 0.74)
    # upturned chairs standing on the table (the black "sticks" in photo 1)
    bm = bmesh.new()
    for dy in (-0.15, 0.15):
        add_box(bm, (2.45 - 0.10, 12.95 + dy, 0.74 + 0.45), (0.035, 0.035, 0.90))
        add_box(bm, (2.45 + 0.10, 12.95 + dy, 0.74 + 0.40), (0.035, 0.035, 0.80))
    add_box(bm, (2.45, 12.95, 0.74 + 0.04), (0.28, 0.45, 0.035))
    to_obj('stacked_chair', bm, MAT['wood'])
    chair('chair_black', (0.80, 23.30, 0), math.radians(-90), MAT['black'])
    chair('chair_blue', (10.15, 21.65, 0), math.radians(95), MAT['blue'])
    table('table_fratino', (6.35, 15.85, 0), math.radians(100), (1.55, 0.60), MAT['wood'], 0.78, legs='trestle')
    # fire extinguishers
    for (x, y) in ((10.55, 11.65), (10.60, 25.7)):
        bm = bmesh.new()
        add_cyl(bm, (x, y, 0.27), 0.085, 0.085, 0.54, 20)
        add_cyl(bm, (x, y, 0.58), 0.035, 0.035, 0.07, 16)
        add_cyl(bm, (x, y, 0.64), 0.04, 0.04, 0.06, 16)
        add_box(bm, (x - 0.02, y, 0.69), (0.14, 0.03, 0.03))
        to_obj('extinguisher', bm, MAT['red'], smooth=True)


def conduit():
    # copper conduit along the right wall
    bm = bmesh.new()
    add_cyl(bm, (W - 0.06, L / 2, 2.85), 0.02, 0.02, L - 1, 10, rotx=math.pi / 2)
    to_obj('conduit', bm, MAT['copper'], smooth=True)


def mat_door_wood():
    b = NB('door_wood')
    sx = b.node('ShaderNodeSeparateXYZ')
    b.nt.links.new(b.coord(), sx.inputs['Vector'])
    cx = b.node('ShaderNodeCombineXYZ')
    b.nt.links.new(sx.outputs['Y'], cx.inputs['X'])      # along the leaf
    b.nt.links.new(sx.outputs['Z'], cx.inputs['Y'])      # up the leaf
    br = b.node('ShaderNodeTexBrick', offset=0.0, offset_frequency=1, squash=1.0, squash_frequency=1)
    b.nt.links.new(cx.outputs['Vector'], br.inputs['Vector'])
    br.inputs['Color1'].default_value = (0.10, 0.055, 0.03, 1)
    br.inputs['Color2'].default_value = (0.15, 0.085, 0.05, 1)
    br.inputs['Mortar'].default_value = (0.012, 0.007, 0.004, 1)
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.012
    br.inputs['Mortar Smooth'].default_value = 0.15
    br.inputs['Bias'].default_value = 0.0
    br.inputs['Brick Width'].default_value = 0.20      # plank width
    br.inputs['Row Height'].default_value = 6.0        # one tall row = vertical planks
    grain = b.noise(22, 4, 0.6)
    col = b.mul(br.outputs['Color'], b.ramp(grain, [(0.3, 0.7), (0.7, 1.15)]), 0.8)
    h = b.math('ADD', br.outputs['Fac'], b.math('MULTIPLY', grain, 0.3))
    return b.finish(col, 0.6, b.bump(h, 0.5, 0.01))


def door(c=DOOR_CENTRES[0], ajar_deg=68):
    """Plank door with an arched head, hung in the right-wall doorway at y=c, hinged on the -y jamb and
    swung into the room. The other doorway is left open."""
    w, t = 1.0, 0.07
    outline = arch_outline(w / 2, 0.02, 2.44, w, n=16)      # (u along leaf, z)
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((-t / 2, u, z)) for u, z in outline])
    ret = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(t, 0, 0), verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    leaf = to_obj('door_leaf', bm, MAT['door'])
    leaf.location = (W + 0.15, c - w / 2, 0.0)
    leaf.rotation_euler = (0, 0, math.radians(ajar_deg))
    bm = bmesh.new()                                         # iron straps + handle on the room face
    for z in (0.35, 1.2, 1.9):
        add_box(bm, (-t / 2 - 0.008, 0.38, z), (0.016, 0.76, 0.07))
    add_box(bm, (-t / 2 - 0.02, w - 0.16, 1.05), (0.04, 0.05, 0.18))
    iron = to_obj('door_ironwork', bm, MAT['iron'])
    iron.parent = leaf
    # stone thresholds through the full wall thickness, flush with the floor
    bm = bmesh.new()
    for cc in DOOR_CENTRES:
        depth = WALL_T + 0.1
        add_box(bm, (W + depth / 2 - 0.05, cc, -0.03), (depth, 1.20, 0.06))
    to_obj('door_thresholds', bm, MAT['corbel'])


# ------------------------------------------------------------------ floor, ground, world, lights, cameras
def floor_bricks(x0=-0.1, y0=-0.1, x1=W + 0.1, y1=L + 0.1):
    """90-degree herringbone of 28 x 14 cm bricks with 8 mm joints. Tiling in brick-width units u:
    H = [0,2]x[0,1], V = [0,1]x[1,3], repeated on the lattice a*(1,1) + b*(2,-2).
    Each brick: top face, worn chamfer, sides down into the mortar bed; two random attributes per brick."""
    u, joint, cham, drop, zb = FLOOR_BRICK_W, 0.008, 0.006, 0.0025, -0.012
    rng = random.Random(7)
    X0, Y0, X1, Y1 = x0 / u, y0 / u, x1 / u, y1 / u
    rects = []
    for a in range(math.floor((X0 + Y0) / 2) - 4, math.ceil((X1 + Y1) / 2) + 4):
        for b_ in range(math.floor((X0 - Y1) / 4) - 3, math.ceil((X1 - Y0) / 4) + 3):
            tx, ty = a + 2 * b_, a - 2 * b_
            for (rx0, ry0, rx1, ry1) in ((0, 0, 2, 1), (0, 1, 1, 3)):
                bx0, by0, bx1, by1 = max((tx + rx0) * u, x0), max((ty + ry0) * u, y0), min((tx + rx1) * u, x1), min((ty + ry1) * u, y1)
                if bx1 - bx0 > 0.03 and by1 - by0 > 0.03:
                    rects.append((bx0, by0, bx1, by1))
    verts, faces, r1s, r2s = [], [], [], []
    h = joint / 2
    for (bx0, by0, bx1, by1) in rects:
        bx0, by0, bx1, by1 = bx0 + h, by0 + h, bx1 - h, by1 - h
        r1, r2 = rng.random(), rng.random()
        zt = -0.001 - rng.random() * 0.002 - (0.0015 if r2 < 0.03 else 0.0)
        sh = rng.random() * 0.003                        # worn, slightly undersized bricks
        bx0, by0, bx1, by1 = bx0 + sh, by0 + sh, bx1 - sh, by1 - sh
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        ang = math.radians(rng.uniform(-0.8, 0.8))
        ca, sa = math.cos(ang), math.sin(ang)
        tx_, ty_ = rng.uniform(-0.004, 0.004), rng.uniform(-0.004, 0.004)   # tilt: about 1 mm over a brick

        def ring(x_0, y_0, x_1, y_1, z, tilt=True):
            out = []
            for (px, py) in ((x_0, y_0), (x_1, y_0), (x_1, y_1), (x_0, y_1)):
                dx, dy = px - cx, py - cy
                qx, qy = cx + dx * ca - dy * sa, cy + dx * sa + dy * ca
                out.append((qx, qy, z + (tx_ * dx + ty_ * dy if tilt else 0.0)))
            return out
        n = len(verts)
        verts += ring(bx0 + cham, by0 + cham, bx1 - cham, by1 - cham, zt)   # n+0..3 top
        verts += ring(bx0, by0, bx1, by1, zt - drop)                        # n+4..7 chamfer foot
        verts += ring(bx0, by0, bx1, by1, zb, tilt=False)                   # n+8..11 bottom
        fs = [(n, n + 1, n + 2, n + 3)]
        for k in range(4):
            k1 = (k + 1) % 4
            fs.append((n + 4 + k, n + 4 + k1, n + k1, n + k))
            fs.append((n + 8 + k, n + 8 + k1, n + 4 + k1, n + 4 + k))
        faces += fs
        r1s += [r1] * len(fs)
        r2s += [r2] * len(fs)
    me = bpy.data.meshes.new('floor_bricks')
    me.from_pydata(verts, [], faces)
    for name, vals in (('brick_rand', r1s), ('brick_rand2', r2s)):
        me.attributes.new(name, 'FLOAT', 'FACE').data.foreach_set('value', vals)
    me.validate()
    ob = bpy.data.objects.new('floor_bricks', me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(MAT['floor_bricks'])
    return ob


def floor_and_ground():
    bm = bmesh.new()       # mortar bed under the bricks (same extents as before: walk.py and render_hero.py read them)
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0,
                          matrix=Matrix.Translation((W / 2, L / 2, -0.005)) @ Matrix.Diagonal((W / 2 + 0.1, L / 2 + 0.1, 1, 1)))
    to_obj('floor', bm, MAT['floor'])
    floor_bricks()
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0,
                          matrix=Matrix.Translation((W / 2, L / 2, -0.06)) @ Matrix.Diagonal((200, 200, 1, 1)))
    to_obj('ground', bm, MAT['ground'])


def world_and_sun():
    sc = bpy.context.scene
    wd = bpy.data.worlds.new('World')
    wd.use_nodes = True
    nt = wd.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new('ShaderNodeTexSky')
    for t in ('MULTIPLE_SCATTERING', 'SINGLE_SCATTERING', 'NISHITA'):
        try:
            sky.sky_type = t
            break
        except TypeError:
            continue
    sky.sun_disc = False
    sky.sun_elevation = math.radians(38)
    sky.sun_rotation = math.radians(150)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 1.0
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sc.world = wd
    # sun enters mostly through the left-wall windows (sun is on the -X side)
    d = Vector((0.80, 0.30, -0.52)).normalized()
    ld = bpy.data.lights.new('sun', 'SUN')
    ld.energy = 5.0
    ld.angle = math.radians(0.6)
    ld.color = (1.0, 0.96, 0.88)
    lo = bpy.data.objects.new('sun', ld)
    lo.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(lo)


def aim(loc, yaw_deg, pitch_deg, right=False):
    """yaw measured from +Y, positive = toward -X (left) unless right=True."""
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    sx = 1 if right else -1
    d = Vector((sx * math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), math.sin(p)))
    return d.to_track_quat('-Z', 'Y').to_euler()


def cameras():
    sc = bpy.context.scene
    defs = {
        # name: (location, yaw, pitch, right?, portrait?)
        'cam_photo1': ((9.37, 5.30, 1.45), 23.0, 6.5, False, False),
        'cam_photo2': ((3.50, 1.30, 0.80), 10.8, 6.8, True, True),
        'cam_photo3': ((2.70, 10.2, 1.30), 4.0, 50.0, False, False),
        'cam_overview': ((-15.0, -13.0, 21.0), None, None, False, False),
        'cam_door': ((6.6, 17.8, 1.55), None, None, False, False),
    }
    targets = {'cam_overview': ((W / 2, L * 0.46, 2.0), 27), 'cam_door': ((W + 0.4, 19.3, 1.25), 24)}
    for name, (loc, yaw, pitch, right, portrait) in defs.items():
        cd = bpy.data.cameras.new(name)
        cd.lens = 25.4
        cd.sensor_width = 36
        cd.clip_start = 0.05
        cd.clip_end = 400
        co = bpy.data.objects.new(name, cd)
        co.location = loc
        if yaw is None:   # look-at camera
            tgt, lens = targets[name]
            co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
            cd.lens = lens
        else:
            co.rotation_euler = aim(loc, yaw, pitch, right)
        co["portrait"] = portrait
        sc.collection.objects.link(co)
    sc.camera = bpy.data.objects['cam_photo1']


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    make_materials()
    floor_and_ground()
    web_object()
    ribs_object()
    bosses_object()
    build_walls()
    window_steps()
    window_frames()
    columns()
    corbels()
    springers()
    if WITH_FURNITURE:
        furniture()
    conduit()
    door()
    world_and_sun()
    cameras()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    path = os.path.join(HERE, 'foresteria_furnished.blend' if WITH_FURNITURE else 'foresteria.blend')
    bpy.context.preferences.filepaths.save_version = 0     # no .blend1 backup (not written to user prefs in -b)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print('saved', path)


main()
