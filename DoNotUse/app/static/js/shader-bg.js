/* ============================================================================
 * shader-bg.js — GTTC Portal
 * A subtle fullscreen GLSL background: deep void + slowly breathing voronoi
 * "cell membranes" + rolling fbm fog, in GTTC colours. One plane, one draw call.
 *
 * Adapted (toned down, clean) from the melboucierayane.com aesthetic. The
 * ray-marched orb and perspective grid layers are intentionally OMITTED — the
 * page already has a particle orb, and the grid added clutter. This stays a
 * calm backdrop that sits BEHIND the particle hero and the text.
 *
 * Uses local Three.js (no CDN), so it works offline / on any LAN device.
 * ==========================================================================*/
import * as THREE from '/static/js/three.module.min.js';

export function initShaderBackground(container, opts = {}) {
  const isSmall = window.innerWidth < 600;
  const hasWebGL = (() => {
    try {
      const c = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl')));
    } catch (_) { return false; }
  })();
  if (isSmall || !hasWebGL) return { destroy() {} };   // panel gradient shows instead

  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));   // dpr cap [1,1.5]
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);
  renderer.domElement.style.display = 'block';

  const scene = new THREE.Scene();
  const camera = new THREE.Camera();   // plane is in NDC; camera is irrelevant

  const uniforms = {
    uTime:       { value: 0 },
    uResolution: { value: new THREE.Vector2(container.clientWidth, container.clientHeight) },
    uMouse:      { value: new THREE.Vector2(0.5, 0.5) },
    uIntensity:  { value: opts.intensity != null ? opts.intensity : 0.55 },
    uLightMode:  { value: opts.theme === 'light' ? 1.0 : 0.0 },
  };

  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.ShaderMaterial({ uniforms, vertexShader: VERT, fragmentShader: FRAG, transparent: true })
  );
  scene.add(mesh);

  // gentle mouse parallax
  function onMove(e) {
    const r = renderer.domElement.getBoundingClientRect();
    uniforms.uMouse.value.set((e.clientX - r.left) / r.width, 1.0 - (e.clientY - r.top) / r.height);
  }
  window.addEventListener('pointermove', onMove, { passive: true });

  const clock = new THREE.Clock();
  let running = true, raf = 0;
  function frame() {
    if (!running) return;
    raf = requestAnimationFrame(frame);
    uniforms.uTime.value = clock.getElapsedTime();
    renderer.render(scene, camera);
  }
  function start() { if (!running) { running = true; clock.start(); frame(); } }
  function stop()  { running = false; cancelAnimationFrame(raf); }

  function onVis() { document.hidden ? stop() : start(); }
  document.addEventListener('visibilitychange', onVis);
  const io = new IntersectionObserver(([e]) => { e.isIntersecting ? start() : stop(); }, { threshold: 0.01 });
  io.observe(container);

  function onResize() {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h);
    uniforms.uResolution.value.set(w, h);
  }
  window.addEventListener('resize', onResize);

  frame();

  return {
    setTheme(t) { uniforms.uLightMode.value = t === 'light' ? 1.0 : 0.0; },
    destroy() {
      stop(); io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('resize', onResize);
      mesh.geometry.dispose(); mesh.material.dispose(); renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    }
  };
}

/* ── passthrough vertex shader (plane already in clip space) ── */
const VERT = /* glsl */`
  varying vec2 vUv;
  void main(){ vUv = uv; gl_Position = vec4(position, 1.0); }
`;

const FRAG = /* glsl */`
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform vec2  uResolution;
  uniform vec2  uMouse;
  uniform float uIntensity;
  uniform float uLightMode;

  // GTTC palette
  const vec3 BLUE   = vec3(0.145, 0.388, 0.922);  // #2563eb
  const vec3 BLUE_L = vec3(0.42,  0.60,  0.97);   // lighter blue for light mode edges
  const vec3 PURPLE = vec3(0.486, 0.227, 0.929);  // #7c3aed
  const vec3 TEAL   = vec3(0.051, 0.580, 0.533);  // #0d9488

  float hash1(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
  vec2  hash2(vec2 p){
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
  }

  float vnoise(vec2 p){
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash1(i), b = hash1(i + vec2(1,0)), c = hash1(i + vec2(0,1)), d = hash1(i + vec2(1,1));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
  }
  float fbm(vec2 p){
    float v = 0.0, amp = 0.5;
    for (int i = 0; i < 4; i++){ v += amp * vnoise(p); p *= 2.0; amp *= 0.5; }
    return v;
  }

  vec2 voronoi(vec2 p){
    vec2 g = floor(p), f = fract(p);
    float f1 = 8.0, f2 = 8.0;
    for (int y = -1; y <= 1; y++)
    for (int x = -1; x <= 1; x++){
      vec2 lat = vec2(float(x), float(y));
      vec2 o = hash2(g + lat);
      o = 0.5 + 0.5 * sin(uTime * 0.35 + 6.2831 * o);
      vec2 r = lat + o - f;
      float d = dot(r, r);
      if (d < f1){ f2 = f1; f1 = d; } else if (d < f2){ f2 = d; }
    }
    return vec2(sqrt(f1), sqrt(f2));
  }

  void main(){
    vec2 uv = vUv;
    uv += (uMouse - 0.5) * 0.012;

    vec2 vo = voronoi(uv * 5.0 + 1.5);
    float edge = vo.y - vo.x;
    vec3 col;

    if (uLightMode > 0.5) {
      // Light mode — white cells, blue lines
      col = vec3(1.0);
      float membrane = smoothstep(0.06, 0.0, edge);
      vec3 edgeCol = mix(BLUE, BLUE_L, smoothstep(0.0, 0.06, edge));
      col = mix(col, edgeCol, membrane * 0.88 * uIntensity);
      col += (hash1(uv * (1.0 + fract(uTime))) - 0.5) * 0.004;
      col = clamp(col, 0.0, 1.0);
    } else {
      // Dark mode — original
      float fog = fbm(uv * 3.0 + uTime * 0.04);
      col = mix(vec3(0.0, 0.012, 0.04), vec3(0.03, 0.06, 0.13), fog);
      col = mix(col, PURPLE * 0.16, fog * 0.35);
      float membrane = smoothstep(0.07, 0.0, edge);
      vec3 edgeCol = mix(BLUE, PURPLE, smoothstep(0.0, 0.07, edge));
      col += membrane * edgeCol * 0.55;
      col += smoothstep(0.28, 0.0, vo.x) * TEAL * 0.07;
      float vig = 1.0 - smoothstep(0.35, 1.25, length(uv - 0.5) * 1.8);
      col *= vig;
      col += (hash1(uv * (1.0 + fract(uTime))) - 0.5) * 0.012;
      col = clamp(col, 0.0, 1.0);
      col = col / (col + 0.8);
    }

    gl_FragColor = vec4(col, 1.0);
  }
`;

export default initShaderBackground;
