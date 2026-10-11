"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

interface FerrofluidProps {
  className?: string;
  mouseInteraction?: boolean;
  fluidColor?: string;
  glowColor?: string;
  speed?: number;
  viscosity?: number;
}

export const Ferrofluid: React.FC<FerrofluidProps> = ({
  className = "",
  mouseInteraction = true,
  fluidColor = "#09090b",
  glowColor = "#6366f1",
  speed = 1.0,
  viscosity = 0.8,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hasWebGL, setHasWebGL] = useState<boolean | null>(null);

  useEffect(() => {
    // 1. Check WebGL support safely on client
    try {
      const canvas = document.createElement("canvas");
      const gl =
        canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!gl) {
        setHasWebGL(false);
        return;
      }
      setHasWebGL(true);
    } catch {
      setHasWebGL(false);
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    // 2. Three.js Scene Setup
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    let renderer: THREE.WebGLRenderer | null = null;

    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "high-performance",
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(container.clientWidth, container.clientHeight);
      container.appendChild(renderer.domElement);
    } catch {
      setHasWebGL(false);
      return;
    }

    // 3. Mouse state tracking
    const mouse = new THREE.Vector2(0.5, 0.5);
    const targetMouse = new THREE.Vector2(0.5, 0.5);

    const handleMouseMove = (e: MouseEvent) => {
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = 1.0 - (e.clientY - rect.top) / rect.height;
      targetMouse.set(x, y);
    };

    if (mouseInteraction) {
      window.addEventListener("mousemove", handleMouseMove, { passive: true });
    }

    // 4. Custom Ferrofluid Raymarch / Noise Shader Material
    const ferrofluidUniforms = {
      uTime: { value: 0 },
      uResolution: {
        value: new THREE.Vector2(container.clientWidth, container.clientHeight),
      },
      uMouse: { value: new THREE.Vector2(0.5, 0.5) },
      uFluidColor: { value: new THREE.Color(fluidColor) },
      uGlowColor: { value: new THREE.Color(glowColor) },
      uSpeed: { value: speed },
      uViscosity: { value: viscosity },
    };

    const vertexShader = `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = vec4(position, 1.0);
      }
    `;

    const fragmentShader = `
      uniform float uTime;
      uniform vec2 uResolution;
      uniform vec2 uMouse;
      uniform vec3 uFluidColor;
      uniform vec3 uGlowColor;
      uniform float uSpeed;
      uniform float uViscosity;
      varying vec2 vUv;

      // Simplex-inspired 3D noise
      vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
      vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
      vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
      vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

      float snoise(vec3 v) {
        const vec2 C = vec2(1.0/6.0, 1.0/3.0);
        const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
        vec3 i  = floor(v + dot(v, C.yyy));
        vec3 x0 = v - i + dot(i, C.xxx);
        vec3 g = step(x0.yzx, x0.xyz);
        vec3 l = 1.0 - g;
        vec3 i1 = min(g.xyz, l.zxy);
        vec3 i2 = max(g.xyz, l.zxy);
        vec3 x1 = x0 - i1 + C.xxx;
        vec3 x2 = x0 - i2 + C.yyy;
        vec3 x3 = x0 - D.yyy;
        i = mod289(i);
        vec4 p = permute(permute(permute(
                    i.z + vec4(0.0, i1.z, i2.z, 1.0))
                  + i.y + vec4(0.0, i1.y, i2.y, 1.0))
                  + i.x + vec4(0.0, i1.x, i2.x, 1.0));
        float n_ = 0.142857142857;
        vec3  ns = n_ * D.wyz - D.xzx;
        vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
        vec4 x_ = floor(j * ns.z);
        vec4 y_ = floor(j - 7.0 * x_);
        vec4 x = x_ *ns.x + ns.yyyy;
        vec4 y = y_ *ns.x + ns.yyyy;
        vec4 h = 1.0 - abs(x) - abs(y);
        vec4 b0 = vec4(x.xy, y.xy);
        vec4 b1 = vec4(x.zw, y.zw);
        vec4 s0 = floor(b0)*2.0 + 1.0;
        vec4 s1 = floor(b1)*2.0 + 1.0;
        vec4 sh = -step(h, vec4(0.0));
        vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
        vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
        vec3 p0 = vec3(a0.xy, h.x);
        vec3 p1 = vec3(a0.zw, h.y);
        vec3 p2 = vec3(a1.xy, h.z);
        vec3 p3 = vec3(a1.zw, h.w);
        vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
        p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
        vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
        m = m * m;
        return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
      }

      void main() {
        vec2 uv = vUv;
        vec2 aspect = vec2(uResolution.x / uResolution.y, 1.0);
        vec2 p = (uv - 0.5) * aspect;
        vec2 m = (uMouse - 0.5) * aspect;

        float distToMouse = length(p - m);
        float t = uTime * uSpeed * 0.4;

        // Ferrofluid magnetic spike distortion
        float magneticPull = exp(-distToMouse * 3.5);
        vec2 spikeDir = normalize(p - m + 0.0001);
        vec2 displacedP = p + spikeDir * magneticPull * 0.12 * uViscosity;

        // Layered noise for organic metallic fluid
        float n1 = snoise(vec3(displacedP * 2.2, t * 0.5));
        float n2 = snoise(vec3(displacedP * 4.8 + n1 * 0.4, t * 0.8));
        float n3 = snoise(vec3(displacedP * 9.5 + n2 * 0.25, t * 1.2));
        
        float fluidPattern = n1 * 0.5 + n2 * 0.3 + n3 * 0.2;

        // Edge detection / normal estimation for liquid sheen
        float eps = 0.005;
        float nx = snoise(vec3((displacedP + vec2(eps, 0.0)) * 3.0, t)) - snoise(vec3((displacedP - vec2(eps, 0.0)) * 3.0, t));
        float ny = snoise(vec3((displacedP + vec2(0.0, eps)) * 3.0, t)) - snoise(vec3((displacedP - vec2(0.0, eps)) * 3.0, t));
        vec3 normal = normalize(vec3(nx, ny, 0.1));

        // Light sources: Key light + Magnetic core glow
        vec3 lightDir = normalize(vec3(0.5, 0.8, 1.2));
        float diff = max(dot(normal, lightDir), 0.0);
        float spec = pow(max(dot(reflect(-lightDir, normal), vec3(0.0, 0.0, 1.0)), 0.0), 16.0);
        float rim = pow(1.0 - max(dot(normal, vec3(0.0, 0.0, 1.0)), 0.0), 3.0);

        // Iridescent chromatic reflection on spikes
        vec3 iridescence = 0.5 + 0.5 * cos(vec3(0.0, 0.33, 0.67) * 6.28 + fluidPattern * 3.0 + t);

        // Blending metallic dark fluid with vibrant indigo/cyan rim
        vec3 baseColor = uFluidColor;
        vec3 sheen = mix(uGlowColor, iridescence, 0.35) * (spec * 0.85 + rim * 0.6);
        vec3 magneticAura = uGlowColor * magneticPull * 0.45;

        vec3 finalColor = baseColor + sheen + magneticAura;

        // Vignette falloff
        float vig = smoothstep(1.2, 0.2, length(p));
        finalColor *= vig;

        gl_FragColor = vec4(finalColor, 0.92);
      }
    `;

    const geometry = new THREE.PlaneGeometry(2, 2);
    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: ferrofluidUniforms,
      transparent: true,
      depthWrite: false,
    });

    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    // 5. Handle Resize
    const handleResize = () => {
      if (!container || !renderer) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      renderer.setSize(width, height);
      ferrofluidUniforms.uResolution.value.set(width, height);
    };

    window.addEventListener("resize", handleResize);

    // 6. Animation Render Loop
    let animationFrameId: number;
    let lastTime = performance.now();

    const animate = (currentTime: number) => {
      const delta = Math.min((currentTime - lastTime) * 0.001, 0.1);
      lastTime = currentTime;
      ferrofluidUniforms.uTime.value += delta;

      // Smooth mouse lerping
      mouse.lerp(targetMouse, 0.05);
      ferrofluidUniforms.uMouse.value.copy(mouse);

      renderer?.render(scene, camera);
      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);

    // 7. Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
      if (mouseInteraction) {
        window.removeEventListener("mousemove", handleMouseMove);
      }
      geometry.dispose();
      material.dispose();
      if (renderer) {
        renderer.dispose();
        if (renderer.domElement && renderer.domElement.parentNode) {
          renderer.domElement.parentNode.removeChild(renderer.domElement);
        }
      }
    };
  }, [fluidColor, glowColor, mouseInteraction, speed, viscosity]);

  return (
    <div
      ref={containerRef}
      className={`relative h-full w-full overflow-hidden ${className}`}
      style={{ pointerEvents: "none" }}
    >
      {/* Graceful Fallback if WebGL is unavailable */}
      {hasWebGL === false && (
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-950 via-indigo-950/20 to-zinc-950 opacity-80" />
      )}
    </div>
  );
};

export default Ferrofluid;
