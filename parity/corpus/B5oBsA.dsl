search user, synth, filter, render, points, mixer, classicNoisedeck

chromeicosahedroninterior(
  reflections: 10,
  glowIntensity: 0.95,
  chromeShift: 0.01,
  cameraOffset: 0.3
)
  .tile(
    symmetry: rotate6,
    scale: 1.15,
    offsetY: -0.26,
    repeat: 4
  )
  .tunnel(
    scale: -1,
    speed: -1,
    center: -78.26
  )
  .write(o0)

sacredGeometry(
  geometry: metatron,
  scale: 14.53,
  rings: 6,
  starPoints: 12,
  thickness: 0.126,
  smoothness: 0.79,
  fgColor: #adfe72,
  bgColor: #d607a4,
  animation: ripple,
  speed: -5,
  pulseDepth: 0.31
)
  .blendMode(
    tex: read(o0),
    mode: diff,
    mix: -2.8
  )
  .lighting(normalStrength: 5, smoothing: 2.1)
  .subchain(name: "lens effects", id: "vk3g") {
    .temporalAberration()
    .bloom(taps: 15)
    .lens(displacement: -0.5)
    .vignette()
  }
  .write(o1)

render(o1)