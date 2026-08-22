/* 影灵 CINE · 星球 3D 布局（立体地球仪）
   590 颗核心片紧贴地球表面（采样落在对应国家真实轮廓内，钉在地表）；
   4410 颗库外片随机漂浮在地球周围太空的壳层里（不按地区）。
   用空间网格加速的碰撞排斥松弛保证任意两颗之间都有间隙，不黏连。 */
import type { Planet } from './types'
import { sampleInGroup, geoToVec3, GLOBE_R, CORE_ALT, EXT_ALT_MIN, EXT_ALT_SPAN } from './worldmap'

/* FNV-1a 哈希 → 确定性伪随机 */
function hash(str: string): number {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}
function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

export interface PlanetPos {
  x: number
  y: number
  z: number
}

/* 星球视觉半径映射范围（PlanetLayer 渲染用，须与布局间隙口径一致） */
export const RENDER_R = { min: 0.36, max: 0.52 }
const SRC_R_MIN = 0.5
const SRC_R_MAX = 2.2
const GAP = 0.55          // 任意两颗星球之间的最小表面间隙
const ITER = 60           // 松弛迭代轮数上限
const CELL = 2.0          // 空间网格边长（≥ 最大中心距 0.52*2+0.55≈1.6，只查相邻格）

/* 地区 → 地图采样组：六值各自钉在对应大陆（美国→美国本土，欧洲→欧洲，
   其他=非西方非中日韩，钉在南亚/南美/非洲/中东等地区） */
function groupOf(p: Planet): '中国' | '日本' | '韩国' | '欧洲' | '美国' | '其他' {
  if (p.region === '中国') return '中国'
  if (p.region === '日本') return '日本'
  if (p.region === '韩国') return '韩国'
  if (p.region === '美国') return '美国'
  if (p.region === '其他') return '其他'
  return '欧洲'
}

const _final: Record<string, PlanetPos> = {}
const _focus: Record<string, PlanetPos> = {}
let _builtFor: Planet[] | null = null

export function renderR(p: Planet): number {
  const t = Math.min(1, Math.max(0, (p.r - SRC_R_MIN) / (SRC_R_MAX - SRC_R_MIN)))
  return RENDER_R.min + t * (RENDER_R.max - RENDER_R.min)
}

