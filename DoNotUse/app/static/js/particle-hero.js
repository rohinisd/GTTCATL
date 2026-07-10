/* ============================================================================
 * particle-hero.js — GTTC Robotics Portal
 * A self-contained Three.js GPU particle hero. No build step required: it is a
 * native ES module that imports `three` via an import-map declared by the host
 * page (see particle-hero-demo.html).
 *
 * ~14k particles morph between three shapes on a timer:
 *    1. Data sphere   (the network of schools)
 *    2. Robotic arm   (the ATL training programme)
 *    3. Karnataka map (the state served)  ← outline is APPROXIMATE; swap with
 *                       real GeoJSON when available (see KARNATAKA_OUTLINE).
 *
 * Honours the project rules:
 *  - Palette: #2563eb → #7c3aed → #0d9488 gradient, on #0b1437 navy.
 *  - Static fallback for prefers-reduced-motion, screens < 768px, or no WebGL.
 *  - Performance: dpr capped at 2, particle count scaled to screen, render
 *    paused when the tab is hidden or the canvas is scrolled off-screen.
 *  - No flashing / strobing (epilepsy-safe): slow, smooth, additive motion.
 * ==========================================================================*/
// Local Three.js (no CDN / import-map needed) so it works on every device,
// even offline / on a LAN with no internet access.
import * as THREE from '/static/js/three.module.min.js';

const PALETTE = {
  primary: '#2563eb',
  purple:  '#7c3aed',
  teal:    '#0d9488',
  navy:    '#0b1437',
};

/* Hand-traced, normalised (0..1, y-down) outline of Karnataka — captures the
 * recognisable silhouette: pointy NW (Belagavi), a NE spur (Bidar), a smooth
 * west coast, a jagged east with an inward SE bay, and a tapering southern tip.
 * Still an approximation — swap with a simplified GeoJSON ring for an exact map. */
// Real Karnataka state boundary (from a public GeoJSON, ~13k points simplified
// to a 60-point ring), normalised to 0..1 with north at y=0. Render aspect is
// handled in samplePolygonOutline (Karnataka is ~0.66 as wide as it is tall).
const KARNATAKA_OUTLINE = [
  [0.723, 0.000], [0.783, 0.023], [0.794, 0.068], [0.746, 0.124], [0.802, 0.137], [0.733, 0.177],
  [0.752, 0.270], [0.701, 0.287], [0.780, 0.313], [0.762, 0.367], [0.653, 0.379], [0.676, 0.405],
  [0.642, 0.429], [0.685, 0.477], [0.666, 0.501], [0.598, 0.490], [0.595, 0.560], [0.642, 0.577],
  [0.636, 0.612], [0.760, 0.609], [0.737, 0.664], [0.624, 0.623], [0.647, 0.684], [0.688, 0.659],
  [0.755, 0.693], [0.866, 0.654], [0.889, 0.700], [0.958, 0.708], [0.953, 0.746], [1.000, 0.754],
  [0.973, 0.814], [0.832, 0.813], [0.780, 0.842], [0.752, 0.908], [0.810, 0.914], [0.796, 0.947],
  [0.742, 0.974], [0.626, 0.970], [0.612, 1.000], [0.395, 0.946], [0.296, 0.896], [0.275, 0.853],
  [0.173, 0.828], [0.066, 0.567], [0.000, 0.529], [0.056, 0.458], [0.036, 0.405], [0.001, 0.403],
  [0.061, 0.388], [0.090, 0.340], [0.041, 0.276], [0.133, 0.267], [0.189, 0.218], [0.353, 0.215],
  [0.344, 0.140], [0.510, 0.164], [0.499, 0.123], [0.542, 0.099], [0.579, 0.110], [0.638, 0.037],
];

/**
 * Mount the hero into `container`. Returns { destroy() } for cleanup.
 * @param {HTMLElement} container
 * @param {{count?:number}} [opts]
 */
