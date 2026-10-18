"""
Render cameras from foresteria.blend.

  Blender -b foresteria.blend --python render.py -- <quality> <cam> [<cam> ...]
  quality: draft | final
  cam:     cam_photo1 | cam_photo2 | cam_photo3 | ...   (any camera object name)
"""
import bpy, sys, os, math

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
quality = argv[0] if argv else 'draft'
cams = argv[1:] or ['cam_photo1']

Q = {
    'draft': dict(long=720, samples=24, denoise=True),
    'final': dict(long=1600, samples=160, denoise=True),
}[quality]

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.samples = Q['samples']
cy.use_denoising = Q['denoise']
cy.max_bounces = 8
cy.diffuse_bounces = 6
cy.glossy_bounces = 3
cy.transmission_bounces = 2
cy.sample_clamp_indirect = 8.0
cy.sample_clamp_direct = 0.0
cy.use_adaptive_sampling = True

# GPU (Metal) if available
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
sc.view_settings.look = 'None'
sc.view_settings.exposure = float(os.environ.get('EXPOSURE', '0.8'))
sc.render.image_settings.file_format = 'PNG'
sc.render.film_transparent = False

for name in cams:
    cam = bpy.data.objects[name]
    sc.camera = cam
    if name == 'cam_overview':   # skeleton view: take the vault webs off, expose for daylight outside
        bpy.data.objects['vault_webs'].hide_render = True
        sc.view_settings.exposure = -0.6
        bpy.data.objects['ground'].data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.42, 0.40, 0.36, 1)
        wnt = sc.world.node_tree
        for n in list(wnt.nodes):
            if n.type == 'TEX_SKY':
                wnt.nodes.remove(n)
        bgn = [n for n in wnt.nodes if n.type == 'BACKGROUND'][0]
        bgn.inputs['Color'].default_value = (0.62, 0.66, 0.72, 1)
    else:
        sc.view_settings.exposure = float(os.environ.get('EXPOSURE', '0.8'))
    portrait = bool(cam.get('portrait', False))
    long_px = Q['long']
    if portrait:
        sc.render.resolution_x, sc.render.resolution_y = round(long_px * 9 / 16), long_px
    else:
        sc.render.resolution_x, sc.render.resolution_y = long_px, round(long_px * 9 / 16)
    sc.render.resolution_percentage = 100
    out = os.path.join(HERE, 'renders', f'{name}_{quality}{os.environ.get("TAG", "")}.png')
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('RENDERED', out)
