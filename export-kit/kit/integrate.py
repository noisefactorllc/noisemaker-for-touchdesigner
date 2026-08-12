"""integrate.py -- build this exported Noisedeck program inside TouchDesigner.

Paste this into an Execute DAT (or point one at this file) and enable its
`onStart` toggle. On project start it puts the bundled engine on `sys.path`,
creates a host Base COMP, and hands it `program.dsl`. The result is an ordinary
TOP you can wire anywhere.

Everything is resolved relative to `project.folder`, the directory your `.toe`
was saved into, so SAVE THE .toe BESIDE program.dsl -- next to this file, at the
root of the unzipped export. No absolute paths, no PYTHONPATH, no install step.

To rebuild after editing program.dsl or the constants below, call rebuild() from
the Textport (Alt+T / Dialogs > Textport and DATs):

    op('execute1').module.rebuild()

substituting the name of your Execute DAT. The DAT's right-click "Run Script"
only re-executes the module body, which defines these functions and builds
nothing -- rebuild() is the entry point that actually tears the old network down
and puts a new one up.

Requirements
    TouchDesigner 2025.32820 (Official). Verified on Apple Silicon / Metal,
    arm64-native macOS. The free Non-Commercial tier renders this with no
    watermark, but it caps cook resolution at 1280x1280 -- which is why
    RENDER_WIDTH/RENDER_HEIGHT below default to 1280 square. Raising either
    past 1280 on a Non-Commercial license does not error; TouchDesigner just
    silently cooks smaller, and non-square atlas textures (the 3D volume path)
    scale down along their long edge and break. On a Commercial or Educational
    license there is no cap and you can raise both freely.

TouchDesigner is not headless: it needs a logged-in, GPU-capable desktop
session, and a one-time license activation through the GUI on a fresh install.
"""

import os
import pathlib
import sys

#: Directory holding the vendored Noisemaker package. It is the *parent* of the
#: importable `noisemaker` package, which is what goes on sys.path. A bare name
#: is resolved inside this export; an absolute path to another checkout's `td/`
#: directory works too, which is how an export made without "include engine
#: code" is pointed at a clone of the port repo.
ENGINE_DIR_NAME = 'engine'

#: Your program, exactly as Noisedeck had it.
PROGRAM_FILE = 'program.dsl'

#: Base COMP the render network is built under. Created if it does not exist.
HOST_COMP_NAME = 'noisemaker'

#: Optional Null/Out TOP in the same COMP; connected to the output when found.
OUTPUT_OP_NAME = 'out'

#: Render resolution. 1280 square is the Non-Commercial cook cap -- see above.
RENDER_WIDTH = 1280
RENDER_HEIGHT = 1280

#: 3D-volume atlas cap. A synth3d volume is a `size x size^2` atlas, so the
#: port's default 32 gives 32x1024 -- under the 1280 cook cap. 64 would give
#: 64x4096, which a Non-Commercial license silently downscales to 20x1280,
#: breaking the atlas indexing and the whole 3D render with it. Raise this on a
#: Commercial or Educational license, which has no cap.
#:
#: The engine reads this from the environment when its backend module is first
#: imported, so :func:`apply_volume_cap` must run before that import and a
#: change here only takes effect in a fresh TouchDesigner session.
MAX_VOLUME_SIZE = 32

#: Environment variable the port's backend reads the cap from.
ENV_MAX_VOLUME_SIZE = 'NM_MAX_VOLUME_SIZE'


def kit_root():
    """Folder holding program.dsl: where the .toe was saved.

    Returns:
        pathlib.Path: the project directory.
    """
    return pathlib.Path(project.folder)


def apply_volume_cap():
    """Publish MAX_VOLUME_SIZE to the environment, before the engine imports.

    The port reads `NM_MAX_VOLUME_SIZE` once, at module import time, into a
    module-level constant. Setting it after the first `import noisemaker...` in
    a session therefore does nothing, which is why this runs first — and why an
    edit to MAX_VOLUME_SIZE needs a TouchDesigner restart to be picked up.

    An existing value wins, whether it came from the OS environment or from an
    earlier build in this session. When it disagrees with MAX_VOLUME_SIZE that
    is reported rather than silently ignored.

    Returns:
        str: the value the engine will use.
    """
    wanted = str(MAX_VOLUME_SIZE)
    current = os.environ.get(ENV_MAX_VOLUME_SIZE)
    if current is None:
        os.environ[ENV_MAX_VOLUME_SIZE] = wanted
        return wanted
    if current != wanted:
        print(
            '[noisemaker] note: {} is already {} in this session, so '
            'MAX_VOLUME_SIZE = {} will not take effect until TouchDesigner is '
            'restarted.'.format(ENV_MAX_VOLUME_SIZE, current, wanted)
        )
    return current


