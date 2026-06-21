search synth, filter, classicNoisedeck, render, points, mixer

perlin(
  scale: 48.74,
  dimensions: 3,
  ridges: true,
  seed: 25,
  speed: 5
)
  .subchain(name: "flow field particles", id: "eage") {
    .pointsEmit()
    .flow(
      behavior: unruly,
      stride: 76,
      strideDeviation: 0,
      kink: 10
    )
    .lenia(
      muK: 24,
      sigmaK: 2.9,
      searchRadius: 12
    )
    .pointsRender(
      density: 100,
      intensity: 94.81,
      inputIntensity: 0
    )
  }
  .adjust(
    mode: hsv,
    rotation: -50.09,
    hueRange: 200,
    _skip: true
  )
  .blur()
  .lighting(
    normalStrength: 1.91,
    smoothing: 5.2,
    specularIntensity: 1.27,
    shininess: 104,
    reflection: 20.7,
    refraction: 57.4,
    aberration: 25.6
  )
  .adjust(
    rotation: 180,
    hueRange: 40.31,
    brightness: 0.61,
    contrast: 0.53
  )
  .grain(alpha: 0.09)
  .motionBlur(amount: 30.87)
  .subchain(name: "lens effects", id: "d94x") {
    .temporalAberration(
      redDelay: 8,
      greenDelay: 1.5,
      blueDelay: 0
    )
    .bloom(
      threshold: 0.15,
      softKnee: 0.12,
      radius: 16,
      taps: 45
    )
    .lens(displacement: -0.33)
    .vignette(brightness: 0.19, alpha: 0.72)
  }
  .adjust(contrast: 0.56)
  .write(o0)

render(o0)