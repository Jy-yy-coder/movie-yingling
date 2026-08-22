import { DNA_DIMS } from '../api'

/* 匹配环 + 迷你雷达：从原「AI 电影导航员」拆出的共用展示组件（导航员弹窗已下线） */

/* 匹配环（SVG 圆环） */
export function MatchRing({ match, color }: { match: number; color: string }) {
  const r = 21
  const c = 2 * Math.PI * r
  return (
    <div className="navi-ring">
      <svg width={52} height={52} viewBox="0 0 52 52">
        <circle cx={26} cy={26} r={r} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={3} />
        <circle
          cx={26} cy={26} r={r} fill="none"
          stroke={color} strokeWidth={3} strokeLinecap="round"
          strokeDasharray={`${(match / 100) * c} ${c}`}
          transform="rotate(-90 26 26)"
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
      </svg>
      <b>{match}</b>
      <span>匹配</span>
    </div>
  )
}

/* 迷你雷达：五维 DNA */
export function MiniRadar({ dna, color }: { dna: Record<string, number>; color: string }) {
  const dims = DNA_DIMS
  const n = dims.length
  const cx = 40, cy = 40, R = 28
  const pt = (i: number, v: number) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2
    const r = (v / 10) * R
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r]
  }
  const pts = dims.map((d, i) => pt(i, dna[d] || 0).join(',')).join(' ')
  return (
    <svg width={80} height={80} viewBox="0 0 80 80" className="navi-radar">
      {[0.33, 0.66, 1].map((f) => (
        <polygon key={f} points={dims.map((_, i) => pt(i, 10 * f).join(',')).join(' ')} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth={1} />
      ))}
      {dims.map((_, i) => {
        const [x, y] = pt(i, 10)
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
      })}
      <polygon points={pts} fill={color} fillOpacity={0.28} stroke={color} strokeWidth={1.5} strokeLinejoin="round" style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
    </svg>
  )
}
