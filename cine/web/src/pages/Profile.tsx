import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { explorer, cnTitle } from '../api'
import { regionLabel } from '../regions'
import type { ExplorerReply } from '../types'

export default function Profile() {
  const [data, setData] = useState<ExplorerReply | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    explorer().then(setData).catch((e) => setErr(e.message))
  }, [])

  return (
    <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.45 }}>
      <div className="profile glass-strong">
        <a className="nav-close" href="#/" aria-label="关闭">✕</a>
        <h2 className="profile-title title-gold">探索档案</h2>

        {err && <div className="profile-err">{err}</div>}
        {!data && !err && <div className="profile-loading">正在同步你的星际足迹…</div>}

        {data && (
          <>
            <div className="profile-level">
              <div className="profile-level-badge">
                <div className="profile-level-tag t-mono">{data.level.tag}</div>
                <div className="profile-level-name">{data.level.name}</div>
              </div>
              <div className="profile-level-meta">
                <div className="profile-progress">
                  <i style={{ width: `${Math.min(100, data.progress)}%` }} />
                </div>
                <div className="profile-progress-txt t-mono">
                  已发现 <b className="t-gold">{data.discovered}</b> / {data.total} 颗星球 · 探索度 {data.progress}%
                </div>
              </div>
            </div>

            {data.badges.length > 0 && (
              <div className="profile-section">
                <div className="profile-section-title">电影徽章 · {data.badges.length}</div>
                <div className="profile-badges">
                  {data.badges.map((b) => (
                    <div className="profile-badge" key={b.key}>
                      <div className="profile-badge-icon">{b.icon}</div>
                      <div className="profile-badge-name">{b.name}</div>
                      <div className="profile-badge-desc">{b.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="profile-section">
              <div className="profile-section-title">我的收藏 · {data.favorites.length}</div>
              {data.favorites.length ? (
                <div className="profile-favs">
                  {data.favorites.map((m) => (
                    <button key={m.movie_id} className="profile-fav" onClick={() => { location.hash = '#/movie/' + m.movie_id }}>
                      <span className="profile-fav-poster">
                        {m.poster_thumb ? <img src={m.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(m.title)}</i>}
                        <em className="t-mono">{m.rating}</em>
                      </span>
                      <span className="profile-fav-title">{cnTitle(m.title)}</span>
                      <span className="profile-fav-meta t-mono">{m.year || ''} · {regionLabel(m.region)}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="profile-empty">还没有收藏。点击银河中的星球，收藏你心仪的电影吧。</div>
              )}
            </div>
          </>
        )}
      </div>
    </motion.div>
  )
}
