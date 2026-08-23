import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import StarField from './StarField'
import MapLayer from './MapLayer'
import PlanetLayer from './PlanetLayer'
import { focusPoint, planetPos } from '../layout'
import { useGalaxy } from '../store'

/* 地球仪整体缓转：地图点阵与星球在同一组内旋转，保持位置对应；
   交互/悬停/聚焦地区/选中星球时暂停（避免目标位置随旋转漂移） */
function GlobeSpin({ children }: { children: ReactNode }) {
  const ref = useRef<THREE.Group>(null!)
  const interacting = useGalaxy((s) => s.interacting)
  const hoverId = useGalaxy((s) => s.hoverId)
  const focusRegion = useGalaxy((s) => s.focusRegion)
  const selectedId = useGalaxy((s) => s.selectedId)
  useFrame((_, delta) => {
    if (ref.current && !interacting && !hoverId && !focusRegion && !selectedId) {
      ref.current.rotation.y += delta * 0.025
    }
  })
  return <group ref={ref}>{children}</group>
}

/* 粒子拾取阈值：让发光粒子能被悬停/点击命中 */
function PointsRaycast() {
  const raycaster = useThree((s) => s.raycaster)
  useEffect(() => { raycaster.params.Points.threshold = 1.3 }, [raycaster])
  return null
}

/* 相机飞行：聚焦星域/星系/选中星球时平滑推近。
   只在「飞行窗口」内接管相机：目标变化时启动，到位或用户手动操作（拖转/滚轮）即交还，
   此后滚轮缩放完全由用户掌控（修复缩放被每帧弹回的问题）。 */
function CameraRig() {
  const controlsRef = useRef<OrbitControlsImpl>(null!)
  const focusRegion = useGalaxy((s) => s.focusRegion)
  const focusGenre = useGalaxy((s) => s.focusGenre)
  const selectedId = useGalaxy((s) => s.selectedId)
  const planets = useGalaxy((s) => s.planets)
  const setInteracting = useGalaxy((s) => s.setInteracting)

  const desired = useMemo(() => focusPoint(focusRegion, focusGenre), [focusRegion, focusGenre])
  const selectedPos = useMemo(() => {
    const p = planets.find((x) => x.id === selectedId)
    return p ? planetPos(p) : null
  }, [selectedId, planets])

  /* 飞行状态用 ref 承载，避免 useFrame 闭包过期；复用临时向量减少 GC 压力 */
  const flyingRef = useRef(true)
  const interactTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const minDist = 8
  const flightKey = `${focusRegion}|${focusGenre}|${selectedId}|${selectedPos ? 1 : 0}`
  useEffect(() => { flyingRef.current = true }, [flightKey])
  const dirTmp = useMemo(() => new THREE.Vector3(), [])
  const targetTmp = useMemo(() => new THREE.Vector3(), [])
  const desiredTmp = useMemo(() => new THREE.Vector3(), [])

  useFrame(() => {
    const c = controlsRef.current
    if (!c || !flyingRef.current) return
    const sp = selectedPos
    targetTmp.set(sp ? sp.x : desired.x, sp ? sp.y : desired.y, sp ? sp.z : desired.z)
    const cam = c.object
    const wantDist = sp ? 12 : focusRegion ? 30 : 96
    dirTmp.copy(cam.position).sub(targetTmp).normalize()
    desiredTmp.copy(targetTmp).add(dirTmp.multiplyScalar(Math.max(wantDist, minDist)))
    cam.position.lerp(desiredTmp, 0.05)
    c.target.lerp(targetTmp, 0.07)
    c.update()
    if (cam.position.distanceTo(desiredTmp) < 0.4) flyingRef.current = false
  })
  return (
    <OrbitControls
      ref={controlsRef}
      enablePan={false}
      enableDamping
      dampingFactor={0.08}
      minDistance={minDist}
      maxDistance={300}
      onStart={() => {
        if (interactTimer.current) clearTimeout(interactTimer.current)
        setInteracting(true)
        flyingRef.current = false
      }}
      onEnd={() => {
        if (interactTimer.current) clearTimeout(interactTimer.current)
        interactTimer.current = setTimeout(() => setInteracting(false), 260)
      }}
    />
  )
}

export default function GalaxyScene() {
  const planets = useGalaxy((s) => s.planets)
  /* overlay 打开时降载：停掉 Bloom / 降 DPR，避免探索/详情下风扇狂转 */
  const [quiet, setQuiet] = useState(() => {
    const h = (typeof location !== 'undefined' ? location.hash : '') || '#/'
    const path = h.split('?')[0]
    const overlay = path !== '#/' && path !== '#' && path !== ''
    const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    return overlay || reduce
  })
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const apply = () => {
      const path = (location.hash || '#/').split('?')[0]
      const overlay = path !== '#/' && path !== '#' && path !== ''
      setQuiet(overlay || mq.matches)
    }
    mq.addEventListener('change', apply)
    window.addEventListener('hashchange', apply)
    apply()
    return () => {
      mq.removeEventListener('change', apply)
      window.removeEventListener('hashchange', apply)
    }
  }, [])
  return (
    <Canvas
      camera={{ position: [-46, 30, 79], fov: 58 }}
      dpr={quiet ? 1 : [1, 2]}
      frameloop={quiet ? 'demand' : 'always'}
      gl={{ antialias: !quiet, powerPreference: 'high-performance' }}
      style={{ position: 'fixed', inset: 0 }}
    >
      <color attach="background" args={['#05060a']} />
      <fog attach="fog" args={['#05060a', 60, 380]} />
      <PointsRaycast />
      <StarField />
      <GlobeSpin>
        <MapLayer />
        <PlanetLayer planets={planets} />
      </GlobeSpin>
      <CameraRig />
      {!quiet && (
        <EffectComposer>
          <Bloom intensity={1.7} luminanceThreshold={0.2} luminanceSmoothing={0.35} mipmapBlur radius={0.8} />
        </EffectComposer>
      )}
    </Canvas>
  )
}
