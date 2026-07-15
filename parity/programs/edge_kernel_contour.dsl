search synth, filter
noise(seed: 1, scaleX: 50, scaleY: 50).edge(kernel: contour, contourSide: upper, invert: on).write(o0)
render(o0)
