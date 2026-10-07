search synth3d, filter3d, render
read3d(vol1, geo1).palette3d().renderLandscape3d().write(o0)
read3d(vol0, geo0).write3d(vol1, geo1)
heightmap3d(volumeSize: x16).write3d(vol0, geo0)
render(o0)
