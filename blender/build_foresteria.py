"""
Staffarda Abbey guesthouse (foresteria), ground floor -- rough reconstruction from 3 photos.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b --python build_foresteria.py
Out:  foresteria.blend  (next to this script)

Everything is in metres. Room axis = +Y (near end wall y=0, far end wall y=L), X across.
Dimensions were estimated from perspective in the photos (camera height ~1.45 m, ~71 deg
horizontal FOV), so they are plausible, not surveyed.
"""
import bpy, bmesh, math, random, os
from statistics import NormalDist
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
# wall springing measured on photo 1 with the calibrated camera (blender/README.md): the side-wall ribs spring higher
# than the columns, from smaller corbels. Corners follow their side wall; the end walls' middle corbel stays at HS.
HS_WALL_L = 2.65             # left wall (x = 0): corbel tops measured at 2.63-2.65 m
HS_WALL_R = 2.95             # right wall (x = W): 2.86-3.04 m
CORBEL_L = (0.30, 0.40, 0.36)   # left wall: projection, width, height; stepped moulded block
CORBEL_R = (0.34, 0.44, 0.40)   # right wall: rounded cushion block
CORBEL_END = (0.25, 0.45, 0.30)  # end walls' middle corbel (photo 1: small block at about 2.25-2.50 m)
CORBEL = CORBEL_R            # the largest wall corbel, used by structural_check.py
DOOR_W, DOOR_TOP = 1.10, 2.55  # right-wall doorways: width and height of the arched head
CAPITAL_STYLES = ('plain', 'leaf', 'panel', 'teeth')   # columns 1..4 from the entrance end, as in photos 1 and 2
BASE_STYLES = ('eroded', 'ring', 'chamfer', 'block')    # their bases differ too (photo 2 for column 1, photo 1 for 2-4)
LOSS_T = 0.535                 # plaster-loss threshold = nq(0.72): about 28 % of the wall between 0.6 and 3 m is bare
UPLIGHT_W = 120              # watts per uplight (two per capital): vault about as bright as the walls, as in photo 2
FLOOR_BRICK_W = 0.14          # floor bricks are 2:1, 28 x 14 cm, laid in herringbone
SPRINGER_PROFILE = [(0.47, HS), (0.45, HS + 0.18), (0.38, HS + 0.55)]   # (radius, z): low brick block above each capital (round, smooth-shaded)
# large windows (left wall, one per bay; end walls, one per nave), measured on photo 1 with the calibrated camera:
# a deep rectangular recess under a flat lintel, steps rising to a narrow round-headed light near the outer face
WIN = dict(zb=1.48, zt=3.52, w=1.10, depth=0.80,              # recess: sill, lintel soffit, width at the face, depth
           w_back=0.64,                                       # splayed: width at the back of the recess, round the light
           light_zb=1.80, light_zt=3.33, light_w=0.50,        # light: sill, top of its round head, width
           steps=4)
# WINDOW_HEADS=arched builds a HYPOTHESIS, not what the photos show: the recess closed by a round rere-arch instead of
# the lintel (crown 0.20 m above today's soffit), as the original 13th-15th century form may have been
WINDOW_HEADS = os.environ.get('WINDOW_HEADS', 'lintel')
ARCHED_CROWN_ABOVE_LINTEL = 0.20
WEB_SINK = 0.12              # plaster cells dip this far where they meet a rib, so rib sides always reach the plaster


# ------------------------------------------------------------------ small helpers
_NOISE = NormalDist(0.5, 0.06)


def nq(p):
    """value of Blender's (normalized FBM) Noise Texture at quantile p: measured median 0.5, sd about 0.06 for every
    scale/detail used here, so masks are written as 'the top 25 %' = nq(0.75) rather than raw thresholds"""
    return _NOISE.inv_cdf(p)


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


def spring_z(x, y):
    """springing height of the ribs at plan point (x, y): side walls higher than the columns"""
    if abs(x) < 1e-6:
        return HS_WALL_L
    if abs(x - W) < 1e-6:
        return HS_WALL_R
    return HS


def arch_z(t, z0, z1, a, rise):
    """height at t (0..1) of an arch of half-span a springing at z0 and z1, crown kept at HS + rise.
    Equal ends at HS give the plain profile HS + prof()."""
    base = z0 + (z1 - z0) * t
    return base + (HS + rise - (z0 + z1) / 2) * prof((t - 0.5) * 2 * a, a, rise) / rise


