"""deposit_shaders.py — TouchDesigner GLSL MAT shaders for the agent-scatter (deposit) passes.

The reference `render/pointsRender/glsl/deposit.{vert,frag}` and `pointsBillboardRender/...` run as
a bufferless `gl.drawArrays(POINTS|TRIANGLES, 0, N|N*6)` keyed off `gl_VertexID`. TD has no
bufferless draw: the deposit is a Geo COMP + this GLSL MAT + a Render TOP (see
docs/TD-PLATFORM-NOTES.md "GPU point scatter"). Points use a Grid SOP converted to point sprites, and
the agent index is recovered from the grid point POSITION (`TDPos()`), validated bit-for-placement by
td/points_probe.py. Billboards instance a corner-at-+-1 rectangle once per agent, so
`TDInstanceID()` is the agent index and `TDPos()` the quad corner. Math, culling, view transform, and
the fragment shading are mirrored verbatim from the reference.

These are MAT vertex/pixel shaders (TDPos / TDInstanceID / TDOutputSwizzle, direct gl_Position NDC),
not fullscreen TOP frags, so they live here rather than in the auto-transpiled shaders/ tree.

Reference 0ed489ec adds to both deposit programs: a perspective VIEW_MODE (2), sharing a camera
model at world Z=80 (posZ/fieldOfView). pointsBillboardRender additionally adds a depth-sorted
alpha-blend path (BLEND_MODE 1 reindexes the scatter through `orderTex`, produced by depthKeys +
depthMerge) and aperture defocus blur (spriteMeanTiles/spriteMean precompute + a blurred `defocus`
composite). All three are ported verbatim on the instanced quads. `BLUR_LAYER` (1 for
depositDefocus, 0 otherwise) is injected as a `#define` per pass clone, exactly as the reference
compiles it.
"""

# Shared vertex prologue: recover the agent texel (x,y) and linear id from the grid point position,
# fetch state, density-cull, and compute the 2D/3D clip position EXACTLY as the reference does.
# (`stateSize` is the agent grid width; `vid = y*ss + x` reproduces the reference gl_VertexID so the
# golden-ratio density random matches.)
_VERT_PROLOGUE = """uniform sampler2D xyzTex;
uniform sampler2D rgbaTex;
uniform vec2 resolution;
uniform float density;
uniform float viewMode;     // float (TD Vectors page is float-only); cast to int in-shader
uniform float rotateX;
uniform float rotateY;
uniform float rotateZ;
uniform float viewScale;
uniform float posX;
uniform float posY;
uniform float posZ;
uniform float fieldOfView;

int nm_agentTexel(out int vid, out int ax, out int ay) {
    int ss = textureSize(xyzTex, 0).x;   // agent grid width (reference reads stateSize from the tex)
    vec3 gp = TDPos();
    int x = int(floor((gp.x * 0.5 + 0.5) * float(ss - 1) + 0.5));
    int y = int(floor((gp.y * 0.5 + 0.5) * float(ss - 1) + 0.5));
    x = clamp(x, 0, ss - 1);
    y = clamp(y, 0, ss - 1);
    vid = y * ss + x;
    ax = x; ay = y;
    return ss;
}

// Density cull: the reference's exact float32 expression `fract(float(gl_VertexID) * GR)`, GR the
// golden ratio. Its rounding at large ids is part of the reference result: at stateSize 256 an
// exact hi/lo split drops agents the reference deposits.
float nm_particleRandom(int vid) {
    return fract(float(vid) * 0.618033988749895);
}

// Reference 0ed489ec: shared Z=80 camera model with renderLandscape3d/pointsBillboardRender.
// `cameraDepth` (world depth in front of the camera) is always written; callers that don't need
// perspective sizing (pointsRender) can ignore it. Returns vec2(2.0) (the existing off-screen
// sentinel) when the near plane would be crossed, matching the reference's explicit cull.
vec2 nm_clipPos(vec4 pos, out float cameraDepth, out vec2 worldXY) {
    int vm = int(viewMode + 0.5);
    cameraDepth = 80.0;
    worldXY = vec2(0.0);
    if (vm == 0) {
        return pos.xy * 2.0 - 1.0;
    }
    vec3 p = pos.xyz;
    bool is2D = vm == 1 && abs(p.z) < 1.0 && p.x >= 0.0 && p.x <= 1.0 && p.y >= 0.0 && p.y <= 1.0;
    if (is2D) { p.xy = p.xy - 0.5; p.z = 0.0; }
    float cx = cos(rotateX), sx = sin(rotateX);
    p = vec3(p.x, p.y * cx - p.z * sx, p.y * sx + p.z * cx);
    float cy = cos(rotateY), sy = sin(rotateY);
    p = vec3(p.x * cy + p.z * sy, p.y, -p.x * sy + p.z * cy);
    float cz = cos(rotateZ), sz = sin(rotateZ);
    p = vec3(p.x * cz - p.y * sz, p.x * sz + p.y * cz, p.z);
    p.x += posX; p.y += posY; p.z += posZ;
    cameraDepth = 80.0 - p.z;
    worldXY = p.xy;
    if (vm == 2) {
        if (cameraDepth <= 0.1) { return vec2(2.0, 2.0); }
        float focalLength = 1.0 / tan(clamp(fieldOfView, 10.0, 150.0) * 0.00872664626);
        vec2 clipPos = p.xy * focalLength * viewScale / cameraDepth;
        clipPos.x *= resolution.y / resolution.x;
        return clipPos;
    } else if (is2D) {
        return p.xy * 3.5 * viewScale;
    } else {
        return p.xy / 40.0 * viewScale;
    }
}
"""