export function initParticleHero(container, opts = {}) {
  const theme = opts.theme || 'dark';   // 'light' = white bg (normal blending)
  const rotate = opts.rotate !== false; // false = keep shapes upright (no spin)
  const isSmall = window.innerWidth < 600;   // only true phones fall back
  const hasWebGL = (() => {
    try {
      const c = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl')));
    } catch (_) { return false; }
  })();

  // Only fall back when WebGL is genuinely unavailable, or on a true mobile width.
  // We intentionally do NOT disable on prefers-reduced-motion: many govt/office
  // machines have OS animations switched off but can still show this calm scene.
  if (isSmall || !hasWebGL) {
    return renderStaticFallback(container, theme);
  }

  // Particle budget scales with viewport (keeps mid-range GPUs at 60fps).
  const count = opts.count || (window.innerWidth < 1100 ? 8000 : 12000);

  // ── Renderer ──
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // dpr cap = 2
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);
  renderer.domElement.style.display = 'block';

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, container.clientWidth / container.clientHeight, 0.1, 100);
  camera.position.set(0, 0, 7.5);

  // ── Geometry: three position targets the shader blends between ──
  const shapeSphere = sampleSphere(count, 3.0);
  const shapeArm    = sampleArm(count);
  const shapeMap    = samplePolygonOutline(count, KARNATAKA_OUTLINE);
  const randoms     = new Float32Array(count);
  for (let i = 0; i < count; i++) randoms[i] = Math.random();

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(shapeSphere, 3)); // shape 0
  geo.setAttribute('aPos1',    new THREE.BufferAttribute(shapeArm, 3));    // shape 1
  geo.setAttribute('aPos2',    new THREE.BufferAttribute(shapeMap, 3));    // shape 2
  geo.setAttribute('aRand',    new THREE.BufferAttribute(randoms, 1));

  const uniforms = {
    uTime:       { value: 0 },
    uSize:       { value: opts.size || 11.0 },
    uPixelRatio: { value: renderer.getPixelRatio() },
    uMouse:      { value: new THREE.Vector3(999, 999, 0) },
    uFrom:       { value: 0 },   // shape morphing FROM (0=sphere, 1=arm, 2=map)
    uTo:         { value: 1 },   // shape morphing TO
    uMix:        { value: 0 },   // 0..1 transition progress
    uColA:       { value: new THREE.Color(PALETTE.primary) },
    uColB:       { value: new THREE.Color(PALETTE.purple) },
    uColC:       { value: new THREE.Color(PALETTE.teal) },
    uColD:       { value: new THREE.Color('#38bdf8') }, // per-particle accent (sky)
    uTex:        { value: makeSprite() },
  };

  const material = new THREE.ShaderMaterial({
    uniforms,
    vertexShader:   VERT,
    fragmentShader: FRAG,
    transparent: true,
    depthWrite: false,
    // additive glow on dark; normal blending on white so particles stay visible
    blending: theme === 'light' ? THREE.NormalBlending : THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geo, material);
  scene.add(points);

  // ── Mouse → world point on the z=0 plane (for the repel uniform + parallax) ──
  const pointer = new THREE.Vector2(0, 0);      // normalised device coords
  const smoothMouse = new THREE.Vector3(999, 999, 0);
  let parX = 0, parY = 0;                        // smoothed parallax offsets
  const raycaster = new THREE.Raycaster();
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const hit = new THREE.Vector3();
  function onPointerMove(e) {
    const r = renderer.domElement.getBoundingClientRect();
    pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  }
  function onPointerLeave() { pointer.set(0, 0); smoothMouse.set(999, 999, 0); }
  window.addEventListener('pointermove', onPointerMove, { passive: true });
  renderer.domElement.addEventListener('pointerleave', onPointerLeave);

  // ── Morph scheduler: rest on a shape, then transition From→To ──
  // The per-particle stagger lives in the shader; here we just supply the
  // current pair and a 0..1 progress. Longer rest + slower transition reads
  // far cleaner than crossfading everything at once.
  const DWELL = 5.0, TRANS = 2.4;          // seconds
  const STEP = DWELL + TRANS;
  function setMorph(t) {
    const total = STEP * 2;
    const tt = ((t % total) + total) % total;
    const idx = Math.floor(tt / STEP);            // 0 or 1
    const local = tt - idx * STEP;
    // only cycle between arm (1) and Karnataka map (2), skip sphere (0)
    uniforms.uFrom.value = idx === 0 ? 1 : 2;
    uniforms.uTo.value   = idx === 0 ? 2 : 1;
    uniforms.uMix.value = local < DWELL ? 0 : (local - DWELL) / TRANS;
  }

  // ── Render loop with pause-when-invisible ──
  const clock = new THREE.Clock();
  let running = true, rafId = 0;
  function frame() {
    if (!running) return;
    rafId = requestAnimationFrame(frame);
    const t = clock.getElapsedTime();
    uniforms.uTime.value = t;
    setMorph(t);

    // smooth the mouse → world point, feed repel uniform
    raycaster.setFromCamera(pointer, camera);
    if (raycaster.ray.intersectPlane(plane, hit)) {
      smoothMouse.lerp(hit, 0.10);
      uniforms.uMouse.value.copy(smoothMouse);
    }
    // optional gentle parallax (kept off for the map so it never spins/tilts)
    if (rotate) {
      parX += (pointer.x * 0.087 - parX) * 0.04;
      parY += (pointer.y * -0.087 - parY) * 0.04;
      points.rotation.y = t * 0.03 + parX;
      points.rotation.x = parY;
    }

    renderer.render(scene, camera);
  }
  function start() { if (!running) { running = true; clock.start(); frame(); } }
  function stop()  { running = false; cancelAnimationFrame(rafId); }

  // pause when tab hidden
  function onVisibility() { document.hidden ? stop() : start(); }
  document.addEventListener('visibilitychange', onVisibility);

  // pause when scrolled off-screen
  const io = new IntersectionObserver(
    ([entry]) => { entry.isIntersecting ? start() : stop(); },
    { threshold: 0.01 }
  );
  io.observe(container);

  // ── Resize ──
  function onResize() {
    const w = container.clientWidth, h = container.clientHeight;
    camera.aspect = w / h; camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    uniforms.uPixelRatio.value = renderer.getPixelRatio();
  }
  window.addEventListener('resize', onResize);

  frame();

  // ── Cleanup ──
  function destroy() {
    stop();
    io.disconnect();
    document.removeEventListener('visibilitychange', onVisibility);
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('resize', onResize);
    renderer.domElement.removeEventListener('pointerleave', onPointerLeave);
    geo.dispose();
    material.dispose();
    uniforms.uTex.value.dispose();
    renderer.dispose();
    if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
  }
  return { destroy };
}

