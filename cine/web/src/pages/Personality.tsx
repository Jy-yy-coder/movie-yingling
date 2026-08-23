import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { loadLocalPersonality, personalityQuestions, personalityProfile, personalityRoute, submitPersonality } from '../api'
import type { PersonalityProfile, PersonalityRoute, QuizQuestion } from '../types'
import PersonalityCard from '../components/PersonalityCard'
import MovieRoute from '../components/MovieRoute'

/* 电影人格测试 #/personality：介绍 → 12 道情境题 → 画像结果卡 */
type Stage = 'intro' | 'quiz' | 'result'

export default function Personality() {
  const [saved, setSaved] = useState<PersonalityProfile | null>(null)
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [stage, setStage] = useState<Stage>('intro')
  const [idx, setIdx] = useState(0)
  const [answers, setAnswers] = useState<{ q: number; o: number }[]>([])
  const [profile, setProfile] = useState<PersonalityProfile | null>(null)
  const [route, setRoute] = useState<PersonalityRoute | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  /* 首屏：读取已有画像（服务端优先；未测过的 404 与网络异常都静默回落本地缓存） */
  useEffect(() => {
    personalityProfile().then(setSaved).catch(() => setSaved(loadLocalPersonality()))
  }, [])

  /* 画像存在时同步拉取专属探索路线（失败静默，不影响画像展示） */
  useEffect(() => {
    if (!profile) { setRoute(null); return }
    personalityRoute().then(setRoute).catch(() => setRoute(null))
  }, [profile])

  const start = async () => {
    if (busy) return
    setErr('')
    setBusy(true)
    try {
      const d = await personalityQuestions()
      setQuestions(d.questions)
      setIdx(0)
      setAnswers([])
      setStage('quiz')
    } catch (e) {
      setErr(e instanceof Error ? `题库加载失败：${e.message}（若提示 Not Found 请刷新页面重试）` : '题库加载失败')
    } finally { setBusy(false) }
  }

  const pick = (o: number) => {
    if (busy) return
    const next = [...answers, { q: idx, o }]
    setAnswers(next)
    if (idx + 1 < questions.length) { setIdx(idx + 1); return }
    setBusy(true)
    submitPersonality(next)
      .then((p) => { setProfile(p); setSaved(p); setStage('result') })
      .catch((e) => setErr(e instanceof Error ? e.message : '提交失败，请重试'))
      .finally(() => setBusy(false))
  }

  const q = questions[idx]
  return (
    <motion.div
      className="overlay personality"
      initial={{ opacity: 0, y: -30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -30 }}
      transition={{ duration: 0.5, ease: [0.32, 0.72, 0.35, 1] }}
    >
      <a className="nav-close" href="#/explore?tab=home" aria-label="关闭">✕</a>
      <div className="p-wrap">
        <AnimatePresence mode="wait">
          {/* ---------- 介绍 ---------- */}
          {stage === 'intro' && (
            <motion.div
              key="intro" className="p-intro"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
            >
              <div className="p-intro-ico">🧬</div>
              <h1 className="p-intro-title">发现你的<span className="title-gold">电影人格</span></h1>
              <p className="p-intro-sub">12 道情境题，约 2 分钟，为五维观影 DNA 画像</p>
              <div className="p-intro-btns">
                {saved && (
                  <motion.button
                    className="p-btn p-btn-ghost"
                    whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                    onClick={() => { setProfile(saved); setStage('result') }}
                  >查看我的画像</motion.button>
                )}
                <motion.button
                  className="p-btn"
                  whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                  onClick={start}
                  disabled={busy}
                >{saved ? '重新测一次' : busy ? '准备中…' : '开始测试'}</motion.button>
              </div>
              {err && <p className="p-err">{err}</p>}
            </motion.div>
          )}

          {/* ---------- 答题 ---------- */}
          {stage === 'quiz' && q && (
            <motion.div
              key={`quiz-${idx}`} className="p-quiz"
              initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.32 }}
            >
              <div className="p-progress">
                {questions.map((_, i) => (
                  <span key={i} className={`p-progress-dot ${i < idx ? 'done' : ''} ${i === idx ? 'now' : ''}`} />
                ))}
              </div>
              <p className="p-quiz-num t-mono">{String(idx + 1).padStart(2, '0')} / {questions.length}</p>
              <h2 className="p-quiz-q">{q.q}</h2>
              <div className="p-opts">
                {q.opts.map((o, oi) => (
                  <motion.button
                    key={oi}
                    className="p-opt"
                    whileHover={{ scale: 1.02, y: -2 }} whileTap={{ scale: 0.97 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 22 }}
                    onClick={() => pick(oi)}
                  >
                    <span className="p-opt-em">{o.em}</span>
                    <span className="p-opt-t">{o.t}</span>
                  </motion.button>
                ))}
              </div>
              {idx > 0 && (
                <button className="p-prev" onClick={() => { setIdx(idx - 1); setAnswers(answers.slice(0, -1)) }}>
                  ← 上一题
                </button>
              )}
              {err && <p className="p-err">{err}</p>}
            </motion.div>
          )}

          {/* ---------- 结果 ---------- */}
          {stage === 'result' && profile && (
            <motion.div
              key="result"
              initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
            >
              <PersonalityCard profile={profile} />
              {route && route.stages.length > 0 && <MovieRoute stages={route.stages} />}
              <div className="p-actions">
                <motion.button
                  className="p-btn p-btn-ghost"
                  whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                  onClick={start} disabled={busy}
                >{busy ? '正在测算…' : '重新测一次'}</motion.button>
                <motion.a
                  className="p-btn" href="#/explore?tab=home"
                  whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                >返回首页</motion.a>
              </div>
              {err && <p className="p-err">{err}</p>}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}
