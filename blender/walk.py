"""
Walk through foresteria.blend in the Blender GUI with real-time (EEVEE) lighting.

  /Applications/Blender.app/Contents/MacOS/Blender foresteria.blend --python walk.py

What it does (the .blend on disk is not touched):
  1. Builds an extra scene "walk" that shares every object of the Cycles scene but has its own world and
     its own EEVEE / colour-management settings, so render.py and render_hero.py (which render the
     original scene) are unaffected.
  2. Switches the window to that scene, maximises the 3D viewport, sets it to Rendered shading, overlays
     off, a wide lens, and puts the eye at the open right-wall doorway (x = W, y = 20.1 m, 1.6 m up),
     looking down the hall.
  3. Switches gravity on in the walk preferences and starts Walk Navigation (view3d.walk) about two
     seconds after the window comes up. The preference is put back as soon as the walk has started.

While walking: WASD move, mouse look, Shift fast, Tab gravity on/off, Enter or left click to stay where you
are, Esc to cancel and return to where you started.

If you save from this session the "walk" scene and its world are removed from the saved copy and put back
afterwards, so the saved file still renders with render.py / render_hero.py as before.

Env: WALK_NO_START=1     set everything up, do not start walking (View > Navigation > Walk Navigation)
     WALK_NO_MAXIMIZE=1  keep the normal window layout
     WALK_FAST=1         raytracing off: smoother and faster on a weak GPU, flatter lighting (no
                         screen-space bounce light / ambient occlusion)
"""
import bpy
import math
import os
from mathutils import Vector

SRC_SCENE = None          # name of the Cycles scene; None = the scene the file opens with
WALK_SCENE = 'walk'
WALK_WORLD = 'walk_world'
EYE = 1.60                # standing eye height, m
DOOR_Y = 20.1             # the open doorway (the other one, y = 18.5, has the door leaf)
START_INSIDE = -0.15      # eye x = W + this: 0.15 m inside the room face of the right wall, in line with the doorway
START_YAW = 28.0          # deg from -X toward -Y (the near end: the long view down the hall)
START_PITCH = 4.0         # deg up
VIEW_LENS = 24.0          # mm, viewport focal length (about 74 degrees horizontal)

# Real-time look, tuned against renders/hero_F_final.jpg (see README). All overridable for experiments.
TUNE = dict(
    exposure=2.2,         # matches the Cycles hero render's mean brightness (headless check, within 2%)
    fill_color=(1.0, 0.84, 0.66),   # warm ambient standing in for the bounce light Cycles gets
    fill_strength=0.08,
    raytracing=True,
    rt_resolution_scale='2',        # raytracing resolution: '1' full, '2' half, '4' quarter
    trace_quality=0.25,
    fast_gi_method='GLOBAL_ILLUMINATION',
    fast_gi_ray_count=2,
    fast_gi_step_count=8,
    fast_gi_distance=0.0,
    fast_gi_quality=0.25,
    fast_gi_resolution='2',
    viewport_samples=64,            # progressive samples the viewport accumulates while you stand still
    sun_energy=None,                # None = keep the lamp's strength
)


# ---------------------------------------------------------------------------------------------- scene
def hall_size():
    fl = bpy.data.objects.get('floor')
    if fl is None:
        return 10.8, 27.0
    xs = [v.co.x for v in fl.data.vertices]
    ys = [v.co.y for v in fl.data.vertices]
    return max(xs) - 0.1, max(ys) - 0.1      # the floor plane overhangs the room by 0.1 m


def source_scene():
    if SRC_SCENE:
        return bpy.data.scenes[SRC_SCENE]
    return next(s for s in bpy.data.scenes if s.name != WALK_SCENE)


def _link_tree(dst_coll, src_coll):
    for ob in src_coll.objects:
        if ob.name not in dst_coll.objects:
            dst_coll.objects.link(ob)
    for ch in src_coll.children:
        if ch.name not in dst_coll.children:
            dst_coll.children.link(ch)


