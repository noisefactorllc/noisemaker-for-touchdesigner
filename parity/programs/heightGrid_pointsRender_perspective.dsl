search synth, points, render

perlin(scale: 35, colorMode: rgb)
  .write(o1)

perlin(scale: 22, octaves: 4, colorMode: mono)
  .write(o2)

solid()
  .pointsEmit(stateSize: x256)
  .heightGrid(heightTex: read(o2), diffuseTex: read(o1), heightScale: 25)
  .pointsRender(viewMode: perspective, rotateX: 0.55, posY: -12, posZ: 22, fieldOfView: 70)
  .write(o0)

render(o0)
