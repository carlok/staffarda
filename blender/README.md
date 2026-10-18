# Staffarda foresteria, ground floor: Blender reconstruction from 3 photos

Procedural model, no point cloud, no photo projection. Geometry and materials are written by hand
from what the photos show, then cameras are placed where the photos were taken so the two can be compared.

## Files

| File | What |
|---|---|
| `build_foresteria.py` | Builds the whole scene, saves `foresteria.blend` (empty room). With `FURNITURE=1` it saves `foresteria_furnished.blend` instead, with the chairs, tables and extinguishers from the photos. All dimensions are parameters at the top. |
| `render.py` | `Blender -b foresteria.blend --python render.py -- final cam_photo1 cam_photo2 cam_photo3 cam_overview` (`draft` for a ~10 s preview) |
| `compare.py` | Writes photo-vs-render side-by-sides to `compare/` |
| `structural_check.py` | Thrust-line check of the vault and its supports; reads its dimensions straight from `build_foresteria.py`. Output in `structural_report.txt`. |
| `render_hero.py` | One-off high-quality still from standing eye height (1.6 m). `final` = 3840x2160, 16-bit, 800 samples + denoise, about 11 min on this Mac. |
| `walk.py` | Opens the model in the Blender GUI with real-time EEVEE lighting and starts Walk Navigation at the doorway. See "Walking through it". |
| `renders/` | Final Cycles renders (1600 px long side, 160 samples, denoised) and the 4K hero; `walk_eevee_*.png` and `walk_vs_cycles_F.jpg` are the EEVEE test renders from `walk.py` (made before the column stone and springer changes) |
| `compare/` | Original photo on the left, render on the right |

Rebuild and re-render:

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --python build_foresteria.py                  # empty room -> foresteria.blend
FURNITURE=1 $B -b --python build_foresteria.py      # with furniture -> foresteria_furnished.blend
EXPOSURE=1.2 $B -b foresteria_furnished.blend --python render.py -- final cam_photo1 cam_photo2 cam_photo3
EXPOSURE=1.2 $B -b foresteria.blend --python render.py -- final cam_overview
$B -b --python compare.py
python3 structural_check.py > structural_report.txt
```

## What is modelled

- Hall of 2 naves x 5 square bays, 4 round stone columns on the centre line (base, shaft with a little
  entasis and irregularity, scalloped capital, octagonal abacus, iron tie band on the first one). The column
  stone is a light greenish grey with faint rust, kept low in saturation so it separates from the ochre walls.
- Above each capital a low, round brick block (`SPRINGER_PROFILE`, 0.55 m high, smooth-shaded) where the ribs
  start. A taller 1.5 m version looked much heavier than the real capitals in photos 1 and 2 and was dropped. A
  small dark notch is still visible where two ribs part above the near capital in the hero view.
- Pointed brick rib vault: 10 bays, each with two round-nosed diagonal ribs, transverse/longitudinal
  arches and wall arches, domed plaster cells, a rosette keystone per bay. Brick courses come from a
  procedural shader driven by arc length along each rib.
- Walls with splayed arched windows (left wall, one per bay) and small lunette windows, an arched window
  plus an oculus per nave in each end wall, two doorways in the right wall near the far end. Window sizes are
  `WIN_SIDE` / `WIN_END`. Each arched window has three stone steps rising toward the glass (`window_steps()`),
  as in photo 1; the real steps are shallower than these 15 cm ones.
- Brick floor laid in 90-degree herringbone, as in photos 1 and 2: 7,771 real bricks of 28 x 14 cm
  (`floor_bricks()`, `FLOOR_BRICK_W`) with worn chamfered edges, small random twist, tilt and size, over a
  dusty mortar bed (the `floor` object). Each brick carries two random attributes that pick its tone, from
  dark red-tan to pale worn beige; large dust patches, scuffs and pits sit on top. The tones are tuned so the
  rendered floor matches the colour measured in the photos; the photos remain about twice as bright overall.
- Uplights on the capitals, a copper conduit along the right wall.
- The room is **empty by default**. The chairs, tables and fire extinguishers from the photos are in
  `furniture()`; build with `FURNITURE=1` to get them, in `foresteria_furnished.blend`.
- Right wall: two arched doorways at y = 18.5 m and 20.1 m (`DOOR_CENTRES`). The first has a plank door with iron straps,
  hinged on its -y jamb and swung 68 degrees into the room (`door(c, ajar_deg)`); the second is left open.
  Both have a stone threshold flush with the floor, so you can walk straight in from the ground outside.
  They are kept clear of the corbels where the ribs spring (1.45 m and 0.65 m with the 0.60 m corbels) with 2+ m
  of masonry over the heads; an earlier position at y = 21.35 m cut the wall right under a corbel and was moved.
- Sun lamp + sky through the openings; the sun is on the -X (left wall) side.

## How the numbers were obtained

Camera height (~1.45 m for photo 1) and a ~71 degree horizontal field of view (typical phone main camera,
~25 mm equivalent) were assumed. From the floor contact points of the columns and the horizon line in
photo 1 I got a column spacing of about 5.4 m and a capital height of about 2.5 m, and used those for
square 5.4 m bays. Cross-checks (chair and fire-extinguisher heights, column diameter versus photo 2) agree
to roughly 10%. With that setup the columns, windows, oculi, doorways and furniture land within a
couple of percent of their image positions in photo 1.

## Guessed or not in the photos

- Absolute scale (+/- 10-15%). Not surveyed.
- Vault heights: springing at 2.5 m, arch crowns about 5.5 m, keystones about 6.4 m. Photo 3 only shows the
  arch shape from below, so rib profiles are eyeballed.
- Wall thickness (1.2 m, checked against the thrust: at least 0.95 m needed), the near end wall (mirrors the far one; never photographed), the right wall away from
  the doors, the exterior (flat ground plane).
- Not modelled: window sill steps, cameras and the gilded frame on the right wall, the carved details of the
  capitals, individual stones and bricks (the floor and walls are shader patterns, not scans).
- Materials are procedural. The render is a plausible reconstruction, not a photoreal match.

## Cameras in the .blend

`cam_photo1`, `cam_photo2` (portrait), `cam_photo3` (looking up at a keystone), `cam_door` (the doorways from
inside), `cam_overview` (bird's-eye, vault webs hidden in `render.py` so the rib skeleton shows).

`renders/cam_photo1..3_final.png` and `compare/` come from `foresteria_furnished.blend`, so the furniture lines
the renders up with the photos. `cam_overview_final.png` and `cam_door_draft_empty.png` come from the empty
`foresteria.blend`. All of them show the current model.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --python build_foresteria.py && FURNITURE=1 $B -b --python build_foresteria.py
EXPOSURE=1.2 $B -b foresteria_furnished.blend --python render.py -- final cam_photo1 cam_photo2 cam_photo3
EXPOSURE=1.2 $B -b foresteria.blend --python render.py -- final cam_overview
$B -b --python compare.py
```

