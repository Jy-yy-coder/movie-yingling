/* 影灵 CINE · 世界地图模块（立体地球仪）
   用 world-atlas 真实国家轮廓（Natural Earth 110m）做两件事：
   ① 在球面上用点阵画出世界地图图案（大陆轮廓贴在星球表面）
   ② 星球按地区采样落在对应国家的真实轮廓内，悬浮在该处地表上空 */
import { feature } from 'topojson-client'
import world from 'world-atlas/countries-110m.json'

/* ---------- 球体投影：经纬度 → 3D 球面坐标（y 轴朝北极） ---------- */
export const GLOBE_R = 30              // 地球仪半径
export const CORE_ALT = 0.55           // 核心 590 颗：紧贴地表
export const EXT_ALT_MIN = 16          // 库外片：漂浮在周围太空（壳层 16~38）
export const EXT_ALT_SPAN = 22

const DEG = Math.PI / 180
export function geoToVec3(lon: number, lat: number, r: number): { x: number; y: number; z: number } {
  const phi = lat * DEG
  const lam = lon * DEG
  return {
    x: r * Math.cos(phi) * Math.sin(lam),
    y: r * Math.sin(phi),
    z: r * Math.cos(phi) * Math.cos(lam),   // 经度 0° 朝向 +z（初始相机方向）
  }
}

/* ---------- 国家轮廓解析 ---------- */
type Ring = number[][]                          // [[lon, lat], ...]
interface Shape { ring: Ring; bbox: [number, number, number, number]; area: number }
interface Country { shapes: Shape[]; area: number }

/* 射线法：点是否在环内（只取外环，忽略内海孔洞，采样误差可忽略） */
function inRing(px: number, py: number, ring: Ring): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1]
    const xj = ring[j][0], yj = ring[j][1]
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

function ringArea(ring: Ring): number {
  let s = 0
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    s += (ring[j][0] + ring[i][0]) * (ring[j][1] - ring[i][1])
  }
  return Math.abs(s / 2)
}

/* ISO 3166-1 数字码（world-atlas 用三位字符串） */
const CHINA = ['156']
const JAPAN = ['392']
const KOREA = ['410']
const AMERICAS = ['840', '124', '484', '076', '032', '170', '152', '604', '862', '068', '218', '858', '600', '192', '320']
const EUROPE = ['826', '250', '276', '380', '724', '620', '528', '056', '752', '578', '208', '246', '616', '756', '040', '372', '300', '203', '348', '642', '804', '688', '100', '191', '352']

const _countries = new Map<string, Country>()
let _ready = false

function build(): void {
  if (_ready) return
  _ready = true
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const topo = world as any
  const feats = (feature(topo, topo.objects.countries) as any).features as any[]
  for (const f of feats) {
    const id = String(f.id)
    const geoms = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates
    const shapes: Shape[] = []
    for (const poly of geoms) {
      const ring = poly[0] as Ring              // 外环
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const pt of ring) {
        if (pt[0] < minX) minX = pt[0]
        if (pt[0] > maxX) maxX = pt[0]
        if (pt[1] < minY) minY = pt[1]
        if (pt[1] > maxY) maxY = pt[1]
      }
      shapes.push({ ring, bbox: [minX, minY, maxX, maxY], area: ringArea(ring) })
    }
    _countries.set(id, { shapes, area: shapes.reduce((s, sh) => s + sh.area, 0) })
  }
}

/* ---------- 地区采样：在对应国家轮廓内随机取一点 ---------- */
export type GeoGroup = '美洲' | '欧洲' | '华语' | '日本' | '韩国'
const GROUPS: Record<GeoGroup, string[]> = {
  美洲: AMERICAS, 欧洲: EUROPE, 华语: CHINA, 日本: JAPAN, 韩国: KOREA,
}

/* 在指定地区的轮廓内采样一个经纬度（按国家面积加权，拒绝采样保证落在陆地上） */
export function sampleInGroup(group: GeoGroup, rnd: () => number): { lon: number; lat: number } {
  build()
  const ids = GROUPS[group]
  const list = ids.map((id) => _countries.get(id)).filter((c): c is Country => !!c && c.area > 0)
  const total = list.reduce((s, c) => s + c.area, 0)
  let pick = rnd() * total
  let country = list[0]
  for (const c of list) { pick -= c.area; if (pick <= 0) { country = c; break } }
  // 在国家内按多边形面积加权选一个外环，再在其 bbox 内拒绝采样
  let p = rnd() * country.area
  let shape = country.shapes[0]
  for (const sh of country.shapes) { p -= sh.area; if (p <= 0) { shape = sh; break } }
  const [minX, minY, maxX, maxY] = shape.bbox
  for (let t = 0; t < 200; t++) {
    const lon = minX + rnd() * (maxX - minX)
    const lat = minY + rnd() * (maxY - minY)
    if (inRing(lon, lat, shape.ring)) return { lon, lat }
  }
  return { lon: (minX + maxX) / 2, lat: (minY + maxY) / 2 }
}

/* ---------- 世界地图点阵：所有陆地国家采样出的暗色点，贴在球面上画出大陆 ---------- */
const DOT_DENSITY = 0.32                 // 每平方度约多少个点（控制点阵疏密）

export function buildMapDots(): Float32Array {
  build()
  const rndDot = mulberry(20260811)      // 点阵固定种子（与星球布局独立）
  const pts: number[] = []
  for (const c of _countries.values()) {
    if (c.area <= 0) continue
    const want = Math.min(900, Math.max(3, Math.round(c.area * DOT_DENSITY)))
    let placed = 0
    for (let t = 0; t < want * 30 && placed < want; t++) {
      // 按多边形面积加权选环
      let p = rndDot() * c.area
      let shape = c.shapes[0]
      for (const sh of c.shapes) { p -= sh.area; if (p <= 0) { shape = sh; break } }
      const [minX, minY, maxX, maxY] = shape.bbox
      const lon = minX + rndDot() * (maxX - minX)
      const lat = minY + rndDot() * (maxY - minY)
      if (lat < -58) continue            // 裁掉南极大陆
      if (!inRing(lon, lat, shape.ring)) continue
      const q = geoToVec3(lon, lat, GLOBE_R)   // 贴在球面表面
      pts.push(q.x, q.y, q.z)
      placed++
    }
  }
  return new Float32Array(pts)
}

/* 点阵专用确定性随机 */
function mulberry(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0
    return s / 2 ** 32
  }
}
