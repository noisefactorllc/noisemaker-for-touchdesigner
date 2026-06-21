search synth, filter

noise(scaleX: 87, scaleY: 87)
  .write(o0)

reactionDiffusion(
  tex: read(o0),
  smoothing: bSpline3x3,
  sourceF: brightness,
  feed: 37.95,
  kill: 62.88,
  rate1: 80.95,
  rate2: 21.19,
  weight: 27.34,
  inputIntensity: 22.61
)
  .palette(
    index: tungsten,
    rotation: fwd,
    offset: 40.731,
    alpha: 0.58
  )
  .lighting(
    normalStrength: 1.7,
    smoothing: 5.9,
    reflection: 26.2,
    refraction: 13.6,
    aberration: 7
  )
  .write(o1)

render(o1)