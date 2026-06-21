search synth, filter, mixer

perlin(scale: 29.7)
  .tetraCosine(
    colorMode: oklch,
    offsetR: 0.087,
    offsetG: 0.765,
    offsetB: 0.994,
    ampR: 0.849,
    ampG: 0.194,
    ampB: 0.244,
    freqR: 3,
    freqG: 4,
    freqB: 3,
    phaseR: 0.065,
    phaseG: 0.026,
    phaseB: 0.797,
    repeat: 3,
    offset: 0.545,
    alpha: 0.64
  )
  .lighting(
    normalStrength: 5,
    smoothing: 10,
    specularIntensity: 0.83,
    shininess: 133,
    reflection: 21.3,
    refraction: 15.1,
    aberration: 19
  )
  .write(o0)

render(o0)