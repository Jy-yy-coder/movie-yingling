import { motion } from 'framer-motion'
import { cnTitle, DNA_DIMS } from '../api'
import type { PersonalityProfile } from '../types'
import ExplainCard from './ExplainCard'
import Radar from './Radar'

/* 电影人格画像结果卡：五维雷达 + 0-100 分数条 + 关键词 + 画像推荐 */
export default function PersonalityCard({ profile }: { profile: PersonalityProfile }) {
  const radarDna = Object.fromEntries(
    DNA_DIMS.map((d) => [d, Math.round(((profile.dna[d] || 0) / 10) * 10) / 10]))
  return (
    <div className="p-card glass">
      <div className="p-card-head">
        <div>
          <h2 className="p-card-title">🧬 你的电影人格画像</h2>
          {profile.created_at && <p className="p-card-date t-mono">测算于 {profile.created_at}</p>}
        </div>
      </div>

      <div className="p-card-body">
        {/* 雷达 + 分数条 */}
        <div className="p-dna">
          <div className="p-radar"><Radar dna={radarDna} size={230} /></div>
          <div className="p-bars">
            {DNA_DIMS.map((d) => (
              <div key={d} className="p-bar-row">
                <span className="p-bar-label">{d}</span>
                <span className="p-bar-track">
                  <motion.span
                    className="p-bar-fill"
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, profile.dna[d] || 0)}%` }}
                    transition={{ duration: 0.9, ease: [0.32, 0.72, 0.35, 1] }}
                  />
                </span>
                <span className="p-bar-val t-mono">{profile.dna[d] || 0}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 观影关键词 */}
        {profile.keywords.length > 0 && (
          <div className="p-kws">
            {profile.keywords.map((k) => <span key={k} className="p-kw">{k}</span>)}
          </div>
        )}

        {/* 按画像推荐 */}
        {profile.movies.length > 0 && (
          <section className="p-recs">
            <h3 className="p-recs-head">✦ 按你的画像推荐</h3>
            <div className="exp-rail">
              {profile.movies.map((m) => (
                <motion.a
                  key={m.movie_id}
                  className="list-card exp-card"
                  href={`#/movie/${m.movie_id}`}
                  whileHover={{ scale: 1.03, y: -4 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                >
                  <span className="list-card-poster">
                    {m.poster_thumb ? <img src={m.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(m.title)}</i>}
                    <em className="t-mono">{m.rating}</em>
                    <b className="list-card-dim t-mono">匹配 {m.match}%</b>
                  </span>
                  <span className="list-card-title">{cnTitle(m.title)}</span>
                  <span className="list-card-meta">{m.reason}</span>
                  {m.explain && <ExplainCard explain={m.explain} />}
                </motion.a>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