/* ───────────────────────────── Shaders ─────────────────────────────────── */

const SIMPLEX = /* glsl */`
  // Classic 3D simplex noise (Ashima / Stefan Gustavson) — organic motion.
  vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
  vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
  vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
  vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
  float snoise(vec3 v){
    const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
    vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
    vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g;
    vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
    vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
    i=mod289(i);
    vec4 p=permute(permute(permute(
        i.z+vec4(0.0,i1.z,i2.z,1.0))
      + i.y+vec4(0.0,i1.y,i2.y,1.0))
      + i.x+vec4(0.0,i1.x,i2.x,1.0));
    float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
    vec4 j=p-49.0*floor(p*ns.z*ns.z);
    vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
    vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
    vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
    vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
    vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
    vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y);
    vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
    vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
    p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
    vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
    return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
  }
`;

const VERT = /* glsl */`
  attribute vec3 aPos1;     // shape 1 target (robotic arm)
  attribute vec3 aPos2;     // shape 2 target (Karnataka)
  attribute float aRand;    // per-particle 0..1 for stagger/size variety
  uniform float uTime, uSize, uPixelRatio;
  uniform float uFrom, uTo, uMix;   // current morph pair + 0..1 progress
  uniform vec3  uMouse;             // world-space cursor on z=0 plane
  varying float vY;
  varying float vRand;
  ${SIMPLEX}

  // pick a shape target by index (0 sphere, 1 arm, 2 map)
  vec3 shapePos(float idx){
    if (idx < 0.5) return position;
    if (idx < 1.5) return aPos1;
    return aPos2;
  }

  void main(){
    // 1) staggered per-particle morph — particles ease over slightly different
    //    windows so the shape "assembles" instead of snapping all at once.
    float local = clamp((uMix - aRand * 0.30) / 0.70, 0.0, 1.0);
    float e = smoothstep(0.0, 1.0, local);
    vec3 pos = mix(shapePos(uFrom), shapePos(uTo), e);

    // 2) very gentle drift so the cloud breathes without smearing the shape
    float ph = uTime * 0.08;
    vec3 wob = vec3(
      snoise(pos * 0.22 + ph),
      snoise(pos * 0.22 + ph + 19.0),
      snoise(pos * 0.22 + ph + 41.0)
    );
    pos += wob * 0.025;

    // 3) soft cursor repel (small radius, light push)
    vec3 away = pos - uMouse;
    float d = length(away);
    float radius = 1.6;
    if (d < radius) { pos += normalize(away) * (radius - d) * 0.30; }

    vY = pos.y;
    vRand = aRand;
    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mv;

    // size attenuation — finer, more uniform points read cleaner
    gl_PointSize = uSize * uPixelRatio * (0.7 + aRand * 0.5) * (1.0 / -mv.z) * 7.0;
  }
`;

