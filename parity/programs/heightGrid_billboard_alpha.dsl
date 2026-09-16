search synth, points, render

perlin(scale: 35, colorMode: rgb)
  .write(o1)

perlin(scale: 22, octaves: 4, colorMode: mono)
  .write(o2)

solid()
  .pointsEmit(stateSize: x256)
  .heightGrid(heightTex: read(o2), diffuseTex: read(o1), heightScale: 25)
  .pointsBillboardRender(viewMode: perspective, blendMode: alpha, rotateX: 0.55, posY: -12, posZ: 22, pointSize: 3, density: 100, intensity: 0, inputIntensity: 0, depositOpacity: 65)
  .write(o0)

render(o0)
