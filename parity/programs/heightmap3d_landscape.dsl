search synth, synth3d, render

noise(scaleX: 90, scaleY: 90, colorMode: mono, speed: 0).write(o1)
gradient(type: fourCorners, color1: #006e94, color2: #24e4ff, color3: #bcff46, color4: #efffff).write(o2)
heightmap3d(heightTex: read(o1), tex: read(o2)).renderLandscape3d(panY: -0.18).write(o0)
render(o0)