# ---- pointsRender: one GL_POINT (gl_PointSize 1) per live, un-culled agent ----------------------
POINTS_VERT = _VERT_PROLOGUE + """
out vec4 vColor;
void main() {
    int vid, ax, ay;
    nm_agentTexel(vid, ax, ay);
    vec4 pos = texelFetch(xyzTex, ivec2(ax, ay), 0);
    vec4 col = texelFetch(rgbaTex, ivec2(ax, ay), 0);
    float cullThreshold = density / 100.0;
    float particleRandom = nm_particleRandom(vid);
    if (particleRandom > cullThreshold || pos.w < 0.5) {
        gl_Position = vec4(2.0, 2.0, 0.0, 1.0); gl_PointSize = 0.0; vColor = vec4(0.0); return;
    }
    float cameraDepth; vec2 worldXY;
    gl_PointSize = 1.0;
    gl_Position = vec4(nm_clipPos(pos, cameraDepth, worldXY), 0.0, 1.0);
    vColor = vec4(col.rgb, col.a);
}
"""

POINTS_FRAG = """in vec4 vColor;
layout(location = 0) out vec4 fragColor;
void main() {
    fragColor = TDOutputSwizzle(vColor);
}
"""

# ---- pointsBillboardRender: one instanced quad per agent; SDF/sprite shading in the frag ----------
# Mirrors render/pointsBillboardRender/glsl/deposit.vert. The Geo COMP instances a corner-at-+-1
# rectangle once per agent: TDInstanceID() is the reference's gl_VertexID / 6 and TDPos().xy the
# quad corner `offset`. BLUR_LAYER is a per-pass `#define` injected by td_backend.py.
BILLBOARD_VERT = """uniform sampler2D xyzTex;
uniform sampler2D rgbaTex;
uniform sampler2D orderTex;   // depthKeys+depthMerge output; read only when blendMode==1
uniform vec2 resolution;
uniform float density;
uniform float viewMode;       // float (TD Vectors page is float-only); cast to int in-shader
uniform float rotateX;
uniform float rotateY;
uniform float rotateZ;
uniform float viewScale;
uniform float posX;
uniform float posY;
uniform float posZ;
uniform float fieldOfView;
uniform float blendMode;
uniform float shapeMode;
uniform float pointSize;
uniform float sizeVariation;
uniform float rotationVar;
uniform float seed;
uniform float sizeDistance;
uniform float brightnessDistance;
uniform float aperture;
uniform float focalDistance;
out vec4 vColor;
out vec2 vSpriteUV;
out float vBlurRadius;
uint hash_uint(uint s) {
    uint state = s * 747796405u + 2891336453u;
    uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}
float hash(float n) {
    return float(hash_uint(floatBitsToUint(n + seed))) / 4294967295.0;
}
void nm_cull() {
    gl_Position = vec4(2.0, 2.0, 0.0, 1.0);
    vColor = vec4(0.0);
    vSpriteUV = vec2(0.0);
}
void main() {
    vBlurRadius = 0.0;
    int vm = int(viewMode + 0.5);
    int bm = int(blendMode + 0.5);
    int sm = int(shapeMode + 0.5);
#if BLUR_LAYER == 1
    if (aperture <= 0.0) { nm_cull(); return; }
#endif
    int particleID = TDInstanceID();
    ivec2 texSize = textureSize(xyzTex, 0);
    int stateSize = texSize.x;
    if (particleID >= stateSize * stateSize) { nm_cull(); return; }
    if (bm == 1 && vm != 0) {
        particleID = int(texelFetch(orderTex, ivec2(particleID % stateSize, particleID / stateSize), 0).g);
    }
    float cullThreshold = density / 100.0;
    float particleRandom = fract(float(particleID) * 0.618033988749895);
    if (particleRandom > cullThreshold) { nm_cull(); return; }
    int x = particleID % stateSize;
    int y = particleID / stateSize;
    vec4 pos = texelFetch(xyzTex, ivec2(x, y), 0);
    vec4 col = texelFetch(rgbaTex, ivec2(x, y), 0);
    if (pos.w < 0.5) { nm_cull(); return; }
    vec2 clipPos;
    float cameraDepth = 80.0;
    float cameraDistance = 0.0;
    float projectedScale = 1.0;
    if (vm == 0) {
        clipPos = pos.xy * 2.0 - 1.0;
    } else {
        vec3 p = pos.xyz;
        bool is2DSystem = vm == 1 && abs(p.z) < 1.0 && p.x >= 0.0 && p.x <= 1.0 && p.y >= 0.0 && p.y <= 1.0;
        if (is2DSystem) {
            p.xy = p.xy - 0.5;
            p.z = 0.0;
        }
        float cosX = cos(rotateX);
        float sinX = sin(rotateX);
        p = vec3(p.x, p.y * cosX - p.z * sinX, p.y * sinX + p.z * cosX);
        float cosY = cos(rotateY);
        float sinY = sin(rotateY);
        p = vec3(p.x * cosY + p.z * sinY, p.y, -p.x * sinY + p.z * cosY);
        float cosZ = cos(rotateZ);
        float sinZ = sin(rotateZ);
        p = vec3(p.x * cosZ - p.y * sinZ, p.x * sinZ + p.y * cosZ, p.z);
        p.x += posX;
        p.y += posY;
        p.z += posZ;
        cameraDepth = 80.0 - p.z;
        cameraDistance = length(vec3(p.xy, cameraDepth));
        if (vm == 2) {
            if (cameraDepth <= 0.1) { nm_cull(); return; }
            float focalLength = 1.0 / tan(clamp(fieldOfView, 10.0, 150.0) * 0.00872664626);
            clipPos = p.xy * focalLength * viewScale / cameraDepth;
            clipPos.x *= resolution.y / resolution.x;
            projectedScale = 80.0 * focalLength * viewScale / (1.732050808 * cameraDepth);
        } else if (is2DSystem) {
            clipPos = p.xy * 3.5 * viewScale;
        } else {
            clipPos = p.xy / 40.0 * viewScale;
        }
    }
    float sizeNoise = hash(float(particleID));
    float sizeMultiplier = 1.0 - (sizeVariation / 100.0) * (sizeNoise - 0.5);
    float sizeFade = 1.0;
    float brightnessFade = 1.0;
    float blurPixels = 0.0;
    if (vm != 0) {
        if (sizeDistance > 0.0) sizeFade = 1.0 - smoothstep(0.0, sizeDistance, cameraDistance);
        if (brightnessDistance > 0.0) brightnessFade = 1.0 - smoothstep(0.0, brightnessDistance, cameraDistance);
        blurPixels = min(32.0, aperture * abs(cameraDepth - focalDistance) / max(abs(cameraDepth), 0.1));
    }
    float baseSize = pointSize * sizeMultiplier * projectedScale;
    float blurRadius = blurPixels / max(baseSize, 0.001);
    float supportRadius = blurPixels > 0.0 ? max(blurRadius, 0.62582015) : 0.0;
    float supportPixels = blurPixels > 0.0 ? max(blurPixels, baseSize * 0.62582015) : 0.0;
    float lowWeight = bm == 0 ? smoothstep(4.0, 8.0, blurPixels * sizeFade) * smoothstep(0.5, 1.0, blurRadius) : 0.0;
    float layerWeight = BLUR_LAYER == 1 ? lowWeight : 1.0 - lowWeight;
    float blurPadding = blurPixels > 0.0 ? (sm == 0 ? 0.5 : (sm == 5 ? 0.04 : 0.0)) : 0.0;
    float finalSize = (baseSize * (1.0 + 2.0 * blurPadding) + 2.0 * supportPixels) * sizeFade;
    if (finalSize <= 0.0 || brightnessFade <= 0.0 || layerWeight <= 0.0) { nm_cull(); return; }
    vBlurRadius = blurRadius;
    float rotationNoise = hash(float(particleID) + 1234.5);
    float rotation = (rotationVar / 100.0) * rotationNoise * 6.283185;
    vec2 pixelToClip = 2.0 / resolution;
    float halfSize = finalSize * 0.5;
    vec2 sizeClip = halfSize * pixelToClip;
    vec2 offset = TDPos().xy;
    float cosR = cos(rotation);
    float sinR = sin(rotation);
    vec2 rotatedOffset = vec2(offset.x * cosR - offset.y * sinR, offset.x * sinR + offset.y * cosR);
    gl_Position = vec4(clipPos + rotatedOffset * sizeClip, 0.0, 1.0);
    vColor = col * brightnessFade * layerWeight;
    vSpriteUV = offset * (0.5 + blurPadding + supportRadius) + 0.5;
}
"""

