# 影灵 CINE · 电影宇宙

> 数可视 AI 应用赛道参赛作品

一个以"电影银河"为核心可视化的 AI 电影推荐平台。590 部高分电影构成 5000 颗星球，AI 导航员「影灵」陪你选片、聊片、陪看。

## 核心功能

- **电影银河**：590 部核心电影 + 4410 部库外精选，构成可交互的 3D 电影宇宙（Three.js + React Three Fiber）
- **AI 问影灵**：自然语言推荐电影，支持多轮对话、无剧透模式、推荐解释
- **AI 陪看**：选片后进入陪看模式，AI 主动破冰、聊剧情、讨论观点
- **电影人格测试**：五维 DNA 人格画像，生成个性化探索路线
- **口碑 DNA 罗盘**：剧情 / 演技 / 情感 / 视听 / 节奏五维可视化
- **观众情绪宇宙**：基于真实评论的情绪温度 / 好评差评分析
- **探索档案**：收藏等级、徽章系统、观影足迹
- **离线降级**：LLM 不可用时自动降级为规则推荐，核心功能不受影响

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19 + TypeScript + Vite 8 + Tailwind CSS 4 |
| 3D 可视化 | Three.js + React Three Fiber + Drei + Postprocessing |
| 图表 | ECharts 6 |
| 状态管理 | Zustand 5 |
| 动画 | Framer Motion 13 |
| 后端 | Python FastAPI + SQLite |
| AI | OpenAI 兼容 API（SenseNova）+ 本地向量检索（bge-small-zh） |
| 数据 | 590 部核心 + 11.7 万条评论 + 23 万部检索库 |

## 项目结构

```
movie/
├── cine/                    # 后端 + 前端
│   ├── main.py              # FastAPI 入口（API + 静态托管）
│   ├── data.py              # 数据加载层
│   ├── chat.py              # 聊天意图 + 离线降级
│   ├── llm.py               # LLM 封装（模型链，失败降级）
│   ├── recommend.py         # DNA / 相似片规则推荐
│   ├── search.py            # FTS 检索 + 标题解析
│   ├── embed.py             # 向量语义检索
│   ├── personality.py       # 电影人格测试
│   ├── web/                 # React 前端源码
│   │   ├── src/             # 页面 + 组件 + 3D 场景
│   │   ├── package.json
│   │   └── vite.config.ts
│   └── data/                # 运行时数据（cine.db / lookup.db）
├── data/                    # 静态数据
│   ├── enriched/            # 核心数据（JSON / DB / 向量）
│   │   ├── movies_core.json # 590 部核心电影
│   │   ├── similarity.json  # 相似片关系
│   │   ├── sentiment.json   # 情绪分析
│   │   └── posters_thumb/   # 缩略图海报
│   ├── posters/             # 全尺寸海报
│   └── *.csv                # 原始数据（爬虫产物）
└── requirements.txt         # Python 依赖
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/<your-username>/cine.git
cd cine
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 构建前端

```bash
cd cine/web
npm install
npm run build
cd ../..
```

### 4. 配置 LLM（可选）

创建环境变量或本地密钥文件：

```bash
# 方式一：环境变量（推荐）
export CINE_LLM_API_KEY="your-api-key"

# 方式二：本地密钥文件（不入库）
echo "your-api-key" > data/task/llm_key.local.txt
```

> 无密钥时自动降级为离线规则推荐模式，核心功能不受影响。

### 5. 启动服务

```bash
# 方式一：直接启动
python -m uvicorn cine.main:app --port 8010

# 方式二：使用启动脚本（Windows）
start_server.bat
```

打开浏览器访问 **http://127.0.0.1:8010**

> 首次启动会自动从 `data/movies_info_clean.csv` 构建库外电影索引（`cine/data/lookup.db`，约 10s），之后秒载。

## 环境变量

| 变量名 | 说明 | 必需 |
|---|---|---|
| `CINE_LLM_API_KEY` | LLM API Key（SenseNova / OpenAI 兼容） | 否（无则降级离线模式） |

### LLM 配置文件

`data/task/llm_config.json`（不入库，需自行创建）：

```json
{
  "provider": "deepseek",
  "base_url": "https://your-api-endpoint/v1",
  "models": {
    "main": "your-model-name",
    "chat": "your-model-name"
  }
}
```

## 开发命令

```bash
# 前端开发（热更新，代理 API 到后端 8010）
cd cine/web
npm run dev         # http://localhost:5173

