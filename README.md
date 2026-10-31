# catmansion

**A site layout that is data, and a Blender scene that is generated from it.**

一份场地布局（纯 JSON，全部厘米），一套从它长出来的 Blender 三维场景。
改布局 ⇒ 三维跟着变。不是"画一张 3D 图"，是"布局驱动的 3D 场地"。

The point is not the render. The point is that the render cannot lie about the layout:
every wall, kerb, bay and pole comes out of the same JSON the editor writes.

## Pipeline

```
_layout.json  ──( _bmod_dump.py )──►  _bmod/scene.json  ──( Blender -b )──►  PNG
      │                                   │
      │                                   └─ boxes only: [x0,y0,z0, x1,y1,z1, rgb, group]
      │                                      group 0 = architecture, 4 = environment
      │
      └──►  layout_editor.html  (drag, pull edges, type exact numbers)
      └──►  _t_plan2.py         (2D plan + section, with dimension callouts)
```

### ⛔ The one step people skip and then get a wrong render

`_bmod_day.py` reads **`_bmod/scene.json`**, not `_layout.json`.
If you edit the layout and render without running the dump first, **you render the old layout
and nothing tells you**. Order is always:

```bash
python _bmod_dump.py                 # layout -> scene.json
blender -b -P _bmod_day.py -- S1_street 100
```

`_bmod_dump.py` prints the box counts (`arch_box_count` / `env_box_count`) — check them,
that is your proof the dump actually picked up your edit.

## Running it

Blender 5.2 LTS, headless. No GUI, no addon, no MCP connection needed:

```bash
BMOD_SPEC=_v1 blender -b -P _bmod_day.py -- S1_street X1_front_wide 100
#   ^ output suffix so a new pass never overwrites the last one
#                          ^ one or more camera tags   ^ resolution %
```

Output lands in `_bmod_day/<tag>_day<SPEC>.png`. A 1920x1080 frame takes ~40-60 s on a laptop.

Editing the layout:

```bash
python _layout_server.py     # serves the editor at 127.0.0.1:8777
# http://127.0.0.1:8777/layout_editor.html?layout=_layout.json
```

## Files

| File | Role |
|---|---|
| `_layout.json` | **the** source of truth. All centimetres. `bands` / `cars` / `poles` / `lamps` / `trees` / `grass` / `building` |
| `layout_editor.html` | single-file canvas editor — drag, pull edges, type exact numbers |
| `_layout_server.py` | tiny static server for the editor (`?layout=` picks the file) |
| `_gmod.py` | the 3D geometry module. Every dimension, every repeated detail. Imported by the dumper, never run in Blender directly |
| `_bmod_dump.py` | geometry → `_bmod/scene.json` + camera table |
| `_bmod_day.py` | EEVEE daylight render, N cameras, exposure per shot |
| `_t_plan2.py` | 2D plan + auto-derived section, dimension callouts |
| `_t_tight8.py` | layout rewrite: trim the parking row to N bays + convert the leftover to verge |
| `_t_cars2.py` | layout rewrite: change how many cars are parked without touching the bays |
| `_t_planB.py` | layout rewrite: the "real regulation" variant (adds an internal drive aisle) |

## Conventions

- **Units: centimetres everywhere.** Blender multiplies by 0.01 at the camera/scene boundary.
- **Axes: +x = east, +y = toward the street (the building faces +y), +z = up.**
  This triple is right-handed, which has one consequence worth knowing before you file a bug:
  a camera standing on the street side looking at the building **facing -y** sees **+x on its
  left**. That is correct, not a mirrored render.
- **Bands are drawn in list order**, and each band kind has a different thickness
  (`walk` 14 / `curb` 18 / `road` 2 / `verge` 6 / `lot` 8). The heights are not construction —
  they exist only so overlapping ground planes don't z-fight.
- **`pitch` on a `lot` band** is what draws the bay stripes. Bays = `(x1-x0)/pitch`.
  Bays, parked cars and households are three different numbers — never derive one from another.

## Things that bit us (keep these)

**A 90° parking row needs a drive aisle in front of it.**
Bays perpendicular to the aisle are typically ~5.4 m deep and want ~5.8 m of aisle to reverse
into. An early variant had 691 cm of frontage: 150 walk + 525 bays + 16 kerb — eleven cars with
no lane to drive into them. It looked fine in the render and was physically unusable. The fix is
not a wider pavement, it's an aisle (the `_t_planB.py` variant adds 580 cm).

**The building's real footprint is not `units × bay_width`.**
`FULL_X = 364 × 8 = 2912` is the eight unit bays. The actual architecture box measures
**x −6 … 3462** — the east stair and shop return hang off the end. Always measure the exported
bbox, never the nominal sum. Filming the nominal number cropped the building at both edges.

**Camera coverage, not vibes.** `sensor_fit = 'VERTICAL'`, `sensor_height = 20.25 mm`,
1920x1080 ⇒ horizontal half-angle `tan = 18 / f`. So:

```
coverage_width = 2 × (18 / lens_mm) × distance_to_subject
```

At 24 mm and 19.1 m that is 2865 cm — which does not fit a 3468 cm building, and the render
proves it. Do the arithmetic before the render, not after.

**If the layout stores a coordinate, the renderer must read it.**
Poles carry `{x, y}` in the layout, but the renderer had forced every pole's `y` to the outer
edge of the largest sidewalk. Dragging a pole onto the lawn in the editor did nothing in 3D —
the data was right, the writer ignored it. Symptom was "poles are stuck on the sidewalk".
The same class of bug: a value is stored, never consumed, and no test fails.

**Draw the plan on its own layer, then paste.**
Plotting geometry and text onto the same image means any unclipped ground rectangle paints over
the label column. Plan on one `Image`, `paste` into the frame, text last.

**Thin bands lose their labels.**
A 16 cm kerb is 3 px wide on a dimension-scaled strip; its label lands on the row below.
Anything under ~54 px gets its label above the bar, with a leader line.

## What is deliberately still grey-box

- **Cars are extruded boxes** — chassis, cabin, two window strips. No wheels, and the chassis
  floats 26 cm off the ground because nothing fills that gap. They read as concrete blocks at
  any distance. Fine for checking bay geometry, not fine for judging how a street looks.
- **The roof is one flat dark slab.** From above it eats most of the frame.
- No people, no signage, no façade material variation past the palette table.

These are visual-quality items, deliberately left as decisions rather than fixed silently.

## License

MIT. See `LICENSE`.
