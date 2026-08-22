import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useGalaxy } from '../store'
import { REGIONS, REGION_COLORS } from '../layout'
import { regionLabel } from '../regions'

const GENRES = ['剧情', '喜剧', '动作', '爱情', '科幻', '犯罪', '悬疑', '动画', '奇幻', '家庭', '战争', '恐怖']

export default function HUD() {
  const hoverId = useGalaxy((s) => s.hoverId)
  const hoverPos = useGalaxy((s) => s.hoverPos)
  const focusRegion = useGalaxy((s) => s.focusRegion)
  const focusGenre = useGalaxy((s) => s.focusGenre)
  const setFocus = useGalaxy((s) => s.setFocus)
  const hovered = hoverId ? useGalaxy.getState().planetsById[hoverId] : null

  /* 首次进入引导：常驻显示，直到用户手动关闭（不再 7 秒自动消失） */
  const [guide, setGuide] = useState(() => !sessionStorage.getItem('cine_guided'))
  const closeGuide = () => {
    sessionStorage.setItem('cine_guided', '1')
    setGuide(false)
  }

  return (
    <>
      {/* ---------- 平台定位标语 + 关于入口 ---------- */}
      <div className="hud-brand glass">
        <b>影灵 CINE · 电影银河</b>
        <span>AI 导航员陪你从 5000 颗星球中，找到今晚的那部片</span>
        <a href="#/about">关于平台 →</a>
      </div>

      {/* ---------- 星图筛选面板 ---------- */}
      <div className="hud-filter glass">
        <div className="hud-filter-title">星图</div>
        <div className="hud-filter-row">
          <span className="hud-filter-lab">星域</span>
          <button className={`chip-mini ${!focusRegion ? 'on' : ''}`} onClick={() => setFocus('', '')}>全部银河</button>
          {REGIONS.map((r) => (
            <button key={r} className={`chip-mini ${focusRegion === r ? 'on' : ''}`}
              onClick={() => setFocus(focusRegion === r ? '' : r, '')}>
              <span className="chip-dot" style={{ background: REGION_COLORS[r], boxShadow: `0 0 6px ${REGION_COLORS[r]}` }} />
              {r}
            </button>
          ))}
        </div>
        <AnimatePresence>
          {focusRegion && (
            <motion.div className="hud-filter-row" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
              <span className="hud-filter-lab">星系</span>
              <button className={`chip-mini ${!focusGenre ? 'on' : ''}`} onClick={() => setFocus(focusRegion, '')}>全部</button>
              {GENRES.map((g) => (
                <button key={g} className={`chip-mini ${focusGenre === g ? 'on' : ''}`}
                  onClick={() => setFocus(focusRegion, focusGenre === g ? '' : g)}>
                  {g}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ---------- 底部功能栏（人格测试入口已移到探索首页与 AI 聊天并排） ---------- */}
      <div className="hud-bottom glass">
        <a href="#/explore" className="hud-explore-btn">🪐 进入探索 <span className="t-mono">EXPLORE</span></a>
      </div>

      {/* 首次进入引导 */}
      <AnimatePresence>
        {guide && (
          <motion.div className="hud-guide" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={{ duration: 0.5, delay: 0.6 }}>
            <div className="hud-guide-arrow" />
            <div className="hud-guide-txt">
              <b>欢迎来到电影宇宙</b>
              <span>拖动旋转 · 滚轮缩放 · 点击星球进入电影空间</span>
            </div>
            <button className="hud-guide-close" onClick={closeGuide} aria-label="关闭引导">✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---------- 星球悬浮信息 ---------- */}
      <AnimatePresence>
        {hovered && hoverPos && (
          <motion.div
            className="hud-tip glass-strong"
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            style={{ left: Math.min(hoverPos.x + 16, window.innerWidth - 240), top: Math.min(hoverPos.y + 18, window.innerHeight - 130) }}
          >
            <div className="hud-tip-dot" style={{ background: REGION_COLORS[hovered.region] || '#e8edff', boxShadow: `0 0 14px 2px ${REGION_COLORS[hovered.region] || 'rgba(232, 237, 255, 0.8)'}` }} />
            <div className="hud-tip-main">
              <div className="hud-tip-title">{hovered.t}</div>
              <div className="hud-tip-meta t-mono">
                {[hovered.y, hovered.rating ? hovered.rating.toFixed(1) : null, regionLabel(hovered.region)].filter(Boolean).join(' · ')}
                {(hovered.k ?? 1) >= 1 ? ' · 点击查看详情' : ''}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
