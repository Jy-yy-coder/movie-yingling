import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { cnTitle, DNA_DIMS, movies } from '../api'
import type { Movie } from '../types'
import { ListPanel } from './List'
import { ChatPanel } from './Chat'
import { AccountPanel } from './Account'

/* 探索模式 #/explore：参考「电影AI助手」的应用式界面
   顶部 Tab（首页 / 电影库 / 问影灵 / 我的）+ 面板内容区，从银河底部指引进入 */

type Tab = 'home' | 'library' | 'chat' | 'me'
const TABS: { key: Tab; label: string }[] = [
  { key: 'home', label: '首页' },
  { key: 'library', label: '电影库' },
  { key: 'chat', label: '问影灵' },
  { key: 'me', label: '我的' },
]

/* 此刻心情 → 电影库类型筛选 */
const MOODS = [
  { label: '😌 想被治愈', genre: '家庭' },
  { label: '🔥 想来点刺激', genre: '动作' },
  { label: '😂 笑一笑', genre: '喜剧' },
  { label: '🧠 烧脑一下', genre: '悬疑' },
  { label: '💧 哭一场', genre: '爱情' },
  { label: '🚀 做个科幻梦', genre: '科幻' },
]

function readHash() {
  const hash = location.hash || '#/explore'
  const params: Record<string, string> = {}
  new URLSearchParams(hash.split('?')[1] || '').forEach((v, k) => { params[k] = v })
  const tab: Tab = (['home', 'library', 'chat', 'me'] as Tab[]).includes(params.tab as Tab) ? (params.tab as Tab) : 'home'
  return { tab, params }
}

