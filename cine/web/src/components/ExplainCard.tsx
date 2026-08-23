import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { ExplainData } from '../types'

/* 推荐解释卡：卡片内「为什么推荐这部？」入口，点击在卡内展开/收起解释面板
   （五维契合对比条 + 结构化理由）。全 span 结构 + stopPropagation/preventDefault，
   可安全嵌入 <a>/<button> 卡片而不触发跳转。 */
export default function ExplainCard({ explain }: { explain: ExplainData }) {
  const [open, setOpen] = useState(false)
  const sorted = [...explain.dims].sort((a, b) => b.fit - a.fit)
  const toggle = (e: React.MouseEvent) => { e.preventDefault(); e.stopPropagation(); setOpen((o) => !o) }
  return (
    <span className="explain-wrap">
      <span
        className={`explain-trigger${open ? ' on' : ''}`}
        onClick={toggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(e as unknown as React.MouseEvent) } }}
        role="button"
        tabIndex={0}
        aria-expanded={open}
      >
        {open ? '✦ 收起推荐解释' : '✦ 为什么推荐这部？'}
      </span>
      <AnimatePresence initial={false}>
        {open && (
          <motion.span
            className="explain-pop"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.26, ease: [0.22, 0.61, 0.36, 1] }}
            onClick={(e) => { e.preventDefault(); e.stopPropagation() }}
          >
            {sorted.length > 0 && (
            <span className="explain-dims">
              {sorted.map((d) => (
                <span key={d.dim} className="explain-dim">
                  <span className="explain-dim-name">{d.dim}</span>
                  <span className="explain-dim-track">
                    <motion.i
                      className="explain-dim-fill"
                      initial={{ width: 0 }}
                      animate={{ width: `${d.fit}%` }}
                      transition={{ duration: 0.7, ease: [0.32, 0.72, 0.35, 1] }}
                    />
                  </span>
                  <span className="explain-dim-nums t-mono">{d.user}·{d.movie}</span>
                </span>
              ))}
            </span>
            )}
            <span className="explain-bullets">
              {explain.bullets.map((b, i) => (
                <span key={i} className="explain-bullet"><em>✧</em>{b}</span>
              ))}
            </span>
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  )
}
