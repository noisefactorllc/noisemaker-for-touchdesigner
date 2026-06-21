search synth, filter, render, points, mixer

perlin(octaves: 6, ridges: true)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit(stateSize: x2048)
    .flow(
      behavior: randomMix,
      stride: 30,
      strideDeviation: 0.5,
      kink: 7.9
    )
    .life(
      typeCount: 8,
      friction: 0.08,
      matrixSeed: 0
    )
    .pointsRender(
      density: 100,
      intensity: 85.86,
      inputIntensity: 59.72
    )
    .pointsBillboardRender(
      shapeMode: soft,
      depositOpacity: 100,
      pointSize: 47.39,
      sizeVariation: 100,
      seed: 0,
      density: 0.78,
      intensity: 39.38,
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
  inputIntensity: 6.01
)
  .palette(
    index: solaris,
    offset: 6,
    alpha: 0.76
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
  .adjust(brightness: 1.9, contrast: 0.8)
  .write(o1)

render(o1)