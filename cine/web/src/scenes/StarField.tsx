import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

/* ================= 电影宇宙 · 星空粒子 =================
   三层柔光粒子 + 远星云，替代生硬的点阵：
   - 深空星点：小而密，冷暖色温混合，缓慢公转
   - 星尘：金白微光，靠近相机层，缓慢反向漂移
   - 光斑 bokeh：极少数大而柔的光点，给景深
   - 星云：三团超大柔光色块，营造银河深浅
   全部使用径向渐变柔光贴图，杜绝方块/硬边。 */

/* 柔光圆点纹理（canvas 生成，一次缓存） */
function softSprite(): THREE.Texture {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const ctx = c.getContext('2d')!
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.2, 'rgba(255,255,255,0.55)')
  g.addColorStop(0.45, 'rgba(255,255,255,0.16)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 64, 64)
  const t = new THREE.CanvasTexture(c)
  t.needsUpdate = true
  return t
}

/* 色温：金 / 蓝紫 / 星尘白 */
const TEMP: [number, number, number][] = [
  [1.0, 0.87, 0.6],
  [0.72, 0.8, 1.0],
  [0.98, 0.98, 1.0],
]

/* 球壳内随机位置（y 压扁成碟状，更像银河盘） */
function shellPoints(n: number, rMin: number, rMax: number, flatten = 0.6): THREE.BufferGeometry {
  const pos = new Float32Array(n * 3)
  const col = new Float32Array(n * 3)
  for (let i = 0; i < n; i++) {
    const r = rMin + Math.random() * (rMax - rMin)
    const th = Math.random() * Math.PI * 2
    const ph = Math.acos(2 * Math.random() - 1)
    pos[i * 3] = r * Math.sin(ph) * Math.cos(th)
    pos[i * 3 + 1] = r * Math.cos(ph) * flatten
    pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th)
    const t = TEMP[Math.random() < 0.55 ? 2 : Math.random() < 0.5 ? 0 : 1]
    const dim = 0.4 + Math.random() * 0.6
    col[i * 3] = t[0] * dim
    col[i * 3 + 1] = t[1] * dim
    col[i * 3 + 2] = t[2] * dim
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3))
  return geo
}

export default function StarField() {
  const sprite = useMemo(softSprite, [])
  const farRef = useRef<THREE.Points>(null!)
  const dustRef = useRef<THREE.Points>(null!)
  const bokehRef = useRef<THREE.Points>(null!)
  const nebulaRef = useRef<THREE.Group>(null!)

  /* 远景深空星：细密、小、雾不吞（fog=false） */
  const far = useMemo(() => shellPoints(1700, 60, 98), [])
  /* 近层星尘：金白，漂浮在星系四周 */
  const dust = useMemo(() => shellPoints(320, 26, 44, 0.75), [])
  /* 光斑 bokeh：少量大柔光点 */
  const bokeh = useMemo(() => shellPoints(26, 30, 60, 0.5), [])

  useEffect(() => {
    return () => { far.dispose(); dust.dispose(); bokeh.dispose(); sprite.dispose() }
  }, [far, dust, bokeh, sprite])

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime
    if (farRef.current) farRef.current.rotation.y += delta * 0.0035
    if (dustRef.current) dustRef.current.rotation.y -= delta * 0.011
    if (bokehRef.current) bokehRef.current.rotation.y += delta * 0.007
    if (nebulaRef.current) nebulaRef.current.rotation.y += delta * 0.0018
    // 全局星尘呼吸：缓慢的亮度起伏，避免呆板
    if (dustRef.current) {
      const m = dustRef.current.material as THREE.PointsMaterial
      m.opacity = 0.55 + Math.sin(t * 0.5) * 0.06
    }
  })

  return (
    <>
      {/* 星云：三团超大柔光色块，给银河深浅与色调 */}
      <group ref={nebulaRef}>
        <sprite position={[-26, 7, -44]} scale={[40, 26, 1]}>
          <spriteMaterial map={sprite} color="#6d4fd8" transparent opacity={0.05} depthWrite={false} blending={THREE.AdditiveBlending} fog={false} />
        </sprite>
        <sprite position={[22, -5, -48]} scale={[34, 22, 1]}>
          <spriteMaterial map={sprite} color="#b8894a" transparent opacity={0.045} depthWrite={false} blending={THREE.AdditiveBlending} fog={false} />
        </sprite>
        <sprite position={[3, 12, -52]} scale={[30, 20, 1]}>
          <spriteMaterial map={sprite} color="#5b6cd8" transparent opacity={0.04} depthWrite={false} blending={THREE.AdditiveBlending} fog={false} />
        </sprite>
      </group>

      {/* 深空星点：小尺寸柔光，冷暖混合 */}
      <points ref={farRef} geometry={far}>
        <pointsMaterial
          map={sprite} vertexColors size={0.085} sizeAttenuation
          transparent opacity={0.85} depthWrite={false}
          blending={THREE.AdditiveBlending} fog={false}
        />
      </points>

      {/* 星尘：金白，略大 */}
      <points ref={dustRef} geometry={dust}>
        <pointsMaterial
          map={sprite} vertexColors size={0.17} sizeAttenuation
          transparent opacity={0.6} depthWrite={false}
          blending={THREE.AdditiveBlending} fog={false}
        />
      </points>

      {/* 光斑 bokeh：大而柔，只有少数 */}
      <points ref={bokehRef} geometry={bokeh}>
        <pointsMaterial
          map={sprite} vertexColors size={0.55} sizeAttenuation
          transparent opacity={0.42} depthWrite={false}
          blending={THREE.AdditiveBlending} fog={false}
        />
      </points>
    </>
  )
}
