search synth, synth3d, render

pattern(type: stripes, scale: 20, thickness: 0.5, smoothness: 0.02).write(o1)
heightmap3d(heightTex: read(o1), tex: solid(color: #ffffff), volumeSize: x16, heightScale: 1, baseHeight: 0).renderLandscape3d(viewMode: perspective, rotateX: 0, lightDirection: vec3(-1, 0, 0), ambient: 0, diffuseIntensity: 1, specularIntensity: 0, bgAlpha: 0).write(o0)
render(o0)