# 后端开发
python -m uvicorn cine.main:app --port 8010 --reload

# 代码检查
cd cine/web
npm run lint        # oxlint
```

## 生产构建

```bash
cd cine/web
npm run build       # TypeScript 编译 + Vite 打包到 dist/
```

构建产物位于 `cine/web/dist/`，由 FastAPI 自动托管为静态文件。

## 数据说明

### 已包含在仓库中

| 文件 | 大小 | 说明 |
|---|---|---|
| `data/enriched/movies_core.json` | ~2.8 MB | 590 部核心电影完整数据 |
| `data/enriched/similarity.json` | ~60 KB | 相似片关系 |
| `data/enriched/sentiment.json` | ~0.9 MB | 情绪分析数据 |
| `data/enriched/posters_thumb/` | ~17 MB | 590 张缩略图海报 |

### 需要单独获取（大数据文件）

| 文件 | 大小 | 说明 |
|---|---|---|
| `data/movies_info_clean.csv` | ~183 MB | 23 万部电影信息（构建库外索引） |
| `data/movie_comments.csv` | ~29 MB | 11.7 万条真实评论 |
| `data/enriched/comments_fts.db` | ~81 MB | 评论全文检索数据库 |
| `data/enriched/movie_vectors.npz` | ~1.2 MB | 语义向量数据 |
| `data/posters/` | ~100 MB | 590 张全尺寸海报 |

> 缺少大数据文件时，平台仍可运行——仅展示 590 部核心电影，库外检索、评论详情等功能降级。

## Vercel 部署说明

### 当前状态

本项目为 **前后端一体** 架构（FastAPI 后端 + React 前端），**不支持直接部署到 Vercel**。原因：

1. Vercel 主要支持 Serverless Functions / 静态站点，不适合运行长驻 Python 进程
2. 后端依赖本地 SQLite 数据库和大量数据文件
3. 海报等静态资源通过 FastAPI 的 `StaticFiles` 挂载

### 推荐部署方式

```bash
# 任意支持 Python 的平台（如 Railway / Render / 自有服务器）
pip install -r requirements.txt
cd cine/web && npm install && npm run build && cd ../..
python -m uvicorn cine.main:app --host 0.0.0.0 --port $PORT
```

### 如需部署到 Vercel

需要将项目拆分为：
1. **前端**：纯静态 SPA，部署到 Vercel（需修改 API 地址指向独立后端）
2. **后端**：部署到 Railway / Render 等支持 Python 的平台

## 页面路由

| 路由 | 说明 |
|---|---|
| `#/` | 首页：电影银河、心情快捷入口、口碑九强 |
| `#/list` | 全部电影：地区 / 类型 / 排序筛选 |
| `#/movie/:id` | 电影详情：海报、DNA 罗盘、口碑解读、评论、相似片 |
| `#/chat` | 问影灵：AI 推荐选片 / 陪看讨论 |
| `#/explore` | 探索档案：等级、徽章、收藏 |
| `#/personality` | 电影人格测试 |
| `#/login` | 登录 / 注册 |
| `#/account` | 个人中心 |
| `#/about` | 关于 |

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/movies` | 电影列表（支持筛选/排序/分页） |
| GET | `/api/movies/{id}` | 电影详情 |
| GET | `/api/galaxy` | 银河星球数据 |
| GET | `/api/search?q=` | 标题 + 短评全文检索 |
| POST | `/api/chat` | AI 聊天（推荐 / 陪看） |
| GET | `/api/personality/questions` | 人格测试题目 |
| POST | `/api/personality/test` | 提交人格测试 |
| GET | `/api/watch/opening` | AI 陪看开场 |
| POST | `/api/auth/*` | 认证（游客 / 短信 / 注册 / 登录） |

## License

MIT
