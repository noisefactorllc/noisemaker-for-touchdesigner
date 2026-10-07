search synth3d, filter3d, render
heightmap3d(volumeSize: x16).write3d(vol0, geo0)
read3d(vol0, geo0).palette3d().write3d(vol0, geo0)
read3d(vol0, geo0).palette3d().write3d(vol0, geo0)
read3d(vol0, geo0).renderLandscape3d().write(o0)
render(o0)
