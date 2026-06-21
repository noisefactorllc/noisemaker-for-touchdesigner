search synth, filter, render, points, mixer

noise(
  type: bSpline4x4,
  octaves: 1,
  scaleX: 100,
  scaleY: 1,
  seed: 84,
  ridges: true,
  loopScale: 100,
  speed: 40,
  colorMode: mono
)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit(stateSize: x128)
    .attractor(speed: 0.01)
    .life(friction: 0.08, _skip: true)
    .pointsRender(
      density: 100,
      intensity: 53.78,
      inputIntensity: 42.74,
      viewMode: ortho,
      rotateY: 0.7,
      viewScale: 8,
      posX: -15,
      posY: 9
    )
    .pointsBillboardRender(
      shapeMode: soft,
      depositOpacity: 100,
      pointSize: 18.39,
      sizeVariation: 100,
      density: 2.18,
      intensity: 0,
      inputIntensity: 100,
      viewMode: ortho,
      rotateY: 0.7,
      viewScale: 8,
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
  dyeDecay: 98.16,
  velocityDecay: 100,
  inputForce: 1,
  inputDye: 1,
  inputIntensity: 3.95
)
  .palette(
    index: grayscale,
    offset: 71,
    alpha: 0.17
  )
  .lighting(
    normalStrength: 3.99,
    specularIntensity: 1.1,
    shininess: 97,
    reflection: 29.3,
    refraction: 23.5,
    aberration: 18.4
  )
  .subchain(name: "lens effects", id: "esfj") {
    .chromaticAberration(aberration: 29.18, passthru: 39.51)
    .bloom(
      threshold: 0.2,
      intensity: 0.55,
      radius: 33,
      taps: 45,
      tint: #00b2ff
    )
    .lens(displacement: -0.6)
    .vignette(brightness: 0.12, alpha: 0.45)
  }
  .smoothstep(edge0: 0.08, edge1: 0.36)
  .adjust(
    saturation: 0.72,
    brightness: 1.64,
    contrast: 0.49
  )
  .write(o1)

render(o1)