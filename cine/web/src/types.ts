/* 影灵 CINE · 电影宇宙 类型定义 */

export interface Planet {
  id: string
  t: string       // title
  y: number | null
  rating: number
  region: string
  genres: string[]
  r: number       // radius 权重
  b: number       // brightness 0-1
  c: string       // 颜色 hex
  temp: number    // 情绪温度 0-100
  rc: number      // 评价人数
  p?: string | null // poster_thumb 路径（星球贴图）
  k?: number      // 亮度系数：核心片 1.0，库外片 0.55（稍暗）
}

export interface Sentiment {
  avg_star: number | null
  n: number
  good5: number
  bad1: number
  temp: number
  emotions: { w: string; n: number }[]
  freq: { w: string; n: number }[]
  trend: { y: number; pos: number; n: number }[]
  ai_summary: string
}

export interface Quote {
  cid?: string
  text: string
  votes: number
  star?: number
  author?: string
}

export interface Movie {
  movie_id: string
  title: string
  year: number | null
  genres: string[]
  region: string
  countries?: string[]
  director?: string[]
  writer?: string[]
  actors?: string[]
  runtime_min?: number
  rating: number
  rating_count?: number
  summary?: string
  brief?: string
  poster_thumb?: string | null
  poster_full?: string | null
  dna: Record<string, number>
  tags?: { mood: string[]; scene: string[]; _evidence: Record<string, unknown> }
  quotes?: { up1?: Quote; dn1?: Quote }
  stats?: { comments_total?: number; reviews_total?: number; votes_sum?: number }
  sentiment: Sentiment | null
  similar?: Movie[]
  egg?: { text?: string } | null
  warn?: { text?: string; points?: string[] } | null
  top_comments?: { up: Quote[]; dn: Quote[] }
}

export interface ExplorerReply {
  total: number
  discovered: number
  progress: number
  level: { tag: string; name: string; threshold: number }
  badges: { key: string; name: string; icon: string; desc: string }[]
  favorites: Movie[]
}

/* ---------- AI 导航员 / 聊天 ---------- */
export interface Citation {
  kind: 'quote' | 'fts'
  movie_id?: string
  title?: string
  text: string
  votes?: number
  star?: number
  author?: string
}

/* ---------- 推荐解释（ExplainCard） ---------- */
export interface ExplainDim {
  dim: string       // 五维名
  user: number      // 用户画像分 0-100
  movie: number     // 影片维度分 0-100
  fit: number       // 契合度 0-100
}
export interface ExplainData {
  dims: ExplainDim[]
  bullets: string[] // 结构化推荐理由（模板生成，只引用真实数据）
}

export interface RecCard {
  movie_id: string
  title: string
  year: number | null
  genres: string[]
  rating: number
  runtime_min?: number | null
  poster_thumb?: string | null
  dna: Record<string, number>
  top_dim: string
  top_val: number
  match: number
  reason: string
  explain?: ExplainData   // 有画像时附推荐解释
}

export interface ChatReply {
  text: string
  offline: boolean
  citations: Citation[]
  kind: string
  model?: string | null
  movie_id?: string
  movie?: RecCard
  movies?: RecCard[]
  conversation_id?: number
  follow_ups?: string[]            // 陪看引导话题 chip
}

/* ---------- AI 陪看开场 ---------- */
export interface WatchOpening {
  text: string
  offline: boolean
  model?: string | null
  kind: string
  citations: Citation[]
  chips: string[]
  movie_id: string
  movie: RecCard
}

export interface AccountData {
  id: number
  phone: string | null
  is_guest: boolean
  device_id: string | null
  created_at: string
  favorites: Movie[]
  history: { role: string; content: string }[]
}

/* ---------- 电影人格测试 ---------- */
export interface QuizOption { em: string; t: string }
export interface QuizQuestion { q: string; opts: QuizOption[] }
export interface PersonalityProfile {
  dna: Record<string, number>      // 五维 0-100
  keywords: string[]
  movies: RecCard[]
  created_at?: string
}
export interface RouteStage {
  seq: number
  name: string                     // 阶段名：热身 · 最熟悉的味道
  desc: string                     // 阶段导语
  movie: RecCard                   // reason 为阶段化推荐理由
}
export interface PersonalityRoute {
  dna: Record<string, number>
  stages: RouteStage[]
}
