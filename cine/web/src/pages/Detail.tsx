import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { cnTitle, DNA_DIMS, explorer, favorite, feedback, movie, num, unfavorite } from '../api'
import type { Movie } from '../types'
import Radar from '../components/Radar'

export default function Detail({ id }: { id: string }) {
  const [m, setM] = useState<Movie | null>(null)
  const [err, setErr] = useState('')
  const [favOn, setFavOn] = useState(false)

  /* 返回目标：从探索/人格页进来的回到来源页，否则回银河 */
  const from = sessionStorage.getItem('cine_detail_from') || ''
  const backHref = from === '/explore' ? '#/explore' : from === '/personality' ? '#/personality' : from === '/list' ? '#/list' : '#/'

  useEffect(() => {
    setM(null)
    setErr('')
    movie(id).then((d) => { setM(d) }).catch((e) => setErr(e.message))
    let alive = true
    explorer().then((d) => {
      if (alive) setFavOn((d.favorites || []).some((f) => f.movie_id === id))
    }).catch(() => { /* 收藏态非关键 */ })
    // B4：浏览行为信号（进入详情页即记录，供隐式画像）
    void feedback(id, 'view').catch(() => { /* 行为信号非关键 */ })
    return () => { alive = false }
  }, [id])

  if (err) return <div className="overlay"><div className="detail-empty">{err}</div></div>
  /* 数据未到：透明占位，不遮挡镜头推进动画，也不单独显示提示文字 */
  if (!m) return <div className="overlay detail-loading-blank" />

  const [cn, ...rest] = (m.title || '').split(/\s+/)
  const orig = rest.join(' ')
  const s = m.sentiment
  const dna = m.dna || {}
  const hasDna = DNA_DIMS.some((d) => (dna[d] || 0) > 0)   // 无五维数据（库外片）则不展示雷达图
  const dims: [string, number][] = DNA_DIMS.map((d): [string, number] => [d, dna[d] || 0]).sort((a, b) => b[1] - a[1])
  const topD = dims[0], lowD = dims[dims.length - 1]
  const up1 = m.quotes?.up1, dn1 = m.quotes?.dn1

  const toggleFav = async () => {
    try {
      if (favOn) { await unfavorite(id); setFavOn(false); void feedback(id, 'unfav').catch(() => {}) }
      else { await favorite(id); setFavOn(true); void feedback(id, 'fav').catch(() => {}) }
    } catch { /* ignore */ }
  }

  return (
    <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.5 }}>
      <div className="detail-scroll">
        <div className="detail">
          <a className="nav-close" href={backHref} aria-label="关闭">✕</a>

          {/* 头部：海报 + 信息 */}
          <div className="detail-head">
            <motion.div className="detail-poster" initial={{ scale: 0.94, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.7, ease: [0.22, 0.61, 0.36, 1] }}>
              <div className="detail-poster-glow" />
              {m.poster_full
                ? <img src={m.poster_full} alt={m.title} />
                : <div className="detail-poster-no">{cn}</div>}
              <span className="detail-poster-rate t-mono">{m.rating}</span>
            </motion.div>

            <div className="detail-info">
              <div className="detail-title">
                <h1 className="title-gold">{cn}</h1>
                {orig && <div className="detail-orig">{orig}</div>}
              </div>
              <div className="detail-meta">
                {(m.genres || []).map((g) => <span className="tag" key={g}>{g}</span>)}
                {(m.countries || []).slice(0, 2).map((c) => <span className="tag" key={c}>{c}</span>)}
                <span className="tag">{m.region}</span>
                {m.year ? <span className="tag">{m.year}</span> : null}
                {m.runtime_min ? <span className="tag">{m.runtime_min} 分钟</span> : null}
              </div>
              {m.director?.length ? <div className="detail-people">导演 <b>{m.director.join(' / ')}</b></div> : null}
              {m.actors?.length ? <div className="detail-people">主演 <b>{m.actors.slice(0, 4).join(' / ')}</b></div> : null}

              {/* 差评预警 */}
              {m.warn?.text && (
                <div className="detail-warn glass">
                  <span className="warn-icon">⚠</span> 有观众提醒：{m.warn.text}
                </div>
              )}

              <div className="detail-score-row">
                <div className="detail-score">{m.rating}</div>
                <div className="detail-score-meta">
                  <div className="t-mono">豆瓣评分 · {num(m.rating_count || 0)} 人评</div>
                  {s && <div className="t-mono">情绪温度 <b className="t-gold">{s.temp}</b> / 100</div>}
                </div>
                <button className={`detail-fav ${favOn ? 'on' : ''}`} onClick={toggleFav}>{favOn ? '♥ 已收藏' : '♡ 收藏这部电影'}</button>
                <a className="detail-ai-talk" href={`#/chat?movie_id=${id}`}>
                  🍿 AI 陪看
                </a>
              </div>

              <p className="detail-summary">{m.brief || m.summary}</p>

              {/* D3 标签：情绪/场景 */}
              {m.tags && ((m.tags.mood?.length > 0) || (m.tags.scene?.length > 0)) && (
                <div className="detail-tags">
                  {m.tags.mood?.map((t) => <span className="tag-chip warm" key={t}>{t}</span>)}
                  {m.tags.scene?.map((t) => <span className="tag-chip" key={t}>{t}</span>)}
                </div>
              )}
            </div>
          </div>

          {/* AI 解读 + 五维图 */}
          {(s?.ai_summary || hasDna) && (
            <div className="detail-block ai-note">
              <div className="detail-block-title">影灵解读</div>
              <div className="ai-note-layout">
                {hasDna && (
                  <div className="ai-note-radar">
                    <Radar dna={dna} />
                  </div>
                )}
                <div className="ai-note-content">
                  {s?.ai_summary && <p>{s.ai_summary}</p>}
                  {hasDna && (
                    <div className="ai-note-fit t-mono">
                      口碑最稳 <b className="t-gold">{topD[0]} {topD[1]}</b> · 相对短板 {lowD[0]} {lowD[1]}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* 观众情绪宇宙：温度 + 高频情绪词（sentiment.json 真实统计，非装饰） */}
          {s && ((s.emotions?.length ?? 0) > 0 || s.temp != null) && (
            <div className="detail-block">
              <div className="detail-block-title">观众情绪宇宙</div>
              <div className="emo-grid">
                <div className="emo-temp glass">
                  <span className="emo-temp-label">情绪温度</span>
                  <div className="emo-temp-ring" style={{ ['--temp' as string]: String(s.temp ?? 50) }}>
                    <div className="emo-temp-ring-inner"><b>{s.temp}</b><span>/100</span></div>
                  </div>
                  <span className="t-mono emo-temp-cap">
                    {(s.temp ?? 50) >= 55 ? '偏暖 · 观众整体满意' : (s.temp ?? 50) <= 45 ? '偏冷 · 口碑有分歧' : '温和 · 褒贬均衡'}
                  </span>
                </div>
                {(s.emotions?.length ?? 0) > 0 && (
                  <div className="emo-freq glass">
                    <div className="emo-chart-title">高频情绪词</div>
                    <div className="emo-freq-list">
                      {s.emotions.slice(0, 6).map((e) => (
                        <div className="emo-freq-item" key={e.w}>
                          <span className="emo-freq-word">{e.w}</span>
                          <i><i style={{ width: `${Math.round((e.n / (s.emotions[0]?.n || 1)) * 100)}%` }} /></i>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 真实短评：优先用 top_comments（各3条），降级用 quotes（各1条） */}
          {(m.top_comments?.up?.length || m.top_comments?.dn?.length || up1 || dn1) && (
            <div className="detail-block">
              <div className="detail-block-title">真实短评</div>
              <div className="quote-section">
                {/* 好评区 */}
                {(m.top_comments?.up?.length ? m.top_comments.up : up1 ? [up1] : []).length > 0 && (
                  <div className="quote-group">
                    <div className="quote-group-label">好评</div>
                    {(m.top_comments?.up?.length ? m.top_comments.up : up1 ? [up1] : []).map((c, i) => (
                      <div key={i} className="quote-card glass">
                        <div className="quote-text">"{c.text}"</div>
                        <div className="quote-meta t-mono">{num(c.votes)} 赞</div>
                      </div>
                    ))}
                  </div>
                )}
                {/* 差评区 */}
                {(m.top_comments?.dn?.length ? m.top_comments.dn : dn1 ? [dn1] : []).length > 0 && (
                  <div className="quote-group">
                    <div className="quote-group-label">差评</div>
                    {(m.top_comments?.dn?.length ? m.top_comments.dn : dn1 ? [dn1] : []).map((c, i) => (
                      <div key={i} className="quote-card glass cool">
                        <div className="quote-text">"{c.text}"</div>
                        <div className="quote-meta t-mono">{num(c.votes)} 赞</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 彩蛋/冷知识 */}
          {m.egg?.text && (
            <div className="detail-block egg-note">
              <div className="detail-block-title">🥚 冷知识</div>
              <p>{m.egg.text}</p>
            </div>
          )}

          {/* 邻近星球 */}
          {m.similar && m.similar.length > 0 && (
            <div className="detail-block">
              <div className="detail-block-title">相似电影</div>
              <div className="sim-grid">
                {m.similar.map((sm) => (
                  <a className="sim" href={`#/movie/${sm.movie_id}`} key={sm.movie_id}>
                    <span className="sim-poster">{sm.poster_thumb ? <img src={sm.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(sm.title)}</i>}<em className="t-mono">{sm.rating}</em></span>
                    <span className="sim-title">{cnTitle(sm.title)}</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          <div className="detail-foot t-mono">影灵 CINE · 全部口碑与评论来自真实豆瓣短评数据</div>
        </div>
      </div>
    </motion.div>
  )
}
