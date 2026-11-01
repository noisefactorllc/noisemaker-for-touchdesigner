#!/usr/bin/env node
// convert-shaders.mjs — AUTOMATED reference-GLSL → TouchDesigner-GLSL-TOP transpiler.
//
// Walks shaders/effects/<ns>/<name>/glsl/<program>.glsl (the reference's shipping
// WebGL2 / GLSL-ES-300 shaders) and emits a TouchDesigner GLSL TOP pixel shader to
//   td/noisemaker/shaders/effects/<ns>/<name>/<program>.frag
//
// WHY GLSL, not WGSL: TouchDesigner's GLSL TOP is OpenGL GLSL with the SAME bottom-left
// raster origin as the reference's WebGL2 backend, so the reference GLSL is the closest
// possible source — the transform is purely structural (no math edits, no Y-flip by
// default), which is why this can be automated. See ARCHITECTURE.md / PORTING-GUIDE.md.
//
// The transform (and ONLY this):
//   1. strip `#version …`, `precision …`, and `#ifdef GL_ES … #endif` precision guards
//      (TD auto-prepends its own `#version` + preamble incl. sTD2DInputs / TDOutputSwizzle).
//   2. drop `uniform sampler2D <name>;` declarations; emit `#define <name> sTD2DInputs[i]`
//      in declaration order, and a machine-readable `// NM_INPUTS: <name>=i …` header that
//      the Python network builder reads to wire TOP inputs in the same order.
//   3. detect the fragment output. Single `out vec4 <name>;` → rename `main`→`nm_main` and
//      append `void main(){ nm_main(); <name> = TDOutputSwizzle(<name>); }` so the swizzle
//      is applied exactly once regardless of how the body writes it. Multiple outputs (MRT,
//      e.g. agent passes) are emitted verbatim and FLAGGED for manual review (no auto-wrap).
//   4. everything else — uniforms, helpers (PCG/prng/map/…), `gl_FragCoord`, `textureSize`,
//      `#ifndef X #define X default #endif` define-fallbacks, the entire body — is preserved
//      VERBATIM, except source-bound phase precision and median selection adaptations. Per-pass compile-time define overrides (NOISE_TYPE, LOOP_OFFSET) are injected
//      by the builder at network-build time, not baked here.
//
// Y-flip: default OFF (TD == reference == OpenGL bottom-left, verified at bring-up Task 2.3).
// `--flip-y` routes `gl_FragCoord` through an `nm_FragCoord` helper that flips Y against
// `uTDOutputInfo.res.w`, the single control point if bring-up ever shows a mismatch.
//
// Usage:
//   node convert-shaders.mjs                 # transpile all effects
//   node convert-shaders.mjs synth/noise     # one effect (ns/name)
//   node convert-shaders.mjs --flip-y        # emit with Y-flip indirection
//   node convert-shaders.mjs --dry-run       # report only, write nothing
//
// Env:
//   NM_REFERENCE_ROOT  reference engine root (required; no default — no sibling assumed)
//   NM_OUT_DIR         output root (default: ../td/noisemaker/shaders/effects)

import { readdirSync, statSync, mkdirSync, writeFileSync, existsSync } from 'node:fs'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, dirname, resolve, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { referenceRoot } from './reference-root.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REFERENCE_ROOT = referenceRoot()
const EFFECTS_DIR = join(REFERENCE_ROOT, 'shaders', 'effects')
const OUT_DIR = process.env.NM_OUT_DIR
  ? resolve(process.env.NM_OUT_DIR)
  : resolve(__dirname, '..', 'td', 'noisemaker', 'shaders', 'effects')

const NAMESPACES = [
  'classicNoisedeck', 'filter', 'filter3d',
  'mixer', 'points', 'render', 'synth', 'synth3d'
]

