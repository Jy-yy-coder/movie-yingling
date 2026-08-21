import { motion } from 'framer-motion'

/* 关于页：数据来源与口径 */

const FACTS = [
  ['🎬', '590 部高分电影', '豆瓣高分片库，四星域：华语 / 日本 / 韩国 / 欧美'],
  ['💬', '88,169 条短评', '真实豆瓣短评全文索引，支持台词与梗的举证检索'],
  ['📝', '29,256 条长评', '长评用于金句候选与冷知识挖掘'],
  ['🖼️', '590 张海报', '原图 + 缩略图，全部真实海报'],
]

const PRINCIPLES = [
  ['🧬', '五维口碑 DNA', '剧情 / 演技 / 情感 / 视听 / 节奏 —— 由种子词库命中真实短评 + 贝叶斯平滑计算，每条分数都有证据条数背书'],
  ['🛡️', '防幻觉铁律', 'AI 只负责组织语言，事实与引用全部由程序从数据卡片与评论原文喂入；每条引用可溯源到真实评论 id 与票数'],
  ['🎯', '宁缺毋编', '数据缺失时前端自动降级隐藏，绝不编造标签、金句或冷知识'],
  ['🌡️', '观众情绪宇宙', '情绪温度、情感关键词、评价趋势均由真实评论统计得出'],
]

export default function About() {
  return (
    <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.45 }}>
      <div className="about glass-strong">
        <a className="nav-close" href="#/" aria-label="关闭">✕</a>
        <h2 className="about-title title-gold">关于影灵 CINE</h2>
        <p className="about-lead">一座由真实评论构建的电影宇宙 —— 5000 颗星球（590 核心高分 + 库外精选），每一颗都经得起点击。</p>

        <div className="about-section">
          <div className="about-section-title">数据资产</div>
          <div className="about-facts">
            {FACTS.map(([icon, k, v]) => (
              <div className="about-fact glass" key={k}>
                <div className="about-fact-icon">{icon}</div>
                <div>
                  <b>{k}</b>
                  <p>{v}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="about-num t-mono">合计 590 × 88,169 短评 + 29,256 长评 ≈ 11.7 万条真实评论</p>
        </div>

        <div className="about-section">
          <div className="about-section-title">方法论与原则</div>
          {PRINCIPLES.map(([icon, k, v]) => (
            <div className="about-principle" key={k}>
              <span className="about-principle-icon">{icon}</span>
              <div>
                <b>{k}</b>
                <p>{v}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="about-foot t-mono">影灵 CINE · 全部口碑与评论来自真实豆瓣短评数据 · 数据构建：D1 规则加工 → D2 样张审稿 → D3 LLM 加工 → D4 组装质检</div>
      </div>
    </motion.div>
  )
}
