import { DNA_DIMS } from '../api'

/* 口碑五维雷达（从旧 app.js 迁移） */
export default function Radar({ dna, size = 230 }: { dna: Record<string, number>; size?: number }) {
  const cx = size / 2, cy = size / 2, R = size / 2 - 32, n = DNA_DIMS.length
  const pt = (i: number, r: number): [number, number] => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / n
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
  }
  const poly = (s: number) => DNA_DIMS.map((_, i) => pt(i, R * s).join(',')).join(' ')
  const rings = [0.25, 0.5, 0.75, 1].map((s) =>
    <polygon key={s} points={poly(s)} fill="none" stroke="rgba(255,255,255,0.08)" />)
  const axes = DNA_DIMS.map((_, i) => {
    const [x, y] = pt(i, R)
    return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="rgba(255,255,255,0.06)" />
  })
  const vals = DNA_DIMS.map((d, i) => pt(i, R * Math.max(0, Math.min(10, dna[d] || 0)) / 10).join(',')).join(' ')
  const labels = DNA_DIMS.map((d, i) => {
    const [x, y] = pt(i, R + 20)
    return <text key={d} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="12" fill="var(--color-dust-500)">{d}</text>
  })
  const vtxt = DNA_DIMS.map((d, i) => {
    const [x, y] = pt(i, R * 0.62)
    const v = dna[d] || 0
    return <text key={d} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="11.5" fontFamily="IBM Plex Mono, ui-monospace, monospace" fontWeight="700" fill={v >= 8 ? 'var(--color-gold-300)' : 'var(--color-dust-500)'}>{v}</text>
  })
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label="口碑五维雷达">
      {rings}{axes}
      <polygon points={vals} fill="rgba(212,168,96,0.18)" stroke="var(--color-gold-500)" strokeWidth="1.8" strokeLinejoin="round" />
      {labels}{vtxt}
    </svg>
  )
}