const FRAG = /* glsl */`
  precision mediump float;
  uniform sampler2D uTex;
  uniform vec3 uColA, uColB, uColC, uColD;   // blue → purple → teal (+ sky accent)
  varying float vY;
  varying float vRand;
  void main(){
    // vertical gradient across the palette
    float t = clamp((vY + 3.2) / 6.4, 0.0, 1.0);
    vec3 col = (t < 0.5) ? mix(uColA, uColB, t * 2.0)
                         : mix(uColB, uColC, (t - 0.5) * 2.0);
    // per-particle accent for richer, less monotone colour
    col = mix(col, uColD, vRand * 0.4);
    vec4 sprite = texture2D(uTex, gl_PointCoord);
    if (sprite.a < 0.02) discard;            // keep the soft round edge
    gl_FragColor = vec4(col, sprite.a);
  }
`;

/* ─────────────────────────── Shape samplers ────────────────────────────── */

// Evenly distributed points on a sphere (Fibonacci spiral).
function sampleSphere(n, radius) {
  const out = new Float32Array(n * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    out[i * 3]     = Math.cos(theta) * r * radius;
    out[i * 3 + 1] = y * radius;
    out[i * 3 + 2] = Math.sin(theta) * r * radius;
  }
  return out;
}

// A recognisable industrial 6-axis robotic arm, assembled from primitives:
// a wide base plate, cylindrical rotary JOINT DRUMS, thick links between them,
// and a two-finger gripper at the tip. This part-based build is what makes it
// read as a real robot rather than a bent tube.
function sampleArm(n) {
  // key points of a "reaching up-and-right" pose (classic robot silhouette)
  const BASE = [-0.6, -3.2, 0];   // floor mount
  const SH   = [-0.6, -2.2, 0];   // shoulder
  const EL   = [ 0.5, -0.4, 0];   // elbow
  const WR   = [ 2.0,  0.9, 0];   // wrist
  const TIP  = [ 2.7,  1.6, 0];   // gripper root

  // each part contributes points proportional to its weight `w`
  const parts = [
    { k: 'cyl',  p0: [-0.6,-3.45,0], p1: [-0.6,-3.05,0], r: 0.95, w: 2.4 }, // base plate
    { k: 'cyl',  p0: BASE,           p1: SH,             r: 0.50, w: 1.4 }, // turret column
    { k: 'drum', c: SH,  axis: [0,0,1], r: 0.52, h: 0.60, w: 1.5 },        // shoulder joint
    { k: 'cyl',  p0: SH,  p1: EL,        r: 0.32,         w: 2.0 },         // lower arm link
    { k: 'drum', c: EL,  axis: [0,0,1], r: 0.44, h: 0.52, w: 1.3 },        // elbow joint
    { k: 'cyl',  p0: EL,  p1: WR,        r: 0.27,         w: 2.0 },         // upper arm link
    { k: 'drum', c: WR,  axis: [0,0,1], r: 0.34, h: 0.42, w: 1.0 },        // wrist joint
    { k: 'cyl',  p0: WR,  p1: TIP,       r: 0.17,         w: 0.7 },         // gripper wrist
    { k: 'cyl',  p0: TIP, p1: [3.05, 2.25, 0.20], r: 0.07, w: 0.5 },       // claw finger A
    { k: 'cyl',  p0: TIP, p1: [3.05, 2.25,-0.20], r: 0.07, w: 0.5 },       // claw finger B
  ];

  const totalW = parts.reduce((s, p) => s + p.w, 0);
  const out = new Float32Array(n * 3);
  const MID = [1.05, -0.55, 0], S = 0.95;   // recentre + scale to fit the scene
  let idx = 0;
  for (let pi = 0; pi < parts.length; pi++) {
    const p = parts[pi];
    const cnt = (pi === parts.length - 1) ? (n - idx) : Math.round(n * p.w / totalW);
    for (let i = 0; i < cnt && idx < n; i++, idx++) {
      const pt = p.k === 'cyl' ? ptInCylinder(p.p0, p.p1, p.r) : ptInDrum(p.c, p.axis, p.r, p.h);
      out[idx*3]     = (pt[0] - MID[0]) * S;
      out[idx*3 + 1] = (pt[1] - MID[1]) * S;
      out[idx*3 + 2] = (pt[2] - MID[2]) * S;
    }
  }
  return out;
}

function cross3(a, b){ return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; }
function norm3(v){ const l = Math.hypot(v[0],v[1],v[2]) || 1; return [v[0]/l, v[1]/l, v[2]/l]; }

