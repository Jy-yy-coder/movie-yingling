import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { cnTitle, DNA_DIMS, movies } from '../api'
import { regionLabel } from '../regions'
import type { Movie } from '../types'

/* 列表页 #/list：地区 / 类型 / 年份 / 评分 / DNA 排序筛选 + 分页 */

const REGIONS = ['中国', '日本', '韩国', '欧洲', '美国', '其他']
const GENRES = ['剧情', '喜剧', '动作', '爱情', '科幻', '犯罪', '悬疑', '动画', '奇幻', '家庭', '战争', '恐怖']
const SORTS = [
  { key: 'dna', label: 'DNA 综合' },
  { key: 'rating', label: '评分' },
  ...DNA_DIMS.map((d) => ({ key: d, label: d })),
]
const PAGE = 24

function readQuery(): Record<string, string> {
  const out: Record<string, string> = {}
  new URLSearchParams(location.hash.split('?')[1] || '').forEach((v, k) => { out[k] = v })
  return out
}

/* 列表主体面板：q/setParam 由外部注入（页面版 hash 驱动，探索版 state 驱动） */
export function ListPanel({ q, setParam, embed = false }: {
  q: Record<string, string>
  setParam: (patch: Record<string, string>) => void
  embed?: boolean
}) {
  const [data, setData] = useState<{ total: number; page: number; items: Movie[]; fallback?: boolean } | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)
  /* 搜索词本地编辑态：可修改/清除（此前搜索词粘住改不了） */
  const [kw, setKw] = useState(q.q || '')
  useEffect(() => { setKw(q.q || '') }, [q.q])

  useEffect(() => {
    setLoading(true)
    movies({
      region: q.region || '', genre: q.genre || '', sort: q.sort || 'dna',
      q: q.q || '', page: Number(q.page) || 1, limit: PAGE,
    }).then((d) => { setData(d); setErr('') })
      .catch((e) => setErr((e as Error).message))
      .finally(() => setLoading(false))
  }, [q])

  const region = q.region || ''
  const genre = q.genre || ''
  const sort = q.sort || 'dna'
  const page = Number(q.page) || 1
  const submitKw = () => {
    const s = kw.trim()
    if (s !== (q.q || '')) setParam({ q: s, page: '' })
  }
  const clearKw = () => { setKw(''); if (q.q) setParam({ q: '', page: '' }) }

  return (
    <div className={'list' + (embed ? ' embed' : '')}>
        <div className="list-head">
          <h2 className="list-title title-gold">{q.q ? `搜索「${q.q}」` : region ? region + ' · ' + (genre || '全部') : '推荐影片'}</h2>
          <div className="exp-search list-search">
            <input
              value={kw}
              onChange={(e) => setKw(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) submitKw() }}
              placeholder="搜索电影 / 导演 / 演员 / 心情，多个词用空格分隔"
            />
            {q.q && <button className="list-search-clear" onClick={clearKw} title="清除搜索词">✕</button>}
            <button onClick={submitKw}>搜索</button>
          </div>
          <div className="list-filters">
            <div className="list-filter-row">
              <span className="list-f-lab">地区</span>
              <button className={`chip-mini ${!region ? 'on' : ''}`} onClick={() => setParam({ region: '' })}>全部</button>
              {REGIONS.map((r) => (
                <button key={r} className={`chip-mini ${region === r ? 'on' : ''}`} onClick={() => setParam({ region: r, genre: '' })}>{r}</button>
              ))}
            </div>
            <div className="list-filter-row">
              <span className="list-f-lab">类型</span>
              <button className={`chip-mini ${!genre ? 'on' : ''}`} onClick={() => setParam({ genre: '' })}>全部</button>
              {GENRES.map((g) => (
                <button key={g} className={`chip-mini ${genre === g ? 'on' : ''}`} onClick={() => setParam({ genre: g })}>{g}</button>
              ))}
            </div>
            <div className="list-filter-row">
              <span className="list-f-lab">排序</span>
              {SORTS.map((s) => (
                <button key={s.key} className={`chip-mini ${sort === s.key ? 'on' : ''}`} onClick={() => setParam({ sort: s.key })}>{s.label}</button>
              ))}
            </div>
          </div>
        </div>

        {err && <div className="list-err">{err}</div>}
        {loading && <div className="list-loading">正在放映…</div>}

        {data && !loading && data.items.length === 0 && (
          <div className="list-empty">
            <p className="list-empty-title">{q.q ? `没有找到与「${q.q}」匹配的影片` : '暂无推荐'}</p>
            {q.q && (
              <>
                <p className="list-empty-tip">试试只用片名或导演名，或换个说法（如「治愈」「悬疑」「宫崎骏 治愈」）</p>
                <a className="list-empty-cta" href="#/explore?tab=chat">去问影灵帮你找 →</a>
              </>
            )}
          </div>
        )}

        {data && !loading && data.items.length > 0 && q.q && data.fallback && (
          <div className="list-fallback-note">未找到与「{q.q}」直接匹配的影片，以下按关键词为你推荐</div>
        )}

        {data && !loading && data.items.length > 0 && (
          <>
            <div className="list-grid">
              {data.items.map((m) => (
                <a className="list-card" href={`#/movie/${m.movie_id}`} key={m.movie_id}>
                  <span className="list-card-poster">
                    {m.poster_thumb ? <img src={m.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(m.title)}</i>}
                    <em className="t-mono">{m.rating}</em>
                    {m.dna && (() => {
                      const dim = DNA_DIMS.reduce((a, d) => (m.dna[d] || 0) > (m.dna[a] || 0) ? d : a, DNA_DIMS[0])
                      return <b className="list-card-dim t-mono">{dim} {m.dna[dim]}</b>
                    })()}
                  </span>
                  <span className="list-card-title">{cnTitle(m.title)}</span>
                  <span className="list-card-meta t-mono">{m.year || ''} · {regionLabel(m.region)} · {m.genres?.[0] || ''}</span>
                </a>
              ))}
            </div>
            {data.total > PAGE && (
              <div className="list-pager">
                <button className={`chip-mini ${page <= 1 ? 'dis' : ''}`} onClick={() => setParam({ page: String(page - 1) })} disabled={page <= 1}>‹ 上一页</button>
                <span className="t-mono">第 {page} / {Math.max(1, Math.ceil(data.total / PAGE))} 页</span>
                <button className={`chip-mini ${page >= Math.ceil(data.total / PAGE) ? 'dis' : ''}`} onClick={() => setParam({ page: String(page + 1) })} disabled={page >= Math.ceil(data.total / PAGE)}>下一页 ›</button>
              </div>
            )}
          </>
        )}
    </div>
  )
}

export default function List() {
  const [q, setQ] = useState(readQuery())

  useEffect(() => {
    const onHash = () => {
      setQ(readQuery())
      document.querySelector('.list')?.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const setParam = (patch: Record<string, string>) => {
    setQ((prev) => {
      const next = { ...prev, ...patch }
      if (!patch.page && next.page) delete next.page   // 筛选/排序变更时重置页码，翻页保留
      return next
    })
    const next = { ...readQuery(), ...patch }
    if (!patch.page && next.page) delete next.page
    const qs = new URLSearchParams(next).toString()
    history.replaceState(null, '', '#/list' + (qs ? '?' + qs : ''))
  }

  return (
    <motion.div
      className="overlay list-page"
      initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
      transition={{ duration: 0.55, ease: [0.32, 0.72, 0.35, 1] }}
    >
      <a className="page-back page-back-l" href="#/">‹ 返回银河</a>
      <ListPanel q={q} setParam={setParam} />
    </motion.div>
  )
}
