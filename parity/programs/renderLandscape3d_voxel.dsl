search synth, synth3d, render

testPattern(pattern: gradient).write(o1)
testPattern(pattern: colorBars).write(o2)
heightmap3d(heightTex: read(o1), tex: read(o2), volumeSize: x32, heightScale: 0.6, baseHeight: 0.1).renderLandscape3d(panY: -0.18).write(o0)
render(o0)
