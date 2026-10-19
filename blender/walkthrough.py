"""
Walkthrough video: a visitor enters by the open right-wall doorway, curves round the first column (column 4, on the
right as you come in), then slaloms between the columns toward the near end, stopping at each one to look around
(up at the ribs and keystones, down at a base, across to a window or a corbel), and ends by turning back for the
long view down the hall (the hero-render composition). Standing eye height, slow walking pace, rendered in EEVEE
with the walk-mode look of walk.py.

  Blender -b foresteria.blend --python walkthrough.py -- preview     640x360, 12 fps, quick, to check the moves
  Blender -b foresteria.blend --python walkthrough.py -- final       1920x1080, 24 fps
  Blender -b foresteria.blend --python walkthrough.py -- plan        only the path diagram and timing, no render
  Blender -b foresteria.blend --python walkthrough.py -- final 2480 2530   only those frames, to test a stretch
  Blender -b foresteria.blend --python walkthrough.py -- compare [256]   8 key moments as stills, EEVEE vs Cycles
                                                                         (Cycles samples), into ../tmp/high_compare/

Frames go to video/<preset>/####.png and are skipped if they already exist, so an interrupted render resumes: run the
same command again (a frame cut off mid-render is redone). While the Mac sleeps nothing renders; Blender just pauses.
When all frames exist the script encodes video/walkthrough_<preset>.mp4 with ffmpeg (if it is on the PATH).
The path diagram is written to video/path_plan.svg.
"""
import bpy, importlib.util, math, os, shutil, subprocess, sys
from mathutils import Vector, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PRESET = argv[0] if argv else 'plan'

PRESETS = {
    'preview': dict(res=(640, 360), samples=16, step=2),
    'final': dict(res=(1920, 1080), samples=40, step=1),     # ~2.4 s/frame on this Mac: about 1.8 h; 64 differs by <1 level
}
FPS = 24
EYE = 1.60            # eye height, m
LENS = 24.0           # mm on a 36 mm sensor: about 74 degrees horizontal
CRUISE = 0.62         # walking speed, m/s: a slow, looking-around pace
ACCEL_T = 2.0         # seconds to reach it from a stop (and to stop)
BOB = 0.006           # head bob amplitude while walking, m
GAZE_W = 2.0          # gaze follows its target like a critically damped spring (rad/s): settles in about 2 s
MAX_YAW_RATE = 24.0   # deg/s: the view never turns faster than a slow head turn, so there is never a cut
MAX_PITCH_RATE = 16.0
BOB_HZ = 1.8          # steps per second

spec = importlib.util.spec_from_file_location('walkmod', os.path.join(HERE, 'walk.py'))
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)
HALL_W, HALL_L = W.hall_size()
S = 5.4
COLS = [(S, S * k) for k in (1, 2, 3, 4)]                # column axes: 1 near end ... 4 far end
CAP = lambda k: (S, S * k, 2.35)                        # top of column k's capital


# ---------------------------------------------------------------- route (plan, metres)
# waypoints the eye passes through; 'stop' marks where the visitor halts and looks around
ROUTE = [
    ((12.5, 20.1), None),          # just outside the open doorway
    ((10.6, 20.1), None),          # threshold
    ((8.3, 20.4), None),
    ((6.9, 21.15), None),          # reaching column 4 on the right
    ((6.45, 22.75), None),         # round its far side
    ((5.2, 23.15), None),
    ((4.15, 22.7), None),
    ((3.9, 21.6), 'S1'),           # west of column 4
    ((3.95, 20.6), None),          # slalom: cross the centre line to the east of column 3
    ((5.4, 18.9), None),
    ((6.85, 17.2), None),
    ((6.9, 16.2), 'S2'),           # east of column 3
    ((6.85, 15.2), None),
    ((5.4, 13.5), None),
    ((3.95, 11.8), None),
    ((3.9, 10.8), 'S3'),           # west of column 2
    ((3.95, 9.8), None),
    ((5.4, 8.1), None),
    ((6.85, 6.4), None),
    ((6.9, 5.4), 'S4'),            # east of column 1
    ((7.5, 3.7), None),
    ((8.6, 1.1), 'END'),           # near end, right nave: turn back for the long view (the hero composition)
]


