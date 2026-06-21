search synth, filter, render, points, mixer

perlin(octaves: 6, ridges: true)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit(stateSize: x2048)
    .flow(
      behavior: randomMix,
      stride: 39,
      kink: 5.9
    )
    .flock(
      separation: 2.8,
      alignment: 1.4,
      cohesion: 2.9,
      perceptionRadius: 35,
      separationRadius: 41,
      maxSpeed: 6.8,
      maxForce: 0.74,
      wallMargin: 10,
      noiseWeight: 0
    )
    .life(
      typeCount: 8,
      friction: 0.08,
      matrixSeed: 0
    )
    .pointsRender(
      density: 100,
      intensity: 73.61,
      inputIntensity: 59.72
    )
    .pointsBillboardRender(
      shapeMode: soft,
      depositOpacity: 100,
      pointSize: 33.19,
      sizeVariation: 100,
      seed: 0,
      density: 0.78,
      intensity: 44.72,
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
    index: silvermane,
    offset: 13,
    alpha: 0.67
  )
  .lighting(
    normalStrength: 5,
    specularIntensity: 0.7,
    shininess: 130,
    reflection: 21.8,
    refraction: 23,
    aberration: 18.4
  )
  .adjust(brightness: 1.9, contrast: 0.8)
  .subchain(name: "lens effects", id: "dpxp") {
    .temporalAberration(redDelay: 8, blueDelay: 0)
    .bloom(taps: 15)
    .lens(displacement: -0.28)
    .vignette(brightness: 0.36, alpha: 0.45)
  }
  .grain(alpha: 0.18)
  .write(o1)

render(o1)