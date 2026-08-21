# 影灵 CINE · 电影推荐平台完整解读文档

**版本**: v2.0  
**更新日期**: 2026-08-18  
**项目路径**: `d:\ai编程\编程\movie`

---

## 📋 目录

1. [项目概述](#1-项目概述)
2. [技术架构](#2-技术架构)
3. [核心功能模块](#3-核心功能模块)
4. [数据层详解](#4-数据层详解)
5. [AI 系统详解](#5-ai-系统详解)
6. [前端架构](#6-前端架构)
7. [API 接口清单](#7-api-接口清单)
8. [部署与启动](#8-部署与启动)
9. [开发指南](#9-开发指南)
10. [常见问题](#10-常见问题)

---

## 1. 项目概述

### 1.1 项目定位

**影灵 CINE** 是一个基于 AI 的智能电影推荐与陪看平台，核心特色：

- ✅ **590 部高分电影精选库**（豆瓣 8.0+）
- ✅ **AI 智能推荐**（规则 + 向量语义双引擎）
- ✅ **AI 陪看讨论**（支持无剧透/允许剧透模式）
- ✅ **3D 银河可视化**（5000 颗电影星球）
- ✅ **真实口碑展示**（基于豆瓣短评数据）
- ✅ **多轮对话记忆**（AI 理解上下文追问）

### 1.2 核心价值

| 维度 | 传统平台 | 影灵 CINE |
|------|---------|-----------|
| 推荐方式 | 协同过滤 / 标签匹配 | DNA 五维评分 + 语义向量检索 |
| 信息呈现 | 百科式罗列 | AI 解读 + 真实短评 + 情绪分析 |
| 交互体验 | 静态浏览 | 3D 银河探索 + AI 对话 |
| 防剧透 | 无 | 支持无剧透模式 |
| 上下文理解 | 无 | 多轮对话记忆 |

### 1.3 数据来源

- **电影基础数据**: 豆瓣电影 API 爬取（`data/movies_info_clean.csv`）
- **短评数据**: 豆瓣短评 CSV（`data/movie_comments.csv`，约 150 万条）
- **长评数据**: 豆瓣长评 CSV（`data/movie_reviews.csv`）
- **海报图片**: 本地存储（`data/posters/`，590 张高清海报）

---

## 2. 技术架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────┐
│                   用户浏览器                      │
│              React 19 + Three.js                  │
│         (cine/web/src/ - Vite 构建)               │
└──────────────┬──────────────────────────────────┘
               │ HTTP / WebSocket
               ▼
┌─────────────────────────────────────────────────┐
│                 FastAPI 后端                      │
│           (cine/main.py - Port 8010)              │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ chat.py  │  │ data.py  │  │ recommend.py │   │
│  │ 聊天层   │  │ 数据层   │  │ 规则推荐层   │   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │             │                │            │
│  ┌────▼─────────────▼────────────────▼───────┐   │
│  │          llm.py (LLM 封装层)               │   │
│  │  OpenAI SDK → DeepSeek v4-flash / GLM-5.2 │   │
│  └────────────────────┬──────────────────────┘   │
│                       │                           │
│  ┌────────────────────▼──────────────────────┐   │
│  │         embed.py (向量检索层)              │   │
│  │  bge-small-zh-v1.5 + movie_vectors.npz     │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────
               │
               ▼
─────────────────────────────────────────────────┐
│                    数据层                        │
│                                                   │
│  • SQLite: cine.db (用户/会话/收藏)              │
│  • SQLite: comments_fts.db (短评全文索引)        │
│  • JSON: movies_core.json (590 部核心电影)       │
│  • JSON: similarity.json (相似片矩阵)            │
│  • JSON: sentiment.json (观众情绪分析)           │
│  • NPZ: movie_vectors.npz (512 维向量库)         │
│  • CSV: movie_comments.csv (原始短评)            │
└─────────────────────────────────────────────────┘
```

### 2.2 技术栈总览

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **前端框架** | React 19 + TypeScript | 组件化开发 |
| **构建工具** | Vite 8 | 极速热更新 |
| **状态管理** | Zustand 5 | 轻量级全局状态 |
| **3D 渲染** | Three.js + React Three Fiber | 银河可视化 |
| **动画** | Framer Motion | 流畅过渡效果 |
| **样式** | Tailwind CSS 4 | 原子化 CSS |
| **后端框架** | Python FastAPI | 异步高性能 |
| **数据库** | SQLite 3 | 轻量级关系型数据库 |
| **全文检索** | SQLite FTS5 | 中文分词搜索 |
| **向量检索** | sentence-transformers | BAAI/bge-small-zh-v1.5 |
| **LLM** | DeepSeek v4-flash | 通过 sensenova 代理 |
| **部署** | Uvicorn ASGI 服务器 | 生产级 WSGI |

### 2.3 项目目录结构

```
movie/
├── cine/                          # 后端核心代码
│   ├── main.py                    # FastAPI 入口，所有 API 路由
│   ├── chat.py                    # 聊天层：意图识别 → 检索 → LLM
│   ├── llm.py                     # LLM 封装：OpenAI SDK 调用
│   ├── data.py                    # 数据层：加载 JSON/FTS/向量
│   ├── recommend.py               # 规则推荐层：DNA + 相似片
│   ├── search.py                  # 检索层：FTS + 标题模糊
│   ├── embed.py                   # 向量语义检索层
│   ├── build_vectors.py           # 离线向量化脚本
│   ├── web/                       # 前端源码
│   │   ├── src/
│   │   │   ├── api.ts             # API 客户端
│   │   │   ├── store.ts           # Zustand 状态管理
│   │   │   ├── types.ts           # TypeScript 类型定义
│   │   │   ├── App.tsx            # 根组件
│   │   │   ├── pages/             # 页面组件
│   │   │   │   ├── Chat.tsx       # 问影灵聊天页
│   │   │   │   ├── Detail.tsx     # 电影详情页
│   │   │   │   ├── GalaxyScene.tsx # 银河场景
│   │   │   │   └── ...
│   │   │   ├── components/        # 通用组件
│   │   │   │   ├── Navigator.tsx  # AI 导航员
│   │   │   │   ├── Radar.tsx      # DNA 雷达图
│   │   │   │   └── ...
│   │   │   └── scenes/            # Three.js 场景
│   │   ├── dist/                  # 构建产物（生产环境）
│   │   └── package.json
│   └── data/                      # 运行时数据
│       ├── cine.db                # SQLite 主数据库
│       ├── lookup.db              # 库外电影索引
│       └── server.log
├── data/                          # 原始数据与中间产物
│   ├── enriched/                  # 处理后数据
│   │   ├── movies_core.json       # 590 部核心电影
│   │   ├── similarity.json        # 相似片矩阵
│   │   ├── sentiment.json         # 情绪分析结果
│   │   ├── comments_fts.db        # 短评全文索引
│   │   ├── movie_vectors.npz      # 向量库
│   │   ── posters_thumb/         # 缩略图
│   ├── posters/                   # 高清海报（590 张）
│   ├── movie_comments.csv         # 原始短评（150 万条）
│   ├── movie_reviews.csv          # 原始长评
│   └── movies_info_clean.csv      # 清洗后电影信息
├── logs/                          # 日志与报告
├── reports/                       # 质检报告
├── build_core_db.py               # 数据库构建脚本
── build_core_llm.py              # LLM 数据处理脚本
├── test_ai_context.py             # AI 上下文测试脚本
└── README.md
```

---

## 3. 核心功能模块

### 3.1 电影银河（Galaxy Scene）

**功能**: 3D 可视化展示 5000 颗电影星球

**技术实现**:
- **Three.js + React Three Fiber**: 3D 渲染引擎
- **StarField**: 背景星空粒子
- **PlanetLayer**: 5000 颗星球（590 核心 + 4410 库外精选）
- **MapLayer**: 地球仪（地区分布）

**星球属性**:
```typescript
interface Planet {
  id: string          // movie_id
  t: string           // title（片名）
  y: number | null    // year（年份）
  rating: number      // 豆瓣评分
  region: string      // 地区（华语/日本/韩国/欧美）
  genres: string[]    // 类型
  r: number           // radius（大小，基于评分+热度）
  b: number           // brightness（亮度，基于评价人数）
  c: string           // color（颜色，基于情绪温度）
  temp: number        // temperature（情绪温度 0-100）
  rc: number          // rating_count（评价人数）
  p?: string          // poster_thumb（海报缩略图）
  k?: number          // 亮度系数（核心片 1.0，库外片 0.55）
}
```

**视觉映射**:
- **大小** = f(评分, 评价人数, 评论数) → 0.5 ~ 2.2
- **亮度** = log₁₀(评价人数) → 0.3 ~ 1.0
- **颜色** = 情绪温度百分位 → 冷色(蓝紫) ~ 暖色(金)

**交互**:
- 悬停显示电影卡片
- 点击进入详情页
- 双击聚焦该星球

### 3.2 AI 导航员（Navigator）

**功能**: 根据用户心情推荐电影路线

**使用流程**:
1. 用户选择心情（如"😌 温暖治愈"）或输入描述
2. AI 分析意图，检索匹配电影
3. 生成 4 部电影探索路线（带序号、连线）
4. 每部电影展示：海报、匹配环、迷你雷达、高赞引用

**技术实现**:
- **意图解析**: `recommend.parse_hint()` 提取关键词
- **规则推荐**: DNA 维度匹配 + 类型/地区过滤
- **向量补位**: 关键词不足时走语义检索
- **LLM 润色**: DeepSeek 生成推荐理由

**UI 组件**:
- `MatchRing`: SVG 圆环展示匹配度（52-98%）
- `MiniRadar`: 五维 DNA 雷达图
- `RouteCard`: 路线节点卡片

### 3.3 问影灵（Chat）

**功能**: AI 聊天助手，支持推荐选片和陪看讨论

**两种模式**:

#### 模式 1: 推荐选片（rec）
- 用户描述需求（如"推荐一部催泪的日本电影"）
- AI 检索匹配电影，推荐 2-4 部
- 展示推荐理由、高赞评论

#### 模式 2: 陪看讨论（talk）
- **无剧透模式**（默认开启）: 只讲口碑强项，不透露剧情
- **允许剧透模式**: 自由讨论情节、结局

**多轮对话记忆**（v2.0 新增）:
- **短期记忆**: 会话内历史（最近 8 条 = 4 轮）
- **电影上下文**: 从详情页进入时自动携带 movie_id
- **追问理解**: AI 能理解"为什么？""然后呢？"等代词引用

**技术实现**:
```python
# 意图识别流程
build_reply(message, mode, spoiler, history, movie_context):
    1. 如果有 movie_context 且是追问 → _answer_movie()
    2. 电影名解析 → _answer_movie()
    3. 评论/梗检索 → _answer_search()
    4. 推荐意图 → _answer_recommend()
    5. 追问/跟进 → _answer_followup()
    6. 兜底帮助
```

**防幻觉机制**:
- 事实全部来自 enriched 数据
- LLM 只改表述，不改事实
- 片名白名单校验（禁止推荐库外电影）
- 推荐编号校验（必须在候选范围内）

### 3.4 电影详情页（Detail）

**展示内容**:
1. **头部**: 海报、片名、年份、类型、地区、导演、主演
2. **评分区**: 豆瓣评分、评价人数、情绪温度
3. **AI 解读**: LLM 生成的影片点评 + DNA 雷达图
4. **真实短评**: 好评/差评各 3 条（按点赞数排序）
5. **差评预警**: 如有争议点，提前提醒
6. **彩蛋/冷知识**: 幕后花絮
7. **相似电影**: 8 部邻近星球

**AI 陪看入口**（v2.0 新增）:
- "🍿 AI 陪看"按钮
- 点击跳转聊天页，自动携带 movie_id
- AI 知道当前讨论的电影

---

## 4. 数据层详解

### 4.1 核心数据文件

#### movies_core.json（590 部核心电影）

**结构**:
```json
{
  "movie_id": "1291546",
  "title": "霸王别姬",
  "year": 1993,
  "genres": ["剧情", "爱情", "同性"],
  "region": "华语",
  "countries": ["中国大陆", "香港"],
  "director": ["陈凯歌"],
  "actors": ["张国荣", "张丰毅", "巩俐"],
  "runtime_min": 171,
  "rating": 9.6,
  "rating_count": 1800000,
  "summary": "段小楼与程蝶衣...",
  "dna": {
    "剧情": 9.2,
    "演技": 9.8,
    "情感": 9.5,
    "视听": 8.7,
    "节奏": 7.8
  },
  "quotes": {
    "up1": {"text": "...", "votes": 41810, "star": 5, "author": "momo"},
    "dn1": {"text": "...", "votes": 335, "star": 2, "author": "东遇西"}
  },
  "sentiment": {...},
  "warn": {"text": "节奏偏慢，需要耐心"},
  "egg": {"text": "张国荣为演程蝶衣..."}
}
```

**DNA 五维评分**:
- **剧情**: 故事性、逻辑性、深度
- **演技**: 演员表演水平
- **情感**: 感染力、共鸣度
- **视听**: 画面、配乐、摄影
- **节奏**: 叙事节奏、剪辑

**数据来源**:
- 基础信息: 豆瓣 API
- DNA 评分: LLM 分析（`build_core_llm.py`）
- quotes: 高赞短评提取
- sentiment: 情绪分析（`build_sentiment.py`）

#### comments_fts.db（短评全文索引）

**表结构**:
```sql
CREATE VIRTUAL TABLE docs USING fts5(
  body,           -- 分词文本（用于搜索）
  cid UNINDEXED,  -- comment_id
  movie_id UNINDEXED,
  category UNINDEXED,  -- 好评/差评
  star UNINDEXED,
  votes UNINDEXED
);
```

**重要说明**:
- `body` 字段存储的是 **jieba 分词 + bigram** 文本，不是原文！
- 用于全文检索（如"哪部电影提到陀螺"）
- 展示评论时需从 CSV 读取原文（`top_comments()` 已修复）

**构建方式**:
```python
# build_core_db.py stage_fts()
def token(s):
    toks = jieba.lcut(s)           # jieba 分词
    bigs = [s[i:i+2] for i in range(len(s)-1)]  # 双字 bigram
    return " ".join(toks + bigs)   # 合并去重
```

#### movie_vectors.npz（向量库）

**结构**:
- `ids`: movie_id 列表（590 个）
- `vectors`: np.ndarray (590, 512)，已归一化

**向量化配方**（`build_vectors.py`）:
```python
content = f"""
{summary}
{sentiment.ai_summary}
{region}
{director}
{runtime_min}分钟
DNA: 剧情{dna['剧情']} 演技{dna['演技']} 情感{dna['情感']} 视听{dna['视听']} 节奏{dna['节奏']}
高频词: {freq_words}
高赞评论: {quotes['up1']['text']}
"""
vector = model.encode(content, normalize_embeddings=True)
```

**模型**: BAAI/bge-small-zh-v1.5（512 维）

**用途**: 语义检索（当关键词匹配不足时）

### 4.2 SQLite 数据库

#### cine.db（主数据库）

**表结构**:

```sql
-- 用户表
CREATE TABLE users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,      -- 手机号（游客为 NULL）
    pass_hash TEXT,         -- 密码哈希
    device_id TEXT,         -- 设备 ID（游客模式）
    token TEXT,             -- 登录令牌
    created_at TEXT
);

-- 短信验证码表
CREATE TABLE sms_codes(
    phone TEXT, code TEXT, expires_at REAL
);

-- 收藏表
CREATE TABLE favorites(
    user_id INTEGER, movie_id TEXT, created_at TEXT,
    PRIMARY KEY(user_id, movie_id)
);

-- 旧聊天表（兼容用）
CREATE TABLE chats(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, role TEXT, content TEXT, created_at TEXT
);

-- 新会话表（v2.0 新增）
CREATE TABLE conversations(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    movie_id TEXT,              -- 关联电影（可选）
    mode TEXT DEFAULT 'rec',    -- rec / talk
    title TEXT,                 -- 会话标题
    created_at TEXT,
    updated_at TEXT
);

-- 新消息表（v2.0 新增）
CREATE TABLE conversation_messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,         -- user / assistant
    content TEXT NOT NULL,
    movie_ids TEXT,             -- 推荐的电影 ID 列表（JSON）
    created_at TEXT,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
```

**设计亮点**:
- **双写过渡**: 新消息同时写入 `chats` 和 `conversation_messages`
- **向后兼容**: 旧版前端不传 `conversation_id` 也能工作
- **会话隔离**: 不同话题互不干扰

### 4.3 辅助数据文件

#### similarity.json（相似片矩阵）

**结构**:
```json
{
  "1291546": ["1291550", "1291560", ...],  // 霸王别姬的相似片
  "1291550": ["1291546", "1291568", ...],  // 十二怒汉的相似片
  ...
}
```

**计算方式**:
- 基于向量余弦相似度
- 取 top 8 作为相似片

#### sentiment.json（观众情绪分析）

**结构**:
```json
{
  "1291546": {
    "avg_star": 3.13,       // 样本内平均星级（分层抽样，数值向中间压缩）
    "n": 150,               // 该片已采集短评数（好/中/差各约 50 条的分层抽样）
    "good5": 0.86,          // 好评区中打 5 星的比例（层内强度，真实区分信号）
    "bad1": 0.14,           // 差评区中打 1 星的比例（层内强度）
    "temp": 92,             // 情绪温度（0-100，复合指标，暖冷渐变用）
    "emotions": [           // 高频情绪词（基于评论文本词频，与抽样比例无关）
      {"w": "感动", "n": 5},
      {"w": "震撼", "n": 3}
    ],
    "freq": [...],          // 高频词
    "trend": [...],         // 年度好评率趋势
    "ai_summary": "..."     // 基于真实统计拼装的总结（模板，不改事实）
  }
}
```

**计算方式**:
- 评论按好/中/差分层抽样（每片约 150 条），保证跨片可比；抽样比例类指标（如好/中/差占比）无统计意义，不输出
- good5 / bad1：各层内部的星级强度；情绪温度 temp = good5×0.6 + (1-bad1)×0.4 的百分位复合分
- emotions / freq：基于评论文本的词频统计
- ai_summary：真实数据模板拼装（防幻觉，不新增事实）

---

## 5. AI 系统详解

### 5.1 AI 架构分层

```
─────────────────────────────────────────┐
│          LLM 封装层 (llm.py)             │
│  • OpenAI SDK 调用                       │
│  • 模型链降级（deepseek → glm）          │
│  • 限流保护（1 秒/次）                   │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────
│        聊天层 (chat.py)                  │
│  • 意图识别                              │
│  • Prompt 组装                           │
│  • LLM 调用 / 离线降级                   │
│  • 防幻觉校验                            │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│        检索层 (search.py + embed.py)     │
│  • 标题模糊匹配                          │
│  • FTS 全文检索                          │
│  • 向量语义检索                          │
└────────────────────────────────────────┘
                 │
────────────────▼────────────────────────┐
│        规则推荐层 (recommend.py)         │
│  • DNA 维度匹配                          │
│  • 类型/地区/年份过滤                    │
│  • 相似片推荐                            │
└─────────────────────────────────────────┘
```

### 5.2 意图识别流程

```python
def build_reply(message, mode, spoiler, history, movie_context):
    """
    意图识别优先级：
    1. 有电影上下文 + 追问 → 电影问答
    2. 电影名解析 → 电影问答
    3. 评论/梗检索 → 搜索回答
    4. 推荐意图 → 推荐回答
    5. 追问/跟进 → 基于历史继续
    6. 兜底帮助
    """
    
    # 优先处理：有电影上下文的追问
    if movie_context and _is_followup(msg):
        return _answer_movie(...)
    
    # 电影名解析
    kind, m = search.resolve_title(msg)
    if m:
        return _answer_movie(...)
    
    # 评论/梗检索
    if _SEARCH_HINT.search(msg):
        return _answer_search(...)
    
    # 陪看模式
    if mode == "talk":
        if movie_context:
            return _answer_movie(...)
        return {"text": "告诉我你准备看哪部..."}
    
    # 推荐意图
    hint = recommend.parse_hint(msg)
    if hint["dim"] or hint["genre"] or ...:
        return _answer_recommend(...)
    
    # 追问处理
    if _is_followup(msg) and history:
        last_titles = _extract_last_rec_movies(history)
        if last_titles:
            return _answer_movie(...)
    
    # 兜底
    return {"text": "我可以..."}
```

### 5.3 追问检测机制

```python
def _is_followup(msg: str) -> bool:
    """判断是否为追问/跟进"""
    msg = msg.strip()
    
    # 短消息（<20字）+ 追问关键词
    if len(msg) < 20 and (_FOLLOWUP_HINT.search(msg) or _BROAD_FOLLOWUP.search(msg)):
        return True
    
    # 含代词/省略式追问
    if re.search(r"(这个|那个|它|他|她|这部|这部片|这部电影|结局|最后|然后呢|什么意思|讲什么)", msg):
        return True
    
    return False

_FOLLOWUP_HINT = re.compile(r"^(换|再|来|有没有|另外|还有|不要|换掉|去掉|更|太|少一点|多一点|别|那|它|这|为什么|然后|但是|不过|怎么|如何|谁|哪里|什么|哪|为啥|结局|最后|导演|演员|拍|演)")
_BROAD_FOLLOWUP = re.compile(r"^(嗯|哦|啊|是|对|好的|那|好|行|可以|明白了|了解|谢谢|感谢|哈哈|确实|真的|同意|不一定|不太|其实|感觉|觉得|为什么|为啥|怎么)")
```

**覆盖场景**:
- "为什么？" → 解释上一轮推荐
- "然后呢？" → 延续话题
- "这个结局" → 指代当前电影
- "换两部" → 重新推荐
- "更短的" → 加片长约束

### 5.4 Prompt 系统设计

#### 系统提示词（5 个场景）

**1. SYSTEM_PROMPT_REC（推荐选片）**
```
你是「影灵」，一位懂电影、懂人心的私人选片顾问。

工作方式：
1. 用户描述想看电影的心情或需求。
2. 每条用户消息后会附上【推荐清单】，来自590部高分电影库的检索结果。
3. 你从中挑选 2~3 部最合适的推荐。

必须遵守：
- 只推荐清单中的电影，绝不提及清单之外的任何影片。
- 推荐理由必须基于清单内容。
- 结合对话历史理解用户意图。
- 需求模糊时先追问 1 个最关键的问题。
- 语气像熟悉的朋友：温暖、口语化。
- 回复末尾附上推荐编号：[推荐编号: 1,3]
```

**2. SYSTEM_PROMPT_MOVIE（电影问答）**
```
你是影灵CINE电影助手，正在回答用户关于某部电影的问题。
用户消息后会附上【该片事实】卡片——这是你唯一的事实来源。

必须遵守：
- 只许改述事实，不许新增任何事实、评价或情节。
- 结合对话历史理解追问。
- 简短自然，像朋友聊天，不写百科腔。
```

**3. SYSTEM_PROMPT_TALK_SAFE（陪看无剧透）**
```
你是影灵CINE电影助手，用户正在和你讨论一部还没看/正在看的电影。
这是看前导览场景，严禁剧透。

必须遵守：
- 只可润色提供的事实，不新增事实。
- 用好评与观众情绪引出期待感。
- 结合对话历史延续话题。
- 简短。
```

**4. SYSTEM_PROMPT_TALK_FULL（陪看允许剧透）**
```
你是影灵CINE电影助手，正和用户自由讨论一部电影（用户已看过）。
用好评与差评的真实观点引出讨论，主动抛出有讨论价值的话题。

必须遵守：
- 只可基于提供的好评/差评观点展开。
- 语气像聊得来的影友，有自己的态度。
- 结合对话历史延续话题。
- 简短。
```

**5. SYSTEM_PROMPT_SEARCH（短评检索）**
```
你是影灵CINE电影助手。基于用户问题与检索命中的短评片段回答。

必须遵守：
- 只可改述检索结果中出现的电影名和评论原文。
- 按相关度组织回答。
- 简短。
```

#### 电影上下文注入（v2.0 新增）

```python
def _build_enhanced_system(base_system: str, movie_context: dict | None = None) -> str:
    """构建增强版系统提示词，注入电影上下文"""
    if not movie_context:
        return base_system
    return base_system + "\n\n" + movie_context["prompt_text"]

# movie_context["prompt_text"] 示例：
"""
【当前讨论电影】
《花样年华》(2000) 豆瓣 8.6
导演：王家卫 | 主演：梁朝伟 / 张曼玉
类型：剧情 / 爱情 | 地区：华语
简介：两段婚外情在1960年代的香港悄然发生……
DNA：剧情8 演技9 情感9 视听10 节奏6
好评：「梁朝伟和张曼玉的表演让人心碎」
差评预警：节奏偏慢，需要耐心
"""
```

### 5.5 防幻觉机制

**三层防护**:

1. **事实来源限制**:
   - 所有事实来自 enriched 数据
   - LLM 只改表述，不改事实

2. **片名白名单校验**:
```python
def _check_foreign_titles(text: str, candidates: list[dict]) -> bool:
    """正文里出现书名号片名且不在候选清单 → True（有库外片名）"""
    allowed = {m["title"].split(" ")[0] for m in candidates}
    found = re.findall(r'[《<]([^》>]{1,30})[》>]', text)
    return any(f.split(" ")[0] not in allowed for f in found)
```

3. **推荐编号校验**:
```python
def _validate_rec_ids(text: str, n_candidates: int) -> bool:
    """校验回复中的 [推荐编号: x,y] 是否都在候选范围内"""
    m = re.search(r'\[推荐编号:\s*([\d,\s]+)\]', text)
    if not m:
        return True  # 没有编号就不校验
    ids = [int(x.strip()) for x in m.group(1).split(",")]
    return all(1 <= i <= n_candidates for i in ids)
```

**降级策略**:
- LLM 失败 → 离线文案
- 校验失败 → 重试一次
- 仍失败 → 完全离线

### 5.6 LLM 调用层

**模型链**:
```python
CHAT_MODELS = ["deepseek-v4-flash", "glm-5.2"]

for model in CHAT_MODELS:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[system] + history + [user],
            temperature=temperature,
            max_tokens=700
        )
        return response.choices[0].message.content, model
    except Exception:
        continue  # 尝试下一个模型
return None, None  # 全部失败，降级离线
```

**配置**:
```json
// data/task/llm_config.json
{
  "provider": "deepseek",
  "base_url": "https://token.sensenova.cn/v1",
  "api_key": "sk-xxx",  // 或使用环境变量 CINE_LLM_API_KEY
  "models": {
    "main": "deepseek-v4-flash",
    "fallback": null,
    "chat": "deepseek-v4-flash"
  }
}
```

**限流保护**:
```python
MIN_INTERVAL = 1.0  # 最少间隔 1 秒

def _throttle():
    with _lock:
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
```

---

## 6. 前端架构

### 6.1 组件层次

```
App.tsx
── GalaxyScene.tsx          # 3D 银河场景
│   ├── StarField.tsx        # 背景星空
│   ├── PlanetLayer.tsx      # 5000 颗星球
│   └── MapLayer.tsx         # 地球仪
├── HUD.tsx                  # HUD 界面（顶部栏、底部栏）
├── Navigator.tsx            # AI 导航员模态框
├── Pages (AnimatePresence)
│   ├── Detail.tsx           # 电影详情页
│   ├── Chat.tsx             # 问影灵聊天页
│   ├── Profile.tsx          # 个人中心
│   ├── Login.tsx            # 登录页
│   ├── Account.tsx          # 账号页
│   ├── Guest.tsx            # 游客页
│   ├── About.tsx            # 关于页
│   ├── List.tsx             # 电影列表页
│   └── Explore.tsx          # 探索档案页
└── BootScene.tsx            # 开场动画
```

### 6.2 状态管理（Zustand）

```typescript
// store.ts
interface GalaxyStore {
  planets: Planet[]
  planetsById: Record<string, Planet>
  loaded: boolean
  booted: boolean
  hoverId: string | null
  hoverPos: { x: number; y: number } | null
  selectedId: string | null      // 当前选中星球
  interacting: boolean
  focusRegion: string
  focusGenre: string
  navigatorOpen: boolean
  
  setPlanets: (ps: Planet[]) => void
  setBooted: (b: boolean) => void
  setHover: (id: string | null) => void
  setSelected: (id: string | null) => void
  setNavigatorOpen: (b: boolean) => void
  // ...
}

export const useGalaxy = create<GalaxyStore>((set) => ({
  planets: [],
  planetsById: {},
  loaded: false,
  booted: false,
  hoverId: null,
  selectedId: null,
  navigatorOpen: false,
  // ...
}))
```

**使用示例**:
```tsx
// 读取状态
const planets = useGalaxy((s) => s.planets)
const selectedId = useGalaxy((s) => s.selectedId)

// 修改状态
useGalaxy.getState().setSelected(movieId)
```

### 6.3 路由系统

**Hash-based 路由**:
```typescript
// App.tsx
function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>({ path: '/', params: {} })
  
  useEffect(() => {
    const onHash = () => {
      const hash = location.hash || '#/'
      const m = hash.match(/^#\/movie\/([\w]+)/)
      if (m) { 
        setRoute({ path: '/movie', params: { id: m[1] } })
        return 
      }
      setRoute({ path: hash.replace(/^#/, '') || '/', params: {} })
    }
    onHash()
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  
  return route
}
```

**路由映射**:
- `#/` → 银河首页
- `#/movie/:id` → 电影详情页
- `#/chat?movie_id=:id` → 聊天页（可选携带电影 ID）
- `#/profile` → 个人中心
- `#/login` → 登录页
- `#/explore` → 探索档案

### 6.4 API 客户端

```typescript
// api.ts
const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init)
  if (!r.ok) throw new Error(`请求失败 ${r.status}`)
  return r.json()
}

const get = <T>(p: string) => api<T>(p)
const post = <T>(p: string, body: unknown) => 
  api<T>(p, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) })

// 聊天 API（v2.0 增强）
export const chat = (
  message: string,
  mode: 'rec' | 'talk' = 'rec',
  spoiler = true,
  conversationId?: number,   // 新增：会话 ID
  movieId?: string           // 新增：电影 ID
) => post<ChatReply>('/api/chat', {
  message,
  device_id: deviceId(),
  mode,
  spoiler,
  conversation_id: conversationId,
  movie_id: movieId
})
```

### 6.5 关键 UI 组件

#### Radar.tsx（DNA 雷达图）

```tsx
// 五维雷达图：剧情、演技、情感、视听、节奏
function Radar({ dna }: { dna: Record<string, number> }) {
  const dims = ['剧情', '演技', '情感', '视听', '节奏']
  const n = dims.length
  const cx = 100, cy = 100, R = 80
  
  // 计算顶点坐标
  const pt = (i: number, v: number) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2
    const r = (v / 10) * R
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r]
  }
  
  // 绘制网格、轴线、数据多边形
  return (
    <svg width={200} height={200}>
      {/* 同心五边形网格 */}
      {/* 轴线 */}
      {/* 数据填充 */}
    </svg>
  )
}
```

#### Navigator.tsx（AI 导航员）

**关键特性**:
- 心情选择快捷按钮
- 路线卡片（带序号圆点、连线）
- 匹配环（SVG 圆环动画）
- 迷你雷达（五维 DNA）
- 高赞引用展示

---

## 7. API 接口清单

### 7.1 电影相关

#### GET /api/galaxy
获取银河星球数据

**响应**:
```json
{
  "total": 5000,
  "planets": [
    {
      "id": "1291546",
      "t": "霸王别姬",
      "y": 1993,
      "rating": 9.6,
      "region": "华语",
      "genres": ["剧情", "爱情"],
      "r": 2.1,
      "b": 0.95,
      "c": "#ffd700",
      "temp": 85,
      "rc": 1800000,
      "p": "/posters_thumb/1291546.jpg",
      "k": 1.0
    },
    ...
  ]
}
```

#### GET /api/movies
电影列表（支持筛选、排序、搜索）

**参数**:
- `region`: 地区（华语/日本/韩国/欧美）
- `genre`: 类型
- `year_min`, `year_max`: 年份范围
- `dim`: DNA 维度（剧情/演技/情感/视听/节奏）
- `dim_min`: DNA 最小值
- `sort`: 排序方式（dna/rating/剧情/演技/情感/视听/节奏）
- `q`: 搜索关键词
- `page`: 页码（默认 1）
- `limit`: 每页数量（默认 24）

**响应**:
```json
{
  "total": 590,
  "page": 1,
  "limit": 24,
  "items": [
    {
      "movie_id": "1291546",
      "title": "霸王别姬",
      "year": 1993,
      "genres": ["剧情", "爱情"],
      "region": "华语",
      "director": ["陈凯歌"],
      "actors": ["张国荣", "张丰毅", "巩俐"],
      "rating": 9.6,
      "rating_count": 1800000,
      "summary": "...",
      "poster_thumb": "/posters_thumb/1291546.jpg",
      "dna": {...},
      "tags": {...},
      "quotes": {...}
    },
    ...
  ]
}
```

#### GET /api/movies/:movie_id
电影详情

**响应**:
```json
{
  "movie_id": "1291546",
  "title": "霸王别姬",
  "year": 1993,
  "genres": ["剧情", "爱情"],
  "region": "华语",
  "countries": ["中国大陆", "香港"],
  "director": ["陈凯歌"],
  "writer": ["芦苇", "李碧华"],
  "actors": ["张国荣", "张丰毅", "巩俐"],
  "runtime_min": 171,
  "rating": 9.6,
  "rating_count": 1800000,
  "summary": "...",
  "brief": "...",
  "poster_full": "/posters/1291546.jpg",
  "poster_thumb": "/posters_thumb/1291546.jpg",
  "dna": {...},
  "tags": {...},
  "quotes": {...},
  "stats": {...},
  "sentiment": {...},
  "similar": [...],
  "warn": {...},
  "egg": {...},
  "top_comments": {
    "up": [
      {"cid": "24303417", "text": "...", "votes": 41810, "star": 5, "author": "momo"},
      ...
    ],
    "dn": [...]
  }
}
```

#### GET /api/search
搜索（标题 + FTS）

**参数**:
- `q`: 搜索关键词
- `type`: all/title/fts
- `limit`: 返回数量

**响应**:
```json
{
  "titles": [
    {"movie_id": "1291546", "title": "霸王别姬", "year": 1993, "rating": 9.6}
  ],
  "fts": [
    {"cid": "24303417", "movie_id": "1291546", "title": "霸王别姬", "snip": "...", "votes": 41810}
  ]
}
```

#### GET /api/suggest
标题联想

**参数**:
- `q`: 前缀

**响应**:
```json
{
  "items": [
    {"type": "core", "title": "霸王别姬", "movie_id": "1291546", "year": 1993},
    {"type": "ext", "title": "霸王别姬(京剧)", "year": 1993}
  ]
}
```

### 7.2 聊天相关

#### POST /api/chat
发送聊天消息

**请求体**:
```json
{
  "message": "推荐一部类似《花样年华》的电影",
  "device_id": "dabc123",
  "mode": "rec",           // rec / talk
  "spoiler": true,         // 无剧透开关
  "conversation_id": 123,  // 可选：会话 ID（v2.0）
  "movie_id": "1291546"    // 可选：电影 ID（v2.0）
}
```

**响应**:
```json
{
  "text": "根据你的需求，我推荐以下几部电影：\n1. 《重庆森林》...",
  "offline": false,
  "citations": [
    {"kind": "quote", "movie_id": "1291550", "title": "重庆森林", "text": "...", "votes": 28404}
  ],
  "kind": "recommend",
  "model": "deepseek-v4-flash",
  "movies": [
    {
      "movie_id": "1291550",
      "title": "重庆森林",
      "year": 1994,
      "genres": ["剧情", "爱情"],
      "rating": 8.8,
      "poster_thumb": "/posters_thumb/1291550.jpg",
      "dna": {...},
      "top_dim": "视听",
      "top_val": 9.2,
      "match": 87,
      "reason": "视听维度 9.2 分 —— 「王家卫的镜头语言令人沉醉」"
    },
    ...
  ],
  "conversation_id": 123  // v2.0 新增
}
```

### 7.3 用户相关

#### POST /api/auth/guest
游客登录

**请求体**:
```json
{"device_id": "dabc123"}
```

**响应**:
```json
{"token": "abc123def456", "device_id": "dabc123", "is_guest": true}
```

#### POST /api/auth/sms
发送验证码

**请求体**:
```json
{"phone": "13800138000"}
```

**响应**:
```json
{"message": "验证码已发送(演示期固定 246810)", "dev_code": "246810"}
```

#### POST /api/auth/register
注册

**请求体**:
```json
{
  "phone": "13800138000",
  "code": "246810",
  "password": "123456",
  "device_id": "dabc123"
}
```

**响应**:
```json
{"token": "xyz789", "user_id": 1, "merged": true}
```

#### POST /api/auth/login
登录

**请求体**:
```json
{"phone": "13800138000", "password": "123456"}
// 或
{"phone": "13800138000", "code": "246810"}
```

**响应**:
```json
{"token": "xyz789", "user_id": 1}
```

#### GET /api/account
获取账号信息

**参数**:
- `token`: 登录令牌

**响应**:
```json
{
  "id": 1,
  "phone": "13800138000",
  "is_guest": false,
  "device_id": "dabc123",
  "created_at": "2026-08-18 10:00:00",
  "favorites": [...],
  "history": [{"role": "user", "content": "..."}, ...]
}
```

#### POST /api/favorites
收藏电影

**请求体**:
```json
{"movie_id": "1291546"}
```

**参数**:
- `token`: 登录令牌

#### DELETE /api/favorites
取消收藏

**参数**:
- `movie_id`: 电影 ID
- `token`: 登录令牌

### 7.4 探索档案

#### GET /api/explorer
获取探索档案

**参数**:
- `token`: 登录令牌

**响应**:
```json
{
  "total": 590,
  "discovered": 45,
  "progress": 7.6,
  "level": {"tag": "Lv.2", "name": "星河漫游者", "threshold": 5},
  "badges": [
    {"key": "traveler", "name": "初入银河", "icon": "🌌", "desc": "收藏了第一部电影"},
    {"key": "east", "name": "东方电影探索者", "icon": "🏮", "desc": "收藏华语/日韩电影 ≥ 3 部"}
  ],
  "favorites": [...]
}
```

---

## 8. 部署与启动

### 8.1 环境要求

- **Python**: 3.13+
- **Node.js**: 18+
- **内存**: ≥ 4GB（向量模型加载需 2GB+）
- **磁盘**: ≥ 10GB（数据文件约 8GB）

### 8.2 依赖安装

#### 后端依赖
```bash
cd d:\ai编程\编程\movie
pip install fastapi uvicorn pydantic pandas sqlite3 sentence-transformers openai jieba chardet
```

#### 前端依赖
```bash
cd cine/web
npm install
```

### 8.3 数据准备

1. **确认数据文件存在**:
   - `data/enriched/movies_core.json`
   - `data/enriched/comments_fts.db`
   - `data/enriched/movie_vectors.npz`
   - `data/enriched/sentiment.json`
   - `data/enriched/similarity.json`
   - `data/posters/*.jpg`

2. **如需重新构建**:
```bash
# D0: 清洗数据
python build_core_db.py --stage load

# D1.2: 五维 DNA
python build_core_llm.py --stage dna

# D1.1: 摘录候选
python build_core_llm.py --stage quotes

# D1.3: 相似片矩阵
python build_core_db.py --stage similar

# D1.4: 短评全文索引
python build_core_db.py --stage fts

# D1.5: 海报缩略图
python build_core_db.py --stage thumbs
```

### 8.4 启动服务

#### 方法 1: 直接启动
```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
D:\anaconda\python.exe -m uvicorn cine.main:app --port 8010
```

#### 方法 2: 开发模式（自动重载）
```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
D:\anaconda\python.exe -m uvicorn cine.main:app --port 8010 --reload
```

#### 方法 3: 后台运行
```powershell
Start-Process -FilePath "D:\anaconda\python.exe" `
  -ArgumentList "-m", "uvicorn", "cine.main:app", "--port", "8010" `
  -WindowStyle Hidden
```

### 8.5 前端构建与部署

#### 开发模式
```bash
cd cine/web
npm run dev
# 访问 http://localhost:5173
```

#### 生产构建
```bash
cd cine/web
npm run build
# 构建产物输出到 cine/web/dist/
```

#### 集成部署
FastAPI 会自动托管 `cine/web/dist/` 目录：
```python
# main.py
WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"
if (WEB_DIST / "index.html").exists():
    STATIC_DIR = WEB_DIST
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
```

访问 `http://127.0.0.1:8010` 即可看到前端页面。

### 8.6 API Key 配置

**方式 1: 配置文件**（不推荐，需加入 .gitignore）
```json
// data/task/llm_config.json
{
  "api_key": "sk-your-key-here",
  "base_url": "https://token.sensenova.cn/v1",
  "models": {"chat": "deepseek-v4-flash"}
}
```

**方式 2: 环境变量**（推荐）
```powershell
$env:CINE_LLM_API_KEY = "sk-your-key-here"
```

代码优先读取环境变量：
```python
cfg["api_key"] = os.environ.get("CINE_LLM_API_KEY") or cfg.get("api_key")
```

---

## 9. 开发指南

### 9.1 添加新功能

#### 示例：新增电影标签功能

**步骤 1: 后端 API**
```python
# main.py
@app.get("/api/movies/{movie_id}/tags")
def api_movie_tags(movie_id: str):
    m = data.movie(movie_id)
    if m:
        return {"tags": m.get("tags")}
    raise HTTPException(404, "movie not found")
```

**步骤 2: 前端 API 客户端**
```typescript
// api.ts
export const movieTags = (id: string) => get<{ tags: Movie['tags'] }>(`/api/movies/${id}/tags`)
```

**步骤 3: 前端组件**
```tsx
// Detail.tsx
const [tags, setTags] = useState<Movie['tags']>(null)

useEffect(() => {
  movieTags(id).then(setTags)
}, [id])

{tags && (
  <div className="detail-tags">
    {tags.mood?.map(t => <span key={t}>{t}</span>)}
  </div>
)}
```

### 9.2 调试技巧

#### 后端日志
```python
import logging
log = logging.getLogger("cine.chat")
log.debug("加载历史 %d 条 for device=%s", len(history), device_id[:8])
log.warning("向量检索失败：%s", str(e)[:120])
```

查看日志：
```powershell
Get-Content cine\data\server.log -Tail 50 -Wait
```

#### 前端调试
```typescript
console.log('API 响应:', data)
console.error('请求失败:', error)
```

浏览器开发者工具 → Network 面板查看 API 请求。

#### 数据库查询
```bash
# 使用 DB Browser for SQLite 或命令行
sqlite3 cine/data/cine.db

SELECT * FROM conversations ORDER BY created_at DESC LIMIT 10;
SELECT * FROM conversation_messages WHERE conversation_id = 1;
```

### 9.3 性能优化

#### 后端优化
1. **懒加载向量模型**: `embed.py` 使用双检锁避免重复加载
2. **SQLite PRAGMA**: `PRAGMA query_only=1` 提升只读性能
3. **限流保护**: `_throttle()` 防止 API 滥用

#### 前端优化
1. **懒加载图片**: `<img loading="lazy" />`
2. **React.memo**: 避免不必要的重渲染
3. **Zustand 细粒度订阅**: `useGalaxy((s) => s.planets)` 而非整个 store

### 9.4 代码规范

#### Python
- 遵循 PEP 8
- 类型注解（Python 3.10+）
- 文档字符串（Google style）

#### TypeScript
- 严格模式（`strict: true`）
- ESLint + Oxlint
- 组件命名：PascalCase
- 函数命名：camelCase

---

## 10. 常见问题

### Q1: 后端启动报错 "No module named 'sentence_transformers'"
**A**: 安装依赖：
```bash
pip install sentence-transformers
```

### Q2: 向量模型下载失败
**A**: 设置镜像源：
```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

### Q3: 评论显示分词文本
**A**: 重启后端服务（已修复，见 [COMMENTS_FIX_INSTRUCTIONS.md](file:///d:/ai编程/编程/movie/COMMENTS_FIX_INSTRUCTIONS.md)）

### Q4: AI 回复很慢
**A**: 
- 检查网络连接（DeepSeek API 需要科学上网）
- 降低 `max_tokens` 或 `temperature`
- 启用离线模式（LLM 失败时自动降级）

### Q5: 前端页面空白
**A**:
- 检查后端是否启动（访问 `http://127.0.0.1:8010/api/movies?limit=1`）
- 清除浏览器缓存（Ctrl+F5）
- 检查 `cine/web/dist/index.html` 是否存在

### Q6: 如何修改 DNA 权重？
**A**: 编辑 `cine/recommend.py` 的 `_KEYMAP` 和 `recommend()` 函数

### Q7: 如何添加新电影？
**A**:
1. 添加到 `data/movies_info_clean.csv`
2. 运行 `build_core_db.py --stage load`
3. 运行 `build_core_llm.py` 生成 DNA
4. 运行 `build_vectors.py` 更新向量库

### Q8: 会话历史在哪里查看？
**A**:
```sql
SELECT * FROM conversations ORDER BY created_at DESC;
SELECT * FROM conversation_messages WHERE conversation_id = 1 ORDER BY created_at;
```

### Q9: 如何备份数据？
**A**:
```bash
# 备份数据库
Copy-Item cine\data\cine.db cine\data\cine.db.bak_$(Get-Date -Format yyyyMMdd_HHmmss)

# 备份 JSON 数据
Copy-Item data\enriched\*.json data\enriched\backup\
```

### Q10: 生产环境部署建议
**A**:
- 使用 Gunicorn + Uvicorn workers
- 配置 Nginx 反向代理
- 启用 HTTPS
- 定期备份数据库
- 监控 API 响应时间

---

## 附录 A: 快速参考卡

### 启动命令速查
```powershell
# 后端
$env:HF_ENDPOINT = "https://hf-mirror.com"
D:\anaconda\python.exe -m uvicorn cine.main:app --port 8010

# 前端开发
cd cine/web
npm run dev

# 前端构建
cd cine/web
npm run build

# 测试 AI 上下文
D:\anaconda\python.exe test_ai_context.py
```

### 关键文件路径
```
后端入口: cine/main.py
聊天逻辑: cine/chat.py
LLM 封装: cine/llm.py
数据加载: cine/data.py
向量检索: cine/embed.py

前端入口: cine/web/src/App.tsx
聊天页: cine/web/src/pages/Chat.tsx
详情页: cine/web/src/pages/Detail.tsx
API 客户端: cine/web/src/api.ts

核心数据: data/enriched/movies_core.json
向量库: data/enriched/movie_vectors.npz
FTS 索引: data/enriched/comments_fts.db
主数据库: cine/data/cine.db
```

### API 端点速查
```
GET  /api/galaxy              # 银河星球
GET  /api/movies              # 电影列表
GET  /api/movies/:id          # 电影详情
GET  /api/search              # 搜索
POST /api/chat                # 聊天
POST /api/auth/guest          # 游客登录
POST /api/auth/login          # 登录
GET  /api/account             # 账号信息
POST /api/favorites           # 收藏
GET  /api/explorer            # 探索档案
```

---

## 附录 B: 更新日志

### v2.0（2026-08-18）
- ✅ AI 多轮对话上下文记忆
- ✅ 电影陪看状态传递
- ✅ 会话管理（conversations 表）
- ✅ 追问检测增强
- ✅ 电影上下文注入 Prompt
- ✅ 影评显示修复（从 CSV 读取原文）

### v1.0（2026-08-04）
- ✅ 590 部核心电影库
- ✅ DNA 五维评分
- ✅ AI 推荐与陪看
- ✅ 3D 银河可视化
- ✅ 真实口碑展示

---

**文档结束**

如有疑问，请参考：
- [AI_CONTEXT_IMPLEMENTATION.md](file:///d:/ai编程/编程/movie/AI_CONTEXT_IMPLEMENTATION.md) - AI 上下文改造详细文档
- [AI_CONTEXT_QUICKSTART.md](file:///d:/ai编程/编程/movie/AI_CONTEXT_QUICKSTART.md) - 快速启动指南
- [COMMENTS_FIX_INSTRUCTIONS.md](file:///d:/ai编程/编程/movie/COMMENTS_FIX_INSTRUCTIONS.md) - 影评修复说明

祝使用愉快！🎬✨
