import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { chat, cnTitle, feedback, num, watchOpening } from '../api'
import type { ChatReply } from '../types'
import ExplainCard from '../components/ExplainCard'
import WatchIntro from '../components/WatchIntro'

/* 问影灵 · 聊天页：推荐选片 / 陪看讨论双模式、无剧透开关、引用卡片、离线标注 */

interface Msg {
  role: 'user' | 'assistant'
  text: string
  reply?: ChatReply
}

/* 刷新/返回后恢复聊天（仅普通会话；陪看场景与具体电影绑定，不恢复） */
const CHAT_STORE = 'cine_chat_session_v1'
type Stored = { mode: 'rec' | 'talk'; msgs: Msg[]; conversationId?: number; resolvedMovieId?: string }
const loadStored = (): Stored | null => {
  try {
    const raw = sessionStorage.getItem(CHAT_STORE)
    return raw ? (JSON.parse(raw) as Stored) : null
  } catch { return null }
}

const QUICK = [
  '推荐一部催泪的日本电影',
  '想轻松两小时，来点搞笑的',
  '千与千寻讲什么',
  '哪部电影里提到「陀螺」',
]

/* 聊天主体面板：embed 时嵌入探索模式，否则由 Chat 包成右侧滑入整屏页 */
export function ChatPanel({ embed = false, initialMovieId }: { embed?: boolean; initialMovieId?: string }) {
  /* 携电影进入 = 陪看场景：默认 talk 模式 + 开场动画；普通会话尝试恢复上次聊天 */
  const stored = initialMovieId ? null : loadStored()
  const [mode, setMode] = useState<'rec' | 'talk'>(stored?.mode ?? (initialMovieId ? 'talk' : 'rec'))
  /* 无剧透默认开关（个人中心设置，默认开启） */
  const [spoiler, setSpoiler] = useState(() => localStorage.getItem('cine_spoiler_default') !== '0')
  const [msgs, setMsgs] = useState<Msg[]>(stored?.msgs ?? [])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [conversationId, setConversationId] = useState<number | undefined>(stored?.conversationId)
  const [movieId] = useState<string | undefined>(initialMovieId)
  /* 手动陪看中聊中的电影：后续消息（含 chip）继续携带，保持上下文 */
  const [resolvedMovieId, setResolvedMovieId] = useState<string | undefined>(stored?.resolvedMovieId)
  const [intro, setIntro] = useState(Boolean(initialMovieId))
  /* 手动陪看讨论是否已播过开场（每个会话只播一次） */
  const playedWatch = useRef(Boolean(initialMovieId))
  const logRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  /* 消息/会话变化时写入 sessionStorage（陪看场景不持久化），刷新或返回后可续聊 */
  useEffect(() => {
    if (initialMovieId) return
    if (!msgs.length && !conversationId) {
      sessionStorage.removeItem(CHAT_STORE)
      return
    }
    sessionStorage.setItem(CHAT_STORE, JSON.stringify({ mode, msgs, conversationId, resolvedMovieId }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [msgs, conversationId, resolvedMovieId])

  const push = (m: Msg) => setMsgs((prev) => [...prev, m])
  const clear = () => {
    setMsgs([])
    setConversationId(undefined) // 清空时创建新会话
    setResolvedMovieId(undefined)
    playedWatch.current = false  // 清空后允许重新播放陪看开场
    inputRef.current?.focus()
  }

  const send = async (text?: string) => {
    const msg = (text ?? input).trim()
    if (!msg || busy) return
    setInput('')
    push({ role: 'user', text: msg })
    setBusy(true)
    try {
      const effMovieId = movieId ?? resolvedMovieId
      const r = await chat(msg, mode, spoiler, conversationId, effMovieId)
      if (r.conversation_id && !conversationId) {
        setConversationId(r.conversation_id)
      }
      /* 记住本轮聊中的电影（含推荐选片模式的电影问答），供后续追问携带 */
      if (r.movie_id) setResolvedMovieId(r.movie_id)
      /* 陪看讨论中首次点名电影 → 同步详情页的开场动画（回复自带引导 chip） */
      if (mode === 'talk' && !movieId && !playedWatch.current && r.kind === 'talk' && r.movie) {
        playedWatch.current = true
        afterIntroRef.current = () => push({ role: 'assistant', text: r.text, reply: r })
        setIntro(true)
      } else {
        push({ role: 'assistant', text: r.text, reply: r })
      }
    } catch (e) {
      push({ role: 'assistant', text: '连接失败：' + ((e as Error).message || '未知错误') })
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    /* 陪看场景不发通用问候，等开场动画后由开场话题接管 */
    if (!msgs.length && !movieId) {
      push({
        role: 'assistant',
        text: '你好，我是影灵。可以让我推荐电影、讲某部片的剧情，或在全库短评里找台词和梗。',
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* 开场动画结束 → AI 主动开启话题（LLM 生成，后端已带模板兑底） */
  const openWatch = async () => {
    if (!movieId) return
    setBusy(true)
    try {
      const o = await watchOpening(movieId, spoiler)
      push({ role: 'assistant', text: o.text, reply: { ...o, follow_ups: o.chips } })
    } catch {
      push({ role: 'assistant', text: '我陪你一起看这部 🍿 看到什么想聊的，随时跟我说。' })
    } finally {
      setBusy(false)
    }
  }

  /* 开场动画结束后要执行的动作：陪看页=拉开场话题，手动陪看=发出已备好的回复 */
  const afterIntroRef = useRef<(() => void) | null>(initialMovieId ? () => void openWatch() : null)
  const handleIntroDone = () => {
    setIntro(false)
    const fn = afterIntroRef.current
    afterIntroRef.current = null
    fn?.()
  }

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [msgs, busy])

  /* 最后一条 AI 回复的索引：只在其上展示引导 chip */
  const lastAssistantIdx = msgs.reduce((acc, m, idx) => (m.role === 'assistant' ? idx : acc), -1)

  return (
    <div className={'chat' + (embed ? ' embed' : '')}>
        {/* 陪看开场动画（约 4.5 秒）：详情页进入 / 手动陪看首次点名电影 */}
        <AnimatePresence>
          {intro && <WatchIntro key="watch-intro" onDone={handleIntroDone} />}
        </AnimatePresence>

        <div className="chat-head">
          <h1 className="chat-title title-gold">问影灵</h1>
          <p className="chat-sub">推荐 · 陪看讨论 · 找评论 —— AI 只改表述，口碑忠于真实短评</p>
          <div className="chat-toolbar">
            <div className="chat-modes">
              <button className={`chat-mode ${mode === 'rec' ? 'on' : ''}`} onClick={() => { setMode('rec'); clear() }}>推荐选片</button>
              <button className={`chat-mode ${mode === 'talk' ? 'on' : ''}`} onClick={() => { setMode('talk'); clear() }}>陪看讨论</button>
            </div>
            <button className={`chat-spoiler ${spoiler ? 'off' : ''}`} onClick={() => setSpoiler(!spoiler)}>
              {spoiler ? '🛡️ 无剧透已开' : '无剧透关闭'}
            </button>
            <button className="chat-clear t-mono" onClick={clear}>清空</button>
          </div>
        </div>

        <div className="chat-log" ref={logRef}>
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="bub">
                {/* 模型信息标注 */}
                {m.reply && (
                  <span className="model-tag">
                    {m.reply.offline ? '离线模式 · 规则推荐' : (m.reply.model ? `AI · ${m.reply.model}` : 'AI 回复')}
                  </span>
                )}
                <div className="bub-text">{m.text}</div>

                {/* 推荐卡片（复数列表） */}
                {m.reply?.movies && m.reply.movies.length > 0 && (
                  <div className="chat-movies">
                    {m.reply.movies.map((card) => (
                      <button key={card.movie_id} className="chat-movie" onClick={() => { void feedback(card.movie_id, 'pick'); location.hash = '#/movie/' + card.movie_id }}>
                        <span className="chat-movie-poster">
                          {card.poster_thumb ? <img src={card.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(card.title)}</i>}
                          <em className="chat-movie-match">{card.match}%</em>
                        </span>
                        <span className="chat-movie-title">{cnTitle(card.title)}</span>
                        <span className="chat-movie-meta t-mono">{card.year || '—'} · 豆瓣 {card.rating}</span>
                        <span className="chat-movie-reason">{card.reason.slice(0, 30)}</span>
                        {card.explain && <ExplainCard explain={card.explain} />}
                      </button>
                    ))}
                  </div>
                )}

                {/* 单部推荐卡（talk 模式） */}
                {m.reply?.movie && (
                  <div className="chat-movies">
                    <button key={m.reply.movie.movie_id} className="chat-movie" onClick={() => { void feedback(m.reply!.movie!.movie_id, 'pick'); location.hash = '#/movie/' + m.reply!.movie!.movie_id }}>
                      <span className="chat-movie-poster">
                        {m.reply.movie.poster_thumb ? <img src={m.reply.movie.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(m.reply.movie.title)}</i>}
                        <em className="chat-movie-match">{m.reply.movie.match}%</em>
                      </span>
                      <span className="chat-movie-title">{cnTitle(m.reply.movie.title)}</span>
                      <span className="chat-movie-meta t-mono">{m.reply.movie.year || '—'} · 豆瓣 {m.reply.movie.rating}</span>
                      <span className="chat-movie-reason">{m.reply.movie.reason.slice(0, 30)}</span>
                      {m.reply.movie.explain && <ExplainCard explain={m.reply.movie.explain} />}
                    </button>
                  </div>
                )}

                {/* 引用卡片 */}
                {m.reply && m.reply.citations.length > 0 && (
                  <div className="chat-cits">
                    {m.reply.citations.slice(0, 3).map((c, ci) => (
                      <button key={ci} className="chat-cit" onClick={() => { if (c.movie_id) location.hash = '#/movie/' + c.movie_id }}>
                        <span className="chat-cit-title">{c.title || '评论引用'}</span>
                        <span className="chat-cit-text">“{c.text.slice(0, 40)}…”</span>
                        <span className="chat-cit-meta t-mono">{num(c.votes || 0)} 票{c.author ? ' · ' + c.author : ''}</span>
                      </button>
                    ))}
                  </div>
                )}

                {/* 陪看引导话题 chip（仅最后一条 AI 回复展示） */}
                {m.role === 'assistant' && m.reply?.follow_ups && m.reply.follow_ups.length > 0
                  && i === lastAssistantIdx && !busy && (
                  <div className="chat-follow">
                    {m.reply.follow_ups.map((f) => (
                      <button key={f} className="chat-follow-chip" onClick={() => void send(f)}>{f}</button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="msg assistant">
              <div className="bub typing"><i /><i /><i /> 影灵正在组织语言…</div>
            </div>
          )}
        </div>

        <div className="chat-input-row">
          {!msgs.filter((m) => m.role === 'assistant').slice(1).length && (
            <div className="chat-quick">
              {QUICK.map((q) => (
                <button key={q} className="chat-quick-chip" onClick={() => void send(q)}>{q}</button>
              ))}
            </div>
          )}
          <div className="chat-input-box">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) void send() }}
              placeholder={mode === 'talk' ? '比如：我看完《霸王别姬》了，想聊聊…' : '比如：推荐一部燃的科幻片…'}
            />
            <button className="chat-send" onClick={() => void send()} disabled={busy}>发送 ✦</button>
          </div>
        </div>
    </div>
  )
}

export default function Chat({ movieId }: { movieId?: string }) {
  // movie_id 由路由层（App.tsx 解析 hash 参数）显式传入，从详情页跳转时为陪看场景
  return (
    <motion.div
      className="overlay chat-page"
      initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
      transition={{ duration: 0.55, ease: [0.32, 0.72, 0.35, 1] }}
    >
      <a className="page-back page-back-r" href="#/">返回银河 ›</a>
      <ChatPanel initialMovieId={movieId} />
    </motion.div>
  )
}