def arch_pts(p0, p1, rise, n=40):
    """Points along a pointed arch from p0 to p1 (their z = the two springing heights)."""
    p0, p1 = Vector(p0), Vector(p1)
    flat = Vector((p1.x - p0.x, p1.y - p0.y, 0.0))
    a = flat.length / 2
    out = []
    for t in clustered(n):
        q = Vector((p0.x + flat.x * t, p0.y + flat.y * t, 0.0))
        q.z = arch_z(t, p0.z, p1.z, a, rise)
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
        return self.axis('Z')

    def axis(self, which, vec=None):
        n = self.node('ShaderNodeSeparateXYZ')
        self.nt.links.new(vec if vec is not None else self.coord(), n.inputs['Vector'])
        return n.outputs[which]

    def voronoi(self, scale, feature='F1', rand=1.0, vec=None):
        n = self.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature=feature)
        self.nt.links.new(vec if vec is not None else self.coord(), n.inputs['Vector'])
        n.inputs['Scale'].default_value = scale
        n.inputs['Randomness'].default_value = rand
        return n

    def dots(self, scale, radius, density, vec=None):
        """1 inside small round spots scattered in Voronoi cells (pits, pores, speckle), 0 elsewhere"""
        v = self.voronoi(scale, 'F1', vec=vec)
        d = self.val(self.ramp(v.outputs['Distance'], [(0.0, 1.0), (radius, 0.0)]))
        pick = self.val(self.ramp(self.val(v.outputs['Color']), [(1 - density - 0.001, 0.0), (1 - density, 1.0)]))
        return self.math('MULTIPLY', d, pick)

    def vmap(self, scale=(1, 1, 1), vec=None):
        """coordinates scaled per axis: a large Z scale stretches the noise into horizontal bands, a small one into
        vertical streaks"""
        n = self.node('ShaderNodeMapping')
        self.nt.links.new(vec if vec is not None else self.coord(), n.inputs['Vector'])
        n.inputs['Scale'].default_value = scale
        return n.outputs['Vector']

    def vadd(self, vec, val, k=(37.0, 11.0, 23.0)):
        """coordinates shifted by val * k, so pieces sharing a material get their own noise"""
        c = self.node('ShaderNodeCombineXYZ')
        for i, kk in enumerate(k):
            self.set(c.inputs[i], self.math('MULTIPLY', val, kk))
        vm = self.node('ShaderNodeVectorMath', operation='ADD')
        self.nt.links.new(vec, vm.inputs[0])
        self.nt.links.new(c.outputs['Vector'], vm.inputs[1])
        return vm.outputs['Vector']

    def obj_random(self):
        return self.node('ShaderNodeObjectInfo').outputs['Random']

    def ridge(self, n, sharp=8.0, k=8.0):
        """ridged Perlin: thin bright lines where the noise crosses its median (cracks, veins, chipped arrises)"""
        a = self.math('MINIMUM', self.math('ABSOLUTE', self.math('MULTIPLY', self.math('SUBTRACT', n, 0.5), 2.0 * k)), 1.0)
        return self.math('POWER', self.math('SUBTRACT', 1.0, a), sharp)

    def lin(self, x, a, b):
        """0 below a, 1 above b, linear between; works for any range (ColorRamp stops are clamped to 0..1)"""
        return self.math('DIVIDE', self.math('SUBTRACT', x, a), b - a, clamp=True)

    def inv(self, x):
        return self.math('SUBTRACT', 1.0, x)

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
    """lime plaster on rubble-and-brick walls, weathered as in photos 1 and 2: large patches where the plaster has
    fallen off (Perlin mask with sharp edges) showing the rubble and brick behind, brown mottling, vertical water
    streaks, a damp tide mark at the foot, stucco grain"""
    b = NB('plaster_wall')
    cream, ochre = (0.88, 0.84, 0.67), (0.74, 0.64, 0.43)        # pale cream to ochre (tuned against the photos)
    big = b.noise(0.30, 6, 0.6)
    mid = b.noise(1.8, 7, 0.55)
    fine = b.noise(28, 4, 0.6)
    z = b.zcoord()
    tone = b.mix(b.ramp(big, [(nq(0.15), 0), (nq(0.85), 1)]), cream, ochre)
    worn_mask = b.math('MULTIPLY', b.val(b.ramp(mid, [(nq(0.62), 0), (nq(0.85), 1)])),
                       b.val(b.ramp(big, [(nq(0.30), 0), (nq(0.70), 1)])))
    col = b.mix(worn_mask, tone, (0.56, 0.51, 0.41))               # grey-brown weathering
    blot = b.val(b.ramp(b.noise(1.2, 6, 0.62, dist=0.3), [(nq(0.10), 1.0), (nq(0.35), 0.0)]))
    col = b.mix(b.math('MULTIPLY', blot, 0.5), col, (0.62, 0.54, 0.40))   # brownish mottling
    streak = b.noise(1.0, 4, 0.5, vec=b.vmap((2.5, 2.5, 0.3)))      # vertical water streaks
    col = b.mul(col, b.ramp(streak, [(nq(0.10), 0.86), (nq(0.90), 1.03)]), 0.8)
    wav = b.noise(1.4, 3, 0.5)                                       # damp tide mark with a wavy top edge
    zt = b.math('ADD', z, b.math('MULTIPLY', b.math('SUBTRACT', wav, 0.5), 2.5))
    tide = b.inv(b.lin(zt, 0.45, 1.0))
    col = b.mix(b.math('MULTIPLY', tide, 0.5), col, (0.42, 0.43, 0.36))
    # plaster loss: big lobed Perlin patches with a sharp edge, mostly between 0.4 and 3.2 m
    lossn = b.noise(0.35, 8, 0.70, dist=0.3)
    zband = b.math('MULTIPLY', b.lin(z, 0.25, 0.6), b.inv(b.lin(z, 3.0, 3.6)))
    loss = b.math('MULTIPLY', b.val(b.ramp(lossn, [(LOSS_T, 0.0), (LOSS_T + 0.006, 1.0)])), zband)
    rim = b.math('MULTIPLY', b.val(b.ramp(lossn, [(LOSS_T - 0.008, 0.0), (LOSS_T + 0.001, 1.0), (LOSS_T + 0.008, 0.0)])), zband)
    cells = b.voronoi(7.0, 'F1')                                     # rubble stones behind the plaster
    stone = b.ramp(b.val(cells.outputs['Color']), [(0.0, (0.50, 0.44, 0.34)), (0.5, (0.56, 0.49, 0.37)),
                                                   (1.0, (0.61, 0.54, 0.41))])
    edges = b.voronoi(7.0, 'DISTANCE_TO_EDGE')
    jt = b.val(b.ramp(edges.outputs['Distance'], [(0.0, 1.0), (0.03, 0.0)]))
    rubble = b.mix(b.math('MULTIPLY', jt, 0.3), stone, (0.62, 0.57, 0.46))
    older = b.mix(b.ramp(b.noise(3.0, 6, 0.6), [(nq(0.2), 0.0), (nq(0.8), 1.0)]), (0.55, 0.48, 0.36), (0.64, 0.57, 0.44))
    showing = b.val(b.ramp(b.noise(1.6, 5, 0.6), [(nq(0.55), 0.0), (nq(0.70), 1.0)]))   # where the rubble shows
    under = b.mix(showing, older, rubble)
    bricky = b.val(b.ramp(b.noise(0.9, 3, 0.5), [(nq(0.90), 0.0), (nq(0.94), 1.0)]))
    under = b.mix(b.math('MULTIPLY', bricky, 0.7), under, (0.50, 0.35, 0.25))
    col = b.mix(loss, col, under)
    col = b.mul(col, b.ramp(rim, [(0.0, 1.0), (1.0, 0.65)]), 1.0)     # shadowed broken edge of the plaster
    col = b.mul(col, b.ramp(fine, [(nq(0.10), 0.84), (nq(0.90), 1.05)]), 0.6)
    h = b.math('ADD', b.inv(loss), b.math('MULTIPLY', fine, 0.12))
    h = b.math('ADD', h, b.math('MULTIPLY', loss, b.math('MULTIPLY', b.math('MULTIPLY', b.inv(jt), showing), 0.45)))
    return b.finish(col, 0.92, b.bump(h, 1.0, 0.015))