## Walking through it

```bash
/Applications/Blender.app/Contents/MacOS/Blender foresteria.blend --python walk.py
```

Blender 5.1 only (it uses 5.1 property names). `walk.py` does not change the .blend on disk. At start-up it:

- builds a second scene, `walk`, that shares all objects with the Cycles scene but has its own world and EEVEE
  settings (raytracing, Fast GI, AgX, exposure 1.25), so `render.py` and `render_hero.py` still see the Cycles scene as it was;
- maximises the 3D viewport (Back to Previous, top bar, or Ctrl+Space, gets the normal layout back), Rendered
  shading, overlays and gizmos off, 24 mm lens;
- puts the eye at the open right-wall doorway (x = 10.65, y = 20.1 m, 1.6 m up) looking down the hall; the door leaf
  on the other doorway (y = 18.5) is at the left edge of the first view;
- turns walk gravity on, starts Walk Navigation about two seconds later, and puts the gravity preference back.

**Walk mode starts moving only after the first mouse movement** (Blender waits for the pointer to be centred).
Keys, all checked in a real Blender 5.1.1 session with injected events: W A S D move (about 2.5 m/s), mouse looks
around, Shift (hold) moves about 5 times faster, Tab turns gravity on or off (with gravity off, E / Q go up / down),
Enter confirms and leaves you where you stand, Esc cancels and puts you back at the doorway. Left click also
confirms in Blender's walk keymap; I did not test that one. The status bar lists the rest (Space teleport, V jump).

Things to know:

- **No collision.** Gravity only follows the floor, at 1.6 m eye height. You can walk through walls and columns
  (tested: straight through a column and the left wall; you step up onto a column base). Outside the hall the ground
  is 6 cm lower than the floor, so the eye drops to 1.54 m there.
- **Lighting is an approximation.** In Cycles the sky hardly gets in (a ray-cast shows about 0.3 % of the floor's
  hemisphere sees it); the room is lit by the sun through the left windows, the eight uplights and their bounces.
  EEVEE ignores that occlusion and floods the interior with sky (nearly white). So the walk world keeps the
  sky only for camera rays (windows and doorways stay bright) and lights everything else with a dim warm fill
  (`fill_color`, `fill_strength` 0.08); the sun and the uplights are the original lamps with real shadows.
  Raytracing with Fast GI adds screen-space bounce light and ambient occlusion on top.
  Against `hero_F_final.jpg` the EEVEE version has the same mean brightness (0.247 vs 0.246 on the 8-bit image),
  colour balance and sun patches (`renders/walk_vs_cycles_F.jpg`). It is darker at the far end wall and has
  less smooth bounce gradients, and screen-space effects cannot see what is off-screen, so the ambient shifts a bit as you turn.
