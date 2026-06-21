search synth, filter, render, points, mixer

noise(
  type: hermite,
  scaleX: 100,
  scaleY: 100,
  ridges: true,
  speed: 30,
  colorMode: mono
)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit()
    .flow(
      behavior: unruly,
      stride: 30,
      strideDeviation: 0.5,
      kink: 10
    )
    .life(friction: 0.08)
    .pointsRender(
      density: 22.39,
      intensity: 64.67,
      inputIntensity: 59.72
    )
    .pointsBillboardRender(
      shapeMode: soft,
      depositOpacity: 23.4,
      pointSize: 64,
      sizeVariation: 100,
      density: 2.03,
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
  inputIntensity: 6.01
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
  .adjust(brightness: 2.02, contrast: 0.78)
  .write(o1)

render(o1)