# Fragment mirrors render/pointsBillboardRender/glsl/deposit.frag.
BILLBOARD_FRAG = """uniform sampler2D spriteTex;
uniform sampler2D spriteMeanTex;
uniform float shapeMode;     // float (TD Vectors page is float-only); cast to int in-shader
uniform float depositOpacity;
in vec4 vColor;
in vec2 vSpriteUV;
in float vBlurRadius;
layout(location = 0) out vec4 fragColor;
vec4 shadeSprite(vec2 uv) {
    int sm = int(shapeMode + 0.5);
    float opacity = depositOpacity / 100.0;
    if (sm == 0) {
        vec4 spriteColor = texture(spriteTex, uv);
        return vec4(spriteColor.rgb * vColor.rgb, spriteColor.a * vColor.a) * opacity;
    }
    vec2 p = uv - 0.5;
    float sdf;
    float alpha;
    if (sm == 1) {
        sdf = length(p) - 0.45;
    } else if (sm == 2) {
        sdf = abs(length(p) - 0.35) - 0.08;
    } else if (sm == 3) {
        sdf = max(abs(p.x), abs(p.y)) - 0.4;
    } else if (sm == 4) {
        sdf = abs(p.x) + abs(p.y) - 0.45;
    } else if (sm == 5) {
        float r = 0.25;
        float k = 1.732050808;
        vec2 t = vec2(abs(p.x) - r, p.y - 0.04 + r / k);
        if (t.x + k * t.y > 0.0) t = vec2(t.x - k * t.y, -k * t.x - t.y) / 2.0;
        t.x -= clamp(t.x, -2.0 * r, 0.0);
        sdf = -length(t) * sign(t.y);
    } else if (sm == 6) {
        float r = 0.35;
        float rf = 0.4;
        vec2 k1 = vec2(0.809016994375, -0.587785252292);
        vec2 k2 = vec2(-k1.x, k1.y);
        vec2 s = vec2(abs(p.x), p.y);
        s -= 2.0 * max(dot(k1, s), 0.0) * k1;
        s -= 2.0 * max(dot(k2, s), 0.0) * k2;
        s.x = abs(s.x);
        s.y -= r;
        vec2 ba = rf * vec2(-k1.y, k1.x) - vec2(0.0, 1.0);
        float h = clamp(dot(s, ba) / dot(ba, ba), 0.0, r);
        sdf = length(s - ba * h) * sign(s.y * ba.x - s.x * ba.y);
    } else {
        alpha = exp(-dot(p, p) * 8.0);
        return vec4(vColor.rgb * alpha, alpha * vColor.a) * opacity;
    }
    alpha = 1.0 - smoothstep(-0.02, 0.02, sdf);
    return vec4(vColor.rgb * alpha, alpha * vColor.a) * opacity;
}
vec4 blurSample(vec2 uv) {
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return vec4(0.0);
    return shadeSprite(uv);
}
float blurWeight(vec2 uv, vec2 center, float expansion) {
    vec2 p = (uv - center) / expansion;
    float gaussian = exp(-dot(p, p) / 0.0648) * (1.0 - smoothstep(0.45, 0.5, length(p)));
    float normalization = 1.0 / (0.19724318 * expansion * expansion);
    return gaussian * normalization;
}
vec4 shadeParticle() {
    if (vBlurRadius <= 0.0) return shadeSprite(vSpriteUV);
    int sm = int(shapeMode + 0.5);
    float expansion = max(1.0 + 2.0 * vBlurRadius, 2.2516403);
    vec4 blurred = vec4(0.0);
    if (sm == 0) {
        for (int y = 0; y < 5; y++) {
            for (int x = 0; x < 5; x++) {
                vec4 source = texelFetch(spriteMeanTex, ivec2(x, y), 0);
                blurred += source * blurWeight(vSpriteUV, vec2(x, y) / 4.0, expansion);
            }
        }
        blurred *= vColor * (depositOpacity / 100.0);
    } else {
        vec4 meanColor = texelFetch(spriteMeanTex, ivec2(0), 0) * vColor * (depositOpacity / 100.0);
        vec2 center = sm == 5 ? vec2(0.5, 0.54) : vec2(0.5);
        blurred = meanColor * blurWeight(vSpriteUV, center, expansion);
    }
    if (vBlurRadius >= 0.5) return blurred;
    return mix(blurSample(vSpriteUV), blurred, smoothstep(0.0, 0.5, vBlurRadius));
}
void main() {
    fragColor = TDOutputSwizzle(shadeParticle());
}
"""