def catmull_rom(pts, per_seg=60):
    """centripetal Catmull-Rom through every point; returns dense samples and the sample index of each point"""
    P = [Vector((x, y)) for (x, y) in pts]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    out, idx = [], []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0.0
        t1 = t0 + max((p1 - p0).length, 1e-6) ** 0.5
        t2 = t1 + max((p2 - p1).length, 1e-6) ** 0.5
        t3 = t2 + max((p3 - p2).length, 1e-6) ** 0.5
        idx.append(len(out))
        for k in range(per_seg):
            t = t1 + (t2 - t1) * k / per_seg
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            out.append(b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1)))
    idx.append(len(out))
    out.append(P[-2])
    return out, idx


SAMPLES, IDX = catmull_rom([p for p, _ in ROUTE])
ARC = [0.0]
for a, b in zip(SAMPLES[:-1], SAMPLES[1:]):
    ARC.append(ARC[-1] + (b - a).length)
S_OF = [ARC[i] for i in IDX]                     # arc length at each route point
L_TOTAL = ARC[-1]


def at_s(s):
    """plan position at arc length s"""
    s = min(max(s, 0.0), L_TOTAL)
    lo, hi = 0, len(ARC) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ARC[mid] <= s:
            lo = mid
        else:
            hi = mid
    f = (s - ARC[lo]) / max(ARC[hi] - ARC[lo], 1e-9)
    return SAMPLES[lo].lerp(SAMPLES[hi], f)


def move_profile(L):
    """duration and s(t) of a walk of length L from rest to rest: cosine-eased start and stop, cruise between"""
    v, ta = CRUISE, ACCEL_T
    if L < v * ta:                               # too short to reach cruise speed
        v = L / ta
    T = L / v + ta

    def s(t):
        t = min(max(t, 0.0), T)
        if t < ta:
            return v / 2 * (t - ta / math.pi * math.sin(math.pi * t / ta))
        if t > T - ta:
            return L - s(T - t)
        return v * ta / 2 + v * (t - ta)
    return T, s


# ---------------------------------------------------------------- timeline
# position: piecewise (hold | move); gaze: keys (time, spec) eased between; spec = ('ahead', pitch_deg) or
# ('point', (x, y, z)) or ('dir', yaw_deg, pitch_deg)
POS = []          # (t0, t1, s0, s1, s_of_t or None)
GAZE = []
MARKS = []         # (name, t): moments for the engine comparison stills (-- compare)
t = 0.0


def hold(T):
    global t
    s_now = POS[-1][3] if POS else 0.0
    POS.append((t, t + T, s_now, s_now, None))
    t += T


def move_to(route_name):
    """walk from the current position to the named stop; returns (t_start, t_end)"""
    global t
    s0 = POS[-1][3] if POS else 0.0
    s1 = S_OF[[n for _, n in ROUTE].index(route_name)]
    T, f = move_profile(s1 - s0)
    POS.append((t, t + T, s0, s1, f))
    t += T
    return t - T, t


def look(dt, spec, hold_after=0.0, mark=None):
    """turn the gaze to spec over dt seconds (from now), then keep it hold_after seconds, advancing time.
    mark names the moment the gaze has settled (end of the hold), for the engine comparison stills."""
    GAZE.append((t + dt, spec))
    hold(dt)                                     # stand still while turning (no gap in the position timeline)
    if hold_after:
        GAZE.append((t + hold_after, spec))
        hold(hold_after)
    if mark:
        MARKS.append((mark, t))


def time_at_s(s_target):
    for (t0, t1, s0, s1, f) in POS:
        if f and s0 <= s_target <= s1:
            lo, hi = t0, t1
            for _ in range(40):
                m = (lo + hi) / 2
                if s0 + f(m - t0) < s_target:
                    lo = m
                else:
                    hi = m
            return lo
    return None