// ---------------------------------------------------------------------------
// The transpile. Pure string surgery; never touches the math.
// ---------------------------------------------------------------------------
function transpile (src, { flipY }) {
  const notes = []
  let lines = src.split('\n')

  // 1. strip headers: #version, standalone precision, and GL_ES precision guards.
  const out = []
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i]
    const t = ln.trim()
    if (/^#version\b/.test(t)) continue
    if (/^precision\s+(highp|mediump|lowp)\b/.test(t)) continue
    // `#ifdef GL_ES … #endif` wrapping only precision lines → drop the whole guard.
    if (/^#ifdef\s+GL_ES\b/.test(t)) {
      let j = i + 1
      const inner = []
      while (j < lines.length && !/^\s*#endif\b/.test(lines[j])) { inner.push(lines[j]); j++ }
      const onlyPrecision = inner.every(l => l.trim() === '' || /^precision\b/.test(l.trim()))
      if (onlyPrecision && j < lines.length) { i = j; continue } // skip guard + #endif
      // otherwise keep the guard (rare) — falls through
    }
    out.push(ln)
  }
  let body = out.join('\n')

  // 2. input samplers: declaration order → sTD2DInputs[i].
  // Tolerate a trailing line comment after the `;` (the reference declares e.g.
  // `uniform sampler2D selfTex;   // Feedback buffer` — without `(?://.*)?` these were missed,
  // left as unbound custom samplers reading black: the all-black `feedback` bug).
  const samplerRe = /^[ \t]*uniform[ \t]+sampler2D[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*;[ \t]*(?:\/\/.*)?$/gm
  const inputs = []
  let m
  while ((m = samplerRe.exec(body)) !== null) inputs.push(m[1])
  body = body.replace(samplerRe, '') // remove declarations
  const inputDefines = inputs.map((n, i) => `#define ${n} sTD2DInputs[${i}]`).join('\n')

  // 2b. v_texCoord: the reference's vertex-shader [0,1] quad varying. A TD GLSL TOP doesn't output
  // it — it provides the built-in `vUV` instead — so a frag declaring `in vec2 v_texCoord;` fails to
  // LINK ("Input 'v_texCoord' … has no corresponding output in vertex shader"). Map it to `vUV.st`
  // (the same bottom-left [0,1] texcoord — no Y-flip, matching the default convention). Only
  // filter/{texture,grime,wobble,spookyTicker} declare it.
  body = body.replace(/^[ \t]*in[ \t]+vec2[ \t]+v_texCoord[ \t]*;[ \t]*(?:\/\/.*)?$/gm,
    '#define v_texCoord vUV.st')

  // 2c. std140 uniform BLOCK -> plain uniform decls. A TD GLSL TOP has no UBO parameter, but it binds
  // a large `uniform vec4 data[N]` as a **Uniform Array** (Arrays page, CHOP-sourced) — the std140 UBO
  // equivalent (proven: td/array_probe.py). Strip `layout(std140) uniform Name { <decls>; };` to its
  // inner `uniform <decl>;` lines; the backend packs the flat uniforms into the array via the effect's
  // uniformLayout. Only synth/remap declares one (`vec4 data[267]`). Flagged so the builder can see it.
  body = body.replace(/layout\s*\(\s*std140\s*\)\s*uniform\s+(\w+)\s*\{([\s\S]*?)\}\s*;/g,
    (_m, blockName, inner) => {
      const decls = inner.split(';').map(s => s.trim()).filter(Boolean)
      notes.push(`UNIFORM_ARRAY (std140 block ${blockName} -> ${decls.join('; ')})`)
      return decls.map(d => `uniform ${d};`).join('\n')
    })

  // 3. fragment outputs.
  const outRe = /^[ \t]*(?:layout\s*\([^)]*\)\s*)?out[ \t]+vec4[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*;[ \t]*(?:\/\/.*)?$/gm
  const outs = []
  let om
  while ((om = outRe.exec(body)) !== null) outs.push(om[1])
  const isMRT = outs.length > 1
  const outName = outs[0] || 'fragColor'
  if (outs.length === 0) notes.push('NO_OUT_VAR (gl_FragColor-style? needs manual port)')
  if (isMRT) notes.push(`MRT (${outs.length} outputs: ${outs.join(',')}) — emitted verbatim, manual swizzle/wiring`)

  // 4. optional Y-flip indirection.
  let flipPreamble = ''
  if (flipY) {
    // route gl_FragCoord through nm_FragCoord (flip Y about the output height).
    body = body.replace(/\bgl_FragCoord\b/g, 'nm_FragCoord')
    flipPreamble =
      '// --flip-y: gl_FragCoord routed through nm_FragCoord (Y flipped about output height)\n' +
      'vec4 nm_FragCoord;\n'
    // define nm_FragCoord at top of nm_main (injected in the rename step below).
  }

  // header the builder reads.
  const inputsHeader = `// NM_INPUTS: ${inputs.length ? inputs.map((n, i) => `${n}=${i}`).join(' ') : '(none)'}`
  const outHeader = `// NM_OUTPUT: ${isMRT ? `MRT ${outs.join(',')}` : outName}`

  // assemble: machine header + input #defines + (flip decl) + transformed body.
  let result = [inputsHeader, outHeader, inputDefines, flipPreamble, body.trim(), ''].filter(s => s !== '').join('\n')

  // 5. single-output: rename main→nm_main and wrap with TDOutputSwizzle.
  if (!isMRT && outs.length === 1) {
    let renamed = false
    result = result.replace(/\bvoid[ \t]+main[ \t]*\(/, () => { renamed = true; return 'void nm_main(' })
    if (renamed) {
      // inject nm_FragCoord assignment at the start of nm_main if flipping.
      if (flipY) {
        result = result.replace(/\bvoid nm_main\s*\(\s*\)\s*\{/,
          'void nm_main() {\n    nm_FragCoord = vec4(gl_FragCoord.x, uTDOutputInfo.res.w - gl_FragCoord.y, gl_FragCoord.z, gl_FragCoord.w);')
      }
      result += `\nvoid main() {\n    nm_main();\n    ${outName} = TDOutputSwizzle(${outName});\n}\n`
    } else {
      notes.push('NO_MAIN (could not find void main) — needs manual port')
    }
  }

  return { result, inputs, outs, isMRT, notes }
}

// ---------------------------------------------------------------------------
function* enumeratePrograms (filter) {
  for (const namespace of NAMESPACES) {
    const nsDir = join(EFFECTS_DIR, namespace)
    if (!existsSync(nsDir)) continue
    for (const entry of readdirSync(nsDir).sort()) {
      const effectDir = join(nsDir, entry)
      if (!statSync(effectDir).isDirectory()) continue
      if (filter && `${namespace}/${entry}` !== filter) continue
      const glslDir = join(effectDir, 'glsl')
      if (!existsSync(glslDir)) continue
      for (const g of readdirSync(glslDir).sort()) {
        if (!g.endsWith('.glsl')) continue
        yield { namespace, name: entry, program: basename(g, '.glsl'), path: join(glslDir, g) }
      }
    }
  }
}

// Preserve the measured phase precision and bounded median selection on regeneration.
function adaptShaderSource (source, key) {
  const contracts = {
    'synth/noise/noise': { declaration: 'float periodicFunction(float p) {', sha: 'ed07796c7faa2d37f67a1ff8d3414e73dca58425921c2cf6b3de6854ff6e5c4c' },
    'filter/median/median': { declaration: 'void main() {', sha: '5a8f9995f50420d9acd64428db5e9aea8da14ae501fb1cbb01420f1782009852' }
  }
  const contract = contracts[key]
  if (!contract) return source
  const fail = () => { throw new Error(`${key}: source shape changed; review the shader adaptation`) }
  const verifyFunction = ({ declaration, sha }) => {
    const start = source.indexOf(declaration)
    if (start < 0 || source.indexOf(declaration, start + 1) >= 0) fail()
    let end = start + declaration.length
    let depth = 1
    while (depth && end < source.length) {
      if (source[end] === '{') depth++
      if (source[end] === '}') depth--
      end++
    }
    const body = source.slice(start, end)
    if (depth || createHash('sha256').update(body).digest('hex') !== sha) fail()
    return { start, end, body }
  }
  const { start, end, body } = verifyFunction(contract)
  if (key === 'synth/noise/noise') {
    const tauDefinitions = source.match(/^#define[ \t]+TAU[^\n]*/gm) || []
    if (tauDefinitions.length !== 1 || tauDefinitions[0] !== '#define TAU 6.28318530718') fail()
    for (const helper of [
  {
    "declaration": "float map(float value, float inMin, float inMax, float outMin, float outMax) {",
    "sha": "11c57c9a006338bc8ecad380620c29d45e7665766e49a604749315c42bbb9f9a"
  },
  {
    "declaration": "vec3 mod289(vec3 x) {",
    "sha": "a4f088cf0693d4298c436c1b2a86a40d3625dadd857f225f0ceb78619fcd2e7f"
  },
  {
    "declaration": "vec2 mod289(vec2 x) {",
    "sha": "2498bae211349d26f431558242f8eec909eb6e63270e083d9c56448ef9e681b1"
  },
  {
    "declaration": "vec3 permute(vec3 x) {",
    "sha": "f066e42fbbd39c0eabb54f96822ee40d56a3446e4e79ac737e849da452d4efca"
  },
  {
    "declaration": "float simplexValue(vec2 st, vec2 freq, float s, float blend) {",
    "sha": "642fdc488e327abacadda823632525fad8de457faf276932f5597b7ad9fb39fe"
  },
  {
    "declaration": "float value(vec2 st, vec2 freq, float s, float blend) {",
    "sha": "ae11a207ed69f88ecba61e524f28c21651c509f43dabc51b7d5cae8e5ccf7d90"
  },
  {
    "declaration": "float offset(vec2 st, vec2 freq) {",
    "sha": "792dfc229bdf5c147f5c0db2f218490d444502d9facdbefcc06af576ca12225b"
  }
]) verifyFunction(helper)
    const simplex = verifyFunction({"declaration": "float simplexValue(vec2 st, vec2 freq, float s, float blend) {", "sha": "642fdc488e327abacadda823632525fad8de457faf276932f5597b7ad9fb39fe"})
    const offset = verifyFunction({"declaration": "float offset(vec2 st, vec2 freq) {", "sha": "792dfc229bdf5c147f5c0db2f218490d444502d9facdbefcc06af576ca12225b"})
    const replacement = `float simplexDot(vec2 st, vec2 freq, float s) {
    const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
    vec2 uv = st * freq;
    uv.x += s;

    vec2 i  = floor(uv + dot(uv, C.yy));
    vec2 x0 = uv - i + dot(i, C.xx);
    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;

    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
    m = m*m;
    m = m*m;

    vec3 x = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);

    vec3 g;
    g.x = a0.x * x0.x + h.x * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return dot(m, g);
}

float simplexValue(vec2 st, vec2 freq, float s, float blend) {
    float v = 130.0 * simplexDot(st, freq, s);
    return periodicFunction(map(v, -1.0, 1.0, 0.0, 1.0) - blend);
}

float simplexOffset(vec2 st, vec2 freq, float s) {
    float phase = simplexDot(st, freq, s) * (130.0 * 0.5 * TAU) + (0.5 * TAU);
    return map(cos(phase), -1.0, 1.0, 0.0, 1.0);
}`
    const offsetReplacement = `float offset(vec2 st, vec2 freq) {
#if LOOP_OFFSET == 10
    return circles(st, freq.x);
#elif LOOP_OFFSET == 20
    return shape(st, 3, freq.x * 0.5);
#elif LOOP_OFFSET == 30
    return (abs(st.x - 0.5 * aspectRatio) + abs(st.y - 0.5)) * freq.x * 0.5;
#elif LOOP_OFFSET == 40
    return shape(st, 4, freq.x * 0.5);
#elif LOOP_OFFSET == 50
    return shape(st, 5, freq.x * 0.5);
#elif LOOP_OFFSET == 60
    return shape(st, 6, freq.x * 0.5);
#elif LOOP_OFFSET == 70
    return shape(st, 7, freq.x * 0.5);
#elif LOOP_OFFSET == 80
    return shape(st, 8, freq.x * 0.5);
#elif LOOP_OFFSET == 90
    return shape(st, 9, freq.x * 0.5);
#elif LOOP_OFFSET == 100
    return shape(st, 10, freq.x * 0.5);
#elif LOOP_OFFSET == 110
    return shape(st, 11, freq.x * 0.5);
#elif LOOP_OFFSET == 120
    return shape(st, 12, freq.x * 0.5);
#elif LOOP_OFFSET == 200
    return st.x * freq.x * 0.5;
#elif LOOP_OFFSET == 210
    return st.y * freq.x * 0.5;
#elif LOOP_OFFSET == 300
    st -= vec2(aspectRatio * 0.5, 0.5);
#if NOISE_TYPE == 10
    return simplexOffset(st, freq, float(seed) + 50.0);
#else
    return value(st, freq, float(seed) + 50.0, 0.0);
#endif
#elif LOOP_OFFSET == 400
    return 1.0 - rings(st, freq.x);
#elif LOOP_OFFSET == 410
    return 1.0 - diamonds(st, freq.x);
#else
    return 0.0;
#endif
}`
    return source.replace(simplex.body, () => replacement)
      .replace(offset.body, () => offsetReplacement)
      .replace(body, () => 'precise ' + body)
  }
  for (const helper of [
  {
    "declaration": "bool lessRecord(uvec2 a, uint blueA, uvec2 b, uint blueB) {",
    "sha": "ef593d067b18eb74d742db49cd6e11215623451d1270727b0ff70d9ffa2b8b87"
  },
  {
    "declaration": "uvec2 packRecordMajor(vec4 sampleColor) {",
    "sha": "4d4a2bc74d3ee12c024191f4894d14d21715145faabbe3b620faee7b2f1a38c2"
  },
  {
    "declaration": "uint packRecordBlue(vec4 sampleColor) {",
    "sha": "4d082a942b05d521a548e79cc72f225dcb88c209566c9367831b8d67d81daa30"
  },
  {
    "declaration": "vec3 unpackRecordRgb(uvec2 major, uint blue) {",
    "sha": "0fab9c2fadd3ecbf8fa7bbe01269936e0098f37728f933349bb41edd2619ea08"
  },
  {
    "declaration": "vec4 readRecord(ivec2 center, ivec2 dimensions, int x, int y) {",
    "sha": "aec4bd949e7b9ed2f958a698b57e8feba6d70237ecdb22402d732c595ed678f9"
  }
]) verifyFunction(helper)
  const previous = `    int left = 0;
    int right = REAL_COUNT - 1;
    while (left < right) {
        uvec2 pivotMajor = majorRecords[medianIndex];
        uint pivotBlue = blueRecords[medianIndex];
        int scanLeft = left;
        int scanRight = right;
        while (scanLeft <= scanRight) {
            while (lessRecord(majorRecords[scanLeft], blueRecords[scanLeft], pivotMajor, pivotBlue)) { scanLeft++; }
            while (lessRecord(pivotMajor, pivotBlue, majorRecords[scanRight], blueRecords[scanRight])) { scanRight--; }
            if (scanLeft <= scanRight) {
                uvec2 temporaryMajor = majorRecords[scanLeft];
                majorRecords[scanLeft] = majorRecords[scanRight];
                majorRecords[scanRight] = temporaryMajor;
                uint temporaryBlue = blueRecords[scanLeft];
                blueRecords[scanLeft] = blueRecords[scanRight];
                blueRecords[scanRight] = temporaryBlue;
                scanLeft++;
                scanRight--;
            }
        }
        if (scanRight < medianIndex) { left = scanLeft; }
        if (medianIndex < scanLeft) { right = scanRight; }
    }`
  const replacement = `    for (int i = 0; i < REAL_COUNT - 1; i++) {
        int minimum = i;
        for (int j = i + 1; j < REAL_COUNT; j++) {
            if (lessRecord(majorRecords[j], blueRecords[j],
                           majorRecords[minimum], blueRecords[minimum])) {
                minimum = j;
            }
        }
        if (minimum != i) {
            uvec2 temporaryMajor = majorRecords[i];
            uint temporaryBlue = blueRecords[i];
            majorRecords[i] = majorRecords[minimum];
            blueRecords[i] = blueRecords[minimum];
            majorRecords[minimum] = temporaryMajor;
            blueRecords[minimum] = temporaryBlue;
        }
    }`
  if (!body.includes(previous)) fail()
  return source.slice(0, start) + body.replace(previous, () => replacement) + source.slice(end)
}

function main () {
  const argv = process.argv.slice(2)
  const dryRun = argv.includes('--dry-run')
  const flipY = argv.includes('--flip-y')
  const filter = argv.find(a => !a.startsWith('--')) || null

  let written = 0, flagged = 0, programs = 0
  const flags = []

  for (const { namespace, name, program, path } of enumeratePrograms(filter)) {
    programs++
    const src = adaptShaderSource(readFileSync(path, 'utf8'), `${namespace}/${name}/${program}`)
    let res
    try {
      res = transpile(src, { flipY })
    } catch (err) {
      flagged++; flags.push(`${namespace}/${name}/${program}: THREW ${err?.message || err}`); continue
    }
    if (res.notes.length) { flagged++; flags.push(`${namespace}/${name}/${program}: ${res.notes.join('; ')}`) }
    const outDir = join(OUT_DIR, namespace, name)
    const outPath = join(outDir, `${program}.frag`)
    if (!dryRun) {
      mkdirSync(outDir, { recursive: true })
      writeFileSync(outPath, res.result)
    }
    written++
    process.stderr.write(`[shaders] ${namespace}/${name}/${program} -> ${program}.frag` +
      `${res.inputs.length ? ` [in:${res.inputs.join(',')}]` : ''}${res.isMRT ? ' [MRT]' : ''}${dryRun ? ' (dry)' : ''}\n`)
  }

  process.stderr.write(`\n[shaders] ${dryRun ? 'would write' : 'wrote'} ${written}/${programs} program(s); ${flagged} flagged for review.\n`)
  for (const f of flags) process.stderr.write(`  ! ${f}\n`)
}

if (basename(process.argv[1] || '') === 'convert-shaders.mjs') {
  try { main() } catch (err) {
    process.stderr.write(`[shaders] FAILED: ${err?.stack || err?.message || err}\n`); process.exit(1)
  }
}
