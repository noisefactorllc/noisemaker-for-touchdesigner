search synth, filter, render, points, mixer

cell(
  scale: 86.73,
  cellScale: 81.69,
  cellSmooth: 100,
  variation: 100,
  speed: 5
)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit(attrition: 0.1)
    .hydraulic()
    .pointsRender(
      density: 100,
      intensity: 96.07,
      inputIntensity: 0
    )
  }
  .blur()
  .write(o0)

navierStokes(
  tex: read(o0),
  zoom: x2,
  iterations: 40,
  smoothing: bSpline4x4,
  speed: 126.71,
  dyeDecay: 98.95,
  velocityDecay: 100,
  inputForce: 1,
  inputDye: 0.94,
  inputIntensity: 0
)
  .adjust(
    rotation: 145.56,
    saturation: 3.16,
    brightness: 1.58,
    contrast: 0.79
  )
  .invert()
  .palette(index: grayscale, alpha: 0.77)
  .lighting(
    normalStrength: 0.8,
    specularIntensity: 0.32,
    shininess: 89,
    reflection: 32.1,
    refraction: 20.5,
    aberration: 12.7
  )
  .temporalAberration(redDelay: 8, blueDelay: 0)
  .adjust(brightness: 0.95, contrast: 0.73)
  .write(o1)

render(o1)