def s_of_name(i):
    return S_OF[i]


AHEAD = ('ahead', 3.0)
LEVEL = ('ahead', 0.0)
GAZE.append((0.0, AHEAD))
hold(2.0)                                                     # standing in the doorway, looking in
MARKS.append(('doorway', 1.5))
ta, tb = move_to('S1')
GAZE.append((time_at_s(S_OF[2]), AHEAD))                      # straight in, past the threshold
GAZE.append((time_at_s(S_OF[3]), ('point', (S, 21.6, 2.4))))  # column 4 and its capital while rounding it
GAZE.append((tb, ('point', CAP(4))))
# stop 1, beyond column 4: up the capital into the ribs, on to the keystone, then across to a window
look(3.2, ('point', (S, 21.6, 4.8)), 0.8)
look(3.2, ('point', (2.7, 24.3, 6.4)), 1.2, mark='ribs and keystone')
ta, tb = move_to('S2')
GAZE.append((ta + 3.0, LEVEL))
GAZE.append((time_at_s(S_OF[9]), ('point', (4.2, 18.9, 6.0))))   # up at the vault while crossing between columns
MARKS.append(('walking under the vault', time_at_s(S_OF[9]) + 1.0))
GAZE.append((time_at_s(S_OF[10]), AHEAD))
GAZE.append((tb, LEVEL))
# stop 2, beside column 3: across to the right wall's doorways and corbel, then down to the column's base
look(3.2, ('point', (HALL_W, 18.6, 2.0)), 1.0, mark='doorways and corbel')
look(3.2, ('point', (S, 16.2, 0.2)), 0.9)
ta, tb = move_to('S3')
GAZE.append((ta + 3.0, LEVEL))
GAZE.append((time_at_s(S_OF[13]), ('point', (0.0, 13.5, 2.4))))  # a left-wall window, walking past
GAZE.append((time_at_s(S_OF[14]), ('point', (S, 10.8, 2.3))))    # column 2's capital
GAZE.append((tb, LEVEL))
# stop 3, beside column 2: the next window with its steps, up to the wall corbel, down to the brick floor
look(3.2, ('point', (0.0, 8.1, 2.3)), 1.0, mark='window and corbel')
look(3.2, ('point', (2.6, 8.8, 0.0)), 1.0, mark='brick floor')
ta, tb = move_to('S4')
GAZE.append((ta + 3.0, LEVEL))
GAZE.append((time_at_s(S_OF[17]), ('point', CAP(1))))            # column 1's capital, coming toward it
GAZE.append((tb, ('ahead', 4.0)))
# stop 4, beside column 1: up to the near bay's keystone, then down to the broken base
look(3.2, ('point', (8.1, 2.7, 6.4)), 1.0)
look(3.5, ('point', (S, 5.4, 0.15)), 0.9, mark='column 1 base')
ta, tb = move_to('END')
T_END_MOVE = ta
GAZE.append((ta + 3.0, ('point', (0.0, 2.7, 2.3))))        # across the hall to the near-left window while walking
GAZE.append((tb, ('dir', 180.0, 5.0)))                     # (not at the near end wall, which is only 1 m away)
# end: turn slowly back past the left-wall windows to the long view down the hall, and stay there
look(2.0, ('dir', 180.0, 5.0))
look(4.0, ('dir', 119.0, 8.0), 3.5, mark='long view')
T_TOTAL = t


def pos_at(tt):
    """eye position (with a little head bob while walking) and walking speed at time tt"""
    for (t0, t1, s0, s1, f) in POS:
        if t0 <= tt <= t1 and t1 > t0:
            if f is None:
                p = at_s(s0)
                return Vector((p.x, p.y, EYE)), 0.0
            s = s0 + f(tt - t0)
            ds = (f(min(tt - t0 + 0.02, t1 - t0)) - f(max(tt - t0 - 0.02, 0.0))) / 0.04
            p = at_s(s)
            bob = BOB * math.sin(2 * math.pi * BOB_HZ * tt) * min(ds / CRUISE, 1.0)
            return Vector((p.x, p.y, EYE + bob)), ds
    p = at_s(POS[-1][3])
    return Vector((p.x, p.y, EYE)), 0.0


