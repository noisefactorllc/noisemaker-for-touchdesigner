#!/usr/bin/env node
// dump-tokens.mjs — dump the REFERENCE lexer's token stream for a DSL file as canonical
// JSON (one array of {type,lexeme,line,col}). The golden the Python lexer port is diffed
// against (parity/compiler/check_lex.py). lex() is pure tokenization — no registry needed,
// so we import lexer.js directly to avoid pulling in the validator/runtime.
//
// Env: NM_REFERENCE_ROOT  reference engine root (required; no default — no sibling assumed)
import { readFileSync } from 'node:fs'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { referenceRoot } from './reference-root.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REF = referenceRoot()

const { lex } = await import(pathToFileURL(join(REF, 'shaders', 'src', 'lang', 'lexer.js')).href)

// Single file: dump its token array as canonical JSON. Multiple files: dump a batch
// envelope {results:[{path,ok:true,data}|{path,ok:false,error}]} in one node process —
// the parity gates walk hundreds of programs and a per-file spawn would dominate the
// runtime. Per-file failures are captured, not fatal to the batch.
const files = process.argv.slice(2)
if (files.length === 0) { process.stderr.write('usage: node dump-tokens.mjs <file.dsl> [file.dsl ...]\n'); process.exit(2) }
if (files.length === 1) {
  const toks = lex(readFileSync(files[0], 'utf8')).map(t => ({ type: t.type, lexeme: t.lexeme, line: t.line, col: t.col }))
  process.stdout.write(JSON.stringify(toks))
} else {
  const results = []
  for (const file of files) {
    try {
      const toks = lex(readFileSync(file, 'utf8')).map(t => ({ type: t.type, lexeme: t.lexeme, line: t.line, col: t.col }))
      results.push({ path: file, ok: true, data: toks })
    } catch (e) {
      results.push({ path: file, ok: false, error: String(e && e.message || e) })
    }
  }
  process.stdout.write(JSON.stringify({ results }))
}
