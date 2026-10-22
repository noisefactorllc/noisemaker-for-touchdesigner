#!/usr/bin/env node
// dump-validated.mjs — dump the REFERENCE validator output `{plans, diagnostics, render}` for a
// DSL file as canonical JSON. The golden the Python validator port is diffed against
// (parity/compiler/check_validate.py). Reuses export-graph.mjs's bootstrapReference() so the
// shared op/enum/starter registries are populated exactly as the golden-graph path sees them.
//
// Env: NM_REFERENCE_ROOT  reference engine root (required; no default — no sibling assumed)
import { readFileSync } from 'node:fs'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { referenceRoot } from './reference-root.mjs'
import { bootstrapReference } from './export-graph.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REF = referenceRoot()

await bootstrapReference()  // populate global op/enum/starter registries
const { compile } = await import(pathToFileURL(join(REF, 'shaders', 'src', 'lang', 'index.js')).href)

// Single file: dump its validated compile result as canonical JSON. Multiple files: dump
// a batch envelope {results:[{path,ok:true,data}|{path,ok:false,error}]} in one node
// process — the parity gates walk hundreds of programs and a per-file spawn would
// dominate the runtime. Per-file failures are captured, not fatal to the batch.
const files = process.argv.slice(2)
if (files.length === 0) { process.stderr.write('usage: node dump-validated.mjs <file.dsl> [file.dsl ...]\n'); process.exit(2) }
if (files.length === 1) {
  process.stdout.write(JSON.stringify(compile(readFileSync(files[0], 'utf8'))))
} else {
  const results = []
  for (const file of files) {
    try {
      results.push({ path: file, ok: true, data: compile(readFileSync(file, 'utf8')) })
    } catch (e) {
      results.push({ path: file, ok: false, error: String(e && e.message || e) })
    }
  }
  process.stdout.write(JSON.stringify({ results }))
}