def mat_plaster_reveal():
    """window and door reveals: clean, pale lime plaster with soft mottling (photo 1)"""
    b = NB('plaster_reveal')
    big = b.noise(1.2, 5, 0.6)
    fine = b.noise(30, 4, 0.6)
    col = b.mix(b.ramp(big, [(nq(0.10), 0), (nq(0.90), 1)]), (0.82, 0.73, 0.53), (0.74, 0.63, 0.43))
    col = b.mul(col, b.ramp(fine, [(nq(0.10), 0.90), (nq(0.90), 1.04)]), 0.6)
    return b.finish(col, 0.93, b.bump(fine, 0.3, 0.01))


def mat_plaster_vault():
    """vault plaster: soft rose and ochre blotches (photo 2), a fine dark speckle and sandy grain (photo 3),
    trowel undulation"""
    b = NB('plaster_vault')
    cream, rosy, ochre = (0.72, 0.60, 0.45), (0.69, 0.52, 0.40), (0.64, 0.48, 0.30)
    big = b.noise(0.45, 6, 0.6, dist=0.5)
    mid = b.noise(2.2, 6, 0.6)
    fine = b.noise(40, 3, 0.6)
    tone = b.mix(b.ramp(big, [(nq(0.10), 0), (nq(0.90), 1)]), cream, rosy)
    rose = b.val(b.ramp(b.noise(0.55, 6, 0.62, dist=0.8), [(nq(0.55), 0.0), (nq(0.85), 1.0)]))
    tone = b.mix(b.math('MULTIPLY', rose, 0.7), tone, (0.76, 0.54, 0.44))
    stain = b.val(b.ramp(b.noise(0.8, 5, 0.65, dist=0.6), [(nq(0.75), 0), (nq(0.93), 1)]))
    col = b.mix(b.math('MULTIPLY', stain, 0.5), tone, ochre)
    grey = b.val(b.ramp(b.noise(1.6, 4, 0.6), [(nq(0.85), 0), (nq(0.97), 1)]))     # sooty / damp blotches
    col = b.mix(b.math('MULTIPLY', grey, 0.35), col, (0.45, 0.40, 0.34))
    col = b.mul(col, b.ramp(mid, [(nq(0.10), 0.88), (nq(0.90), 1.06)]), 0.8)
    col = b.mul(col, b.ramp(fine, [(nq(0.10), 0.90), (nq(0.90), 1.05)]), 0.7)
    speck = b.dots(35.0, 0.18, 0.35)                                   # fine dark speckle (photo 3)
    col = b.mul(col, b.ramp(speck, [(0.0, 1.0), (1.0, 0.50)]), 1.0)
    sand = b.dots(120.0, 0.25, 0.5)                                    # sandy grain of the lime plaster
    col = b.mul(col, b.ramp(sand, [(0.0, 1.0), (1.0, 0.82)]), 1.0)
    trowel = b.noise(2.5, 3, 0.5)
    h = b.math('ADD', b.math('ADD', fine, b.math('MULTIPLY', mid, 0.5)), b.math('MULTIPLY', trowel, 1.2))
    h = b.math('ADD', h, b.math('MULTIPLY', sand, 0.3))
    return b.finish(col, 0.95, b.bump(h, 0.6, 0.02))


