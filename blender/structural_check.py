"""
First-order structural check of the foresteria vault (plain Python, no dependencies).

Method: lower-bound limit analysis of masonry (Heyman's safe theorem). Each rib/arch is cut into voussoirs,
loaded by its own weight plus its share of the web and (optionally) the upper-floor fill. For every pair
(H, delta) of crown thrust and crown eccentricity the thrust line is computed, and a state is admissible if the
line stays inside the section at every joint (no tension, joints at the section edge = hinge). The scan gives:
  H_min, H_max : smallest and largest horizontal thrust for which a stable state exists
  t_min        : thinnest uniform section for which any stable state exists (loads held fixed)
  GFS          : geometric factor of safety = actual depth / t_min   (>1 stable; historic arches are ~1.5-3)

Then the supports (columns, corbels, wall piers) are checked against those thrusts.

Assumptions are listed in ASSUME. Nothing here comes from a survey: dimensions are the model's, material
data and the upper-floor arrangement are guesses. Run:  python3 structural_check.py [wall_thickness_m]
"""
import ast, math, os, sys


# ---------------------------------------------------------------- model geometry, read from build_foresteria.py
def model_constants(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_foresteria.py')):
    """top-level literal constants of the Blender build script (parsed, not imported: importing it would build
    the scene), so the model and this check can't drift apart"""
    out = {}
    for node in ast.parse(open(path).read()).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        try:
            val = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError):
            continue
        tgt = node.targets[0]
        if isinstance(tgt, ast.Name):
            out[tgt.id] = val
        elif isinstance(tgt, ast.Tuple) and isinstance(val, tuple) and len(val) == len(tgt.elts):
            out.update({e.id: v for e, v in zip(tgt.elts, val) if isinstance(e, ast.Name)})
    return out


M = model_constants()
S, HS, NX, NY = M['S'], M['HS'], M['NX'], M['NY']
R_SIDE, R_DIAG = M['R_SIDE'], M['R_DIAG']
HK = HS + R_DIAG
A_D = S * math.sqrt(2) / 2
WALL_T = float(sys.argv[1]) if len(sys.argv) > 1 else M['WALL_T']
W_TRANS, W_DIAG, W_WALL = M['W_TRANS'], M['W_DIAG'], M['W_WALL']
D_VIS_BIG, D_VIS_DIAG, D_VIS_WALL = M['D_BELOW_BIG'], M['D_BELOW_DIAG'], M['D_BELOW_WALL']   # hang below the web
D_HID = M['D_ABOVE']                                       # masonry above the web line
CORBEL = tuple(M['CORBEL'])                                # projection, width, height of the wall corbels (m)
DOOR_CENTRES, DOOR_W, DOOR_TOP = M['DOOR_CENTRES'], M['DOOR_W'], M['DOOR_TOP']
HAUNCH_BACKING = HS + 2.0                                  # masonry backing of the haunches up to this level (m)
WEB_AREA_RATIO = 1.78                                      # web surface / plan area, measured on the mesh

# ---------------------------------------------------------------- assumptions
ASSUME = dict(
    gamma_brick=18.0,      # kN/m3 brick masonry
    gamma_stone=26.0,      # kN/m3 column / corbel stone
    gamma_fill=17.0,       # kN/m3 rubble / sand fill over the vault
    web_t=0.15,            # m brick web
    floor_dead=3.0,        # kN/m2 tiles + bedding on top of the fill
    floor_live=2.0,        # kN/m2 dormitory (EC1 cat. A) -- partitions ignored
    fill_top=HK + 0.30,    # m, level of the upper floor above the ground-floor floor
    share_side=0.40,       # share of each web patch + fill carried by the side arch
    share_diag=0.60,       # share carried by the two diagonals (together)
)
G_B = ASSUME['gamma_brick']


