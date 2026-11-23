search synth, synth3d, render

pattern(type: checkerboard, scale: 20, smoothness: 0.02).write(o1)
heightmap3d(heightTex: read(o1), tex: solid(color: #ffffff), volumeSize: x16, heightScale: 1, baseHeight: 0).renderLandscape3d(lightDirection: vec3(0, 0, 1), ambient: 0, diffuseIntensity: 1, specularIntensity: 0, bgAlpha: 0).write(o0)
render(o0)