def s_at(tt):
    for (t0, t1, s0, s1, f) in POS:
        if t0 <= tt <= t1 and t1 > t0:
            return s0 if f is None else s0 + f(tt - t0)
    return POS[-1][3]


def resolve(spec_, tt, eye):
    kind = spec_[0]
    if kind == 'ahead':
        s = s_at(tt)
        a, b = at_s(s), at_s(s + 3.5)
        if (b - a).length < 0.3:                  # at the end of the path: keep the last walking direction
            a = at_s(s - 3.5)
            b = at_s(s)
        yaw = math.atan2(b.y - a.y, b.x - a.x)
        return yaw, math.radians(spec_[1])
    if kind == 'point':
        d = Vector(spec_[1]) - eye
        return math.atan2(d.y, d.x), math.atan2(d.z, Vector((d.x, d.y)).length)
    return math.radians(spec_[1]), math.radians(spec_[2])


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


GAZE.sort(key=lambda k: k[0])


def gaze_at(tt, eye):
    if tt <= GAZE[0][0]:
        return resolve(GAZE[0][1], tt, eye)
    for (ta_, sa), (tb_, sb) in zip(GAZE[:-1], GAZE[1:]):
        if ta_ <= tt <= tb_:
            ya, pa = resolve(sa, tt, eye)
            yb, pb = resolve(sb, tt, eye)
            w = smooth((tt - ta_) / max(tb_ - ta_, 1e-6))
            dy = (yb - ya + math.pi) % (2 * math.pi) - math.pi
            return ya + dy * w, pa + (pb - pa) * w
    return resolve(GAZE[-1][1], tt, eye)


def gaze_track(n_frames, fps=FPS):
    """per-frame (yaw, pitch): the eased key targets followed by a critically damped spring with a speed limit, so
    the view always drifts like a turning head; returns the track and its peak angular speeds (deg/s)"""
    dt = 1.0 / fps
    eye0, _ = pos_at(0.0)
    y, p = gaze_at(0.0, eye0)
    vy = vp = 0.0
    out, peak = [], [0.0, 0.0]
    for f in range(n_frames):
        tt = f * dt
        eye, _ = pos_at(tt)
        ty, tp = gaze_at(tt, eye)
        ey = (ty - y + math.pi) % (2 * math.pi) - math.pi
        vy += (GAZE_W ** 2 * ey - 2 * GAZE_W * vy) * dt
        vp += (GAZE_W ** 2 * (tp - p) - 2 * GAZE_W * vp) * dt
        my, mp = math.radians(MAX_YAW_RATE), math.radians(MAX_PITCH_RATE)
        vy, vp = max(-my, min(my, vy)), max(-mp, min(mp, vp))
        y += vy * dt
        p += vp * dt
        peak = [max(peak[0], abs(math.degrees(vy))), max(peak[1], abs(math.degrees(vp)))]
        out.append((y, p))
    return out, peak


def camera_quat(yaw, pitch):
    d = Vector((math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)))
    return d.to_track_quat('-Z', 'Y')


# ---------------------------------------------------------------- checks and plan
def clearances():
    mins = {'column axis': 9.0, 'side walls': 9.0, 'end walls': 9.0}
    for k in range(0, len(SAMPLES), 3):
        p = SAMPLES[k]
        for (cx, cy) in COLS:
            mins['column axis'] = min(mins['column axis'], math.hypot(p.x - cx, p.y - cy))
        in_doorway = p.x > HALL_W - 1.2 and abs(p.y - 20.1) < 0.6
        if p.x < HALL_W - 0.05 and not in_doorway:  # inside the hall (the doorway passage is meant to be narrow)
            mins['side walls'] = min(mins['side walls'], p.x, HALL_W - p.x)
            mins['end walls'] = min(mins['end walls'], p.y, HALL_L - p.y)
    return mins