def prof(x, a, r):
    x = abs(x)
    if x >= a:
        return 0.0
    if r >= a:
        xc = (a * a - r * r) / (2 * a)
        rho = a - xc
        return math.sqrt(max(rho * rho - (x - xc) ** 2, 0.0))
    return r * math.sqrt(1 - (x / a) ** 2)


# ---------------------------------------------------------------- one half arch, crown -> springing
class Arch:
    def __init__(self, name, a, rise, t_geo, A_rib, b_trib, n=80, shape='uniform'):
        self.name, self.a, self.rise, self.t = name, a, rise, t_geo
        self.A_rib, self.b_mean, self.shape = A_rib, b_trib, shape
        self.pts = []
        for i in range(n + 1):
            x = a * math.sin(math.pi / 2 * i / n)      # dense near the steep springing
            self.pts.append((x, prof(x, a, rise)))
        self.th = []
        for i, (x, y) in enumerate(self.pts):
            j0, j1 = max(i - 1, 0), min(i + 1, n)
            self.th.append(math.atan2(self.pts[j1][1] - self.pts[j0][1], self.pts[j1][0] - self.pts[j0][0]))
        self.segs = []                                   # (ds, dx, xmid, ymid)
        for (x0, y0), (x1, y1) in zip(self.pts[:-1], self.pts[1:]):
            self.segs.append((math.hypot(x1 - x0, y1 - y0), x1 - x0, (x0 + x1) / 2, (y0 + y1) / 2))

    def b_at(self, x):
        u = min(abs(x) / self.a, 1.0)
        if self.shape == 'tri':          # diagonal: tributary web width grows linearly from the keystone to the corner
            return self.b_mean * 2.0 * u
        if self.shape == 'parab':        # side arch: widest at mid-span, tapering to the corners
            return self.b_mean * 1.5 * (1 - u * u)
        return self.b_mean

    def weights(self, case, t_scale_selfweight=None, haunch=None):
        """lumped vertical load per segment (kN) for the half arch.
        haunch: level (m above the floor) up to which the extrados is backed with masonry"""
        out = []
        for ds, dx, xm, ym in self.segs:
            w = self.A_rib * G_B * ds if t_scale_selfweight is None else t_scale_selfweight * ds
            # web: weight per plan area times the tributary width
            q_web = ASSUME['web_t'] * G_B * WEB_AREA_RATIO
            w += q_web * self.b_at(xm) * dx
            if haunch is not None and case != 'floor':
                depth = max(haunch - (HS + ym), 0.0)
                w += G_B * depth * self.b_at(xm) * dx
            if case == 'floor':
                z = HS + ym
                depth = max(ASSUME['fill_top'] - z, 0.0)
                w += (ASSUME['gamma_fill'] * depth + ASSUME['floor_dead'] + ASSUME['floor_live']) * self.b_at(xm) * dx
            out.append(w)
        return out


def feasible(arch, W, H, t):
    """does a thrust line exist for crown thrust H (kN) inside a section of depth t?"""
    pts, th = arch.pts, arch.th
    yc = pts[0][1]
    lo, hi = -t / 2, t / 2
    V = 0.0
    A = 0.0
    xs = [s[2] for s in arch.segs]
    for k in range(1, len(pts)):
        V += W[k - 1]
        A = sum(W[j] * (pts[k][0] - xs[j]) for j in range(k))
        N = H * math.cos(th[k]) - V * math.sin(th[k])
        base = -H * (yc - pts[k][1]) + A
        hi = min(hi, (base + t * N / 2) / H)
        lo = max(lo, (base - t * N / 2) / H)
        if lo > hi:
            return False
    return True


def thrust_range(arch, W, t=None, Hmax=4000.0, step=0.25):
    t = arch.t if t is None else t
    ok = [H for H in frange(step, Hmax, step) if feasible(arch, W, H, t)]
    return (min(ok), max(ok)) if ok else None


def frange(a, b, s):
    x = a
    while x <= b:
        yield x
        x += s


