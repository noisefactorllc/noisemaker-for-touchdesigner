// harness-port.mjs — keep the golden renderers' harness server bindable.
//
// The vendored shade-mcp harness reads SHADE_VIEWER_PORT once. An explicit
// value is the ONLY candidate it will bind (no fallback); an unset value
// makes it try an ephemeral port first, and a sandboxed host that rejects
// that bind can abort the whole candidate chain before it reaches the
// 43117-43126 harness range (observed: golden renders dying with
// "listen EPERM" while the first range port was held by an unrelated
// session). So probe explicitly: when the pinned port is already bound,
// move the override to the first FREE port of the harness range; leave
// everything as-is when the pinned port is bindable or no range port is.
import { createServer } from 'node:net'

const HARNESS_PORTS = [43117, 43118, 43119, 43120, 43121,
                       43122, 43123, 43124, 43125, 43126]

function probePort(port) {
  return new Promise((resolve) => {
    const probe = createServer()
    probe.once('error', () => resolve(false))
    probe.listen(port, '127.0.0.1', () => probe.close(() => resolve(true)))
  })
}

export async function ensureFreeHarnessPort() {
  const pinned = Number.parseInt(process.env.SHADE_VIEWER_PORT ?? '', 10)
  if (!Number.isInteger(pinned) || pinned <= 0) return
  if (await probePort(pinned)) return
  for (const port of HARNESS_PORTS) {
    if (await probePort(port)) {
      process.env.SHADE_VIEWER_PORT = String(port)
      return
    }
  }
}
