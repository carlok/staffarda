# Staffarda foresteria, ground floor: Blender reconstruction from 3 photos

Procedural model, no point cloud, no photo projection. Geometry and materials are written by hand
from what the photos show, then cameras are placed where the photos were taken so the two can be compared.

## Files

| File | What |
|---|---|
| `build_foresteria.py` | Builds the whole scene, saves `foresteria.blend` (empty room). With `FURNITURE=1` it saves `foresteria_furnished.blend` instead, with the chairs, tables and extinguishers from the photos; with `WINDOW_HEADS=arched` it saves `foresteria_arched.blend`, the arched-window hypothesis. All dimensions are parameters at the top. |
| `render.py` | `Blender -b foresteria.blend --python render.py -- final cam_photo1 cam_photo2 cam_photo3 cam_overview` (`draft` for a ~10 s preview) |
| `compare.py` | Writes photo-vs-render side-by-sides to `compare/` |
| `structural_check.py` | Thrust-line check of the vault and its supports; reads its dimensions straight from `build_foresteria.py`. Output in `structural_report.txt`. |
| `render_hero.py` | One-off high-quality still from standing eye height (1.6 m). `final` = 3840x2160, 16-bit, 800 samples + denoise, about 11 min on this Mac. |
| `walkthrough.py` | Renders the walkthrough video (EEVEE, walk-mode look): slalom between the columns with stops. See "Walkthrough video". |
| `walk.py` | Opens the model in the Blender GUI with real-time EEVEE lighting and starts Walk Navigation at the doorway. See "Walking through it". |
| `renders/` | Final Cycles renders (1600 px long side, 160 samples, denoised) and the 4K hero; `walk_eevee_*.png` and `walk_vs_cycles_F.jpg` are the EEVEE test renders from `walk.py` (made before the lighting, stone, capital and arch changes) |
| `compare/` | Original photo on the left, render on the right |

