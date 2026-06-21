search synth, filter, render, points, mixer, classicNoisedeck

julia(
  outputMode: smoothIteration,
  centerX: 0.432,
  centerY: 0.181,
  zoomDepth: 1.688
)
  .warp(
    strength: 11.12,
    scale: 1.97,
    speed: 5
  )
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit(attrition: 1.07)
    .hydraulic()
    .pointsRender(
      density: 100,
      intensity: 83.78,
      inputIntensity: 14.95
    )
  }
  .blur()
  .write(o0)

navierStokes(
  tex: read(o0),
  iterations: 40,
  smoothing: bSpline4x4,
  speed: 145,
  dyeDecay: 98.7,
  velocityDecay: 100,
  inputForce: 0,
  inputDye: 1,
  inputIntensity: 9.17
)
  .palette(
    index: solaris,
    offset: 35,
    alpha: 0.92
  )
  .smoothstep(edge1: 0.94)
  .invert(_skip: true)
  .lighting(
    normalStrength: 0.77,
    smoothing: 1.5,
    specularIntensity: 0.32,
    shininess: 89,
    reflection: 22.8,
    refraction: 17,
    aberration: 27.6
  )
  .subchain(name: "lens effects", id: "ubkh") {
    .chromaticAberration(aberration: 16.43, passthru: 40.39)
    .bloom(intensity: 1.7, taps: 15)
    .lens(displacement: -0.3)
    .vignette(brightness: 0.72, alpha: 0.2)
  }
  .adjust(
    rotation: -15.84,
    saturation: 0.63,
    brightness: 0.84,
    contrast: 0.75
  )
  .temporalAberration(redDelay: 8, blueDelay: 0)
  .write(o1)

render(o1)