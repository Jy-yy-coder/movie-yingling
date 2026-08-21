/* 影灵 CINE · 电影宇宙 API 客户端（从旧 app.js 迁移 + 新端点） */
import type { AccountData, ChatReply, ExplorerReply, Movie, PersonalityProfile, PersonalityRoute, Planet, QuizQuestion, WatchOpening } from './types'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init)
  if (!r.ok) {
    let detail = ''
    try { detail = (await r.json()).detail || '' } catch { /* ignore */ }
    throw new Error(detail || `请求失败 ${r.status}`)
  }
  return r.json()
}
const get = <T>(p: string) => api<T>(p)
const post = <T>(p: string, body: unknown) => api<T>(p, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) })

export const galaxy = () => get<{ total: number; planets: Planet[] }>('/api/galaxy')
export const movie = (id: string) => get<Movie>(`/api/movies/${id}`)
export const movies = (params: Record<string, string | number | undefined>) => {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.set(k, String(v)) })
  return get<{ total: number; page: number; limit: number; items: Movie[] }>(`/api/movies?${qs}`)
}
export const suggest = (q: string) =>
  get<{ items: { title: string; type: string; movie_id?: string; year?: string }[] }>(`/api/suggest?q=${encodeURIComponent(q)}`)

/* ---------- 聊天 / AI 导航员 ---------- */
export const chat = (
  message: string,
  mode: 'rec' | 'talk' = 'rec',
  spoiler = true,
  conversationId?: number,
  movieId?: string
) =>
  post<ChatReply>('/api/chat', {
    message,
    device_id: deviceId(),
    mode,
    spoiler,
    conversation_id: conversationId,
    movie_id: movieId
  })

/* ---------- 设备 & 登录态 ---------- */
export const deviceId = () => {
  let d = localStorage.getItem('cine_device')
  if (!d) { d = 'd' + Math.random().toString(36).slice(2, 10); localStorage.setItem('cine_device', d) }
  return d
}
export const token = () => localStorage.getItem('cine_token') || ''
export const setToken = (t: string) => t ? localStorage.setItem('cine_token', t) : localStorage.removeItem('cine_token')

export const ensureGuest = async () => {
  const t = token()
  if (t) return t
  const r = await post<{ token: string }>('/api/auth/guest', { device_id: deviceId() })
  setToken(r.token)
  return r.token
}
/* 本地 token 失效（如后端数据重建）时丢弃旧 token 重新注册游客，
   避免个人中心/探索档案卡在「未登录」报错 */
const freshGuest = async () => {
  setToken('')
  return ensureGuest()
}
const retryOn401 = async <T>(fn: (tok: string) => Promise<T>): Promise<T> => {
  try {
    return await fn(await ensureGuest())
  } catch (e) {
    if (String((e as Error).message || '').includes('未登录')) return fn(await freshGuest())
    throw e
  }
}

export const explorer = () => retryOn401((t) => get<ExplorerReply>(`/api/explorer?token=${encodeURIComponent(t)}`))
export const account = () => retryOn401((t) => get<AccountData>(`/api/account?token=${encodeURIComponent(t)}`))
export const favorite = async (movieId: string) => {
  await retryOn401((t) => post<{ ok: boolean }>(`/api/favorites?token=${encodeURIComponent(t)}`, { movie_id: movieId }))
}
export const unfavorite = async (movieId: string) => {
  await retryOn401((t) => api<{ ok: boolean }>(`/api/favorites?movie_id=${encodeURIComponent(movieId)}&token=${encodeURIComponent(t)}`, { method: 'DELETE' }))
}

/* ---------- 行为反馈（B4：收藏/浏览/点卡/换片 → 隐式画像） ---------- */
export const feedback = async (movieId: string, kind: 'fav' | 'unfav' | 'view' | 'pick') => {
  await retryOn401((t) => post<{ ok: boolean }>(`/api/feedback?token=${encodeURIComponent(t)}`, { movie_id: movieId, kind }))
}

/* ---------- 电影人格测试 ---------- */
const P_KEY = 'cine_personality'
export const personalityQuestions = () => get<{ questions: QuizQuestion[] }>('/api/personality/questions')
export const submitPersonality = async (answers: { q: number; o: number }[]) => {
  const r = await post<PersonalityProfile>('/api/personality/test', { answers, device_id: deviceId() })
  try { localStorage.setItem(P_KEY, JSON.stringify(r)) } catch { /* ignore */ }
  return r
}
export const personalityProfile = async () => {
  return retryOn401((t) => get<PersonalityProfile>(
    `/api/personality/profile?token=${encodeURIComponent(t)}&device_id=${encodeURIComponent(deviceId())}`))
}
export const loadLocalPersonality = (): PersonalityProfile | null => {
  try { const s = localStorage.getItem(P_KEY); return s ? JSON.parse(s) : null } catch { return null }
}
export const personalityRoute = async () => {
  return retryOn401((t) => get<PersonalityRoute>(
    `/api/personality/route?token=${encodeURIComponent(t)}&device_id=${encodeURIComponent(deviceId())}`))
}

/* ---------- AI 陪看开场 ---------- */
export const watchOpening = (movieId: string, spoiler = true) =>
  get<WatchOpening>(`/api/watch/opening?movie_id=${encodeURIComponent(movieId)}&spoiler=${spoiler}`)

/* ---------- 账号 ---------- */
export const guest = () => post<{ token: string; device_id: string; is_guest: boolean }>('/api/auth/guest', { device_id: deviceId() })
export const login = (phone: string, password = '', code = '') =>
  post<{ token: string; user_id: number }>('/api/auth/login', { phone, password, code })
export const register = (phone: string, code: string, password: string) =>
  post<{ token: string; user_id: number; merged: boolean }>('/api/auth/register', { phone, code, password, device_id: deviceId() })
export const sms = (phone: string) => post<{ message: string; dev_code: string }>('/api/auth/sms', { phone })
export const logout = () => setToken('')
export const isLoggedIn = () => Boolean(token())

/* ---------- 小工具 ---------- */
export const DNA_DIMS = ['剧情', '演技', '情感', '视听', '节奏']
export const cnTitle = (s: string) => String(s || '').split(/\s+/)[0]
export const num = (n: number) => (n ?? 0).toLocaleString()
