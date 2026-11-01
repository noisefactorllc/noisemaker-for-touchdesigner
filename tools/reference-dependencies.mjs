import { registerHooks } from 'node:module'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { lstatSync } from 'node:fs'

const root = process.env.NM_REFERENCE_DEPENDENCIES
if (!root) throw new Error('NM_REFERENCE_DEPENDENCIES must identify the external dependency directory.')
const dependency = resolve(root, 'node_modules/playwright')
for (const file of ['index.js', 'index.mjs']) {
  if (!lstatSync(resolve(dependency, file)).isFile()) throw new Error('Playwright entry points must be regular files.')
}
registerHooks({ resolve(specifier, context, nextResolve) {
  if (specifier !== 'playwright') return nextResolve(specifier, context)
  const target = resolve(dependency, context.conditions.includes('require') ? 'index.js' : 'index.mjs')
  return nextResolve(context.conditions.includes('require') ? target : pathToFileURL(target).href, context)
} })