def write_plan(path):
    k, mx, my = 30.0, 210.0, 40.0                     # px per metre, side and top margins
    tx = lambda x: mx + x * k                         # plan seen from above: near end at the bottom, left wall on the left
    ty = lambda y: my + (HALL_L - y) * k
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{(HALL_W + 2.5) * k + 2 * mx:.0f}" height="{HALL_L * k + 2 * my:.0f}" '
           f'font-family="sans-serif" font-size="12">',
           '<rect width="100%" height="100%" fill="#faf7f0"/>',
           f'<rect x="{tx(0):.1f}" y="{ty(HALL_L):.1f}" width="{HALL_W * k:.1f}" height="{HALL_L * k:.1f}" '
           f'fill="#efe6d4" stroke="#6b5a40" stroke-width="3"/>']
    for c in (18.5, 20.1):
        svg.append(f'<line x1="{tx(HALL_W):.1f}" y1="{ty(c - 0.55):.1f}" x2="{tx(HALL_W):.1f}" y2="{ty(c + 0.55):.1f}" '
                   f'stroke="#efe6d4" stroke-width="5"/>')
    for j in range(5):
        c = j * S + S / 2
        svg.append(f'<line x1="{tx(0):.1f}" y1="{ty(c - 0.3):.1f}" x2="{tx(0):.1f}" y2="{ty(c + 0.3):.1f}" stroke="#9ec6e8" stroke-width="6"/>')
    for i, (cx, cy) in enumerate(COLS):
        svg.append(f'<circle cx="{tx(cx):.1f}" cy="{ty(cy):.1f}" r="{0.47 * k:.1f}" fill="#b9b3a0" stroke="#555"/>')
        svg.append(f'<text x="{tx(cx) - 4:.1f}" y="{ty(cy) + 4:.1f}">{i + 1}</text>')
    pts = ' '.join(f'{tx(p.x):.1f},{ty(p.y):.1f}' for p in SAMPLES[::4])
    svg.append(f'<polyline points="{pts}" fill="none" stroke="#c0392b" stroke-width="2.5"/>')
    notes = {'S1': 'stop 1: capital, ribs, keystone', 'S2': 'stop 2: right wall, base 3',
             'S3': 'stop 3: window, corbel', 'S4': 'stop 4: keystone, base 1', 'END': 'end: turn back, long view'}
    for (p, n), s in zip(ROUTE, S_OF):
        if n:
            svg.append(f'<circle cx="{tx(p[0]):.1f}" cy="{ty(p[1]):.1f}" r="6" fill="#c0392b"/>')
            west = p[0] < S                               # label outside the hall, on the stop's side
            xt = tx(-0.4) if west else tx(HALL_W + 0.4)
            svg.append(f'<line x1="{tx(p[0]):.1f}" y1="{ty(p[1]):.1f}" x2="{xt:.1f}" y2="{ty(p[1]):.1f}" stroke="#c0392b" '
                       f'stroke-dasharray="3 3"/>')
            svg.append(f'<text x="{xt + (-6 if west else 6):.1f}" y="{ty(p[1]) + 4:.1f}" '
                       f'text-anchor="{"end" if west else "start"}">{notes[n]}</text>')
    svg.append(f'<text x="{tx(12.5):.1f}" y="{ty(20.1) - 10:.1f}" text-anchor="middle">start (doorway)</text>')
    svg.append(f'<text x="{tx(HALL_W / 2):.1f}" y="{my - 12:.1f}" text-anchor="middle">far end (y = 27 m)</text>')
    svg.append(f'<text x="{tx(HALL_W / 2):.1f}" y="{ty(0) + 22:.1f}" text-anchor="middle">near end</text>')
    svg.append(f'<text x="{tx(0) + 8:.1f}" y="{ty(HALL_L / 2 + 1.5):.1f}" fill="#6b5a40">left wall (windows)</text>')
    svg.append(f'<text x="{tx(HALL_W) - 8:.1f}" y="{ty(HALL_L / 2 + 1.5):.1f}" text-anchor="end" fill="#6b5a40">right wall</text>')
    svg.append('</svg>')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w').write('\n'.join(svg))


