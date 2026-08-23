import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useGalaxy } from '../store'

/* 放映机音效（WebAudio 合成，无需素材；未获用户手势时静默跳过） */
function useProjectorSound() {
  const ctxRef = useRef<AudioContext | null>(null)
  /* useCallback 保证函数引用稳定，避免蓄力 effect 因依赖变化而每帧重触发音效 */
  const play = useCallback((kind: 'gear' | 'burst') => {
    try {
      const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      if (!ctxRef.current) ctxRef.current = new Ctor()
      const ctx = ctxRef.current
      if (ctx.state === 'suspended') void ctx.resume()
      const t = ctx.currentTime
      if (kind === 'gear') {
        // 齿轮咔哒 + 胶片低鸣
        const click = ctx.createBufferSource()
        const buf = ctx.createBuffer(1, ctx.sampleRate * 0.05, ctx.sampleRate)
        const d = buf.getChannelData(0)
        for (let i = 0; i < d.length; i++) d[i] = Math.sin(2 * Math.PI * 240 * i / ctx.sampleRate) * Math.exp(-i / 200)
        click.buffer = buf
        const g = ctx.createGain(); g.gain.value = 0.25
        click.connect(g).connect(ctx.destination)
        click.start(t)
      } else {
        // 投影爆发：白噪声上扫 + 泛音
        const noise = ctx.createBufferSource()
        const nb = ctx.createBuffer(1, ctx.sampleRate * 1.2, ctx.sampleRate)
        const nd = nb.getChannelData(0)
        for (let i = 0; i < nd.length; i++) nd[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * 0.5))
        noise.buffer = nb
        const f = ctx.createBiquadFilter(); f.type = 'bandpass'; f.frequency.setValueAtTime(300, t); f.frequency.exponentialRampToValueAtTime(2200, t + 0.9); f.Q.value = 0.8
        const ng = ctx.createGain(); ng.gain.value = 0.3; ng.gain.exponentialRampToValueAtTime(0.001, t + 1.1)
        noise.connect(f).connect(ng).connect(ctx.destination)
        noise.start(t)
        const osc = ctx.createOscillator()
        osc.type = 'sine'; osc.frequency.setValueAtTime(160, t); osc.frequency.exponentialRampToValueAtTime(520, t + 1.0)
        const og = ctx.createGain(); og.gain.value = 0.12; og.gain.exponentialRampToValueAtTime(0.001, t + 1.1)
        osc.connect(og).connect(ctx.destination)
        osc.start(t); osc.stop(t + 1.2)
      }
    } catch { /* 音频不可用则静默 */ }
  }, [])
  return play
}

const DUST = Array.from({ length: 26 }, (_, i) => ({
  left: (i * 37) % 100,
  delay: (i * 0.21) % 3.4,
  dur: 2.6 + (i % 5) * 0.5,
  size: 1 + (i % 3) * 1.1,
}))

/* 胶片盘结构：外圈刻度（进度） + 齿孔（胶片感） */
const TICKS = Array.from({ length: 12 }, (_, i) => (i * 360) / 12)
const SPROCKETS = Array.from({ length: 16 }, (_, i) => (i * 360) / 16)

/* 蓄力参数 */
const CHARGE_PER_TICK = 1.6     // 每 16ms 蓄力值（约 1.1s 蓄满）
const RELEASE_MIN = 24          // 松手触发的最小蓄力