def mat_floor_bricks():
    """old cotto floor: each brick has its own tone (mesh attributes brick_rand / brick_rand2 from floor_bricks()),
    fired-clay mottling, and grey-white dust bloom in large patches, as in photos 1 and 2"""
    b = NB('floor_brick')
    r1 = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='brick_rand').outputs['Fac']
    r2 = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='brick_rand2').outputs['Fac']
    # tan cotto, tuned so the rendered floor matches the colour measured in photos 1 and 2
    # (red:green:blue about 0.42 : 0.34 : 0.24); the room's warm light pushes it redder, so the albedo leans yellow
    tone = b.ramp(r1, [(0.00, (0.52, 0.39, 0.24)),     # dark, reddish
                       (0.15, (0.58, 0.45, 0.28)),     # warmer red-tan
                       (0.45, (0.63, 0.52, 0.33)),     # ordinary faded cotto
                       (0.80, (0.68, 0.59, 0.40)),     # pale, worn
                       (1.00, (0.65, 0.59, 0.43))])    # greyish, dust ground in
    jitter = b.ramp(r2, [(0.0, 0.75), (0.03, 0.75), (0.035, 0.92), (1.0, 1.06)])   # r2 < 0.03: sunken, darker bricks
    col = b.mul(tone, jitter, 1.0)
    per_brick = b.vadd(b.coord(), r1, (13.1, 7.7, 3.3))                # each brick gets its own mottling
    mott = b.noise(18, 5, 0.6, dist=0.4, vec=per_brick)
    col = b.mul(col, b.ramp(mott, [(nq(0.10), 0.82), (nq(0.90), 1.10)]), 1.0)
    burn = b.noise(5, 4, 0.6, vec=per_brick)                           # firing marks: darker clouds inside a brick
    col = b.mul(col, b.ramp(burn, [(nq(0.70), 1.0), (nq(0.95), 0.80)]), 1.0)
    wear = b.val(b.ramp(b.noise(9, 5, 0.6, dist=0.6), [(nq(0.60), 0.0), (nq(0.90), 0.65)]))   # pale scuffed patches on the faces
    col = b.mix(wear, col, (0.73, 0.66, 0.47))
    pits = b.dots(110.0, 0.22, 0.35)                                    # small dark pits in the clay
    col = b.mul(col, b.ramp(pits, [(0.0, 1.0), (1.0, 0.62)]), 1.0)
    dust = b.math('MULTIPLY', b.val(b.ramp(b.noise(0.35, 5, 0.6), [(nq(0.10), 0.35), (nq(0.90), 0.90)])),
                  b.val(b.ramp(b.noise(2.5, 4, 0.6), [(nq(0.10), 0.65), (nq(0.90), 1.0)])))
    col = b.mix(dust, col, (0.70, 0.61, 0.43))     # beige dust
    x = b.axis('X')                                 # lighter, dustier, worn path down the middle of each nave
    d = b.math('MINIMUM', b.math('ABSOLUTE', b.math('SUBTRACT', x, S / 2)), b.math('ABSOLUTE', b.math('SUBTRACT', x, 1.5 * S)))
    aisle = b.math('MULTIPLY', b.inv(b.lin(d, 0.0, 1.8)), b.val(b.ramp(b.noise(0.6, 4, 0.6), [(nq(0.10), 0.4), (nq(0.90), 1.0)])))
    col = b.mix(b.math('MULTIPLY', aisle, 0.22), col, (0.72, 0.63, 0.44))
    fine = b.noise(70, 4, 0.6)
    col = b.mul(col, b.ramp(fine, [(nq(0.10), 0.88), (nq(0.90), 1.05)]), 0.6)
    dips = b.noise(1.3, 3, 0.5, vec=per_brick)                          # uneven, worn brick faces
    h = b.math('ADD', fine, b.math('MULTIPLY', dips, 2.5))
    h = b.math('SUBTRACT', h, b.math('MULTIPLY', pits, 0.6))
    return b.finish(col, 0.82, b.bump(h, 0.30, 0.004))


def mat_floor_mortar():
    b = NB('floor_mortar')
    n = b.noise(6, 4, 0.6)
    col = b.mix(b.ramp(n, [(nq(0.10), 0), (nq(0.90), 1)]), (0.62, 0.54, 0.40), (0.72, 0.63, 0.46))   # dust-filled joints
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
    brick = b.ramp(rnd, [(0.0, (0.26, 0.08, 0.04)), (0.40, (0.40, 0.14, 0.07)), (0.78, (0.50, 0.22, 0.11)),
                         (0.95, (0.58, 0.34, 0.20)), (1.0, (0.64, 0.46, 0.32))])   # deep red ... a few pale buff, as in photo 1
    wash = b.val(b.ramp(b.noise(2.2, 4, 0.5), [(nq(0.30), 0), (nq(0.90), 1)]))
    brick = b.mix(b.math('MULTIPLY', wash, 0.45), brick, (0.40, 0.27, 0.19))
    per_brick = b.vadd(b.coord(), b.math('FLOOR', t), (3.1, 1.7, 2.3))
    mott = b.noise(14, 4, 0.6, vec=per_brick)                          # mottling inside each brick
    brick = b.mul(brick, b.ramp(mott, [(nq(0.10), 0.82), (nq(0.90), 1.10)]), 1.0)
    chip = b.ridge(b.noise(6, 5, 0.6), 10.0)                           # chipped spots showing the paler core
    brick = b.mix(b.math('MULTIPLY', chip, 0.3), brick, (0.64, 0.46, 0.33))
    pores = b.dots(70.0, 0.14, 0.40)
    brick = b.mul(brick, b.ramp(pores, [(0.0, 1.0), (1.0, 0.62)]), 1.0)
    eff = b.val(b.ramp(b.noise(0.9, 5, 0.6, dist=0.5), [(nq(0.88), 0.0), (nq(0.96), 1.0)]))   # lime smears / salt bloom
    brick = b.mix(b.math('MULTIPLY', eff, 0.25), brick, (0.76, 0.71, 0.62))
    soot = b.val(b.ramp(b.noise(0.5, 4, 0.6), [(nq(0.70), 0.0), (nq(0.90), 1.0)]))
    brick = b.mul(brick, b.ramp(soot, [(0.0, 1.0), (1.0, 0.78)]), 1.0)
    dirt = b.noise(3.0, 4, 0.6)                                        # mortar: clean lime to dirty, eroded joints
    mortar = b.mix(b.val(b.ramp(dirt, [(nq(0.30), 0.0), (nq(0.80), 1.0)])), (0.74, 0.68, 0.58), (0.52, 0.47, 0.39))
    col = b.mix(joint, mortar, brick)
    depth = b.ramp(dirt, [(nq(0.10), 0.35), (nq(0.90), 1.0)])                    # how far each joint is recessed
    h = b.math('ADD', b.math('MULTIPLY', b.math('SUBTRACT', 1.0, joint), b.math('MULTIPLY', b.val(depth), -1.0)),
               b.math('MULTIPLY', rnd, 0.15))
    h = b.math('ADD', h, b.math('MULTIPLY', mott, 0.25))
    h = b.math('SUBTRACT', h, b.math('MULTIPLY', pores, 0.4))
    return b.finish(col, 0.85, b.bump(h, 0.9, 0.012))


