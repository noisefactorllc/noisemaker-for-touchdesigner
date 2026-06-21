search synth, filter, mixer

mnca(
  tex: read(o1),
  zoom: x16,
  smoothing: hermite,
  speed: 66.518,
  weight: 33,
  n1v1: 27.925,
  n1r1: 17.511,
  n1v2: 29.292,
  n1r2: 48.396,
  n1v3: 94.195,
  n1r3: 45.071,
  n1v4: 97.281,
  n1r4: 15.723,
  n2v1: 38.295,
  n2r1: 35.33,
  n2v2: 37.429,
  n2r2: 3.021
)
  .tetraCosine(
    colorMode: hsv,
    offsetR: 0.665,
    offsetG: 0.312,
    offsetB: 0.072,
    ampR: 0.186,
    ampG: 0.96,
    ampB: 0.522,
    freqR: 4,
    freqG: 3,
    phaseR: 0.917,
    phaseG: 0.921,
    phaseB: 0.411,
    repeat: 2.16,
    offset: 0.91,
    alpha: 0.944
  )
  .lighting(
    normalStrength: 5,
    smoothing: 10,
    specularIntensity: 0.83,
    shininess: 133,
    reflection: 21.3,
    refraction: 18.2,
    aberration: 19
  )
  .adjust(
    saturation: 0.43,
    brightness: 2.34,
    contrast: 0.71
  )
  .write(o0)

noise(
  type: sine,
  octaves: 1,
  scaleX: 24.38,
  scaleY: 100,
  seed: 30,
  loopScale: 100,
  speed: 100
)
  .write(o1)

render(o0)