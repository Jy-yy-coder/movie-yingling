import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { chat, cnTitle, DNA_DIMS, num } from '../api'
import { useGalaxy } from '../store'
import type { ChatReply, RecCard } from '../types'
import ExplainCard from './ExplainCard'

/* AI 电影导航员：输入心情 → 点亮一条探索路线 1→2→3→4
   设计稿 05：推荐序列带序号圆点、连线、匹配环+迷你雷达+高赞引用 */

const MOODS = [
  { label: '😌 温暖治愈', q: '最近压力很大，想看温暖治愈一点的' },
  { label: '😭 催泪', q: '想哭一下，来点催泪的' },
  { label: '🔥 热血', q: '想重新振作，看部热血的' },
  { label: '🧠 烧脑悬疑', q: '想看烧脑悬疑的' },
  { label: '😂 轻松搞笑', q: '想轻松两小时，来点搞笑的' },
  { label: '💗 浪漫爱情', q: '想看浪漫的爱情片' },
]

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

function RouteCard({ card, idx, delay }: { card: RecCard; idx: number; delay: number }) {
  const color = '#b48cff'
  return (
    <motion.div
      className="navi-route-node"
      initial={{ opacity: 0, x: -26 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 0.61, 0.36, 1] }}
    >
      <div className="navi-route-seq" style={{ boxShadow: `0 0 16px 2px ${color}66` }}>{idx}</div>
      <button
        className="navi-route-card"
        onClick={() => { location.hash = '#/movie/' + card.movie_id; useGalaxy.getState().setNavigatorOpen(false) }}
      >
        <div className="navi-route-poster">
          {card.poster_thumb
            ? <img src={card.poster_thumb} alt="" loading="lazy" />
            : <i>{cnTitle(card.title)}</i>}
          <MatchRing match={card.match} color={color} />
        </div>
        <div className="navi-route-info">
          <div className="navi-route-title">{cnTitle(card.title)}</div>
          <div className="navi-route-meta t-mono">{card.year || '—'} · 豆瓣 {card.rating}</div>
          <div className="navi-route-reason">
            <span className="navi-route-dim" style={{ color }}>{card.top_dim} {card.top_val} 分</span>
            {card.reason && <span className="navi-route-quote">「{card.reason.replace(/^.+?分/, '').trim().slice(0, 30)}」</span>}
          </div>
          {card.explain && <ExplainCard explain={card.explain} />}
        </div>
        <div className="navi-route-radar-wrap">
          <MiniRadar dna={card.dna} color={color} />
        </div>
      </button>
    </motion.div>
  )
}

export default function Navigator() {
  const open = useGalaxy((s) => s.navigatorOpen)
  const setOpen = useGalaxy((s) => s.setNavigatorOpen)
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [reply, setReply] = useState<ChatReply | null>(null)
  const [err, setErr] = useState('')
  const bodyRef = useRef<HTMLDivElement>(null)

  const go = async (text?: string) => {
    const msg = (text ?? q).trim()
    if (!msg || busy) return
    setBusy(true)
    setErr('')
    setReply(null)
    try {
      const r = await chat(msg, 'rec', true)
      setReply(r)
    } catch (e) {
      setErr((e as Error).message || '请求失败')
    } finally {
      setBusy(false)
    }
  }

  const close = () => { setOpen(false); setTimeout(() => { setReply(null); setQ(''); setErr('') }, 300) }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="navi-mask"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          onClick={close}
        >
          <motion.div
            className="navi glass-strong"
            initial={{ opacity: 0, scale: 0.92, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ duration: 0.35, ease: [0.22, 0.61, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            <button className="nav-close" onClick={close} aria-label="关闭">✕</button>

            <div className="navi-head">
              <div className="navi-logo">影灵</div>
              <div>
                <h2 className="navi-title title-gold">AI 电影导航员</h2>
                <p className="navi-sub">告诉我此刻的心情，影灵会为你点亮一条属于你的探索路线。</p>
              </div>
            </div>

            {!reply && (
              <>
                <div className="navi-input-row">
                  <input
                    className="navi-input"
                    placeholder="比如：最近压力很大，想看温暖一点的..."
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) void go() }}
                  />
                  <button className={`navi-go ${busy ? 'busy' : ''}`} onClick={() => void go()} disabled={busy}>
                    {busy ? '点亮中…' : '出发 ✦'}
                  </button>
                </div>
                <div className="navi-moods">
                  {MOODS.map((m) => (
                    <button key={m.label} className="navi-mood" onClick={() => { setQ(m.q); void go(m.q) }}>{m.label}</button>
                  ))}
                </div>
                {err && <div className="navi-err">{err}</div>}
              </>
            )}

            {busy && (
              <div className="navi-loading">
                <div className="navi-loading-dots"><i /><i /><i /><i /><i /></div>
                <p>正在银河中寻找与你共鸣的电影…</p>
              </div>
            )}

            {reply && !busy && (
              <div className="navi-body" ref={bodyRef}>
                {reply.movies && reply.movies.length > 0 ? (
                  <>
                    <div className="navi-route-head">
                      <span className="navi-route-line" />
                      <span>为你点亮的探索路线</span>
                      <span className="navi-route-line" />
                    </div>
                    <div className="navi-route">
                      {reply.movies.map((m, i) => (
                        <RouteCard key={m.movie_id} card={m} idx={i + 1} delay={0.25 + i * 0.4} />
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="navi-answer">
                      {reply.offline && <span className="offline-tag">离线模式 · 规则推荐</span>}
                      <p>{reply.text}</p>
                    </div>
                    {reply.citations.length > 0 && (
                      <div className="navi-cits">
                        {reply.citations.slice(0, 3).map((c, i) => (
                          <button key={i} className="navi-cit" onClick={() => { if (c.movie_id) { location.hash = '#/movie/' + c.movie_id; setOpen(false) } }}>
                            <em>{c.title}</em>
                            <span>“{c.text.slice(0, 44)}…”</span>
                            <b className="t-mono">{num(c.votes || 0)} 票</b>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
                <button className="navi-again" onClick={() => { setReply(null); setQ('') }}>↺ 换个心情再试</button>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