def mat_stone(name, base, alt, rust=True, rust_amt=0.7, rust_col=(0.34, 0.2, 0.1), rust_zone=None):
    """gneiss-like stone as on the columns in photo 2: crystal speckle, large pale lime/lichen patches and darker damp
    ones, vertical water streaks, thin cracks, grime toward the floor. Each object gets its own noise offset.
    rust_zone = (y_max, z_max) keeps the rust staining to one area (the first column's foot)."""
    b = NB(name)
    co = b.vadd(b.coord(), b.obj_random())
    n1 = b.noise(1.6, 6, 0.6, dist=0.3, vec=co)
    n2 = b.noise(9, 5, 0.6, vec=co)
    fine = b.noise(45, 4, 0.6, vec=co)
    col = b.mix(b.ramp(n1, [(nq(0.10), 0), (nq(0.90), 1)]), base, alt)
    pat = b.noise(0.9, 6, 0.62, dist=0.4, vec=co)
    col = b.mix(b.math('MULTIPLY', b.val(b.ramp(pat, [(nq(0.72), 0.0), (nq(0.88), 1.0)])), 0.65), col, (0.82, 0.78, 0.60))
    col = b.mix(b.math('MULTIPLY', b.val(b.ramp(pat, [(nq(0.06), 1.0), (nq(0.22), 0.0)])), 0.45), col, (0.38, 0.39, 0.26))
    grain = b.voronoi(150, 'F1', vec=co)                                # crystals
    col = b.mul(col, b.ramp(b.val(grain.outputs['Color']), [(0.0, 0.82), (0.5, 1.0), (1.0, 1.16)]), 0.8)
    streak = b.noise(1.0, 4, 0.5, vec=b.vmap((12.0, 12.0, 0.8), vec=co))
    col = b.mul(col, b.ramp(streak, [(nq(0.10), 0.86), (nq(0.90), 1.05)]), 1.0)
    sparse = b.val(b.ramp(b.noise(0.7, 3, 0.5, vec=co), [(nq(0.80), 0.0), (nq(0.90), 1.0)]))   # cracks only in some places
    crack = b.math('MULTIPLY', b.ridge(b.noise(1.3, 4, 0.5, vec=co), 60.0), sparse)
    col = b.mul(col, b.ramp(crack, [(0.0, 1.0), (1.0, 0.86)]), 1.0)
    z = b.zcoord()
    col = b.mul(col, b.ramp(z, [(0.0, 0.72), (0.7, 1.0)]), 1.0)          # grime toward the floor
    if rust:
        r = b.val(b.ramp(b.noise(3.0, 4, 0.55, vec=co), [(nq(0.45), 0), (nq(0.80), 1)]))
        if rust_zone:
            zone = b.math('MULTIPLY', b.inv(b.lin(b.axis('Y'), rust_zone[0] - 1.0, rust_zone[0])),
                          b.inv(b.lin(z, rust_zone[1] - 0.5, rust_zone[1])))
            r = b.math('MULTIPLY', r, zone)
        col = b.mix(b.math('MULTIPLY', r, rust_amt), col, rust_col)
    col = b.mul(col, b.ramp(n2, [(nq(0.10), 0.72), (nq(0.90), 1.12)]), 0.9)
    h = b.math('ADD', b.math('MULTIPLY', n2, 0.7), fine)
    h = b.math('SUBTRACT', h, b.math('MULTIPLY', crack, 0.4))
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
    MAT['reveal'] = mat_plaster_reveal()
    MAT['floor'] = mat_floor_mortar()
    MAT['floor_bricks'] = mat_floor_bricks()
    MAT['rib'] = mat_brick_rib()
    MAT['springer'] = mat_brick_rib(use_z=True)
    MAT['col'] = mat_stone('column_stone', (0.57, 0.53, 0.30), (0.69, 0.65, 0.38), rust_amt=0.75, rust_col=(0.36, 0.20, 0.10),
                           rust_zone=(S + 1.5, 1.0))   # light warm grey stone (photo 2); rust only at the first column's foot
    MAT['cap_plain'] = mat_stone('capital_plain', (0.45, 0.41, 0.27), (0.54, 0.50, 0.34), rust=False)   # darker, column 1
    MAT['cap_leaf'] = mat_stone('capital_leaf', (0.58, 0.55, 0.36), (0.68, 0.65, 0.45), rust=False)
    MAT['cap_panel'] = mat_stone('capital_panel', (0.59, 0.55, 0.36), (0.69, 0.65, 0.45), rust=False)
    MAT['cap_teeth'] = mat_stone('capital_teeth', (0.66, 0.63, 0.43), (0.75, 0.73, 0.53), rust=False)   # palest, column 4
    MAT['step'] = mat_stone('step_stone', (0.70, 0.66, 0.54), (0.78, 0.74, 0.61), rust=False)   # pale worn steps
    MAT['corbel'] = mat_stone('corbel_stone', (0.50, 0.46, 0.33), (0.58, 0.53, 0.39), rust=False)
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
            zc = [spring_z(c.x, c.y) for c in cs]
            for side in range(4):
                ca, cb = cs[side], cs[(side + 1) % 4]
                za, zb = zc[side], zc[(side + 1) % 4]
                grid = []
                for u in us:
                    row = []
                    side_xy = ca + (cb - ca) * u
                    zs = arch_z(u, za, zb, S / 2, R_SIDE)
                    w = abs(2 * u - 1) ** P_W
                    k = side if u < 0.5 else (side + 1) % 4          # nearer corner: its diagonal rib
                    z_near, z_opp = zc[k], zc[(k + 2) % 4]
                    for v in vs:
                        xy = side_xy * (1 - v) + C * v
                        dd = arch_z(v / 2, z_near, z_opp, A_D, R_DIAG)
                        lin = (1 - v) * z_near + v * HK
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
                z_end = pts[0].z if i < n // 2 else pts[-1].z
                if plaster_sides and not rounded and k != 1 and pts[i].z > z_end + 0.75:   # side faces, above the springer
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
                pts = arch_pts((*p0, spring_z(*p0)), (*p1, spring_z(*p1)), R_DIAG, 56)
                d = (Vector(p1) - Vector(p0))
                bvec = Vector((-d.y, d.x, 0)).normalized()
                add_rib(bm, uvl, pts, bvec, W_DIAG, D_BELOW_DIAG, D_ABOVE, rounded=True)
    # transverse arches (run along x at y = j*S); end ones are wall arches
    for j in range(NY + 1):
        for i in range(NX):
            pts = arch_pts((i * S, j * S, spring_z(i * S, j * S)), ((i + 1) * S, j * S, spring_z((i + 1) * S, j * S)), R_SIDE, 48)
            wall = j in (0, NY)
            add_rib(bm, uvl, pts, ey, W_WALL if wall else W_TRANS, D_BELOW_WALL if wall else D_BELOW_BIG, D_ABOVE, plaster_sides=True)
    # longitudinal arches (run along y at x = i*S); outer ones are wall arches
    for i in range(NX + 1):
        for j in range(NY):
            pts = arch_pts((i * S, j * S, spring_z(i * S, j * S)), (i * S, (j + 1) * S, spring_z(i * S, (j + 1) * S)), R_SIDE, 48)
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

    def plan(a):                       # plan point on the wall line at distance a along it
        return (at, a) if axis == 'x' else (a, at)

    z_first, z_last = spring_z(*plan(0.0)), spring_z(*plan(span))
    pts2 = [(-WALL_T, -0.4), (span + WALL_T, -0.4), (span + WALL_T, z_last)]
    for j in reversed(range(along)):
        a0, a1 = j * S, (j + 1) * S
        z0, z1 = spring_z(*plan(a0)), spring_z(*plan(a1))
        for t in reversed(clustered(40)):
            pts2.append((a0 + t * S, arch_z(t, z0, z1, S / 2, R_SIDE)))
    pts2.append((-WALL_T, z_first))
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
        for op in openings:
            pa, pb, d_in = op[:3]
            d_out = op[3] if len(op) > 3 else WALL_T + 0.1
            hb = hull_cutter(pa, pb, lambda a, z, d: p3(a, z, d), d_in, d_out)
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
        mod.use_self = True             # recess and light cutters overlap
        bpy.context.view_layer.objects.active = ob
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.ops.object.modifier_apply(modifier='cut')
        bpy.data.objects.remove(cut, do_unlink=True)
        # reveals, soffits and sills of the openings: clean lime plaster (as in the photos), not the flaking wall
        n_main = Vector((1, 0, 0)) if axis == 'x' else Vector((0, 1, 0))
        ob.data.materials.append(MAT['reveal'])
        for poly in ob.data.polygons:
            if abs(poly.normal.dot(n_main)) < 0.9 and HS - 2.0 < poly.center.z < HS + 2.5 and poly.center.z > 0.05:
                poly.material_index = 1
    return ob