# ---- filter3d/flow3d deposit: agents carry a 3D VOLUME position, scattered into a 2D atlas --------
# Distinct from the 2D pointsRender deposit above: flow3d's agents live in a volume (state1.xyz in
# VOXEL units [0,volSize)), and the trail is that volume stored as a 2D atlas (width=volSize,
# height=volSize², row = y + floor(z)·volSize). The cull is the reference's index threshold
# (maxAgents = maxDim·density·0.2), not the golden-ratio fract used by pointsRender. Mirrors
# filter3d/flow3d/glsl/deposit.vert verbatim; only gl_VertexID -> the grid texel (xyzTex == stateTex1,
# rgbaTex == stateTex2) changes, exactly as for the 2D deposit. See docs/TD-PLATFORM-NOTES.md.
FLOW3D_VERT = """uniform sampler2D xyzTex;   // stateTex1: xyz = 3D voxel position
uniform sampler2D rgbaTex;  // stateTex2: rgb = agent color
uniform float density;
uniform int volumeSize;
out vec4 vColor;
void main() {
    ivec2 sz = textureSize(xyzTex, 0);
    int texW = sz.x, texH = sz.y;
    vec3 gp = TDPos();
    int x = clamp(int(floor((gp.x * 0.5 + 0.5) * float(texW - 1) + 0.5)), 0, texW - 1);
    int y = clamp(int(floor((gp.y * 0.5 + 0.5) * float(texH - 1) + 0.5)), 0, texH - 1);
    int agentIndex = y * texW + x;                 // == reference gl_VertexID (texW == stateSize)
    int maxAgents = int(float(max(texW, texH)) * density * 0.2);
    if (agentIndex >= maxAgents) {
        gl_Position = vec4(2.0, 2.0, 0.0, 1.0); gl_PointSize = 0.0; vColor = vec4(0.0); return;
    }
    vec4 state1 = texelFetch(xyzTex, ivec2(x, y), 0);
    vec4 state2 = texelFetch(rgbaTex, ivec2(x, y), 0);
    float volF = float(volumeSize);
    float atlasX = state1.x;                        // voxel x in [0,volSize)
    float atlasY = state1.y + floor(state1.z) * volF;   // atlas row = y + z·volSize
    vec2 ndc = vec2((atlasX / volF) * 2.0 - 1.0, (atlasY / (volF * volF)) * 2.0 - 1.0);
    gl_Position = vec4(ndc, 0.0, 1.0);
    gl_PointSize = 1.0;
    vColor = vec4(state2.rgb, 1.0);
}
"""


def shaders_for(draw_mode):
    """(vertex_src, fragment_src) for a deposit pass: 'points', 'billboards', or 'points3d'.

    'points3d' is the filter3d/flow3d volume-atlas deposit (agents in voxel space); it reuses the
    plain points fragment (straight additive color write)."""
    if draw_mode == 'billboards':
        return BILLBOARD_VERT, BILLBOARD_FRAG
    if draw_mode == 'points3d':
        return FLOW3D_VERT, POINTS_FRAG
    return POINTS_VERT, POINTS_FRAG