def t_min(arch, W, t_hi=1.5, self_weight_scales=False):
    """thinnest section for which a stable state exists (bisection); loads fixed unless self_weight_scales"""
    lo, hi = 0.005, t_hi
    for _ in range(18):
        mid = (lo + hi) / 2
        if self_weight_scales:
            W2 = arch.weights('self', t_scale_selfweight=mid * G_B)
            arch.t = mid
        else:
            W2 = W
        r = thrust_range(arch, W2, t=mid, Hmax=2500.0, step=0.5 if not self_weight_scales else 0.25)
        if r:
            hi = mid
        else:
            lo = mid
    return hi


# ---------------------------------------------------------------- self-test: semicircular arch, self weight only
# classical Couplet-Heyman result: t_min / R = 0.1075 for a semicircle with uniform thickness
def self_test():
    R = 2.0
    ar = Arch('semicircle', R, R, 0.2, 0.0, 0.0, n=120)
    # radial thickness t, weight of a voussoir ring segment ~ gamma*t*ds*(1+t/(2R)); gamma = 1 (arbitrary units)
    def run(t):
        W = [t * ds * (1 + t / (2 * R)) for ds, *_ in ar.segs]
        # centreline here is the arch axis; weight acts at the axis -> use mid-depth radius for the weight
        return thrust_range(ar, W, t=t, Hmax=40.0, step=0.01)
    lo, hi = 0.005, 1.0
    for _ in range(20):
        mid = (lo + hi) / 2
        if run(mid):
            hi = mid
        else:
            lo = mid
    print(f"self-test: semicircle t_min/R = {hi / R:.4f}  (classical value 0.1075; this vertical-slice approximation is expected within a few %)")
    return hi / R


# ---------------------------------------------------------------- the real arches
def build_arches():
    A_trans = W_TRANS * (D_VIS_BIG + D_HID)
    A_wall = W_WALL * (D_VIS_WALL + D_HID)
    # round-nosed diagonal: half ellipse below + hidden rectangle
    A_diag = math.pi / 2 * (W_DIAG / 2) * D_VIS_DIAG + W_DIAG * D_HID
    bay_plan = S * S
    # tributary plan widths: share of the bay plan area divided by the rib length
    b_diag = ASSUME['share_diag'] * bay_plan / 2 / (2 * A_D)               # per diagonal
    b_side = ASSUME['share_side'] * bay_plan / 4 * 2 / S                    # side arch serves two bays
    t_diag = D_VIS_DIAG + D_HID
    arches = {
        'diagonal rib': Arch('diagonal rib', A_D, R_DIAG, t_diag, A_diag, b_diag, shape='tri'),
        'transverse arch': Arch('transverse arch', S / 2, R_SIDE, D_VIS_BIG + D_HID, A_trans, b_side, shape='parab'),
        'wall arch': Arch('wall arch', S / 2, R_SIDE, D_VIS_WALL + D_HID, A_wall, b_side / 2, shape='parab'),
    }
    return arches


def analyse(case, verbose=True, haunch=None):
    arches = build_arches()
    res = {}
    for name, ar in arches.items():
        W = ar.weights(case, haunch=haunch)
        V_spring = sum(W)                      # vertical reaction at one springing (half of the arch load x1)
        rng = thrust_range(ar, W)
        tm = t_min(ar, W)
        res[name] = dict(V=V_spring, rng=rng, tmin=tm, t=ar.t, arch=ar, W=W)
        if verbose and name == 'wall arch':
            print(f"  {name:16s} (sits in the wall mass, not a free arch)  V={V_spring:6.0f} kN/end")
        elif verbose:
            if rng:
                print(f"  {name:16s} t={ar.t*100:4.0f} cm  V={V_spring:6.0f} kN/end  H {rng[0]:6.1f}..{rng[1]:6.1f} kN  "
                      f"t_min={tm*100:5.1f} cm  GFS={ar.t/tm:4.2f}")
            else:
                print(f"  {name:16s} t={ar.t*100:4.0f} cm  V={V_spring:6.0f} kN/end  NO stable thrust line in the section  "
                      f"(needs t >= {tm*100:.0f} cm)")
    return res


