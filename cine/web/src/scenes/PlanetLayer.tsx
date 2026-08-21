/* ============ 发光粒子星球 ============
   5000 部电影全部渲染为发光小粒子（不再是球体外观）：
   - 四个地区四种颜色（华语红 / 日本粉 / 韩国青绿 / 欧美金）
   - 每颗粒子独立的一闪一闪（相位与速度由 id 决定）
   - 库外片亮度系数 k<1，更暗更小
   单个 THREE.Points 一次 draw call 渲染全部粒子。
   悬停显示影片信息；点击仅核心 590 部可进详情页。 */
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { planetPos, renderR, REGION_COLORS } from '../layout'
import { useGalaxy } from '../store'
import type { Planet } from '../types'
/* 粒子着色器：圆形光斑（中心白亮 + 边缘地区色光晕），逐粒子闪烁 */
const VERT = /* glsl */ `
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aPhase;
  attribute float aSpeed;
  uniform float uTime;
  varying vec3 vColor;
  varying float vTw;
  void main() {
    float tw = 0.5 + 0.5 * sin(uTime * aSpeed + aPhase);   // 0~1 呼吸
    vTw = 0.35 + 0.65 * tw;
    vColor = aColor;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * (0.7 + 0.3 * tw) * (46.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`
const FRAG = /* glsl */ `
  varying vec3 vColor;
  varying float vTw;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    float glow = smoothstep(0.5, 0.05, d);
    float core = smoothstep(0.22, 0.0, d);
    vec3 col = vColor * glow + vec3(1.0) * core * 0.85;    // 中心发白
    gl_FragColor = vec4(col, glow * vTw);
  }
`

export default function PlanetLayer({ planets }: { planets: Planet[] }) {
  const matRef = useRef<THREE.ShaderMaterial>(null!)

  /* 一次性构建几何体：位置 / 地区色 / 尺寸 / 闪烁参数 */
  const geo = useMemo(() => {
    const n = planets.length
    const g = new THREE.BufferGeometry()
    const pos = new Float32Array(n * 3)
    const col = new Float32Array(n * 3)
    const size = new Float32Array(n)
    const phase = new Float32Array(n)
    const speed = new Float32Array(n)
    const c = new THREE.Color()
    planets.forEach((p, i) => {
      const q = planetPos(p)
      pos[i * 3] = q.x; pos[i * 3 + 1] = q.y; pos[i * 3 + 2] = q.z
      const k = p.k ?? 1
      c.set(REGION_COLORS[p.region] || '#ffd76a').multiplyScalar(0.45 + 0.55 * k)  // 库外片更暗
      col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b
      size[i] = (k < 1 ? 4.2 + 2.2 : 7 + 4) * renderR(p) / 0.44                    // 库外片更小
      let s = 0
      for (let j = 0; j < p.id.length; j++) s = (s * 31 + p.id.charCodeAt(j)) % 9973
      phase[i] = (s % 628) / 100
      speed[i] = 0.7 + ((s % 19) / 19) * 1.9
    })
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    g.setAttribute('aColor', new THREE.BufferAttribute(col, 3))
    g.setAttribute('aSize', new THREE.BufferAttribute(size, 1))
    g.setAttribute('aPhase', new THREE.BufferAttribute(phase, 1))
    g.setAttribute('aSpeed', new THREE.BufferAttribute(speed, 1))
    return g
  }, [planets])

  useFrame((state) => {
    if (matRef.current) matRef.current.uniforms.uTime.value = state.clock.elapsedTime
  })

  const hit = (e: { index?: number; clientX: number; clientY: number }) => {
    const s = useGalaxy.getState()
    const idx = e.index ?? null
    if (idx != null && planets[idx]) {
      s.setHover(planets[idx].id)
      s.setHoverPos({ x: e.clientX, y: e.clientY })
    }
  }
  const leave = () => {
    useGalaxy.getState().setHover(null)
    useGalaxy.getState().setHoverPos(null)
  }
  const click = (e: { index?: number }) => {
    const idx = e.index ?? null
    const p = idx != null ? planets[idx] : null
    /* 只有核心 590 部可进详情页，库外片仅悬浮展示信息 */
    if (p && (p.k ?? 1) >= 1) location.hash = '#/movie/' + p.id
  }
  /* 按下/抬起位移判定：拖转地球（移动 > 6px）不触发点击导航 */
  const downPos = useRef<{ x: number; y: number } | null>(null)
  const down = (e: { clientX: number; clientY: number }) => {
    downPos.current = { x: e.clientX, y: e.clientY }
  }
  const up = (e: { index?: number; clientX: number; clientY: number }) => {
    const d = downPos.current
    downPos.current = null
    if (!d) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    if (dx * dx + dy * dy > 36) return   // 拖转，非点击
    click(e)
  }

  if (!planets.length) return null

  return (
    <points
      geometry={geo}
      frustumCulled={false}
      onPointerMove={(e) => { e.stopPropagation(); hit(e) }}
      onPointerOut={leave}
      onPointerDown={(e) => { e.stopPropagation(); down(e) }}
      onPointerUp={(e) => { e.stopPropagation(); up(e) }}
    >
      <shaderMaterial
        ref={matRef}
        vertexShader={VERT}
        fragmentShader={FRAG}
        uniforms={{ uTime: { value: 0 } }}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}