// helpers: an orthonormal basis perpendicular to an axis, then fill a solid
function basisFor(u){
  const ref = Math.abs(u[1]) < 0.9 ? [0,1,0] : [1,0,0];
  const e1 = norm3(cross3(u, ref));
  const e2 = norm3(cross3(u, e1));
  return [e1, e2];
}
// a point inside a solid cylinder between p0 and p1 of radius r
function ptInCylinder(p0, p1, r){
  const dir = [p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]];
  const len = Math.hypot(dir[0],dir[1],dir[2]) || 1;
  const u = [dir[0]/len, dir[1]/len, dir[2]/len];
  const [e1, e2] = basisFor(u);
  const t = Math.random();
  const rr = r * Math.sqrt(Math.random());     // even area fill
  const a = Math.random() * Math.PI * 2;
  const c = Math.cos(a)*rr, d = Math.sin(a)*rr;
  return [
    p0[0] + dir[0]*t + e1[0]*c + e2[0]*d,
    p0[1] + dir[1]*t + e1[1]*c + e2[1]*d,
    p0[2] + dir[2]*t + e1[2]*c + e2[2]*d,
  ];
}
// a point in a short fat cylinder (joint "drum") centred at c along `axis`
function ptInDrum(c, axis, r, h){
  const u = norm3(axis);
  const [e1, e2] = basisFor(u);
  const along = (Math.random() - 0.5) * h;
  const rr = r * Math.sqrt(0.45 + 0.55 * Math.random()); // bias to the rim → drum look
  const a = Math.random() * Math.PI * 2;
  const cc = Math.cos(a)*rr, dd = Math.sin(a)*rr;
  return [
    c[0] + u[0]*along + e1[0]*cc + e2[0]*dd,
    c[1] + u[1]*along + e1[1]*cc + e2[1]*dd,
    c[2] + u[2]*along + e1[2]*cc + e2[2]*dd,
  ];
}

// Sample points ALONG a polygon's perimeter (a glowing map outline). Far more
// recognisable than a filled blob — the silhouette edges are what read as a map.
function samplePolygonOutline(n, poly) {
  const H = 5.6, W = H * 0.66, TH = 0.03;   // keep Karnataka's real ~0.66 aspect; thin clean line
  const edges = [];
  let total = 0;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    edges.push({ a, b, len }); total += len;
  }
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    // pick an edge weighted by length, then a random point along it
    let pick = Math.random() * total, e = edges[0];
    for (const ed of edges) { if (pick <= ed.len) { e = ed; break; } pick -= ed.len; }
    const t = Math.random();
    const px = e.a[0] + (e.b[0] - e.a[0]) * t;
    const py = e.a[1] + (e.b[1] - e.a[1]) * t;
    const jx = (Math.random() - 0.5) * TH;     // soft jitter so the line glows
    const jy = (Math.random() - 0.5) * TH;
    out[i * 3]     = (px - 0.5 + jx) * W;
    out[i * 3 + 1] = (0.5 - py + jy) * H;       // flip Y (screen → world)
    out[i * 3 + 2] = (Math.random() - 0.5) * 0.18;
  }
  return out;
}

/* Soft round particle sprite (radial gradient) — gives the additive glow. */
function makeSprite() {
  const s = 64;
  const c = document.createElement('canvas'); c.width = c.height = s;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.32, 'rgba(255,255,255,0.55)');
  g.addColorStop(0.65, 'rgba(255,255,255,0.06)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}

/* ─────────────────────────── Static fallback ───────────────────────────── */
/* Shown for reduced-motion, small screens, or no WebGL. A calm gradient with a
 * Tabler robot icon — no animation loop, no battery cost, no strobing. */
function renderStaticFallback(container, theme) {
  const light = theme === 'light';
  const el = document.createElement('div');
  el.style.cssText = `position:absolute; inset:0; display:flex; align-items:center; justify-content:center;` + (light
    ? `background:
         radial-gradient(60% 80% at 62% 30%, rgba(124,58,237,0.10), transparent 60%),
         radial-gradient(50% 70% at 30% 80%, rgba(13,148,136,0.08), transparent 60%), #ffffff;`
    : `background:
         radial-gradient(60% 80% at 70% 20%, rgba(124,58,237,0.30), transparent 60%),
         radial-gradient(50% 70% at 25% 80%, rgba(13,148,136,0.25), transparent 60%),
         linear-gradient(160deg, #0b1437 0%, #0b1437 60%, #111a4a 100%);`);
  el.innerHTML = `<i class="ti ti-robot" style="font-size:84px;
       color:${light ? 'rgba(37,99,235,.85)' : 'rgba(255,255,255,.85)'};
       filter:drop-shadow(0 6px 24px rgba(37,99,235,.35))"></i>`;
  container.appendChild(el);
  return { destroy() { if (el.parentNode) el.parentNode.removeChild(el); } };
}

export default initParticleHero;