export function buildLayout(planets: Planet[]): void {
  if (_builtFor === planets && Object.keys(_final).length) return
  _builtFor = planets
  for (const k in _final) delete _final[k]
  for (const k in _focus) delete _focus[k]
  if (!planets.length) return

  const n = planets.length
  const rnd = rng(hash('cine:universe'))
  const xs = new Float64Array(n)
  const ys = new Float64Array(n)
  const zs = new Float64Array(n)
  const rs = planets.map(renderR)

  const R_CORE = GLOBE_R + CORE_ALT        // 核心片钉在地表的半径
  const MIN_R_EXT = GLOBE_R + 12           // 库外片壳层下限，不侵入地表附近
  const isExt = planets.map((p) => (p.k ?? 1) < 1)

  /* 初始种子：核心片按国家轮廓钉在地表；库外片随机方向漂浮在周围壳层 */
  for (let i = 0; i < n; i++) {
    if (isExt[i]) {
      const rad = GLOBE_R + EXT_ALT_MIN + rnd() * EXT_ALT_SPAN
      const u = rnd() * 2 - 1                              // 球面均匀分布
      const phi = rnd() * Math.PI * 2
      const s = Math.sqrt(1 - u * u)
      xs[i] = rad * s * Math.cos(phi)
      ys[i] = rad * u
      zs[i] = rad * s * Math.sin(phi)
    } else {
      const q = sampleInGroup(groupOf(planets[i]), rnd)
      const v = geoToVec3(q.lon, q.lat, R_CORE)
      xs[i] = v.x
      ys[i] = v.y
      zs[i] = v.z
    }
  }

  /* 碰撞排斥松弛（空间网格加速）：把表面距离 < (r_i + r_j + GAP) 的球对沿连线推开；
     每轮结束后做球面约束：核心片重新钉回地表，库外片不允许跌进近地空间 */
  const keyOf = (x: number, y: number, z: number) =>
    ((Math.floor(x / CELL) + 64) << 14) | ((Math.floor(y / CELL) + 64) << 7) | (Math.floor(z / CELL) + 64)
  for (let it = 0; it < ITER; it++) {
    const grid = new Map<number, number[]>()
    for (let i = 0; i < n; i++) {
      const key = keyOf(xs[i], ys[i], zs[i])
      const arr = grid.get(key)
      if (arr) arr.push(i); else grid.set(key, [i])
    }
    let moved = false
    for (let i = 0; i < n; i++) {
      const ix = Math.floor(xs[i] / CELL), iy = Math.floor(ys[i] / CELL), iz = Math.floor(zs[i] / CELL)
      for (let ax = -1; ax <= 1; ax++) for (let ay = -1; ay <= 1; ay++) for (let az = -1; az <= 1; az++) {
        const arr = grid.get(((ix + ax + 64) << 14) | ((iy + ay + 64) << 7) | (iz + az + 64))
        if (!arr) continue
        for (const j of arr) {
          if (j <= i) continue
          const dx = xs[j] - xs[i]
          const dy = ys[j] - ys[i]
          const dz = zs[j] - zs[i]
          const min = rs[i] + rs[j] + GAP
          const d2 = dx * dx + dy * dy + dz * dz
          if (d2 < min * min) {
            const d = Math.sqrt(d2) || 0.001
            const push = ((min - d) / d) * 0.5
            xs[i] -= dx * push; xs[j] += dx * push
            ys[i] -= dy * push; ys[j] += dy * push
            zs[i] -= dz * push; zs[j] += dz * push
            moved = true
          }
        }
      }
    }
    if (!moved) break
    for (let i = 0; i < n; i++) {
      const rr = Math.sqrt(xs[i] * xs[i] + ys[i] * ys[i] + zs[i] * zs[i])
      if (rr <= 0.001) continue
      if (!isExt[i]) {
        const s = R_CORE / rr                    // 核心片：始终钉在地表
        xs[i] *= s; ys[i] *= s; zs[i] *= s
      } else if (rr < MIN_R_EXT) {
        const s = MIN_R_EXT / rr                 // 库外片：不跌进近地空间
        xs[i] *= s; ys[i] *= s; zs[i] *= s
      }
    }
  }

  planets.forEach((p, i) => { _final[p.id] = { x: xs[i], y: ys[i], z: zs[i] } })

  /* 聚焦中心：地区 / 地区+类型 的质心（相机飞行用）——只用核心片计算，
     因为库外片随机散布在周围太空，混入会把质心拉向球心 */
  const acc: Record<string, { x: number; y: number; z: number; n: number }> = {}
  planets.forEach((p) => {
    if ((p.k ?? 1) < 1) return
    const pos = _final[p.id]
    const keys = [p.region, p.region + '|' + (p.genres[0] || '')]
    keys.forEach((k) => {
      const a = acc[k] || (acc[k] = { x: 0, y: 0, z: 0, n: 0 })
      a.x += pos.x; a.y += pos.y; a.z += pos.z; a.n++
    })
  })
  Object.keys(acc).forEach((k) => {
    const a = acc[k]
    _focus[k] = { x: a.x / a.n, y: a.y / a.n, z: a.z / a.n }
  })
}

export function planetPos(p: Planet): PlanetPos {
  return _final[p.id] || { x: 0, y: 0, z: 0 }
}

/* 聚焦点：无筛选=球心；选地区/类型=对应星球群的质心。
   六值地区（中国/日本/韩国/欧洲/美国/其他）直接命中；复合词（欧美/日韩）
   取各成员地区质心的均值；「地区|类型」二级质心优先，缺失时回落地区质心。 */
const GROUP_MEMBERS: Record<string, string[]> = {
  欧美: ['欧洲', '美国'],
  日韩: ['日本', '韩国'],
}
export function focusPoint(region: string, genre: string): PlanetPos {
  if (!region) return { x: 0, y: 0, z: 0 }
  const members = GROUP_MEMBERS[region] || [region]
  const pts: PlanetPos[] = []
  for (const k of members) {
    const p = (genre && _focus[k + '|' + genre]) || _focus[k]
    if (p) pts.push(p)
  }
  if (!pts.length) return { x: 0, y: 0, z: 0 }
  const n = pts.length
  return {
    x: pts.reduce((s, p) => s + p.x, 0) / n,
    y: pts.reduce((s, p) => s + p.y, 0) / n,
    z: pts.reduce((s, p) => s + p.z, 0) / n,
  }
}

/* UI 星域分组口径（HUD 面板，与数据六值一致） */
export const REGIONS = ['中国', '日本', '韩国', '欧洲', '美国', '其他']

/* 六个地区六种颜色（星球发光粒子用，HUD 按钮/悬浮提示同步标识） */
export const REGION_COLORS: Record<string, string> = {
  中国: '#ff5f5f',
  日本: '#ff9ed2',
  韩国: '#6ee7b7',
  欧洲: '#ffd76a',
  美国: '#6ea8ff',
  其他: '#c9cede',
}
