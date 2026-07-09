// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Median - 3x3 box median pass. Executed `iterations` times per frame (pass
 * repeat), ping-ponging the global_median_state surface: each iteration
 * reads the previous iteration's result and writes the next one. Uses the
 * standard 9-element min/max exchange network (Devillard opt_med9) applied
 * per RGB channel -- 19 compare-exchange ops, element 4 ends up holding the
 * median.
 */



uniform vec2 resolution;

out vec4 fragColor;

void sort2(inout vec3 a, inout vec3 b) {
    vec3 lo = min(a, b);
    vec3 hi = max(a, b);
    a = lo;
    b = hi;
}

void nm_main() {
    vec2 texel = 1.0 / resolution;
    vec2 uv = gl_FragCoord.xy / resolution;

    vec4 s0 = texture(inputTex, uv + vec2(-texel.x, -texel.y));
    vec4 s1 = texture(inputTex, uv + vec2(0.0, -texel.y));
    vec4 s2 = texture(inputTex, uv + vec2(texel.x, -texel.y));
    vec4 s3 = texture(inputTex, uv + vec2(-texel.x, 0.0));
    vec4 s4 = texture(inputTex, uv);
    vec4 s5 = texture(inputTex, uv + vec2(texel.x, 0.0));
    vec4 s6 = texture(inputTex, uv + vec2(-texel.x, texel.y));
    vec4 s7 = texture(inputTex, uv + vec2(0.0, texel.y));
    vec4 s8 = texture(inputTex, uv + vec2(texel.x, texel.y));

    vec3 p0 = s0.rgb; vec3 p1 = s1.rgb; vec3 p2 = s2.rgb;
    vec3 p3 = s3.rgb; vec3 p4 = s4.rgb; vec3 p5 = s5.rgb;
    vec3 p6 = s6.rgb; vec3 p7 = s7.rgb; vec3 p8 = s8.rgb;

    sort2(p1, p2); sort2(p4, p5); sort2(p7, p8);
    sort2(p0, p1); sort2(p3, p4); sort2(p6, p7);
    sort2(p1, p2); sort2(p4, p5); sort2(p7, p8);
    sort2(p0, p3); sort2(p5, p8); sort2(p4, p7);
    sort2(p3, p6); sort2(p1, p4); sort2(p2, p5);
    sort2(p4, p7); sort2(p4, p2); sort2(p6, p4);
    sort2(p4, p2);

    fragColor = vec4(p4, s4.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
