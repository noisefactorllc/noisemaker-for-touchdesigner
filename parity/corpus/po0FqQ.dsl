search filter, mixer, synth

curl(
  scale: 6.807,
  seed: 357,
  ridges: false,
  intensity: 2,
  outputMode: magnitude
)
  .write(o0)

osc2d(
  oscType: sawtooth,
  freq: 3,
  speed: 10,
  rotation: -45,
  seed: 169
)
  .focusBlur(
    tex: read(o0),
    depthSource: sourceA,
    focalDistance: 59.56,
    aperture: 1,
    sampleBias: 5.75
  )
  .palette(index: sherbet, repeat: 4)
  .write(o1)

render(o1)