/* =========================================================================
   Jarvis Orb — Advanced WebGL Stark Orb Visualizer
   Exposes: window.JarvisOrb = { setState(name), setVolume(value) }
   ========================================================================= */

(function() {
  const STATES = {
    idle: {
      speed: 0.12, pulseAmt: 0.15, pulseFreq: 0.35, waveAmt: 0.05,
      brightness: 1.15, saturation: 0.8, hueShift: 0.0, noiseScale: 0.50,
      innerR: 0.55, glowSize: 1.40, rotation: 0.04, chromaAber: 0.0,
      flicker: 0.0, sparks: 0.02
    },
    thinking: {
      speed: 0.25, pulseAmt: 0.20, pulseFreq: 0.6, waveAmt: 0.10,
      brightness: 1.2, saturation: 0.9, hueShift: -10.0, noiseScale: 0.65,
      innerR: 0.52, glowSize: 1.45, rotation: 0.15, chromaAber: 0.002,
      flicker: 0.0, sparks: 0.15
    },
    speaking: {
      speed: 0.30, pulseAmt: 0.12, pulseFreq: 0.8, waveAmt: 0.08,
      brightness: 1.25, saturation: 1.0, hueShift: 15.0, noiseScale: 0.60,
      innerR: 0.60, glowSize: 1.50, rotation: 0.10, chromaAber: 0.001,
      flicker: 0.0, sparks: 0.10
    },
    listening: {
      speed: 0.15, pulseAmt: 0.18, pulseFreq: 0.45, waveAmt: 0.05,
      brightness: 1.20, saturation: 0.85, hueShift: 30.0, noiseScale: 0.45,
      innerR: 0.58, glowSize: 1.35, rotation: -0.05, chromaAber: 0.0,
      flicker: 0.0, sparks: 0.05
    },
    executing: {
      speed: 0.40, pulseAmt: 0.25, pulseFreq: 1.0, waveAmt: 0.15,
      brightness: 1.30, saturation: 1.05, hueShift: -30.0, noiseScale: 0.70,
      innerR: 0.50, glowSize: 1.55, rotation: 0.25, chromaAber: 0.004,
      flicker: 0.0, sparks: 0.30
    },
    alert: {
      speed: 0.60, pulseAmt: 0.30, pulseFreq: 1.5, waveAmt: 0.20,
      brightness: 1.35, saturation: 1.15, hueShift: -140.0, noiseScale: 0.80,
      innerR: 0.45, glowSize: 1.60, rotation: 0.40, chromaAber: 0.010,
      flicker: 0.05, sparks: 0.50
    },
    error: {
      speed: 0.70, pulseAmt: 0.35, pulseFreq: 2.0, waveAmt: 0.25,
      brightness: 1.30, saturation: 1.10, hueShift: -130.0, noiseScale: 0.90,
      innerR: 0.48, glowSize: 1.50, rotation: 0.35, chromaAber: 0.015,
      flicker: 0.15, sparks: 0.60
    }
  };

  const VERT = `
    precision highp float;
    attribute vec2 position;
    attribute vec2 uv;
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = vec4(position, 0.0, 1.0);
    }
  `;

  const FRAG = `
    precision highp float;
    uniform float iTime;
    uniform vec3  iResolution;
    uniform float hue;
    uniform float uSpeed;
    uniform float uPulseAmt;
    uniform float uPulsePhase;
    uniform float uWaveAmt;
    uniform float uBrightness;
    uniform float uSaturation;
    uniform float uHueShift;
    uniform float uNoiseScale;
    uniform float uInnerR;
    uniform float uGlowSize;
    uniform float uRotation;
    uniform float uChromaAber;
    uniform float uFlicker;
    uniform float uSparks;
    uniform float uVolume;
    uniform vec3  backgroundColor;
    varying vec2  vUv;

    vec3 rgb2yiq(vec3 c){ return vec3(dot(c,vec3(.299,.587,.114)),dot(c,vec3(.596,-.274,-.322)),dot(c,vec3(.211,-.523,.312))); }
    vec3 yiq2rgb(vec3 c){ return vec3(c.x+.956*c.y+.621*c.z,c.x-.272*c.y-.647*c.z,c.x-1.106*c.y+1.703*c.z); }
    
    vec3 adjustHue(vec3 color, float hDeg){
      float h = hDeg*3.14159265/180.0;
      vec3 yiq = rgb2yiq(color);
      float c2 = cos(h); float s2 = sin(h);
      float i2 = yiq.y*c2 - yiq.z*s2;
      float q2 = yiq.y*s2 + yiq.z*c2;
      yiq.y = i2; yiq.z = q2;
      return clamp(yiq2rgb(yiq), 0.0, 1.0);
    }

    vec3 hash33(vec3 p){
      p = fract(p*vec3(.1031,.11369,.13787));
      p += dot(p, p.yxz+19.19);
      return -1.0 + 2.0*fract(vec3(p.x+p.y, p.x+p.z, p.y+p.z)*p.zyx);
    }

    float snoise3(vec3 p){
      const float K1 = 0.333333333; const float K2 = 0.166666667;
      vec3 i = floor(p + (p.x+p.y+p.z)*K1);
      vec3 d0 = p - (i - (i.x+i.y+i.z)*K2);
      vec3 e = step(vec3(0.0), d0-d0.yzx);
      vec3 i1 = e*(1.0-e.zxy); vec3 i2 = 1.0-e.zxy*(1.0-e);
      vec3 d1 = d0 - (i1-K2); vec3 d2 = d0 - (i2-K1); vec3 d3 = d0 - 0.5;
      vec4 h = max(0.6 - vec4(dot(d0,d0), dot(d1,d1), dot(d2,d2), dot(d3,d3)), 0.0);
      vec4 n = h*h*h*h*vec4(dot(d0,hash33(i)), dot(d1,hash33(i+i1)), dot(d2,hash33(i+i2)), dot(d3,hash33(i+1.0)));
      return dot(vec4(31.316), n);
    }

    float hash21(vec2 p){ p=fract(p*vec2(127.1,311.7)); p+=dot(p,p+19.19); return fract(p.x*p.y); }
    float light1(float i, float a, float d){ return i/(1.0+d*a); }
    float light2(float i, float a, float d){ return i/(1.0+d*d*a); }
    
    vec4 extractAlpha(vec3 c){
      float a = max(max(c.r, c.g), c.b);
      return vec4(c/(a+1e-5), a);
    }

    const vec3 baseColor1 = vec3(0.95, 0.98, 1.0);
    const vec3 baseColor2 = vec3(0.00, 0.85, 0.98); // Neon Jarvis cyan
    const vec3 baseColor3 = vec3(0.01, 0.08, 0.15);

    float spark(vec2 uv, vec2 pos, float size){
      float d = distance(uv, pos);
      return smoothstep(size, 0.0, d) * light2(1.0, 800.0, d);
    }

    vec4 draw(vec2 uv){
      float totalHue = hue + uHueShift;
      vec3 c1 = adjustHue(baseColor1, totalHue);
      vec3 c2 = adjustHue(baseColor2, totalHue);
      vec3 c3 = adjustHue(baseColor3, totalHue);
      float ang = atan(uv.y, uv.x);
      float len = length(uv);
      float invLen = len > 0.0 ? 1.0/len : 0.0;
      float bgLum = 0.0; // Transparent background
      float pulse = sin(uPulsePhase * 6.2832) * uPulseAmt;
      pulse += uVolume * uPulseAmt * 2.0;
      float n0 = snoise3(vec3(uv*uNoiseScale, iTime*uSpeed))*0.5+0.5;
      float innerR = uInnerR + pulse;
      float r0 = mix(mix(innerR, 1.0, 0.4), mix(innerR, 1.0, 0.6), n0);
      float d0 = distance(uv, (r0*invLen)*uv);
      float v0 = light1(1.0, 10.0, d0);
      v0 *= smoothstep(r0*1.05, r0, len);
      float innerFade = smoothstep(r0*0.75, r0*0.92, len);
      v0 *= innerFade;
      float a2 = iTime * uSpeed * -1.5;
      vec2 hPos = vec2(cos(a2), sin(a2)) * r0;
      float d1 = distance(uv, hPos);
      float v1 = light2(1.5, 5.0, d1) * light1(1.0, 50.0, d0);
      float a3 = iTime * uSpeed * 0.8 + 1.5;
      vec2 hPos2 = vec2(cos(a3)*0.8, sin(a3)*0.8) * r0;
      float d2b = distance(uv, hPos2);
      float v1b = light2(0.8, 8.0, d2b) * light1(1.0, 60.0, d0);
      float v2 = smoothstep(uGlowSize*0.92, mix(innerR, 1.0, n0*0.5), len);
      float v3 = smoothstep(innerR*0.9, mix(innerR, 1.0, 0.5), len);
      float sparkVal = 0.0;
      if(uSparks > 0.05){
        for(int i=0; i<6; i++){
          float fi = float(i);
          float angle = iTime*uSpeed*1.3 + fi*1.047 + sin(iTime*0.7+fi)*0.5;
          float radius = r0*(0.85+0.15*sin(iTime*1.2+fi*2.3));
          vec2 sPos = vec2(cos(angle), sin(angle)) * radius;
          float sz = 0.04 * (0.5+0.5*sin(iTime*2.0+fi));
          sparkVal += spark(uv, sPos, sz) * uSparks;
        }
      }
      float flickerMult = 1.0;
      if(uFlicker > 0.01){
        float ft = floor(iTime*18.0);
        flickerMult = 1.0 - uFlicker * hash21(vec2(ft, 3.7));
      }
      float cl = cos(ang + iTime*uSpeed*1.5)*0.5+0.5;
      vec3 colBase = mix(c1, c2, cl) * uSaturation;
      colBase = mix(colBase, colBase * 1.3, uBrightness - 1.0);
      vec3 darkCol = mix(c3, colBase, v0);
      darkCol = (darkCol + v1 + v1b) * v2 * v3;
      darkCol += vec3(sparkVal) * colBase;
      darkCol = clamp(darkCol * uBrightness * flickerMult, 0.0, 1.0);
      return extractAlpha(darkCol);
    }

    vec4 mainImage(vec2 fragCoord){
      vec2 center = iResolution.xy * 0.5;
      float sz = min(iResolution.x, iResolution.y);
      vec2 uv = (fragCoord - center) / sz * 2.0;
      float s2 = sin(uRotation); float c2 = cos(uRotation);
      uv = vec2(c2*uv.x - s2*uv.y, s2*uv.x + c2*uv.y);
      float ph = uPulsePhase * 6.2832;
      float volWave = uVolume * 0.7;
      float baseWave = uWaveAmt * 0.06;
      float wave = baseWave + volWave * uWaveAmt;
      float t1 = iTime * uSpeed * 2.5;
      uv.x += wave * 0.55 * sin(uv.y * 4.5 + t1 + ph * 0.3);
      uv.y += wave * 0.55 * sin(uv.x * 4.5 + t1 * 1.1 + ph * 0.4);
      uv.x += wave * 0.30 * sin(uv.y * 11.0 + t1 * 1.7 + 2.0);
      uv.y += wave * 0.30 * sin(uv.x * 9.5  + t1 * 1.5 + 3.1);
      return draw(uv);
    }

    void main(){
      vec2 fc = vUv * iResolution.xy;
      vec4 col = mainImage(fc);
      gl_FragColor = vec4(col.rgb * col.a, col.a);
    }
  `;

  const UNIFORM_NAMES = [
    'iTime', 'iResolution', 'hue', 'uSpeed', 'uPulseAmt', 'uPulsePhase',
    'uWaveAmt', 'uBrightness', 'uSaturation', 'uHueShift', 'uNoiseScale',
    'uInnerR', 'uGlowSize', 'uRotation', 'uChromaAber', 'uFlicker',
    'uSparks', 'uVolume', 'backgroundColor'
  ];

  class OrbRenderer {
    constructor(container, opts = {}) {
      this.container = container;
      this.hue = opts.hue || 0;
      this._current = {};
      this._target = {};
      const idle = STATES.idle;
      for (const k in idle) {
        this._current[k] = idle[k];
        this._target[k] = idle[k];
      }
      this._rot = 0;
      this._lastTs = 0;
      this._pulsePhase = 0;
      this._volume = 0;

      this.canvas = document.createElement('canvas');
      this.canvas.style.cssText = 'width:100%;height:100%;display:block;background:transparent;';
      container.appendChild(this.canvas);

      this.gl = this.canvas.getContext('webgl', { alpha: true });
      if (!this.gl) return;

      this._build();
      this._resize();
      window.addEventListener('resize', () => this._resize());
      this._loop(0);
    }

    setState(name) {
      const def = STATES[name];
      if (def) {
        for (const k in def) this._target[k] = def[k];
        this.container.dataset.orbState = name;
      }
    }

    setVolume(v) {
      this._volume = Math.max(0, Math.min(1, v));
    }

    _compile(type, src) {
      const gl = this.gl;
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        console.error("Shader compile error:", gl.getShaderInfoLog(s));
        return null;
      }
      return s;
    }

    _build() {
      const gl = this.gl;
      const vs = this._compile(gl.VERTEX_SHADER, VERT);
      const fs = this._compile(gl.FRAGMENT_SHADER, FRAG);
      if (!vs || !fs) return;

      this.pgm = gl.createProgram();
      gl.attachShader(this.pgm, vs);
      gl.attachShader(this.pgm, fs);
      gl.linkProgram(this.pgm);
      if (!gl.getProgramParameter(this.pgm, gl.LINK_STATUS)) {
        console.error("Program link error:", gl.getProgramInfoLog(this.pgm));
        return;
      }

      gl.useProgram(this.pgm);

      const posBuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const posLoc = gl.getAttribLocation(this.pgm, 'position');
      gl.enableVertexAttribArray(posLoc);
      gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

      const uvBuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, uvBuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 2, 0, 0, 2]), gl.STATIC_DRAW);
      const uvLoc = gl.getAttribLocation(this.pgm, 'uv');
      gl.enableVertexAttribArray(uvLoc);
      gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 0, 0);

      this.u = {};
      for (let i = 0; i < UNIFORM_NAMES.length; i++) {
        this.u[UNIFORM_NAMES[i]] = gl.getUniformLocation(this.pgm, UNIFORM_NAMES[i]);
      }

      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    }

    _resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = this.container.getBoundingClientRect();
      this.canvas.width = rect.width * dpr;
      this.canvas.height = rect.height * dpr;
      this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    }

    _loop(ts) {
      requestAnimationFrame((t) => this._loop(t));
      if (!this.pgm) return;

      const t = ts * 0.001;
      const dt = this._lastTs ? t - this._lastTs : 0.016;
      this._lastTs = t;

      const k = Math.min(dt * 4.0, 1.0);
      for (const key in this._target) {
        this._current[key] += (this._target[key] - this._current[key]) * k;
      }

      this._rot += this._current.rotation * dt;
      this._pulsePhase += this._current.pulseFreq * dt;

      const gl = this.gl;
      gl.clearColor(0.0, 0.0, 0.0, 0.0); // Clear to fully transparent
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.uniform1f(this.u.iTime, t);
      gl.uniform3f(this.u.iResolution, this.canvas.width, this.canvas.height, 1.0);
      gl.uniform1f(this.u.hue, this.hue);
      gl.uniform1f(this.u.uSpeed, this._current.speed);
      gl.uniform1f(this.u.uPulseAmt, this._current.pulseAmt);
      gl.uniform1f(this.u.uPulsePhase, this._pulsePhase);
      gl.uniform1f(this.u.uWaveAmt, this._current.waveAmt);
      gl.uniform1f(this.u.uBrightness, this._current.brightness);
      gl.uniform1f(this.u.uSaturation, this._current.saturation);
      gl.uniform1f(this.u.uHueShift, this._current.hueShift);
      gl.uniform1f(this.u.uNoiseScale, this._current.noiseScale);
      gl.uniform1f(this.u.uInnerR, this._current.innerR);
      gl.uniform1f(this.u.uGlowSize, this._current.glowSize);
      gl.uniform1f(this.u.uRotation, this._rot);
      gl.uniform1f(this.u.uChromaAber, this._current.chromaAber);
      gl.uniform1f(this.u.uFlicker, this._current.flicker);
      gl.uniform1f(this.u.uSparks, this._current.sparks);
      gl.uniform1f(this.u.uVolume, this._volume);
      gl.uniform3f(this.u.backgroundColor, 0.0, 0.0, 0.0);

      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
  }

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('orb-container');
    if (container) {
      try {
        const renderer = new OrbRenderer(container);
        window.JarvisOrb = {
          setState: (name) => renderer.setState(name),
          setVolume: (v) => renderer.setVolume(v)
        };
        // Default state
        renderer.setState('idle');
      } catch (err) {
        console.error("Failed to initialize Stark WebGL Orb:", err);
      }
    }
  });
})();
