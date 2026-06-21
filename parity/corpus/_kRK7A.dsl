search synth, filter, render, points, mixer

noise(
  type: hermite,
  ridges: true,
  speed: 30,
  colorMode: mono
)
  .subchain(name: "flow field particles", id: "lkjw") {
    .pointsEmit()
    .flow(behavior: unruly, stride: 25)
    .pointsRender(
      density: 36.63,
      intensity: 96.07,
      inputIntensity: 0
    )
  }
  .write(o0)

navierStokes(
  tex: read(o0),
  iterations: 40,
  speed: 55.14,
  dyeDecay: 99.1,
  velocityDecay: 100,
  inputForce: 0.39,
  inputDye: 1,
  inputIntensity: 9.55
)
  .write(o1)

render(o1)