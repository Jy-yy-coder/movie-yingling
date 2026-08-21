/* 立体地球仪层：
   ① 深色不透明球体内核——遮挡背面，让地图呈现真实的球体剪影
   ② 大陆点阵贴在球面上（圆形光点纹理，由真实国家轮廓采样而来）
   ③ 背面加性光晕壳，营造大气层微光边缘 */
import { useMemo } from 'react'
import * as THREE from 'three'
import { buildMapDots, GLOBE_R } from '../worldmap'

/* 圆形光点纹理：THREE.Points 默认是方形像素，贴圆形径向渐变纹理才是圆点 */
function makeDotTexture(): THREE.Texture {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const ctx = c.getContext('2d')!
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.4, 'rgba(255,255,255,0.55)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 64, 64)
  const t = new THREE.CanvasTexture(c)
  t.needsUpdate = true
  return t
}

export default function MapLayer() {
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(buildMapDots(), 3))
    return g
  }, [])
  const dotTex = useMemo(() => makeDotTexture(), [])

  return (
    <group>
      {/* 球体内核：深色不透明，挡住背面的点与星球 */}
      <mesh>
        <sphereGeometry args={[GLOBE_R - 0.4, 48, 32]} />
        <meshBasicMaterial color="#070b16" />
      </mesh>

      {/* 大陆点阵：贴在球面上，白色圆形光点（与四色电影粒子区分） */}
      <points geometry={geo} frustumCulled={false}>
        <pointsMaterial
          color="#ffffff" size={0.5} sizeAttenuation map={dotTex}
          transparent opacity={0.55} alphaTest={0.02} depthWrite={false} blending={THREE.AdditiveBlending}
        />
      </points>

      {/* 大气微光：背面加性壳，形成柔和的星球边缘光 */}
      <mesh>
        <sphereGeometry args={[GLOBE_R + 0.6, 48, 32]} />
        <meshBasicMaterial
          color="#1c2f5e" transparent opacity={0.16}
          side={THREE.BackSide} blending={THREE.AdditiveBlending} depthWrite={false}
        />
      </mesh>
    </group>
  )
}
