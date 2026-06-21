search synth, filter, render, points, mixer

noise(
  type: hermite,
  octaves: 4,
  scaleX: 100,
  scaleY: 100,
  seed: 40,
  speed: 30,
  colorMode: mono
)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit()
    .flow(
      behavior: unruly,
      strideDeviation: 0.5,
      kink: 10
    )
    .life(friction: 0.08)
    .pointsRender(
      density: 4.79,
      intensity: 93.63,
      inputIntensity: 59.72
    )
    .pointsBillboardRender(
      shapeMode: soft,
      depositOpacity: 19.7,
      pointSize: 64,
      sizeVariation: 100,
      density: 1.3,
      intensity: 0,
      inputIntensity: 100
    )
  }
  .blur()
  .write(o0)

navierStokes(
  tex: read(o0),
  zoom: x4,
  iterations: 40,
  smoothing: bSpline4x4,
  speed: 145,
  dyeDecay: 97.52,
  velocityDecay: 100,
  inputForce: 1,
  inputDye: 1,
  inputIntensity: 3.9
)
  .palette(
    index: grayscale,
    offset: 58,
    alpha: 0.25
  )
  .lighting(
    normalStrength: 5,
    smoothing: 2.1,
    specularIntensity: 0.7,
    shininess: 130,
    reflection: 21.8,
    refraction: 23,
    aberration: 18.4
  )
  .subchain(name: "lens effects", id: "esfj") {
    .chromaticAberration(aberration: 25)
    .bloom(
      threshold: 0.3,
      intensity: 1.2,
      radius: 33,
      taps: 45,
      tint: #00b2ff
    )
    .lens(displacement: -0.41)
    .vignette(brightness: 0.12, alpha: 0.67)
  }
  .smoothstep(edge0: 0.01, edge1: 0.56)
  .adjust(brightness: 2.49, contrast: 0.8)
  .write(o1)

render(o1)