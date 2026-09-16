search synth
noise(seed: 3, scaleX: 30, scaleY: 30).write(o0)
remap(zoneCount: 1, zone0_count: 3, zone0_v0: [0.2, 0.2, 0.8, 0.25], zone0_v1: [0.5, 0.85, 0.0, 0.0], zone0_tex: read(o0), bgColor: [0.05, 0.05, 0.12]).write(o1)
render(o1)
