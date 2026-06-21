search synth, filter, render, mixer

perlin(
  scale: 22.25,
  octaves: 3,
  ridges: true,
  speed: 2
)
  .adjust(
    mode: hsv,
    rotation: 109.39,
    hueRange: 44.57
  )
  .subchain(name: "feedback loop with warp", id: "rp9q") {
    .loopBegin(alpha: 96.37)
    .warp(strength: 5.39)
    .feedback(mix: 60.63, refractBAmt: 5.8)
    .loopEnd()
  }
  .lighting(
    normalStrength: 5,
    smoothing: 3.5,
    specularIntensity: 1.14,
    shininess: 134,
    reflection: 38.7,
    refraction: 35.3,
    aberration: 29.7
  )
  .subchain(name: "lens effects", id: "yqdu") {
    .temporalAberration()
    .bloom(
      threshold: 0.6,
      intensity: 0.75,
      taps: 15
    )
    .lens(displacement: -0.5)
    .vignette(brightness: 0.27, alpha: 0.7)
  }
  .write(o0)

navierStokes(
  tex: read(o0),
  iterations: 40,
  speed: 145,
  dyeDecay: 98.34,
  inputForce: 1,
  inputDye: 1,
  inputIntensity: 0
)
  .lighting(
    normalStrength: 5,
    smoothing: 2.5,
    specularIntensity: 1.35,
    shininess: 125,
    reflection: 83.2,
    refraction: 58.4,
    aberration: 42.3
  )
  .blendMode(tex: read(o0), mode: overlay)
  .write(o1)

render(o1)