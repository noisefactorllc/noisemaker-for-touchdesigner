search filter, synth, mixer, render, points

let osc2 = osc(type: oscKind.noise)
let osc1 = osc(type: oscKind.noise)
let osc3 = osc(type: oscKind.noise, min: 0.09, max: 0.46, speed: 3, seed: 5701)
let osc4 = osc(type: oscKind.noise, min: 0.39, max: 0.8, speed: 5)

mandala(
  scale: 20,
  rotation: -157.326,
  thickness: 0.762,
  smoothness: 0.074,
  symmetry: 15,
  bindu: true,
  layers: 4,
  layerSpacing: 2.1,
  twist: 13.65,
  shapeGrowth: 0.435,
  fgColor: #d4a70c,
  bgColor: #f8642b,
  animation: ripple,
  pulseDepth: 0.603
)
  .write(o0)

mandala(
  scale: 20,
  rotation: -140.991,
  thickness: 0.133,
  smoothness: 0.87,
  symmetry: 22,
  bindu: true,
  layers: 10,
  layerSpacing: 0.589,
  twist: 10.19,
  shapeGrowth: 0.556,
  fgColor: #5ad28d,
  bgColor: #c56d1c,
  animation: spiralWave,
  speed: -1,
  pulseDepth: 0.356
)
  .blendMode(
    tex: read(o0),
    mode: hardLight,
    mix: -0.069
  )
  .write(o1)

mandala(
  scale: 13.86,
  rotation: 68.927,
  thickness: 0.974,
  smoothness: 0.423,
  symmetry: 22,
  shape: triangle,
  layers: 12,
  layerSpacing: 2.44,
  twist: 2.37,
  shapeGrowth: 0.574,
  fgColor: #cb49c6,
  bgColor: #f51832,
  animation: ripple,
  speed: -1,
  pulseDepth: 0.857
)
  .blendMode(
    tex: read(o1),
    mode: hardLight,
    mix: 6.769
  )
  .tetraCosine(
    offsetR: 0.843,
    offsetG: 0.262,
    offsetB: 0.103,
    ampR: 0.79,
    ampG: 0.273,
    ampB: 0.533,
    freqR: 4,
    freqG: 3,
    freqB: 0,
    phaseR: 0.873,
    phaseG: 0.838,
    phaseB: 0.182,
    rotation: back,
    repeat: 5.38,
    alpha: 0.715
  )
  .celShading(
    levels: 2,
    gamma: 0.3,
    edgeWidth: 0,
    edgeThreshold: 0.51,
    edgeColor: #340001
  )
  .write(o2)

render(o2)