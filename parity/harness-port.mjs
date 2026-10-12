// harness-port.mjs — keep the golden renderers' harness server bindable.
//
// The vendored shade-mcp harness reads SHADE_VIEWER_PORT once: an explicit
// value is the ONLY candidate port it will bind (no fallback). On shared
// hosts that port (the first of the 43117-43126 harness range) can be held
// by an unrelated session for hours, which hard-fails every golden render
// with EADDRINUSE. Probe the pinned port before the harness binds: when it
// is already taken, drop the override so the harness walks its own fallback
// chain (ephemeral port, then the harness range) and binds a free one. When
// the pinned port is free, the override is kept — behavior is unchanged.
import { createServer } from 'node:net'

export async function ensureFreeHarnessPort() {
  const pinned = Number.parseInt(process.env.SHADE_VIEWER_PORT ?? '', 10)
  if (!Number.isInteger(pinned) || pinned <= 0) return
  const isFree = await new Promise((resolve) => {
    const probe = createServer()
    probe.once('error', () => resolve(false))
    probe.listen(pinned, '127.0.0.1', () => probe.close(() => resolve(true)))
  })
  if (!isFree) delete process.env.SHADE_VIEWER_PORT
}