- **Grain while moving.** Raytracing is noisy for a frame or two after the view changes and clears up while you stand
  still (64 samples). I could not watch the viewport in motion, so frame rate and how the grain looks while walking
  are untested. If it is choppy, start with `WALK_FAST=1` (raytracing off: smooth and fast, flatter, no bounce
  or occlusion, still close in colour) or lower `rt_resolution_scale` in the `TUNE` dict at the top of `walk.py`.
- Light probe volumes (baked indirect light) would be the proper fix for the ambient, but baking did nothing in a headless
  test (a closed test room showed no bounce after the bake), so it is not used. A bake from the GUI is untested.
- Saving from this session (Ctrl+S) leaves the `walk` scene and world out of the file and puts them back
  afterwards, so the saved .blend still renders with the Cycles scripts. Tested with a copy save.
- Other env switches: `WALK_NO_START=1` (set up, do not start walking; use View > Navigation > Walk Navigation,
  Shift+`), `WALK_NO_MAXIMIZE=1` (normal window layout).

Headless EEVEE check of the same setup (about 4 s): load `walk.py` with `importlib`, call `make_walk_scene()`, add a
camera to that scene and `bpy.ops.render.render(scene='walk')`. The images in `renders/walk_*` came from that, with 128
samples.

Not verified: real mouse-look feel (the GUI test injected events instead of a physical mouse), frame rate and grain in
motion, other GPUs, left click to confirm. The GUI run, its screenshots and the key tests were done on this Mac
with Blender 5.1.1.

## Hero render

`renders/hero_F_final.png` (16-bit) and `hero_F_final.jpg` come from view `F` in `render_hero.py`: camera at
x = 8.7 m, y = 1.0 m in the right nave near the entrance end, eye height 1.6 m, 20 mm lens (about 84 degrees
horizontal), tilted up 8 degrees, looking diagonally toward the far-left corner.

```bash
EXPOSURE=1.25 /Applications/Blender.app/Contents/MacOS/Blender -b foresteria.blend --python render_hero.py -- final F
```

Other candidate viewpoints (`A` to `E`) are in the script; `test` renders 1280 px in about 15 s.
`HAZE=0.006` adds a dust volume for sun beams. I tried it and dropped it: the beams barely show and it
muddies and grains the floor.

## Structural check and tuning

`structural_check.py` (plain Python, no dependencies; output saved in `structural_report.txt`) is a lower-bound
limit analysis of the masonry (Heyman's safe theorem): thrust lines through the diagonal ribs and the transverse
arches, then the columns, corbels and wall piers against the resulting thrusts. It reproduces the classical
minimum thickness of a semicircular arch to within 2% (0.1096 vs 0.1075 R), which is how the code was validated.

Two load cases, because the photos don't show how the dormitory floor above is carried:
- **A1**: vault carries only itself, haunches backed with rubble masonry up to 2 m above the springing.
- **B**: vault carries the dormitory floor on fill (fill to 0.3 m over the keystones, 3 + 2 kN/m2 floor and live load).

What the first version of the model got wrong, and what was changed (all in `build_foresteria.py`):
- Transverse arches were 40 cm deep: marginal (geometric factor of safety 1.01 to 1.09). Now 50 cm (GFS 1.3 to 1.5).
- Corbels were 0.34 x 0.50 x 0.56 m: bending tension ~3.9 MPa in case B. Now 0.40 x 0.60 x 0.65 m (~2.9 MPa).
- Walls were 1.3 m, more than needed: the minimum for an overturning factor of 2 is 0.95 m (case B). Now 1.2 m (F = 2.3 to 2.8).
- Diagonal ribs, 32 cm deep, are only marginal without backing (GFS 1.01) and fine with it (1.48) or with the floor on fill (1.58).
  The haunch backing is not modelled (it is behind the visible surface); it is assumed.
- Doorways moved clear of the corbels (see above).

Remaining numbers: interior columns carry ~1.3 MPa (case A1) or ~4.4 MPa (case B), well below the crushing strength of
stone but the highest stress in the building. The web-load split between diagonals and side arches changes the
GFS by less than 0.15.

Limits: it is a 2D slice analysis with a simplified load distribution, assumed densities and web thickness
(15 cm), assumed rib depths, no foundations, no iron ties, no unbalanced loading at the end bays, no seismic
action, and the upper-floor arrangement is a guess. It tells you the proportions are plausible; it is not a
substitute for a survey and an engineer.