def window_openings(c):
    """cutters for one large window: the recess (flat lintel head, or the arched hypothesis) and the light"""
    w = WIN
    if WINDOW_HEADS == 'arched':
        crown = w['zt'] + ARCHED_CROWN_ABOVE_LINTEL
        front, back = arch_outline(c, w['zb'], crown, w['w']), arch_outline(c, w['zb'], crown, w['w_back'])
    else:
        front, back = rect_outline(c, w['zb'], w['zt'], w['w']), rect_outline(c, w['zb'], w['zt'], w['w_back'])
    light = arch_outline(c, w['light_zb'], w['light_zt'], w['light_w'])
    return [(front, back, -0.05, w['depth']), (light, light, w['depth'] - 0.03, WALL_T + 0.1)]


def build_walls():
    # left wall (x=0): large window per bay, plus small lunette window
    left = []
    for j in range(NY):
        c = j * S + S / 2
        left += window_openings(c)
        left.append((rect_outline(c, 4.25, 5.05, 0.80), rect_outline(c, 4.45, 4.90, 0.35), -0.05))
    wall_slab('wall_left', 'x', 0.0, -1, left)

    # right wall (x=W): two doorways near the far end, nothing else
    right = []
    for c in DOOR_CENTRES:
        right.append((arch_outline(c, -0.2, DOOR_TOP, DOOR_W), arch_outline(c, -0.2, DOOR_TOP, DOOR_W), -0.05))
    wall_slab('wall_right', 'x', W, +1, right)

    # end walls: large window + oculus per nave
    ends = []
    for i in range(NX):
        c = i * S + S / 2
        ends += window_openings(c)
        ends.append((circle_outline(c, 4.55, 0.42), circle_outline(c, 4.55, 0.24), -0.05))
    wall_slab('wall_near', 'y', 0.0, -1, ends)
    wall_slab('wall_far', 'y', L, +1, ends)


