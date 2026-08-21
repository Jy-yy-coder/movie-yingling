# 影灵 CINE · 平台（Phase-P P1）

电影 AI 助手网站。数据全部来自项目内 `data/`（590 部高分片 + 11.7 万条真实评论 + 23 万部检索库）。

## 启动

```bash
python -m uvicorn cine.main:app --port 8010
```

打开 http://127.0.0.1:8010

- 首次启动会自动从 `data/movies_info_clean.csv` 构建库外电影索引（`cine/data/lookup.db`，约 10s），之后秒载。
- LLM 配置在 `data/task/llm_config.json`。聊天用 `models.chat`（默认 deepseek-v4-flash），全部模型不可用或断网时自动降级为规则推荐并标注「离线模式」。

## 页面

| 路由 | 说明 |
|---|---|
| `#/` | 首页：真实数字、此刻心情快捷入口、口碑九强、分区推荐 |
| `#/list?region=&genre=&sort=&q=` | 全部电影：地区/类型/排序筛选 + DNA 五维排序 |
| `#/movie/:id` | 详情：海报、DNA 口碑罗盘、影灵口碑解读、好评/差评顶流摘录（无剧透默认收起）、相似片 |
| `#/chat` | 问影灵：推荐选片 / 陪看讨论双模式、无剧透开关、推荐卡片（匹配环+迷你雷达+高赞引用） |
| `#/login` | 验证码 / 密码 / 游客 三入口 |
| `#/account` | 游客自动账号，注册时合并收藏与聊天记录 |

## API（概览）

- `GET /api/movies` 列表（region/genre/year/dim/sort/page，sort 支持五维名按维度降序）
- `GET /api/movies/{id}` 详情（含相似片）
- `GET /api/search?q=` 标题 + 短评 FTS
- `GET /api/suggest?q=` 联想
- `GET /api/movie-lookup?title=` 库外电影查询
- `POST /api/chat` `{message, device_id, mode?: rec|talk, spoiler?: bool}` → `{text, offline, citations[], movies?, movie?}`
- `POST /api/auth/guest|sms|register|login`、`GET /api/account`、`POST/DELETE /api/favorites`

## 目录

- `cine/main.py` FastAPI 入口
- `cine/data.py` 数据加载 + lookup 索引
- `cine/search.py` FTS 检索 + 标题解析
- `cine/recommend.py` DNA/相似片规则推荐
- `cine/chat.py` 聊天意图 + 离线降级
- `cine/llm.py` LLM 封装（模型链，失败降级）
- `cine/static/` 无构建 SPA（HTML/CSS/原生 JS，hash 路由）

## 已知边界（P1）

- tags / brief / warn / egg / 金句(citation) 为 D3 LLM 字段，当前 590 部全空，前端按渐进增强隐藏；D3 数据到位后自动显示。
- 聊天联网需 LLM key 可用；`sensenova-6.7-flash-lite` 为推理型模型、聊天不可用（content 恒为空），勿设为 `models.chat`。
- `data/task/llm_config.json` 含明文 key，演示后建议轮换、入库前确保不被提交。
