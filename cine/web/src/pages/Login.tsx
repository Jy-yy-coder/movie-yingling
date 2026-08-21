import { useState } from 'react'
import { motion } from 'framer-motion'
import { guest, login, register, sms, setToken } from '../api'

/* 登录页：验证码（新用户注册）/ 密码 / 游客 三入口（C4 已拍板） */

type Tab = 'code' | 'pass' | 'guest'

export default function Login() {
  const [tab, setTab] = useState<Tab>('code')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [pass, setPass] = useState('')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [countdown, setCountdown] = useState(0)

  const tip = (s: string) => { setToast(s); setTimeout(() => setToast(''), 3200) }

  const sendCode = async () => {
    if (!/^1\d{10}$/.test(phone)) { tip('手机号格式不对'); return }
    setBusy(true)
    try {
      const r = await sms(phone)
      tip(r.message + '（' + r.dev_code + '）')
      setCountdown(60)
      const t = setInterval(() => setCountdown((c) => { if (c <= 1) clearInterval(t); return c - 1 }), 1000)
    } catch (e) {
      tip((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const doRegister = async () => {
    if (!/^1\d{10}$/.test(phone)) { tip('手机号格式不对'); return }
    if (!code.trim()) { tip('请输入验证码'); return }
    if (pass.length < 6) { tip('密码至少 6 位'); return }
    setBusy(true)
    try {
      const r = await register(phone, code.trim(), pass)
      setToken(r.token)
      tip(r.merged ? '注册成功，游客记录已合并 ✨' : '注册成功 ✨')
      setTimeout(() => { location.hash = '#/account' }, 600)
    } catch (e) {
      tip((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const doLogin = async () => {
    if (!/^1\d{10}$/.test(phone)) { tip('手机号格式不对'); return }
    if (!pass) { tip('请输入密码'); return }
    setBusy(true)
    try {
      const r = await login(phone, pass)
      setToken(r.token)
      tip('登录成功 ✨')
      setTimeout(() => { location.hash = '#/account' }, 600)
    } catch (e) {
      tip((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const doGuest = async () => {
    setBusy(true)
    try {
      await guest()
      tip('已以游客身份进入')
      setTimeout(() => { location.hash = '#/account' }, 600)
    } catch (e) {
      tip((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <motion.div
      className="overlay login-page"
      initial={{ y: '-100%' }} animate={{ y: 0 }} exit={{ y: '-100%' }}
      transition={{ duration: 0.55, ease: [0.32, 0.72, 0.35, 1] }}
    >
      <div className="login">
        <a className="page-back page-back-t" href="#/">⌃ 返回银河</a>
        <div className="login-head">
          <div className="login-logo">影灵</div>
          <h1 className="login-title title-gold">登录影灵</h1>
          <p className="login-sub">登录后收藏与聊天记录将同步到你的星际档案</p>
        </div>

        <div className="login-tabs">
          <button className={`login-tab ${tab === 'code' ? 'on' : ''}`} onClick={() => setTab('code')}>验证码</button>
          <button className={`login-tab ${tab === 'pass' ? 'on' : ''}`} onClick={() => setTab('pass')}>密码</button>
          <button className={`login-tab ${tab === 'guest' ? 'on' : ''}`} onClick={() => setTab('guest')}>游客</button>
        </div>

        {tab === 'code' && (
          <div className="login-form">
            <label className="login-field">
              <span>手机号</span>
              <input value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 11))} placeholder="1 开头的 11 位手机号" />
            </label>
            <label className="login-field">
              <span>验证码</span>
              <div className="login-code-row">
                <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="演示期固定 246810" />
                <button className="login-code-btn" onClick={() => void sendCode()} disabled={countdown > 0 || busy}>
                  {countdown > 0 ? `${countdown}s` : '获取验证码'}
                </button>
              </div>
            </label>
            <label className="login-field">
              <span>设置密码 <em className="t-mono">（≥6 位，首次注册）</em></span>
              <input type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="至少 6 位" />
            </label>
            <button className="login-btn" onClick={() => void doRegister()} disabled={busy}>{busy ? '处理中…' : '注册并进入 ✦'}</button>
            <p className="login-note t-mono">新手机号自动注册；若已注册过，请用「密码」入口登录</p>
          </div>
        )}

        {tab === 'pass' && (
          <div className="login-form">
            <label className="login-field">
              <span>手机号</span>
              <input value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 11))} placeholder="1 开头的 11 位手机号" />
            </label>
            <label className="login-field">
              <span>密码</span>
              <input type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="注册时设置的密码" onKeyDown={(e) => { if (e.key === 'Enter') void doLogin() }} />
            </label>
            <button className="login-btn" onClick={() => void doLogin()} disabled={busy}>{busy ? '处理中…' : '登录 ✦'}</button>
            <p className="login-note t-mono">首次使用请切到「验证码」入口注册</p>
          </div>
        )}

        {tab === 'guest' && (
          <div className="login-form">
            <p className="login-guest-txt">以游客身份进入，无需任何信息。收藏与聊天记录将保存在本机，<b>注册后自动合并</b>到正式账号。</p>
            <button className="login-btn" onClick={() => void doGuest()} disabled={busy}>{busy ? '进入中…' : '🚀 以游客身份进入'}</button>
          </div>
        )}

        {toast && <div className="login-toast">{toast}</div>}
      </div>
    </motion.div>
  )
}