Rebuild and re-render:

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --python build_foresteria.py                  # empty room -> foresteria.blend
FURNITURE=1 $B -b --python build_foresteria.py      # with furniture -> foresteria_furnished.blend
WINDOW_HEADS=arched $B -b --python build_foresteria.py   # hypothesis: arched window heads -> foresteria_arched.blend
$B -b foresteria_furnished.blend --python render.py -- final cam_photo1 cam_photo2 cam_photo3
$B -b foresteria.blend --python render.py -- final cam_overview
$B -b --python compare.py
python3 structural_check.py > structural_report.txt
```

## What is modelled

- Hall of 2 naves x 5 square bays, 4 round stone columns on the centre line (base, shaft with a little
  entasis and irregularity, iron tie band on the first one). The shaft stone is a light olive grey.
- The four bases differ too (`BASE_STYLES`, `column_base()`), from crops of photos 1 and 2: 1 a rough, broken drum
  of lumpy blocks with rust staining; 2 a straight drum with a fillet ring under the shaft; 3 a lower drum with a
  chamfered top; 4 a taller lumpy drum with a flat ledge.
- The four capitals differ, as in photos 1 and 2 (`CAPITAL_STYLES`, `capital()`), counting from the entrance end:
  1 a plain round cushion under a thick octagonal slab (darker stone); 2 a bell with eight broad leaves curling
  out under the slab corners; 3 a flared octagonal bell with flat carved panels; 4 a drum with a band of small
  teeth (palest stone). Their carving is simplified: shapes and proportions, not the real ornament.
- Above each capital a low, round brick block (`SPRINGER_PROFILE`, 0.55 m high, smooth-shaded) where the ribs
  start. A taller 1.5 m version looked much heavier than the real capitals in photos 1 and 2 and was dropped. A
  small notch is still visible where two ribs part above the near capital in the hero view.
- Pointed brick rib vault: 10 bays, each with two round-nosed diagonal ribs, transverse/longitudinal
  arches and wall arches, domed plaster cells, a rosette keystone per bay. The ribs spring at 2.5 m from the
  columns but higher on the side walls, from smaller corbels, as measured on photo 1 with the calibrated camera:
  `HS_WALL_L` = 2.65 m on the left wall (corbel tops measured 2.63-2.65 m), `HS_WALL_R` = 2.95 m on the right
  (2.86-3.04 m). The crowns and keystones stay where they were; only the wall-side haunches are shallower
  (`spring_z()`, `arch_z()`). Left-wall corbels are stepped moulded blocks (0.30 x 0.40 x 0.36 m), right-wall ones
  rounded cushions (0.34 x 0.44 x 0.40 m), the end walls' middle corbels small blocks at 2.5 m. Brick courses come from a
  procedural shader driven by arc length along each rib: bricks vary from deep red to pale buff, with bold
  white lime joints. The square-section arches are brick only on the soffit; above the springer blocks their
  sides are plastered like the cells, which gives the light/red banding seen in the photos. Lower down, where
  the ribs gather above the capitals, the sides stay brick.
- Large windows (left wall, one per bay; one per nave in each end wall), as they are today and measured on
  photo 1 with the calibrated camera (`WIN`): a deep, strongly splayed rectangular recess (1.10 m wide at the
  face, 0.64 m at the back, 0.80 m deep) under a flat lintel at 3.52 m, its sill at 1.48 m, four pale stone steps
  (8 cm risers) rising to a narrow round-headed light (0.50 m wide, 1.80-3.33 m) with iron glazing bars. The
  reveals are clean lime plaster, without the wall's flaking. Plus small rectangular windows high in the left
  wall's lunettes, an oculus per nave in the end walls, and two doorways in the right wall near the far end.
- **Hypothesis, not in the photos:** `WINDOW_HEADS=arched` builds the recesses with a round rere-arch instead of
  the lintel (crown 0.20 m above today's soffit), saved as `foresteria_arched.blend`. A flat lintel across a 1.1 m
  splay in a 13th-15th century vaulted hall looks like a later alteration, and an arched head would be the usual
  original form; I found no source on these windows, so this is a reading of the forms, not documented history.
- Brick floor laid in 90-degree herringbone, as in photos 1 and 2: 7,771 real bricks of 28 x 14 cm
  (`floor_bricks()`, `FLOOR_BRICK_W`) with worn chamfered edges, small random twist, tilt and size, over a
  dusty mortar bed (the `floor` object). Each brick carries two random attributes that pick its tone, from
  dark red-tan to pale worn beige; large dust patches, scuffs and pits sit on top.
- Walls in pale cream-to-ochre lime plaster, weathered as in the photos (see "Weathering" below).
- Lighting: sun and sky through the openings, plus eight uplights on the capitals at `UPLIGHT_W` = 120 W each,
  and a copper conduit along the right wall.
- Colour and brightness were matched by measuring the same regions in the photos and in renders from the
  matching cameras (renders at exposure 2.6). Against photo 2: walls about 0.82 of the photo's brightness, floor
  0.90, column 1.00, vault 0.99; against photo 1: walls 0.90, floor 0.98. The rendered floor is still less
  yellow than in the photos (red/blue about 1.3-1.6 against 1.7-1.8). The photos are phone shots with automatic
  exposure and processing, so these are targets for the look, not physical measurements.

### Weathering

Every material kind has its own procedural noise (Blender's Perlin-based Noise Texture plus Voronoi cells), tuned
against close-ups of the photos:
- **Walls**: lobed patches where the plaster has fallen off (about a quarter of the wall between 0.6 and 3 m,
  `LOSS_T`), showing older brown plaster and faint rubble, with a shadowed broken edge and a bump step; brown
  mottling, grey-brown weathering, vertical water streaks, a damp tide mark at the foot, stucco grain.
- **Vault plaster**: rose and ochre blotches, sooty patches, a fine dark speckle and sandy grain (photo 3), trowel
  undulation in the bump.
- **Brick ribs**: per-brick tone and mottling, pores, chipped spots showing a paler core (ridged noise), lime smears,
  soot, mortar from clean lime to dirty with joints recessed by varying depth.
- **Stone** (columns, bases, capitals, corbels, steps, keystones): crystal speckle, large pale lime/lichen patches
  and darker olive damp ones, vertical streaks, a few hairline cracks, grime toward the floor, a per-object noise
  offset; rust only at the first column's foot.
- **Floor**: every brick has its own mottling and firing marks, pits, worn dips in the bump, dust in large patches
  and filling the shallow joints, a lighter worn path down the middle of each nave.

Masks are written as quantiles of the noise (`nq()`): Blender's normalised Noise Texture has a median of 0.5 and a
standard deviation of only about 0.06 (measured), so "the top 25 %" is `nq(0.75)` = 0.54. Height masks use a clamped
linear helper (`NB.lin`), because ColorRamp clamps its stop positions to 0..1.
- The room is **empty by default**. The chairs, tables and fire extinguishers from the photos are in
  `furniture()`; build with `FURNITURE=1` to get them, in `foresteria_furnished.blend`.
- Right wall: two arched doorways at y = 18.5 m and 20.1 m (`DOOR_CENTRES`). The first has a plank door with iron straps,
  hinged on its -y jamb and swung 68 degrees into the room (`door(c, ajar_deg)`); the second is left open.
  Both have a stone threshold flush with the floor, so you can walk straight in from the ground outside.
  They are kept clear of the corbels where the ribs spring (1.53 m and 0.73 m with the 0.44 m right-wall corbels) with 2+ m
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
- Vault heights: springing at 2.5 m on the columns (2.65 / 2.95 m on the walls, measured), arch crowns about 5.5 m,
  keystones about 6.4 m. Photo 3 only shows the arch shape from below, so rib profiles are eyeballed. The right-wall
  corbel at y = 16.2 m, near the edge of photo 1, measured higher still (about 3.6 m); I treated that reading as
  unreliable and used the other right-wall corbels.
- Wall thickness (1.2 m, checked against the thrust: at least 0.95 m needed), the near end wall (mirrors the far one; never photographed), the right wall away from
  the doors, the exterior (flat ground plane).
- Not modelled: cameras and the gilded frame on the right wall, the carved details of the capitals and corbels,
  individual wall stones (the walls are shader patterns, not scans).
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
$B -b foresteria_furnished.blend --python render.py -- final cam_photo1 cam_photo2 cam_photo3
$B -b foresteria.blend --python render.py -- final cam_overview
$B -b --python compare.py
```

