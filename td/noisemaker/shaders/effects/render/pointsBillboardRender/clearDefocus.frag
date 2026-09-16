// NM_INPUTS: (none)
// NM_OUTPUT: fragColor
uniform float clearValue;
out vec4 fragColor;
void nm_main() {
    fragColor = vec4(clearValue);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