def window_places():
    """(axis, wall plane, outward sign, centre along the wall) of every large window"""
    out = [('x', 0.0, -1, j * S + S / 2) for j in range(NY)]
    for i in range(NX):
        out += [('y', 0.0, -1, i * S + S / 2), ('y', L, +1, i * S + S / 2)]
    return out


def wall_box(bm, axis, at, outward, c, d0, d1, z0, z1, width):
    """box in a wall's frame: depth d0..d1 behind the inner face, z0..z1, width along the wall"""
    dc, dl = (d0 + d1) / 2, d1 - d0
    if axis == 'x':
        add_box(bm, (at + outward * dc, c, (z0 + z1) / 2), (dl, width, z1 - z0))
    else:
        add_box(bm, (c, at + outward * dc, (z0 + z1) / 2), (width, dl, z1 - z0))


def window_steps():
    """stone steps filling each recess from its sill up to the light, as in photo 1 (about 8 cm risers); in the
    lintel version also the stone lintel, hanging 4 cm below the soffit"""
    w, bm = WIN, bmesh.new()
    n, D = w['steps'], w['depth']
    rise = (w['light_zb'] - w['zb']) / n
    for (axis, at, outward, c) in window_places():
        for k in range(n):
            d0 = 0.003 if k == 0 else D * k / n
            width = w['w'] + (w['w_back'] - w['w']) * d0 / D + 0.04        # follows the splay, ends hidden in the reveals
            wall_box(bm, axis, at, outward, c, d0, D * (k + 1) / n, w['zb'], w['zb'] + rise * (k + 1), width)
    steps = to_obj('window_steps', bm, MAT['step'])
    if WINDOW_HEADS != 'arched':
        bm = bmesh.new()
        for (axis, at, outward, c) in window_places():
            wall_box(bm, axis, at, outward, c, 0.005, 0.35, w['zt'] - 0.04, w['zt'] + 0.12, w['w'] + 0.30)
        to_obj('window_lintels', bm, MAT['reveal'])
    return steps


def window_frames():
    """thin iron glazing bars in each round-headed light"""
    w, bm = WIN, bmesh.new()
    zb, zt, lw = w['light_zb'] + 0.02, w['light_zt'] - 0.02, w['light_w'] - 0.04
    zs = zt - lw / 2                                  # springing of the round head
    d = w['depth'] + 0.12
    for (axis, at, outward, c) in window_places():
        wall_box(bm, axis, at, outward, c, d - 0.015, d + 0.015, zb, zs + 0.15, 0.025)     # mullion
        for f in (0.33, 0.66):
            z = zb + (zs - zb) * f
            wall_box(bm, axis, at, outward, c, d - 0.015, d + 0.015, z - 0.0125, z + 0.0125, lw)
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


def column_base(bm, style, cx, cy, seed):
    """the four bases differ, as in photos 1 and 2; all end just inside the shaft (r 0.33 at z 0.315), so no seam shows"""
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.28) for _ in range(4)]
    if style == 'eroded':         # column 1: rough, broken drum of lumpy blocks with a missing chunk
        prof_ = [(0.47, 0.0), (0.48, 0.04), (0.475, 0.12), (0.47, 0.21), (0.455, 0.265), (0.40, 0.29), (0.33, 0.315)]
        gap = rnd.uniform(0, 6.28)

        def radial(th, z):
            r = 1 + 0.045 * math.sin(5 * th + ph[0]) + 0.03 * math.sin(11 * th + 9 * z + ph[1]) + 0.02 * math.sin(23 * th + ph[2])
            d = (th - gap + math.pi) % (2 * math.pi) - math.pi
            if abs(d) < 0.35 and z > 0.13:                # broken-off piece of the upper edge
                r -= 0.07 * (1 - abs(d) / 0.35) * smooth01(0.13, 0.20, z)
            return r
    elif style == 'ring':         # column 2: straight drum, then a fillet ring under the shaft
        prof_ = [(0.44, 0.0), (0.445, 0.02), (0.445, 0.185), (0.43, 0.20), (0.40, 0.205), (0.40, 0.225),
                 (0.418, 0.24), (0.40, 0.255), (0.365, 0.27), (0.33, 0.315)]
        radial = lambda th, z: 1 + 0.012 * math.sin(3 * th + ph[0]) + 0.008 * math.sin(7 * th + 6 * z + ph[1])
    elif style == 'chamfer':      # column 3: lower drum with a chamfered top
        prof_ = [(0.42, 0.0), (0.425, 0.02), (0.425, 0.15), (0.405, 0.17), (0.355, 0.27), (0.33, 0.315)]
        radial = lambda th, z: 1 + 0.015 * math.sin(4 * th + ph[0]) + 0.01 * math.sin(9 * th + 5 * z + ph[1])
    else:                         # 'block', column 4: taller lumpy drum with a flat ledge
        prof_ = [(0.46, 0.0), (0.47, 0.03), (0.47, 0.15), (0.465, 0.26), (0.44, 0.285), (0.36, 0.295), (0.33, 0.315)]
        radial = lambda th, z: 1 + 0.03 * math.sin(4 * th + ph[0]) + 0.02 * math.sin(9 * th + 7 * z + ph[1])
    lathe(bm, prof_, 72, radial=radial, cx=cx, cy=cy)


