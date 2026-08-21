import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

/* 陪看开场动画（约 4.5 秒）：灯光渐暗 → 3·2·1 倒数 → 「开始放映」 */
const PHASES = [
  { key: 'dim', ms: 900 },
  { key: '3', ms: 750 },
  { key: '2', ms: 750 },
  { key: '1', ms: 750 },
  { key: 'title', ms: 1400 },
]

export default function WatchIntro({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (step >= PHASES.length) { onDone(); return }
    const t = setTimeout(() => setStep((s) => s + 1), PHASES[step].ms)
    return () => clearTimeout(t)
  }, [step, onDone])

  const phase = step < PHASES.length ? PHASES[step].key : 'title'
  return (
    <motion.div
      className="watch-intro"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      <AnimatePresence mode="wait">
        {phase === 'dim' && (
          <motion.p
            key="dim" className="watch-dim-txt"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          >灯光渐暗 · 请入座 🍿</motion.p>
        )}
        {['3', '2', '1'].includes(phase) && (
          <motion.div
            key={phase} className="watch-count t-mono"
            initial={{ opacity: 0, scale: 1.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.7 }}
            transition={{ duration: 0.28 }}
          >{phase}</motion.div>
        )}
        {phase === 'title' && (
          <motion.div
            key="title" className="watch-title-wrap"
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
          >
            <div className="watch-title-txt title-gold">✦ 开始放映 ✦</div>
            <div className="watch-start">影灵已就位，随时开聊</div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
