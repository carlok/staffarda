"""
One-off hero shot(s) from inside the hall at standing eye height.

  Blender -b foresteria.blend --python render_hero.py -- <preset> <view> [<view> ...]
  preset: test | final | preview
  view:   a key of VIEWS below
A final render of view F (no TAG) also refreshes ../docs/preview.jpg, the 1600 px picture at the top of the
repo README. `preview` only rebuilds that picture from an existing renders/hero_F_final.png.
Env: EXPOSURE (default 2.6), HAZE (dust density, 0 = off), TAG (file suffix)
"""
import bpy, sys, os, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath))
argv = sys.argv[sys.argv.index('--') + 1:]
preset, views = argv[0], argv[1:]
PREVIEW = os.path.join(os.path.dirname(HERE), 'docs', 'preview.jpg')


def write_preview(src, width=1600):
    """keep the README's picture current: a 1600 px JPEG copy of the final hero render"""
    try:
        os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
        im = bpy.data.images.load(src)
        im.scale(width, round(width * im.size[1] / im.size[0]))
        im.filepath_raw = PREVIEW
        im.file_format = 'JPEG'
        im.save(quality=82)
        bpy.data.images.remove(im)
        print('PREVIEW', PREVIEW)
    except Exception as exc:
        print('render_hero.py: could not write the README preview (%s)' % exc)


if preset == 'preview':
    for v in views or ['F']:
        write_preview(os.path.join(HERE, 'renders', f'hero_{v}_final.png'))
    sys.exit(0)

EYE = 1.60   # average standing eye height, metres

# name: (x, y, yaw deg (+ = toward -X / left), pitch deg, focal length mm)
VIEWS = {
    'A': (8.4, 1.0, 20.0, 9.0, 18.0),
    'B': (2.9, 0.9, -8.0, 9.0, 18.0),
    'C': (8.7, 1.0, 29.0, 8.0, 20.0),
    'D': (4.0, 1.0, -3.0, 9.0, 18.0),
    'E': (8.6, 0.8, 24.0, 9.5, 20.0),
    'F': (8.7, 1.0, 29.0, 8.0, 20.0),
}

P = {
    'test': dict(w=1280, samples=48),
    'final': dict(w=3840, samples=800),
}[preset]
P['w'] = int(os.environ.get('WIDTH', P['w']))

sc = bpy.context.scene
cy = sc.cycles
sc.render.engine = 'CYCLES'
cy.samples = P['samples']
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.005 if preset == 'final' else 0.03
cy.use_denoising = True
try:
    cy.denoiser = 'OPENIMAGEDENOISE'
    cy.denoising_prefilter = 'ACCURATE'
except Exception as e:
    print('denoiser settings:', e)
cy.max_bounces = 12
cy.diffuse_bounces = 8
cy.glossy_bounces = 4
cy.transmission_bounces = 4
cy.volume_bounces = 2
cy.sample_clamp_indirect = 10.0
cy.sample_clamp_direct = 0.0
cy.volume_step_rate = 1.0
cy.volume_max_steps = 256

try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    cy.device = 'GPU'
except Exception as e:
    print('GPU setup failed, using CPU:', e)

sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = os.environ.get('LOOK', 'None')
sc.view_settings.exposure = float(os.environ.get('EXPOSURE', '2.6'))
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '16' if preset == 'final' else '8'
sc.render.resolution_x = P['w']
sc.render.resolution_y = round(P['w'] * 9 / 16)
sc.render.resolution_percentage = 100

# dust in the air so the sun beams read; render-only, not stored in the .blend
haze = float(os.environ.get('HAZE', '0'))
if haze > 0:
    import bmesh
    W = max(v.co.x for v in bpy.data.objects['floor'].data.vertices) - 0.1
    L = max(v.co.y for v in bpy.data.objects['floor'].data.vertices) - 0.1
    bm = bmesh.new()
    from mathutils import Matrix
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((W / 2, L / 2, 3.4)) @ Matrix.Diagonal((W - 0.05, L - 0.05, 6.8, 1)))
    me = bpy.data.meshes.new('haze')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('haze', me)
    sc.collection.objects.link(ob)
    m = bpy.data.materials.new('haze')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    vs = nt.nodes.new('ShaderNodeVolumeScatter')
    vs.inputs['Density'].default_value = haze
    vs.inputs['Anisotropy'].default_value = 0.55
    vs.inputs['Color'].default_value = (1.0, 0.95, 0.85, 1)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(vs.outputs['Volume'], out.inputs['Volume'])
    me.materials.append(m)
    ob.visible_shadow = False   # the box itself must not shadow anything

tag = os.environ.get('TAG', '')
for v in views:
    x, y, yaw, pitch, lens = VIEWS[v]
    cd = bpy.data.cameras.new('hero_' + v)
    cd.lens, cd.sensor_width, cd.clip_start, cd.clip_end = lens, 36, 0.05, 400
    co = bpy.data.objects.new('hero_' + v, cd)
    sc.collection.objects.link(co)
    co.location = (x, y, EYE)
    yw, p = math.radians(abs(yaw)), math.radians(pitch)
    sx = -1 if yaw >= 0 else 1
    d = Vector((sx * math.sin(yw) * math.cos(p), math.cos(yw) * math.cos(p), math.sin(p)))
    co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = co
    out = os.path.join(HERE, 'renders', f'hero_{v}_{preset}{tag}.png')
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('RENDERED', out)
    if preset == 'final' and v == 'F' and not tag:
        write_preview(out)