def make_walk_world(src_world, tune):
    """A copy of the Cycles world where camera rays still see the sky (windows stay bright) but every other
    ray (= light) sees a dim warm fill instead of the sky. In Cycles the sky barely gets in (about 0.3 % of
    the floor's hemisphere sees it); EEVEE ignores that occlusion, so the sky is switched off as a light."""
    old = bpy.data.worlds.get(WALK_WORLD)
    if old is not None:
        bpy.data.worlds.remove(old)
    wd = src_world.copy()
    wd.name = WALK_WORLD
    nt = wd.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
    sky_bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    lp = nt.nodes.new('ShaderNodeLightPath')
    fill = nt.nodes.new('ShaderNodeBackground')
    fill.inputs['Color'].default_value = (*tune['fill_color'], 1.0)
    fill.inputs['Strength'].default_value = tune['fill_strength']
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(fill.outputs['Background'], mix.inputs[1])
    nt.links.new(sky_bg.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return wd


def configure_eevee(sc, tune):
    sc.render.engine = 'BLENDER_EEVEE'
    e = sc.eevee
    e.use_raytracing = tune['raytracing']
    e.ray_tracing_method = 'SCREEN'
    ro = e.ray_tracing_options
    ro.resolution_scale = tune['rt_resolution_scale']
    ro.use_denoise = True
    ro.screen_trace_quality = tune['trace_quality']
    e.use_fast_gi = True
    e.fast_gi_method = tune['fast_gi_method']
    e.fast_gi_ray_count = tune['fast_gi_ray_count']
    e.fast_gi_step_count = tune['fast_gi_step_count']
    e.fast_gi_distance = tune['fast_gi_distance']
    e.fast_gi_quality = tune['fast_gi_quality']
    e.fast_gi_resolution = tune['fast_gi_resolution']
    e.use_shadows = True
    e.taa_samples = tune['viewport_samples']
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = tune['exposure']


def make_walk_scene(tune=None):
    tune = {**TUNE, **(tune or {})}
    if os.environ.get('WALK_FAST'):
        tune['raytracing'] = False
    src = source_scene()
    sc = bpy.data.scenes.get(WALK_SCENE) or bpy.data.scenes.new(WALK_SCENE)
    _link_tree(sc.collection, src.collection)
    sc.world = make_walk_world(src.world, tune)
    sc.unit_settings.system = src.unit_settings.system
    configure_eevee(sc, tune)
    if tune['sun_energy'] is not None:
        bpy.data.lights['sun'].energy = tune['sun_energy']
    return sc


# ------------------------------------------------------------------------------------------- viewport
def start_view():
    """(eye position, view rotation quaternion) at the open doorway, looking into the hall."""
    W, _ = hall_size()
    eye = Vector((W + START_INSIDE, DOOR_Y, EYE))
    a, p = math.radians(START_YAW), math.radians(START_PITCH)
    look = Vector((-math.cos(a) * math.cos(p), -math.sin(a) * math.cos(p), math.sin(p)))
    return eye, look.to_track_quat('-Z', 'Y')


def find_view3d(window):
    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region is not None:
                return area, region
    return None, None


def maximize(window, area, region):
    if os.environ.get('WALK_NO_MAXIMIZE') or window.screen.show_fullscreen:
        return
    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.screen.screen_full_area()
    except Exception as exc:
        print('walk.py: could not maximise the viewport (%s)' % exc)


def setup_viewport(window):
    area, region = find_view3d(window)
    if area is None:
        print('walk.py: no 3D viewport found in the window')
        return None, None
    maximize(window, area, region)
    area, region = find_view3d(window)        # the maximised area lives in a temporary screen
    space = area.spaces.active
    space.shading.type = 'RENDERED'
    space.clip_start = 0.05
    space.clip_end = 400.0
    space.lens = VIEW_LENS
    space.overlay.show_overlays = False
    space.show_gizmo = False
    rv3d = space.region_3d
    eye, rot = start_view()
    rv3d.view_perspective = 'PERSP'
    rv3d.view_rotation = rot
    rv3d.view_distance = 0.0                  # eye == view_location
    rv3d.view_location = eye
    return area, region


def start_walk(window, area, region):
    """Gravity is read from the preferences when the walk starts; set it, start, put the preference back."""
    nav = bpy.context.preferences.inputs.walk_navigation
    saved = (nav.use_gravity, nav.view_height)
    nav.use_gravity, nav.view_height = True, EYE
    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.view3d.walk('INVOKE_DEFAULT')
        print('walk.py: view3d.walk started')
    except Exception as exc:
        print('walk.py: could not start walk navigation (%s). Use View > Navigation > Walk Navigation (Shift+`).' % exc)
    finally:
        nav.use_gravity, nav.view_height = saved


# ----------------------------------------------------------------------------- keep saves clean
def _set_windows_scene(sc):
    for win in bpy.context.window_manager.windows:
        win.scene = sc


def _before_save(*_):
    try:
        walk = bpy.data.scenes.get(WALK_SCENE)
        if walk is None:
            return
        _set_windows_scene(source_scene())
        bpy.data.scenes.remove(walk)
        wd = bpy.data.worlds.get(WALK_WORLD)
        if wd is not None:
            bpy.data.worlds.remove(wd)
        print('walk.py: walk scene left out of the saved file')
    except Exception as exc:
        print('walk.py: save clean-up failed (%s)' % exc)


def _after_save(*_):
    try:
        sc = make_walk_scene()
        _set_windows_scene(sc)
    except Exception as exc:
        print('walk.py: could not rebuild the walk scene after saving (%s)' % exc)


def _install_save_handlers():
    for lst, fn in ((bpy.app.handlers.save_pre, _before_save), (bpy.app.handlers.save_post, _after_save)):
        lst[:] = [f for f in lst if getattr(f, '__name__', '') != fn.__name__]
        lst.append(fn)


# ------------------------------------------------------------------------------------------ launcher
def launch():
    wm = bpy.context.window_manager
    window = wm.windows[0] if wm.windows else None
    if window is None:
        print('walk.py: no window (running with -b?); nothing to do')
        return None
    sc = make_walk_scene()
    window.scene = sc
    _install_save_handlers()
    area, region = setup_viewport(window)
    if area is not None and not os.environ.get('WALK_NO_START'):
        def _go():
            a, r = find_view3d(window)
            if a is not None:
                start_walk(window, a, r)
            return None
        bpy.app.timers.register(_go, first_interval=2.0)
    return None


bpy.app.driver_namespace['foresteria_walk'] = globals()     # lets a test script reach the functions above

if not bpy.app.background:
    bpy.app.timers.register(launch, first_interval=0.5)