# ---------------------------------------------------------------- main
print(f'WALKTHROUGH path {L_TOTAL:.1f} m, duration {T_TOTAL:.1f} s, {int(round(T_TOTAL * FPS))} frames at {FPS} fps')
TRACK, PEAK = gaze_track(int(round(T_TOTAL * FPS)))
print(f'WALKTHROUGH last walk starts at {T_END_MOVE:.1f} s (frame {int(T_END_MOVE * FPS) + 1})')
_n = int(round(T_TOTAL * FPS))
_steps = [(pos_at((f + 1) / FPS)[0] - pos_at(f / FPS)[0]).length * FPS for f in range(_n - 1)]
print(f'WALKTHROUGH peak eye speed: {max(_steps):.2f} m/s (must stay near the walking speed, {CRUISE} m/s)')
gaps = [(a[1], b[0]) for a, b in zip(POS[:-1], POS[1:]) if abs(b[0] - a[1]) > 1e-6]
print(f'WALKTHROUGH gaps in the position timeline: {len(gaps)}')
print(f'WALKTHROUGH peak turning speed: yaw {PEAK[0]:.1f} deg/s, pitch {PEAK[1]:.1f} deg/s')
print('WALKTHROUGH clearances (min, m): ' + ', '.join(f'{k} {v:.2f}' for k, v in clearances().items()))
write_plan(os.path.join(HERE, 'video', 'path_plan.svg'))

def slug(name):
    return name.replace(' ', '_')


def render_compare(sc, cam):
    """the MARKS moments as stills, EEVEE (as in the video) and Cycles (as the hero render), into ../tmp/high_compare/"""
    import time
    out = os.path.normpath(os.path.join(HERE, '..', 'tmp', 'high_compare'))
    os.makedirs(out, exist_ok=True)
    samples = int(argv[1]) if len(argv) > 1 else 256
    shots = [(k + 1, name, int(round(tt * FPS)) + 1) for k, (name, tt) in enumerate(sorted(MARKS, key=lambda m: m[1]))]
    src = W.source_scene()
    src.collection.objects.link(cam)
    src.camera = cam
    cy = src.cycles
    src.render.engine = 'CYCLES'
    cy.samples, cy.use_denoising, cy.use_adaptive_sampling = samples, True, True
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces = 8, 6, 3, 2
    cy.sample_clamp_indirect, cy.sample_clamp_direct = 8.0, 0.0
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    cy.device = 'GPU'
    src.view_settings.view_transform, src.view_settings.look, src.view_settings.exposure = 'AgX', 'None', 2.6
    log = []
    engines = [e for e in (('eevee', sc), ('cycles', src)) if os.environ.get('COMPARE_ONLY', e[0]) == e[0]]
    for engine, s_ in engines:
        s_.render.resolution_x, s_.render.resolution_y, s_.render.resolution_percentage = 1920, 1080, 100
        s_.render.use_motion_blur, s_.render.motion_blur_shutter = True, 0.5
        s_.render.image_settings.file_format = 'PNG'
        s_.render.use_overwrite, s_.render.use_placeholder = True, False
        for (k, name, f) in shots:
            # a one-frame animation render: frame_set on a scene that is not the active one does not move the camera
            s_.frame_start = s_.frame_end = f
            s_.render.filepath = os.path.join(out, f'{k}_{slug(name)}_{engine}_')
            t0 = time.time()
            bpy.ops.render.render(animation=True, scene=s_.name)
            os.replace(os.path.join(out, f'{k}_{slug(name)}_{engine}_{f:04d}.png'),
                       os.path.join(out, f'{k}_{slug(name)}_{engine}.png'))
            log.append(f'{k} {name:24s} frame {f:5d} ({(f - 1) / FPS:6.1f} s)  {engine:6s} {time.time() - t0:6.1f} s')
            print('COMPARE', log[-1])
    with open(os.path.join(out, 'timings.txt'), 'a') as fh:
        fh.write(f'EEVEE: {sc.eevee.taa_render_samples} samples, walk.py look (exposure {sc.view_settings.exposure}).\n'
                 f'Cycles: {samples} samples, adaptive, denoised, render.py light paths (exposure 2.6).\n'
                 f'Both 1920x1080 with motion blur (shutter 0.5).\n\n' + '\n'.join(log) + '\n')


