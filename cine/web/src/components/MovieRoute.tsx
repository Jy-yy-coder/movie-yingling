import { motion } from 'framer-motion'
import { cnTitle } from '../api'
import type { RouteStage } from '../types'
import ExplainCard from './ExplainCard'
import { MatchRing, MiniRadar } from './Navigator'

/* AI 电影探索路线：四段式时间轴（热身→深入→跨界→奇遇），复用导航员路线样式 */
const ROUTE_COLOR = '#d4a860'

export default function MovieRoute({ stages }: { stages: RouteStage[] }) {
  if (!stages.length) return null
  return (
    <section className="mroute glass">
      <div className="mroute-head">
        <span className="navi-route-line" />
        <span>✦ 你的专属探索路线</span>
        <span className="navi-route-line" />
      </div>
      <p className="mroute-sub">按你的五维画像生成，四站由浅入深，跟着走一遍吧。</p>
      <div className="navi-route">
        {stages.map((s, i) => (
          <motion.div
            key={s.movie.movie_id}
            className="navi-route-node"
            initial={{ opacity: 0, x: -26 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.15, ease: [0.22, 0.61, 0.36, 1] }}
          >
            <div className="navi-route-seq" style={{ boxShadow: `0 0 16px 2px ${ROUTE_COLOR}66` }}>{s.seq}</div>
            <button
              className="navi-route-card"
              onClick={() => { location.hash = '#/movie/' + s.movie.movie_id }}
            >
              <div className="navi-route-poster">
                {s.movie.poster_thumb
                  ? <img src={s.movie.poster_thumb} alt="" loading="lazy" />
                  : <i>{cnTitle(s.movie.title)}</i>}
                <MatchRing match={s.movie.match} color={ROUTE_COLOR} />
              </div>
              <div className="navi-route-info">
                <div className="mroute-stage t-mono">{s.name}</div>
                <div className="navi-route-title">{cnTitle(s.movie.title)}</div>
                <div className="navi-route-meta t-mono">{s.movie.year || '—'} · 豆瓣 {s.movie.rating}</div>
                <div className="navi-route-reason">
                  <span className="navi-route-dim" style={{ color: ROUTE_COLOR }}>{s.movie.top_dim} {s.movie.top_val} 分</span>
                  <span className="mroute-why">{s.movie.reason}</span>
                </div>
                {s.movie.explain && <ExplainCard explain={s.movie.explain} />}
              </div>
              <div className="navi-route-radar-wrap">
                <MiniRadar dna={s.movie.dna} color={ROUTE_COLOR} />
              </div>
            </button>
            <p className="mroute-desc">{s.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  )
}