def columns():
    bm_col = bmesh.new()
    bm_iron = bmesh.new()
    bm_lamp = bmesh.new()
    pos = [(S, (k + 1) * S) for k in range(NY - 1)]
    for idx, (cx, cy) in enumerate(pos):
        ph = random.uniform(0, 6.28)
        irr = lambda th, z, ph=ph: 1 + 0.014 * math.sin(3 * th + z * 1.7 + ph) + 0.01 * math.sin(5 * th - 2.1 * z + ph)
        bm_base = bmesh.new()
        column_base(bm_base, BASE_STYLES[idx], cx, cy, seed=101 + idx)
        to_obj('base_%d_%s' % (idx + 1, BASE_STYLES[idx]), bm_base, MAT['col'], smooth=True)
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
    wb = W_TRANS + 0.02      # 1 cm proud of the arch sides each way: coplanar faces z-fought (flickered) in EEVEE
    for (x, y, k) in pts:
        zs_ = spring_z(x, y)
        if abs(k) == 1:
            add_box(bm, (x + (0.2 if k > 0 else -0.2), y, zs_ + 0.28), (0.40, wb, 0.56))
        else:
            add_box(bm, (x, y + (0.2 if k > 0 else -0.2), zs_ + 0.28), (wb, 0.40, 0.56))
    for (x, y, dx, dy) in ((0, 0, 1, 1), (W, 0, -1, 1), (0, L, 1, -1), (W, L, -1, -1)):
        add_box(bm, (x + dx * 0.2, y + dy * 0.2, spring_z(x, y) + 0.28), (0.40, 0.40, 0.56))
    return to_obj('springers', bm, MAT['springer'])


def corbel_block(bm, base, out, along, levels):
    """a corbel swept from the wall face: levels = [(z, projection, width), ...] bottom to top"""
    rings = []
    for (z, p, w) in levels:
        ring = []
        for (o, a_) in ((0.0, -w / 2), (p, -w / 2), (p, w / 2), (0.0, w / 2)):
            q = base + out * (o - 0.02) + along * a_      # 2 cm buried in the wall
            ring.append(bm.verts.new((q.x, q.y, z)))
        rings.append(ring)
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(4):
            bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])


def corbel_levels(style, top, size):
    P_, W_, H_ = size
    z0 = top - H_
    if style == 'cushion':        # right wall: rounded, bulging block (photo 1)
        return [(z0 + H_ * f, P_ * p, W_ * w) for f, p, w in
                ((0.0, 0.35, 0.62), (0.08, 0.62, 0.80), (0.22, 0.82, 0.92), (0.42, 0.95, 0.98),
                 (0.65, 1.0, 1.0), (1.0, 1.0, 1.0))]
    # 'stepped': left wall and end walls, a moulded block narrowing downward in small steps
    return [(z0 + H_ * f, P_ * p, W_ * w) for f, p, w in
            ((0.0, 0.45, 0.60), (0.24, 0.50, 0.66), (0.27, 0.68, 0.78), (0.50, 0.73, 0.84),
             (0.53, 0.90, 0.94), (0.76, 0.94, 0.98), (0.79, 1.0, 1.0), (1.0, 1.0, 1.0))]


def corbels():
    """stone corbels under the wall springing points, sized and placed from photo 1"""
    bm = bmesh.new()
    ex, ey = Vector((1, 0, 0)), Vector((0, 1, 0))
    for j in range(NY + 1):
        for (x, out, size, style) in ((0.0, ex, CORBEL_L, 'stepped'), (W, -ex, CORBEL_R, 'cushion')):
            y = j * S
            if j in (0, NY):            # corner: sits diagonally in the corner, narrower
                out_c = (out + (ey if j == 0 else -ey)).normalized()
                along = Vector((-out_c.y, out_c.x, 0))
                base = Vector((x, y, 0)) + out_c * 0.03
                corbel_block(bm, base, out_c, along, corbel_levels(style, spring_z(x, y), (size[0], size[1] * 0.8, size[2])))
            else:
                corbel_block(bm, Vector((x, y, 0)), out, ey, corbel_levels(style, spring_z(x, y), size))
    for (y, out) in ((0.0, ey), (L, -ey)):    # end walls, middle
        corbel_block(bm, Vector((S, y, 0)), out, ex, corbel_levels('stepped', HS, CORBEL_END))
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
    u, joint, cham, drop, zb = FLOOR_BRICK_W, 0.008, 0.003, 0.001, -0.012
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
        zt = -0.001 - rng.random() * 0.0012 - (0.001 if r2 < 0.03 else 0.0)
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
                          matrix=Matrix.Translation((W / 2, L / 2, -0.0036)) @ Matrix.Diagonal((W / 2 + 0.1, L / 2 + 0.1, 1, 1)))
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
    name = 'foresteria' + ('_furnished' if WITH_FURNITURE else '') + ('_arched' if WINDOW_HEADS == 'arched' else '')
    path = os.path.join(HERE, name + '.blend')
    bpy.context.preferences.filepaths.save_version = 0     # no .blend1 backup (not written to user prefs in -b)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print('saved', path)


main()
