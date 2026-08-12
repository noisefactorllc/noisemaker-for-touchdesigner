# {{NM_PROGRAM_NAME}}

Your program, exported from Noisedeck for **Derivative TouchDesigner**. `integrate.py` builds it as
a live network of TouchDesigner's own GLSL TOPs, so the result is an ordinary TOP: composite it,
texture with it, project it, record it. It fetches nothing at runtime.

## Requirements

- **TouchDesigner 2025.32820** (Official). The free **Non-Commercial** tier is enough — it renders
  this with no watermark.
- A logged-in, GPU-capable desktop session. TouchDesigner is not headless, and a fresh install
  stops at the license activation modal until you sign in once through the GUI.
- Verified on Apple Silicon / Metal, arm64-native macOS.

Nothing else. The runtime imports only the Python standard library and TouchDesigner's built-in `td`
module. No Node, no pip.

## Run it

1. Unzip this folder somewhere you can find again.
2. Open TouchDesigner and create a **new project**.
3. **Save the `.toe` into this folder**, beside `program.dsl`. Everything resolves relative to
   `project.folder`, so this step is what makes the paths work.
4. Add an **Execute DAT** (`Tab` → DAT → Execute).
5. Point it at `integrate.py`: set the DAT's **File** parameter to `integrate.py` and click
   **Sync to File** — or just open `integrate.py` and paste its contents over the DAT's default
   text.
6. Turn on the DAT's **Start** toggle, then **File ▸ Save** and reopen the project. `onStart` runs
   on load, which is what builds the network.

You get a Base COMP named `noisemaker` holding the built network. Its output TOP is `nm.Output`; add
a **Null TOP** named `out` beside the Base COMP and `integrate.py` wires it up for you.

## Rebuilding after an edit

Open the **Textport** (`Alt`+`T`, or *Dialogs ▸ Textport and DATs*) and call:

```python
op('execute1').module.rebuild()
```

using the name of your Execute DAT. `rebuild()` re-reads `program.dsl`, tears the old network down
and puts a new one up.

Right-click ▸ **Run Script** on the DAT is not a rebuild. It re-executes the module body, which only
defines these functions — nothing is built and nothing changes on screen. Use it after editing
`integrate.py` itself, to load the new definitions, then call `rebuild()`.

## What's inside

| Path | What it is |
| --- | --- |
| `integrate.py` | The Execute DAT script. Resolution and names are constants at the top. |
| `program.dsl` | Your program's source, exactly as Noisedeck had it. |
| `noisedeck-export.json` | What was exported, when, against which engine build. |
| `engine/noisemaker/` | The TouchDesigner port — compiler, runtime, effect definitions. Present if you kept **include engine code** checked. |
| `shaders/` | The translated per-effect GLSL (`.frag`). Present if you kept **include shader code** checked. The engine reads its own copy from `engine/`; this tree is for reading and editing. |
| `LICENSES/` | Licenses for everything shipped here. |

## Resolution and the free-tier cap

`integrate.py` renders at **1280×1280**. That is not a style choice: the free Non-Commercial license
caps cook resolution at **1280×1280**, and going over does not raise an error — TouchDesigner
quietly cooks smaller. Non-square textures suffer worst, because they scale down along their long
edge, which is what breaks the 3D volume atlas.

For the same reason, 3D-volume effects are clamped to `MAX_VOLUME_SIZE` in `integrate.py`, default
**32**. A `synth3d` volume is a `size × size²` atlas, so 32 gives 32×1024 — inside the cap. The next
step up, 64, would need 64×4096, which the free license quietly cooks at 20×1280 and the 3D render
breaks.

On a Commercial or Educational license there is no cap: raise `RENDER_WIDTH` / `RENDER_HEIGHT` and
`MAX_VOLUME_SIZE`, all three at the top of `integrate.py`.

One catch on `MAX_VOLUME_SIZE`: the engine reads it out of the environment (`NM_MAX_VOLUME_SIZE`)
the first time its backend is imported, and Python caches that import for the life of the process.
`integrate.py` sets the variable before importing, so the value is picked up on the first build of a
session — but **changing it needs a TouchDesigner restart**, not just a `rebuild()`. The script says
so in the Textport when it notices.

## The engine

Left **include engine code** checked? The port is here, at `engine/noisemaker/`. `integrate.py`
finds it and builds offline.

Already have the port installed? Then you only need `program.dsl`, plus `shaders/` if you kept
**include shader code** checked. Point `ENGINE_DIR_NAME` in `integrate.py` at your copy's `td/`
directory.

Do not have it at all? Get it from
<https://github.com/noisefactorllc/noisemaker-for-touchdesigner> and point `ENGINE_DIR_NAME` at its
`td/` directory.

This export targets Noisemaker `{{NM_ENGINE_VERSION}}`. Pinning is deliberate: the network keeps
building the same way after the engine moves on.

## Editing the program

`program.dsl` is plain text. Every program has the same shape — name the namespaces it uses, chain
effects, write to a surface, pick one to show:

```
search synth, filter
noise(scaleX: 60).bloom().write(o0)
render(o0)
```

**The first line must be a `search` directive.** Without it the effects never resolve and the
compiler reports an unknown op. Noisedeck always writes one; keep it when you edit.

## Effects used by this program

{{NM_EFFECT_LIST}}

## Fidelity

Most effects match the web reference exactly, within 8-bit rounding. Chaotic programs — particles
and fluid feeding back on themselves — render as a *different instance* of the same chaos: the same
look and behavior, not the same pixels. Tiny GPU rounding differences get amplified by feedback,
which is inherent to the simulation rather than a porting defect.

## License

The Noisemaker engine and its TouchDesigner port are MIT licensed; see `LICENSES/`. Your program and
the imagery it renders are yours.