# ---------------------------------------------------------------- supports
def supports(res, case):
    Vd, Vs, Vw = res['diagonal rib']['V'], res['transverse arch']['V'], res['wall arch']['V']
    rd, rs = res['diagonal rib']['rng'], res['transverse arch']['rng']
    out = {}
    # interior column
    shaft = math.pi * 0.31 ** 2 * 2.2 * ASSUME['gamma_stone']
    cap = 1.1 * 1.1 * 0.17 * ASSUME['gamma_stone'] + math.pi * 0.45 ** 2 * 0.2 * ASSUME['gamma_stone']
    spr = 0.8 * 0.8 * 0.55 * G_B
    N = 4 * Vd + 4 * Vs + shaft + cap + spr
    A_sh = math.pi * 0.30 ** 2
    out['column_N'] = N
    out['column_sigma'] = N / A_sh / 1000
    # wall corbel at an interior cusp
    Vc = Vs + 2 * Vd + 2 * Vw
    out['corbel_V'] = Vc
    bearing = CORBEL[0] * CORBEL[1]
    out['corbel_bearing'] = Vc / bearing / 1000
    arm = CORBEL[0] / 2
    Z = CORBEL[1] * CORBEL[2] ** 2 / 6
    out['corbel_bending'] = Vc * arm / Z / 1000
    # outward horizontal force on the wall at the corbel: 2 diagonals at 45deg + the transverse arch
    def Hout(i):
        if not rd or not rs:
            return None
        return math.sqrt(2) * rd[i] + rs[i]
    out['H_min'], out['H_max'] = Hout(0), Hout(1)
    return out


def wall_check(sup, t_w):
    """overturning of the wall strip (width S) below one corbel; thrust at z = HS"""
    Vc = sup['corbel_V']
    h = HS
    W_wall = S * t_w * (h + 0.8) * G_B          # wall to springing plus a share of the lunette masonry
    out = {}
    for label, H in (('H_min', sup['H_min']), ('H_max', sup['H_max'])):
        if H is None:
            out[label] = None
            continue
        N = Vc + W_wall
        # moment about the wall mid-plane at the base: thrust pushes out, the corbel load sits 0.17 m inside the face
        M = H * h - Vc * (t_w / 2 - CORBEL[0] / 2)
        e = M / N
        F = (Vc * (t_w - CORBEL[0] / 2) + W_wall * t_w / 2) / (H * h)
        out[label] = dict(H=H, e=e, e_over_t=e / t_w, F=F, sigma=N / (S * t_w) / 1000 * (1 + 6 * max(abs(e), 0) / t_w if abs(e) <= t_w / 6 else 2 * N / (3 * S * (t_w / 2 - abs(e))) / (N / (S * t_w)) if abs(e) < t_w / 2 else 99))
    return out


def wall_min_thickness(sup, F_min=2.0, F_max=1.3):
    """thinnest wall strip that keeps the overturning factor >= F_min under H_min and >= F_max under H_max"""
    best = None
    t = 0.4
    while t < 3.0:
        wc = wall_check(sup, t)
        if wc['H_min'] and wc['H_max'] and wc['H_min']['F'] >= F_min and wc['H_max']['F'] >= F_max:
            best = t
            break
        t += 0.05
    return best


