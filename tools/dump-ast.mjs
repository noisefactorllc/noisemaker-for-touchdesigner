#!/usr/bin/env node
// dump-ast.mjs — dump the REFERENCE parser's AST for a DSL file as canonical JSON. The golden
// the Python parser port is diffed against (parity/compiler/check_parse.py). `parse(lex(src))`
// is self-contained for the builtin namespaces (shaders/src/runtime/tags.js seeds them), so no
// effect bootstrap is needed at the parse stage.
//
// Env: NM_REFERENCE_ROOT  reference engine root (required; no default — no sibling assumed)
import { readFileSync } from 'node:fs'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { referenceRoot } from './reference-root.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REF = referenceRoot()

const lang = await import(pathToFileURL(join(REF, 'shaders', 'src', 'lang', 'index.js')).href)
const { lex, parse } = lang

// Single file: dump its AST as canonical JSON. Multiple files: dump a batch envelope
// {results:[{path,ok:true,data}|{path,ok:false,error}]} in one node process — the parity
// gates walk hundreds of programs and a per-file spawn would dominate the runtime.
// Per-file failures are captured, not fatal to the batch.
const files = process.argv.slice(2)
if (files.length === 0) { process.stderr.write('usage: node dump-ast.mjs <file.dsl> [file.dsl ...]\n'); process.exit(2) }
if (files.length === 1) {
  process.stdout.write(JSON.stringify(parse(lex(readFileSync(files[0], 'utf8')))))
} else {
  const results = []
  for (const file of files) {
    try {
      results.push({ path: file, ok: true, data: parse(lex(readFileSync(file, 'utf8'))) })
    } catch (e) {
      results.push({ path: file, ok: false, error: String(e && e.message || e) })
    }
  }
  process.stdout.write(JSON.stringify({ results }))
}