export default function BootScene() {
  const setBooted = useGalaxy((s) => s.setBooted)
  const booted = useGalaxy((s) => s.booted)
  const [stage, setStage] = useState(0)     // 0 黑屏 1 光点待蓄力 2 爆发大厅 3 投影成星
  const [charge, setCharge] = useState(0)   // 蓄力 0-100
  const [charging, setCharging] = useState(false)
  const [nudge, setNudge] = useState(false) // 蓄力不足松手提示
  const sound = useProjectorSound()
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  /* 阶段 0：黑屏 → 光点出现 */
  useEffect(() => {
    if (stage !== 0) return
    sound('gear')
    const t = setTimeout(() => setStage(1), 700)
    return () => clearTimeout(t)
  }, [stage, sound])

  /* 蓄力推进 */
  useEffect(() => {
    if (!charging || stage !== 1) return
    sound('gear')
    timerRef.current = setInterval(() => {
      setCharge((c) => {
        const nc = Math.min(100, c + CHARGE_PER_TICK)
        if (nc >= 100) {
          /* 蓄满自动投影 */
          setCharging(false)
          setStage(2)
        }
        return nc
      })
    }, 16)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [charging, stage, sound])

  /* 松手 */
  const release = () => {
    if (stage !== 1) return
    setCharging(false)
    if (charge >= RELEASE_MIN) {
      setStage(2)
    } else {
      setNudge(true)
      setTimeout(() => setNudge(false), 900)
    }
  }

  /* 爆发大厅 → 投影成星 → 进入（写 sessionStorage，看过不再重播） */
  useEffect(() => {
    if (stage === 2) {
      sound('burst')
      const t = setTimeout(() => setStage(3), 1000)
      return () => clearTimeout(t)
    }
    if (stage === 3) {
      const t = setTimeout(() => {
        sessionStorage.setItem('cine_booted', '1')
        setBooted(true)
      }, 1700)
      return () => clearTimeout(t)
    }
  }, [stage, sound, setBooted])

  /* 蓄力不足时回弹 */
  useEffect(() => {
    if (nudge && charge > 0) {
      const t = setTimeout(() => setCharge(0), 500)
      return () => clearTimeout(t)
    }
  }, [nudge, charge])

  const lightScale = stage === 1 ? 1 + (charge / 100) * 2.4 : stage >= 2 ? 9 : 1
  const ringDeg = (charge / 100) * 360
  const litTicks = Math.floor((charge / 100) * TICKS.length)

  return (
    <AnimatePresence>
      {!booted && (
        <motion.div
          className="boot"
          exit={{ opacity: 0, scale: 1.12, filter: 'blur(10px)' }}
          transition={{ duration: 1.2, ease: [0.22, 0.61, 0.36, 1] }}
          onPointerDown={() => { if (stage === 1) { setCharging(true); setCharge((c) => Math.max(c, 1)) } }}
          onPointerUp={release}
          onPointerCancel={release}
        >
          <div className="boot-bg" />

          {/* 阶段0：纯黑 */}
          <motion.div
            className="boot-black"
            initial={{ opacity: 1 }}
            animate={{ opacity: stage >= 1 ? 0 : 1 }}
            transition={{ duration: 0.8 }}
          />

          {/* 阶段1：胶片盘蓄力（齿孔转盘 + 刻度点亮 + 中央光点） */}
          {stage === 1 && (
            <motion.div
              className="boot-charge"
              initial={{ opacity: 0, scale: 0.4 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 1.1, ease: 'easeOut' }}
            >
              <div
                className={`boot-reel ${charging ? 'charging' : ''}`}
                style={{ background: `conic-gradient(#ffd98a ${ringDeg}deg, rgba(255,255,255,0.06) 0deg)` }}
              >
                {/* 外圈刻度：随蓄力逐格点亮 */}
                {TICKS.map((deg, i) => (
                  <span key={deg} className={`boot-tick${i < litTicks ? ' on' : ''}`} style={{ transform: `rotate(${deg}deg) translateY(-97px)` }} />
                ))}
                {/* 胶片转盘：蓄力时随进度转动 */}
                <div className="boot-reel-disc" style={{ transform: `rotate(${charge * 3}deg)` }}>
                  {SPROCKETS.map((deg) => (
                    <span key={deg} className="reel-sprocket" style={{ transform: `rotate(${deg}deg) translateY(-60px)` }} />
                  ))}
                  <span className="reel-hole reel-h1" />
                  <span className="reel-hole reel-h2" />
                  <span className="reel-hole reel-h3" />
                  <span className="reel-hub" />
                </div>
                <div className="boot-light" style={{ transform: `scale(${lightScale})` }} />
              </div>
              <div className="boot-charge-hint">
                {nudge
                  ? <span className="boot-nudge">再按住久一点…</span>
                  : charging
                    ? <span>{charge >= 96 ? '松手！' : '继续按住 · 点亮电影宇宙'}</span>
                    : <span className="boot-pulse-hint">按住光点 · 点亮电影宇宙</span>}
              </div>
              <div className="boot-charge-sub">{charging ? `${Math.round(charge)}%` : '长按蓄力，松开投影成星'}</div>
            </motion.div>
          )}

          {/* 阶段2：影院大厅闪现 */}
          <motion.div
            className="hall"
            initial={{ opacity: 0 }}
            animate={{ opacity: stage >= 2 ? 1 : 0, scale: stage >= 2 ? 1 : 1.25 }}
            transition={{ duration: 0.9 }}
          >
            <motion.div className="hall-beam" animate={{ opacity: stage >= 3 ? 0 : [0, 0.85, 0.7] }} transition={{ duration: 2, times: [0, 0.3, 1], repeat: Infinity, repeatType: 'mirror' }} />
            <div className="hall-projector" />
            <div className="hall-screen">
              <div className="hall-film-top" />
              <div className="hall-film-bottom" />
              <div className="hall-screen-shimmer" />
            </div>
            <div className="hall-floor" />
            <div className="hall-title">
              <span className="hall-title-cn title-gold">影灵 CINE</span>
              <span className="hall-title-en">MOVIE UNIVERSE</span>
            </div>
            {DUST.map((d, i) => (
              <span key={i} className="hall-dust" style={{ left: `${d.left}%`, animationDelay: `${d.delay}s`, animationDuration: `${d.dur}s`, width: d.size, height: d.size }} />
            ))}
          </motion.div>

          {/* 阶段3：投影扩散成星 */}
          <motion.div
            className="boot-starburst"
            initial={{ opacity: 0 }}
            animate={{ opacity: stage >= 3 ? [0, 1, 0] : 0 }}
            transition={{ duration: 1.6, times: [0, 0.45, 1] }}
          >
            {Array.from({ length: 46 }, (_, i) => (
              <span
                key={i}
                className="burst-star"
                style={{
                  left: `${(i * 53) % 100}%`,
                  top: `${(i * 37) % 100}%`,
                  animationDelay: `${(i % 9) * 0.06}s`,
                  animationDuration: `${0.8 + (i % 4) * 0.25}s`,
                }}
              />
            ))}
          </motion.div>

          <button
            type="button"
            className="boot-skip"
            onPointerDown={(e) => { e.stopPropagation(); e.preventDefault() }}
            onPointerUp={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation()
              sessionStorage.setItem('cine_booted', '1')
              setBooted(true)
            }}
          >跳过 进入宇宙 ›</button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