## Walking through it

```bash
/Applications/Blender.app/Contents/MacOS/Blender foresteria.blend --python walk.py
```

Blender 5.1 only (it uses 5.1 property names). `walk.py` does not change the .blend on disk. At start-up it:

- builds a second scene, `walk`, that shares all objects with the Cycles scene but has its own world and EEVEE
  settings (raytracing, Fast GI, AgX, exposure 2.2), so `render.py` and `render_hero.py` still see the Cycles scene as it was;
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
  After the lighting and wall changes (dimmer uplights, exposure 2.6 in Cycles, paler plaster) the walk exposure
  was re-matched to 2.2 and the fill made less warm: a headless EEVEE render from the hero camera is within 2 % of
  the Cycles hero's mean brightness. `renders/walk_vs_cycles_F.jpg` is from the earlier lighting. It is darker at the far end wall and has
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
/Applications/Blender.app/Contents/MacOS/Blender -b foresteria.blend --python render_hero.py -- final F
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
- Wall springing raised to the measured 2.65 / 2.95 m with smaller corbels. The check now analyses the wall-side
  half of each arch and diagonal separately (smaller rise) and requires a crown thrust both halves accept: they
  overlap (diagonal 12.5-13.2 kN, transverse 16.5-19.5 kN in case A1), wall-side GFS 1.17-1.81. The thrust acts
  higher on the wall: the 1.2 m wall still passes (F = 1.96-2.22 in case B; minimum 1.15 m).
- A corbel this small cracks if it has to carry the whole springing load as a cantilever (bending tension 8.2 MPa
  in case B, 2.2 MPa in A1). It works only if the springer's courses are bonded into the wall (tas-de-charge),
  the usual medieval detail; then it carries about 59 kN and 0.9 MPa. The report gives both cases.

Remaining numbers: interior columns carry ~1.3 MPa (case A1) or ~4.4 MPa (case B), well below the crushing strength of
stone but the highest stress in the building. The web-load split between diagonals and side arches changes the
GFS by less than 0.15.

Limits: it is a 2D slice analysis with a simplified load distribution, assumed densities and web thickness
(15 cm), assumed rib depths, no foundations, no iron ties, no unbalanced loading at the end bays, no seismic
action, and the upper-floor arrangement is a guess. It tells you the proportions are plausible; it is not a
substitute for a survey and an engineer.

## Walkthrough video

`walkthrough.py` renders a visitor's walk at standing eye height (1.6 m), 24 mm lens, about 1 m/s with eased
starts and stops, a slight head bob and motion blur, in EEVEE with the walk-mode look (`walk.py`). The route
(`video/path_plan.svg`): in through the open right-wall doorway, round the far side of column 4, then a slalom past
columns 3, 2 and 1, stopping at each to look around (capital, ribs and keystone; the right wall and a base; a window
with its steps and a corbel; the near keystone and column 1's broken base), and at the near end a turn back into
the long view of the hero render. One continuous take, 35 m at a slow 0.62 m/s, 1 min 52 s, at least 1.3 m from
every column axis and 1.1 m from the walls. The gaze eases toward each target through a damped follower whose turning
speed is capped (24 deg/s side to side, 16 deg/s up and down), so the view never jumps.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b foresteria.blend --python walkthrough.py -- plan       # path diagram and timing only
$B -b foresteria.blend --python walkthrough.py -- preview    # 640x360, 12 fps, ~30 min
caffeinate -i $B -b foresteria.blend --python walkthrough.py -- final   # 1920x1080, 24 fps, 40 samples, ~1.8 h
$B -b foresteria.blend --python walkthrough.py -- final 2480 2530       # only frames 2480-2530, into video/final_2480-2530/
```

Frames go to `video/<preset>/` and are skipped when they exist, so an interrupted render resumes by running the same
command again (a frame cut off mid-render is redone). While the Mac sleeps nothing renders; Blender just pauses and
continues on wake. `caffeinate -i` keeps the Mac from idle-sleeping during the render (closing a laptop lid still
sleeps it). When all frames exist the script encodes `video/walkthrough_<preset>.mp4` with ffmpeg. Frames and MP4s
are not tracked in git. Measured on this Mac at 1080p: about 2.4 s per frame at 40 samples with the GPU to itself
(8.5 s while other renders shared it; 64 samples differ by under one 8-bit level on average).

The first final render flickered on the brick springer blocks above the wall corbels. Those blocks were exactly as
wide as the arches springing from them (0.56 m), so their sides were coplanar and EEVEE's depth test picked a
different winner each frame. The blocks are now 2 cm wider, which hides the arch faces inside them. Raising the
sample count would not have helped: this was a geometry problem, not noise.