if PRESET in PRESETS or PRESET == 'compare':
    P = PRESETS.get(PRESET, PRESETS['final'])
    sc = W.make_walk_scene()
    cd = bpy.data.cameras.new('walkthrough')
    cd.lens, cd.sensor_width, cd.clip_start, cd.clip_end = LENS, 36.0, 0.05, 400.0
    cam = bpy.data.objects.new('walkthrough', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.rotation_mode = 'QUATERNION'
    n_frames = int(round(T_TOTAL * FPS))
    q_prev = None
    for f in range(1, n_frames + 1):
        tt = (f - 1) / FPS
        eye, _ = pos_at(tt)
        q = camera_quat(*TRACK[f - 1])
        if q_prev is not None and q.dot(q_prev) < 0:
            q = -q
        q_prev = q
        cam.location = eye
        cam.rotation_quaternion = q
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_quaternion', frame=f)
    ad = cam.animation_data
    fcurves = ad.action.fcurves if hasattr(ad.action, 'fcurves') else [fc for layer in ad.action.layers
                                                                       for strip in layer.strips
                                                                       for bag in strip.channelbags for fc in bag.fcurves]
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    sc.frame_start, sc.frame_end, sc.frame_step = 1, n_frames, P['step']
    if PRESET == 'compare':
        sc.eevee.taa_render_samples = P['samples']
        render_compare(sc, cam)
        sys.exit(0)
    if len(argv) >= 3:                             # test a stretch: -- final 2470 2520 renders into video/final_2470-2520/
        sc.frame_start, sc.frame_end = int(argv[1]), int(argv[2])
        PRESET = f'{PRESET}_{argv[1]}-{argv[2]}'
    sc.render.fps = FPS
    sc.render.resolution_x, sc.render.resolution_y = P['res']
    sc.render.resolution_percentage = 100
    sc.eevee.taa_render_samples = P['samples']
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_overwrite = False                # resume: existing frames are skipped
    sc.render.use_placeholder = True
    out_dir = os.path.join(HERE, 'video', PRESET)
    os.makedirs(out_dir, exist_ok=True)
    for x in os.listdir(out_dir):                 # a frame interrupted by a kill leaves an empty placeholder: redo it
        fp = os.path.join(out_dir, x)
        if x.endswith('.png') and os.path.getsize(fp) == 0:
            os.remove(fp)
            print('WALKTHROUGH removed unfinished frame', x)
    sc.render.filepath = os.path.join(out_dir, '')
    bpy.ops.render.render(animation=True, scene=sc.name)
    frames = sorted(x for x in os.listdir(out_dir) if x.endswith('.png'))
    print(f'WALKTHROUGH rendered: {len(frames)} frames in {out_dir}')
    ffmpeg = shutil.which('ffmpeg') or ('/opt/homebrew/bin/ffmpeg' if os.path.exists('/opt/homebrew/bin/ffmpeg') else None)
    if ffmpeg:
        mp4 = os.path.join(HERE, 'video', f'walkthrough_{PRESET}.mp4')
        lst = os.path.join(out_dir, 'frames.txt')
        with open(lst, 'w') as fh:
            for x in frames:
                fh.write(f"file '{os.path.join(out_dir, x)}'\nduration {P['step'] / FPS:.6f}\n")
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                        '-vf', f"fps={FPS // P['step']}", '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-crf', '18' if PRESET == 'final' else '23', '-preset', 'slow', '-movflags', '+faststart', mp4],
                       check=True)
        print('WALKTHROUGH video', mp4)