def ensure_engine_on_path(root):
    """Put the bundled engine on sys.path so `import noisemaker` resolves.

    Args:
        root (pathlib.Path): the kit root, from :func:`kit_root`.

    Returns:
        pathlib.Path: the directory added to sys.path.

    Raises:
        RuntimeError: if the engine was not included in this export.
    """
    engine_dir = pathlib.Path(ENGINE_DIR_NAME)
    if not engine_dir.is_absolute():
        engine_dir = root / engine_dir
    if not (engine_dir / 'noisemaker' / 'runtime' / 'nm_renderer.py').exists():
        raise RuntimeError(
            'Noisemaker engine not found at {}. This export was made without '
            '"include engine code". See README.md for where to get the port, then '
            'set ENGINE_DIR_NAME to an absolute path to its td/ directory, or '
            're-export with the engine included.'.format(engine_dir)
        )
    entry = str(engine_dir)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return engine_dir


def read_program(root):
    """Read program.dsl and check the one thing the compiler insists on.

    Every program must name the namespaces it uses before it uses them, so the
    first meaningful line is a `search` directive. Noisedeck writes one; this
    only catches a hand-edit that dropped it, where the compiler's own error is
    a confusing "unknown op".

    Args:
        root (pathlib.Path): the kit root, from :func:`kit_root`.

    Returns:
        str: the DSL source.

    Raises:
        RuntimeError: if program.dsl is not beside the saved .toe.
    """
    program = root / PROGRAM_FILE
    if not program.exists():
        raise RuntimeError(
            'No program at {}. Everything here resolves relative to '
            'project.folder, so save your .toe into the unzipped export folder '
            '— beside {} and integrate.py — then build again.'.format(
                program, PROGRAM_FILE
            )
        )
    source = program.read_text()
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if not stripped.startswith('search'):
            print(
                '[noisemaker] warning: {} does not start with a `search` '
                'directive, so its effects will not resolve.'.format(PROGRAM_FILE)
            )
        break
    return source


def ensure_host_comp(container):
    """Find or create the Base COMP the render network is built under.

    Args:
        container (COMP): COMP the Execute DAT lives in.

    Returns:
        COMP: the host Base COMP.
    """
    host = container.op(HOST_COMP_NAME)
    if host is None:
        host = container.create(baseCOMP, HOST_COMP_NAME)
        host.nodeX = 0
        host.nodeY = 0
    return host


def teardown_previous(host):
    """Destroy the network an earlier build left under `host`.

    Each build constructs a fresh NMRenderer, and a renderer only tears down the
    pipeline it built itself. Without this the previous renderer's GLSL TOPs and
    surface operators stay in the network forever, one full copy per rebuild,
    holding their GPU memory with them.

    Failures are reported and swallowed: a half-built previous renderer must not
    be able to block the rebuild that is trying to replace it.

    Args:
        host (COMP): the host Base COMP.

    Returns:
        bool: True when a previous renderer was found.
    """
    previous = host.fetch('nm', None, search=False)
    if previous is None:
        return False
    try:
        pipeline = getattr(previous, 'pipeline', None)
        if pipeline is not None:
            pipeline.teardown()
    except Exception as err:
        print(
            '[noisemaker] warning: could not fully tear down the previous '
            'network ({}); rebuilding anyway.'.format(err)
        )
    host.unstore('nm')
    return True


def connect_output(container, renderer):
    """Wire the rendered TOP into a Null/Out TOP beside the host, if there is one.

    Args:
        container (COMP): COMP the Execute DAT lives in.
        renderer (NMRenderer): the built renderer.

    Returns:
        bool: True when a connection was made.
    """
    sink = container.op(OUTPUT_OP_NAME)
    if sink is None or renderer.Output is None:
        return False
    sink.inputConnectors[0].connect(renderer.Output)
    return True


def build():
    """Build the program as a live TouchDesigner network.

    Safe to call repeatedly: any network from an earlier build is torn down
    first.

    Returns:
        NMRenderer: the renderer, also stored on the host COMP as `nm`.
    """
    root = kit_root()
    apply_volume_cap()
    ensure_engine_on_path(root)

    # Imported after the environment and sys.path bootstrap, never at module
    # scope: the backend reads NM_MAX_VOLUME_SIZE as this import runs.
    from noisemaker.runtime.nm_renderer import NMRenderer

    container = parent()
    if container is None:
        container = root_comp()
    host = ensure_host_comp(container)
    teardown_previous(host)

    # Read the program before building, so a missing or malformed program.dsl
    # fails with its own message instead of half a network.
    source = read_program(root)

    renderer = NMRenderer(host, width=RENDER_WIDTH, height=RENDER_HEIGHT)
    # TouchDesigner drops any Python object nothing references; the store keeps
    # the renderer (and its whole network) alive past this function.
    host.store('nm', renderer)
    renderer.set_dsl(source)
    connect_output(container, renderer)

    print(
        '[noisemaker] built {} at {}x{} under {}'.format(
            PROGRAM_FILE, RENDER_WIDTH, RENDER_HEIGHT, host.path
        )
    )
    return renderer


def rebuild():
    """Re-read program.dsl and rebuild the network. Call this from the Textport.

    The documented entry point for iterating:

        op('execute1').module.rebuild()

    Returns:
        NMRenderer: the new renderer.
    """
    return build()


def root_comp():
    """The `/` COMP, for the case where this DAT sits at the project root."""
    return op('/')


def onStart():
    """Execute DAT callback. Enable the DAT's `Start` toggle to arm it."""
    build()