function greet(): string {
  const h = new Date().getHours()
  if (h < 5) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

export default function Explore() {
  const [route, setRoute] = useState(readHash)
  const tab = route.tab
  /* 日/夜主题：默认夜晚版，可切换白天版（仅作用于探索界面） */
  const [theme, setTheme] = useState<'day' | 'night'>(() => localStorage.getItem('cine_theme') === 'day' ? 'day' : 'night')
  const toggleTheme = () => {
    setTheme((t) => {
      const n = t === 'day' ? 'night' : 'day'
      localStorage.setItem('cine_theme', n)
      return n
    })
  }

  useEffect(() => {
    const onHash = () => setRoute(readHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (t: Tab, extra: Record<string, string> = {}) => {
    const qs = new URLSearchParams({ tab: t, ...extra }).toString()
    location.hash = '#/explore?' + qs
    document.querySelector('.explore-body')?.scrollTo({ top: 0 })
  }

  return (
    <motion.div className={`overlay explore${theme === 'day' ? ' theme-day' : ''}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.5, ease: [0.32, 0.72, 0.35, 1] }}>
      {/* ---------- 顶部导航 ---------- */}
      <header className="explore-nav">
        <button className="explore-logo" onClick={() => go('home')}>
          影灵<span className="explore-logo-ai t-mono">CINE</span>
        </button>
        <nav className="explore-tabs">
          {TABS.map((t) => (
            <motion.button
              key={t.key}
              className={`explore-tab ${tab === t.key ? 'on' : ''}`}
              onClick={() => go(t.key)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 400, damping: 17 }}
            >
              {t.label}
              {tab === t.key && (
                <motion.div
                  className="explore-tab-indicator"
                  layoutId="tab-indicator"
                  transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                />
              )}
            </motion.button>
          ))}
        </nav>
        <button className="exp-theme-btn" onClick={toggleTheme} title="切换日/夜主题">
          {theme === 'day' ? '🌙 夜晚版' : '☀️ 白天版'}
        </button>
      </header>

      {/* ---------- 内容区 ---------- */}
      <div className={`explore-body${tab === 'chat' ? ' exp-noscroll' : ''}`}>
        {tab === 'home' && <Home go={go} />}
        {tab === 'library' && (
          <div className="exp-wrap">
            <LibStateBridge params={route.params} />
          </div>
        )}
        {tab === 'chat' && <ChatPanel embed />}
        {tab === 'me' && <div className="exp-wrap exp-wrap-narrow"><AccountPanel embed /></div>}
      </div>
    </motion.div>
  )
}

/* ---------- 电影库：state 驱动 ListPanel，并同步到 hash 便于首页深链 ---------- */
function LibStateBridge({ params }: { params: Record<string, string> }) {
  const [q, setQ] = useState<Record<string, string>>(() => ({
    region: params.region || '', genre: params.genre || '', sort: params.sort || '', q: params.q || '', page: params.page || '',
  }))
  /* 外部深链变化（首页心情/搜索跳转）时重置内部状态 */
  const key = [params.region, params.genre, params.sort, params.q].join('|')
  useEffect(() => {
    setQ({ region: params.region || '', genre: params.genre || '', sort: params.sort || '', q: params.q || '', page: '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const setParam = (patch: Record<string, string>) => {
    setQ((prev) => {
      const next = { ...prev, ...patch }
      if (!patch.page && next.page) delete next.page
      return next
    })
  }
  return <ListPanel q={q} setParam={setParam} embed />
}

/* ---------- 首页 ---------- */
function Home({ go }: { go: (t: Tab, extra?: Record<string, string>) => void }) {
  const [recs, setRecs] = useState<Movie[]>([])
  const [rail, setRail] = useState<Movie[]>([])
  const [recPage, setRecPage] = useState(1)
  const [kw, setKw] = useState('')
  const [loadErr, setLoadErr] = useState(false)

  useEffect(() => {
    movies({ sort: 'rating', limit: 12 }).then((d) => { setRail(d.items); setLoadErr(false) }).catch(() => setLoadErr(true))
  }, [])
  useEffect(() => {
    movies({ sort: 'dna', limit: 10, page: recPage }).then((d) => { setRecs(d.items); setLoadErr(false) }).catch(() => setLoadErr(true))
  }, [recPage])

  const search = () => {
    const q = kw.trim()
    if (q) go('library', { q })
  }

  return (
    <div className="exp-wrap exp-home">
      {/* 问候 + AI 引导（搜索栏在上，影灵聊天/人格测试两个入口在搜索栏下方） */}
      <div className="exp-hero">
        <h1 className="exp-hi">{greet()}，<span className="title-gold">想看点什么？</span></h1>
        <div className="exp-search">
          <input
            value={kw}
            onChange={(e) => setKw(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) search() }}
            placeholder="搜索电影 / 导演 / 演员 / 类型，如「诺兰」「张国荣」「悬疑」"
          />
          <button onClick={search}>搜索</button>
        </div>
        <div className="exp-guide-row">
          <motion.button
            className="exp-guide"
            onClick={() => go('chat')}
            whileHover={{ scale: 1.02, boxShadow: '0 0 30px rgba(240, 217, 160, 0.2)' }}
            whileTap={{ scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          >
            <span className="exp-guide-ava">🌌</span>
            <span className="exp-guide-txt">
              <b>影灵懂你 · 陪你 · 记得你</b>
              <small>说说心情或需求，我为你在高分电影里挑片 →</small>
            </span>
            <span className="exp-guide-go">开始聊</span>
          </motion.button>
          <motion.button
            className="exp-guide exp-quiz-strip"
            onClick={() => { location.hash = '#/personality' }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          >
            <span className="exp-guide-ava">🧬</span>
            <span className="exp-guide-txt">
              <b>测一测你的电影人格</b>
              <small>12 道情境题，生成五维观影 DNA 画像与专属推荐 →</small>
            </span>
            <span className="exp-guide-go">去测试</span>
          </motion.button>
        </div>
      </div>

      {/* 影灵今日推荐 */}
      <section className="exp-sec">
        <div className="exp-sec-head">
          <h2>✦ 影灵今日推荐</h2>
          <button className="exp-more" onClick={() => setRecPage((p) => (p % 59) + 1)}>换一批 →</button>
        </div>
        {loadErr && !recs.length
          ? <p className="exp-load-err">⚠ 推荐加载失败，请确认服务已启动后刷新</p>
          : (
            <div className="exp-rail">
              {recs.map((m) => <Card key={m.movie_id} m={m} dim />)}
            </div>
          )}
      </section>

      {/* 此刻心情 */}
      <section className="exp-sec">
        <div className="exp-sec-head"><h2>── 此刻心情 ──</h2></div>
        <div className="exp-moods">
          {MOODS.map((m) => (
            <motion.button
              key={m.genre}
              className="exp-mood"
              onClick={() => go('library', { genre: m.genre })}
              whileHover={{ scale: 1.05, y: -2 }}
              whileTap={{ scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            >
              {m.label}
            </motion.button>
          ))}
        </div>
      </section>

      {/* 口碑榜 */}
      <section className="exp-sec">
        <div className="exp-sec-head">
          <h2>🏆 口碑榜</h2>
          <button className="exp-more" onClick={() => go('library', { sort: 'rating' })}>进电影库 →</button>
        </div>
        <div className="exp-rail">
          {rail.map((m) => <Card key={m.movie_id} m={m} />)}
        </div>
      </section>
    </div>
  )
}

/* 海报卡（与电影库卡片同款） */
function Card({ m, dim = false }: { m: Movie; dim?: boolean }) {
  /* DNA 最强维度 */
  const topDim = m.dna ? DNA_DIMS.reduce((a, d) => (m.dna[d] || 0) > (m.dna[a] || 0) ? d : a, DNA_DIMS[0]) : ''
  return (
    <motion.a
      className="list-card exp-card"
      href={`#/movie/${m.movie_id}`}
      whileHover={{ scale: 1.03, y: -4 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      <span className="list-card-poster">
        {m.poster_thumb ? <img src={m.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(m.title)}</i>}
        <em className="t-mono">{m.rating}</em>
        {dim && m.dna && <b className="list-card-dim t-mono">{topDim} {m.dna[topDim]}</b>}
      </span>
      <span className="list-card-title">{cnTitle(m.title)}</span>
      <span className="list-card-meta t-mono">{m.year || ''} · {m.region}</span>
    </motion.a>
  )
}
