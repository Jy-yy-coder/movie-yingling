import { motion } from 'framer-motion'

/* 游客模式：独立界面（对应参考设计 view-ask「要让影灵记住你吗？」）
   居中询问卡：游客 vs 登录对比 + 双入口，随时可登录，游客数据自动合并 */

export default function Guest() {
  return (
    <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.45 }}>
      <div className="guest glass-strong">
        <a className="nav-close" href="#/explore?tab=me" aria-label="关闭">✕</a>
        <div className="guest-ava">🌌</div>
        <h2 className="guest-title title-gold">要让影灵记住你吗？</h2>
        <p className="guest-sub">登录后，你的口味档案将永久保存并跨设备同步</p>
        <div className="guest-compare">
          <div className="guest-li">👤 <span><b>游客模式</b>：数据保存在本机，清除浏览器即失效</span></div>
          <div className="guest-li">🌟 <span><b>登录账号</b>：收藏、对话记录云端同步</span></div>
          <div className="guest-li">🧬 <span><b>随时找回</b>：重装或换设备也能找回你的电影档案</span></div>
        </div>
        <div className="guest-actions">
          <button className="guest-btn-main" onClick={() => { location.hash = '#/login' }}>登录 / 注册</button>
          <button className="guest-btn-ghost" onClick={() => { location.hash = '#/' }}>先逛逛，游客模式 →</button>
        </div>
        <div className="guest-foot">随时可在「我的 · 个人中心」登录，游客数据自动合并</div>
      </div>
    </motion.div>
  )
}
