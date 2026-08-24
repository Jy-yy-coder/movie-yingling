import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { account, cnTitle, logout } from '../api'
import { regionLabel } from '../regions'
import type { AccountData } from '../types'

/* 个人中心：头部（头像 / 昵称 / 档案完成度环）+ 收藏 + 聊天历史 + 设置
   游客登录询问为独立界面（#/guest），此处仅保留引导入口 */

function maskName(d: AccountData): string {
  if (d.is_guest || !d.phone) return '游客用户'
  return d.phone.slice(0, 3) + '****' + d.phone.slice(7)
}

/* 个人中心主体面板：embed 时嵌入探索模式，否则由 Account 包成底部升起整屏页 */
export function AccountPanel({ embed = false }: { embed?: boolean }) {
  const [data, setData] = useState<AccountData | null>(null)
  const [err, setErr] = useState('')
  const [spoilerDefault, setSpoilerDefault] = useState(() => localStorage.getItem('cine_spoiler_default') !== '0')

  useEffect(() => {
    account().then(setData).catch((e) => setErr(e.message))
  }, [])

  /* 档案完成度：有收藏 +40 / 有聊天 +30 / 已登录 +30 */
  const pct = data
    ? (data.favorites.length > 0 ? 40 : 0) + (data.history.length > 0 ? 30 : 0) + (!data.is_guest ? 30 : 0)
    : 0

  const toggleSpoiler = () => {
    const v = !spoilerDefault
    setSpoilerDefault(v)
    localStorage.setItem('cine_spoiler_default', v ? '1' : '0')
  }

  const [confirming, setConfirming] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)

  /* 退出登录：清 token 与本地凭据，回到游客态并刷新面板数据 */
  const doLogout = async () => {
    setLoggingOut(true)
    logout()
    try {
      setData(await account())
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setLoggingOut(false)
    }
  }

  const clearLocal = () => {
    Object.keys(localStorage).filter((k) => k.startsWith('cine_')).forEach((k) => localStorage.removeItem(k))
    location.hash = '#/'
    location.reload()
  }

  return (
    <div className={'account' + (embed ? ' embed' : '')}>
        <h2 className="account-title title-gold">个人中心</h2>

        {err && <div className="account-err">{err}</div>}
        {!data && !err && <div className="account-loading">正在同步…</div>}

        {data && (
          <>
            {/* ---------- 头部：头像 / 昵称 / 档案完成度 ---------- */}
            <div className="account-profile">
              <div className="account-avatar">{data.is_guest ? '👤' : '🌟'}</div>
              <div className="account-info">
                <div className="account-name">
                  {maskName(data)}
                  {data.is_guest && (
                    <button className="account-login-hint" onClick={() => { location.hash = '#/login' }}>（登录后云端同步 →）</button>
                  )}
                </div>
                <div className="account-meta t-mono">
                  {data.is_guest ? '游客模式 · 数据保存在本机' : '手机号账号 · 云端同步'} · 注册于 {data.created_at || '—'}
                </div>
              </div>
              <div className="account-ring-wrap">
                <div className="account-ring" data-pct={`${pct}%`}
                  style={{ background: pct > 0 ? `conic-gradient(var(--color-gold-300) ${pct}%, rgba(255,255,255,0.07) 0)` : 'none' }} />
                档案完成度
              </div>
            </div>

            {/* ---------- 游客状态横幅：引导到独立的游客模式页 ---------- */}
            {data.is_guest && (
              <button className="account-guest-banner" onClick={() => { location.hash = '#/guest' }}>
                👤 当前为游客模式，数据仅保存在本机 · 查看说明并登录 →
              </button>
            )}

            {/* ---------- 我的收藏 ---------- */}
            <div className="account-section">
              <div className="account-section-title">我的收藏 · {data.favorites.length}</div>
              {data.favorites.length ? (
                <div className="account-favs">
                  {data.favorites.map((m) => (
                    <button key={m.movie_id} className="account-fav" onClick={() => { location.hash = '#/movie/' + m.movie_id }}>
                      <span className="account-fav-poster">
                        {m.poster_thumb ? <img src={m.poster_thumb} alt="" loading="lazy" /> : <i>{cnTitle(m.title)}</i>}
                        <em className="t-mono">{m.rating}</em>
                      </span>
                      <span className="account-fav-title">{cnTitle(m.title)}</span>
                      <span className="account-fav-meta t-mono">{m.year || ''} · {regionLabel(m.region)}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="account-empty">还没有收藏。去银河里点击星球，收藏心仪的电影吧。</div>
              )}
            </div>

            {/* ---------- 聊天记录 ---------- */}
            <div className="account-section">
              <div className="account-section-title">AI 聊天历史 · 最近 {Math.min(data.history.length, 20)} 条</div>
              {data.history.length ? (
                <div className="account-history">
                  {data.history.map((h, i) => (
                    <div key={i} className={`account-his-row ${h.role}`}>
                      <span className="account-his-role t-mono">{h.role === 'user' ? '我' : '影灵'}</span>
                      <span className="account-his-text">{h.content.slice(0, 60)}{h.content.length > 60 ? '…' : ''}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="account-empty">暂无聊天记录。去「问影灵」聊聊电影吧。</div>
              )}
            </div>

            {/* ---------- 设置 ---------- */}
            <div className="account-section">
              <div className="account-section-title">设置</div>
              <div className="set-row">
                <span className="set-lab">无剧透模式默认开启</span>
                <button className={`switch ${spoilerDefault ? 'on' : ''}`} onClick={toggleSpoiler} aria-label="无剧透默认开关" />
              </div>
              <div className="set-row">
                <span className="set-lab">本地数据</span>
                {confirming ? (
                  <span className="set-confirm">
                    <button className="set-danger" onClick={clearLocal}>确认清除</button>
                    <button className="set-cancel" type="button" onClick={() => setConfirming(false)}>取消</button>
                  </span>
                ) : (
                  <button className="set-danger" type="button" onClick={() => setConfirming(true)}>清除全部</button>
                )}
              </div>
              <div className="set-row">
                <span className="set-lab">探索档案</span>
                <a className="set-link" href="#/profile">等级 / 徽章 →</a>
              </div>
            </div>

            {/* ---------- 账号与安全 ---------- */}
            <div className="account-section">
              <div className="account-section-title">账号与安全</div>
              <div className="acct-status">
                <span className={`acct-dot ${data.is_guest ? 'guest' : 'online'}`} />
                <span className="acct-label">{data.is_guest ? '游客模式' : '已登录'}</span>
                {!data.is_guest && (
                  <>
                    <span className="acct-sep">·</span>
                    <span className="acct-phone t-mono">{maskName(data)}</span>
                    <span className="acct-sep">·</span>
                    <span className="acct-sync">云端同步中</span>
                  </>
                )}
                {data.is_guest && (
                  <>
                    <span className="acct-sep">·</span>
                    <span className="acct-sync acct-sync-local">数据仅本机</span>
                  </>
                )}
              </div>
              {!data.is_guest && (
                <div className="acct-detail t-mono">
                  注册于 {data.created_at || '—'} · 设备 ID {data.device_id ? data.device_id.slice(0, 8) + '…' : '—'}
                </div>
              )}
              <div className="acct-actions">
                {data.is_guest ? (
                  <a className="set-link" href="#/login">去登录 / 注册 →</a>
                ) : loggingOut ? (
                  <span className="acct-logging-out">正在退出…</span>
                ) : (
                  <button className="set-danger" type="button" onClick={doLogout}>退出登录</button>
                )}
              </div>
            </div>
          </>
        )}
    </div>
  )
}

export default function Account() {
  return (
    <motion.div
      className="overlay account-page"
      initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
      transition={{ duration: 0.55, ease: [0.32, 0.72, 0.35, 1] }}
    >
      <a className="page-back page-back-b" href="#/explore?tab=home">⌄ 返回首页</a>
      <AccountPanel />
    </motion.div>
  )
}
