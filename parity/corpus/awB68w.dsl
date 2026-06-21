search synth, filter, render, points, mixer

noise(
  type: hermite,
  octaves: 4,
  scaleX: 100,
  scaleY: 100,
  seed: 40,
  loopScale: 100,
  speed: 100,
  colorMode: mono
)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit()
    .attractor(speed: 0.12)
    .life(friction: 0.08, _skip: true)
    .pointsRender(
      density: 74.91,
      intensity: 81.66,
      inputIntensity: 59.72,
      viewMode: ortho,
      rotateY: 0.7,
      viewScale: 4,
      posX: -15,
      posY: 9
    )
    .pointsBillboardRender(
      shapeMode: soft,
      depositOpacity: 100,
      pointSize: 16.48,
      sizeVariation: 100,
      density: 7.07,
      intensity: 0,
      inputIntensity: 100,
      viewMode: ortho,
      rotateY: 0.7,
      viewScale: 4,
      posX: -15,
      posY: 9
    )
  }
  .blur()
  .write(o0)

navierStokes(
  tex: read(o0),
  iterations: 40,
  smoothing: bSpline4x4,
  speed: 145,
  dyeDecay: 97.24,
  velocityDecay: 100,
  inputForce: 1,
  inputDye: 1,
  inputIntensity: 3.08
)
  .palette(
    index: grayscale,
    offset: 62,
    alpha: 0.13
  )
  .lighting(
    normalStrength: 4.15,
    specularIntensity: 1.1,
    shininess: 97,
    reflection: 21.8,
    refraction: 23,
    aberration: 18.4
  )
  .subchain(name: "lens effects", id: "esfj") {
    .chromaticAberration(aberration: 29.18, passthru: 50.12)
    .bloom(
      threshold: 0.55,
      intensity: 0.45,
      radius: 33,
      taps: 45,
      tint: #00b2ff
    )
    .lens(displacement: -0.6)
    .vignette(brightness: 0.12, alpha: 0.45)
  }
  .smoothstep(edge0: 0.05, edge1: 0.43)
  .adjust(brightness: 1.64, contrast: 0.47)
  .write(o1)

render(o1)