def report(case, title, haunch=None, show_wall=True):
    print(f"\n=== {title} ===")
    res = analyse(case, haunch=haunch)
    free = [res['diagonal rib'], res['transverse arch']]
    ok = all(r['rng'] for r in free)
    sup = supports(res, case) if ok else None
    if not ok:
        print("  -> the free arches are not stable in these sections: supports not evaluated")
        return res, None
    print(f"  interior column: N = {sup['column_N']:.0f} kN -> {sup['column_sigma']:.2f} MPa on the shaft")
    print(f"  wall corbel: V = {sup['corbel_V']:.0f} kN, bearing {sup['corbel_bearing']:.2f} MPa, bending tension at the wall face {sup['corbel_bending']:.2f} MPa")
    print(f"  outward force on the wall per corbel: {sup['H_min']:.0f} kN (minimum equilibrium) .. {sup['H_max']:.0f} kN (maximum)")
    if show_wall:
        wc = wall_check(sup, WALL_T)
        for k, v in wc.items():
            if v:
                tag = 'inside middle third' if abs(v['e_over_t']) <= 1 / 6 else ('inside section, tension at the base' if abs(v['e_over_t']) < 0.5 else 'OVERTURNS')
                print(f"  wall t={WALL_T:.2f} m under {k}: e/t = {v['e_over_t']:+.2f} ({tag}), overturning factor F = {v['F']:.2f}")
        tm = wall_min_thickness(sup)
        print(f"  thinnest wall strip with F>=2.0 (H_min) and F>=1.3 (H_max): {tm:.2f} m" if tm else "  no wall thickness up to 3 m satisfies the factors (needs ties or buttresses)")
    return res, sup


def gfs(res):
    return {k: (r['t'] / r['tmin']) for k, r in res.items() if k != 'wall arch'}


def openings_check():
    """right-wall doorways against the corbels where the ribs spring, and the masonry left over their heads"""
    print("\n=== right-wall doorways vs springing points ===")
    half = CORBEL[1] / 2
    corbels = [j * S for j in range(NY + 1)]

    def wall_top(y):                     # top of the wall under the lunette arch of the bay containing y
        yc = (min(int(y // S), NY - 1) + 0.5) * S
        return HS + prof(y - yc, S / 2, R_SIDE)

    for c in DOOR_CENTRES:
        lo, hi = c - DOOR_W / 2, c + DOOR_W / 2
        clear = min(max(cy - half - hi, lo - (cy + half)) for cy in corbels)       # < 0 means overlap
        over = min(wall_top(lo + (hi - lo) * i / 50) for i in range(51)) - DOOR_TOP
        tag = 'ok' if clear > 0 and over > 0.5 else 'CHECK'
        print(f"  doorway y={c:.2f} m: {clear:.2f} m clear of the nearest corbel, >= {over:.2f} m of masonry over the head  [{tag}]")


def sensitivity(case, haunch):
    old = (ASSUME['share_diag'], ASSUME['share_side'])
    print("  sensitivity to how the web load is split between diagonals and side arches:")
    for sd in (0.5, 0.6, 0.7):
        ASSUME['share_diag'], ASSUME['share_side'] = sd, 1 - sd
        r = analyse(case, verbose=False, haunch=haunch)
        g = gfs(r)
        print(f"    diagonals {sd*100:.0f}% / side arches {100-sd*100:.0f}%: GFS diagonal {g['diagonal rib']:.2f}, transverse {g['transverse arch']:.2f}")
    ASSUME['share_diag'], ASSUME['share_side'] = old


if __name__ == '__main__':
    self_test()
    print(f"\nDESIGN VALUES: transverse arch depth {(D_VIS_BIG + D_HID)*100:.0f} cm, diagonal rib {(D_VIS_DIAG + D_HID)*100:.0f} cm, "
          f"wall {WALL_T:.2f} m, corbel {CORBEL[0]:.2f} x {CORBEL[1]:.2f} x {CORBEL[2]:.2f} m, haunch backing to {HAUNCH_BACKING:.1f} m")
    openings_check()
    report('vault', 'CASE A1: vault only, haunches backed with masonry up to %.1f m' % HAUNCH_BACKING, haunch=HAUNCH_BACKING)
    sensitivity('vault', HAUNCH_BACKING)
    report('floor', 'CASE B: vault carries the dormitory floor on fill (fill to %.1f m, floor %.0f+%.0f kN/m2)'
           % (ASSUME['fill_top'], ASSUME['floor_dead'], ASSUME['floor_live']))
    sensitivity('floor', None)
