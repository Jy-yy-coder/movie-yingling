# G · 综合审查裁决（P0/P1/P2）

| 项 | 内容 |
|---|---|
| 审查日期 | 2026-08-21 |
| 仓库 | `I:\movie-yingling` |
| 项目 | 影灵 CINE |
| Agent ID | `b3cb2451-c199-426e-bcda-1b4065f16be6` |
| 方式 | 只读多角度 Sub Agent 审查 |

> 本文由并行 Sub Agent 审查产出，未改动业务代码。

---
# 影灵 CINE 综合审查裁决

## 一句话总判

产品内核（590 卡对齐、DNA/相似、防幻觉推荐骨架）可答辩，但**当前仓库缺海报/`dist`/向量/FTS/`llm_config`，游客登录不写 token、登录不合并游客**——不修资产与鉴权闭环则演示起不来、叙事撑不住；AI/可视化落差用演示剧本规避，勿赛前大重构。

## 旧问题状态（已修 / 仍在 / 变异）

| 旧项（2026-08-21） | 状态 | 核实要点 |
|---|---|---|
| 注册双行 / 注册合并游客 | **已修** | `api_register` 迁聊天/收藏/人格/信号/会话并删游客行 |
| 详情 CSV 相关 | **按旧报告视为已修** | 本轮未再列为阻断；勿当 P0 |
| FTS 跨线程 | **变异→资产缺失** | `comments_fts.db` 现不在仓；线程问题次于「库没有」 |
| 会话越权 | **已修（主体）** | `_conversation_owned` 校验仍在；勿当 P0 |
| 登录合并游客 | **仍在** | `api_login` 无 `device_id`、无合并逻辑 |
| BootScene 16ms 音效轰炸 | **已修（报告口径）** | 蓄力仍 16ms tick，勿当 P0；勿再「修音效」大改 |
| 固定短信码 + `dev_code` | **仍在** | `246810` + 响应回传；演示期可留码，须控曝光 |
| 前端游客入口 | **仍在 / 更严重** | `Login.doGuest` 调 `guest()`，**不** `setToken`（`ensureGuest` 才会写） |

## P0（不修不能演）

| # | 问题 | 类型 | 来源 | 位置 | 预估 | 依赖 |
|---|---|---|---|---|---|---|
| P0-1 | `posters` / `posters_thumb` 缺失 → `StaticFiles` 挂载即 `RuntimeError`，服务起不来 | 演示阻断 | D,E,F | `cine/main.py` ~791–792；`data/posters`、`data/enriched/posters_thumb` | 0.5–2h（拷回） | 无 |
| P0-2 | `cine/web/dist` 缺失 +「有 index 才切 STATIC」的 fallback 名存实亡 | 演示阻断 | E,F | `cine/main.py` 24–28、793；`cine/web/` | 0.5–1h（`npm run build`） | 建议在 P0-1 后，避免只起 API 无 SPA |
| P0-3 | Login 游客入口未 `setToken` → 「以游客身份进入」后账号/收藏/人格全断 | 演示阻断 | B（A/F 交叉） | `Login.tsx` `doGuest`；`api.ts` `guest` vs `ensureGuest` | 15–30min | 无（可与资产并行） |
| P0-4 | 演示机无 `data/task/llm_config.json`（且无可用 key）→ 实质离线；仅设 `CINE_LLM_API_KEY` **不够**（`_cfg()` 读文件失败直接 `None`） | 演示阻断 | C,E,F | `cine/llm.py` `_cfg`；`data/task/` | 30–60min | 无 |
| P0-5 | `movie_vectors.npz` 缺失 → 语义检索空转，答辩「向量/语义」必翻 | 演示阻断 / 叙事 | C,D,F | `cine/embed.py`；`data/enriched/movie_vectors.npz` | 0.5–2h（拷回或预构建产物） | 无（可与海报并行） |
| P0-6 | 登录不合并游客 + chat/personality 主路径偏 `device_id` → 游客测人格再密码登录「人设蒸发」 | 演示阻断 | A,B,F | `api_login`；`_resolve_user_id`；人格 API | 2–4h | **先 P0-3**（先有稳定 token/游客行） |
| P0-7 | 评论口径不统一（答辩口误 150 万 vs 页内 ≈11.7 万） | 叙事增强（评委 P0） | F（About 已写 11.7 万） | 讲稿 / `About.tsx` | 15min | 无 |

**说明：** 固定验证码/`dev_code` **不升为 P0**（演示刚需）；对外投屏时关掉 Network 面板或口播「演示码」即可。`comments_fts.db` 缺失为 **强 P1**（搜评论/梗路径），缺则演示禁止点该能力。

## P1（强烈建议）

| # | 问题 | 类型 | 来源 | 位置 | 预估 | 依赖 |
|---|---|---|---|---|---|---|
| P1-1 | 无剧透开启时 `_movie_card` 仍注入完整 `summary` | 安全合规 / 体验 | C | `cine/chat.py` `_movie_card` / talk safe 分支 | 1–2h | 建议在 LLM 可用后验 |
| P1-2 | 标题 `resolve` 压过推荐意图（「类似《X》」误路由） | 体验瑕疵 | C | `chat.build_reply` 意图顺序 | 1–2h | 需若干金句回归用例 |
| P1-3 | history 带 `movie_ids` 等脏字段进 messages | 安全合规 | C | chat history 组装 | 1h | 可与 P1-1 同批 |
| P1-4 | 详情「情绪宇宙」数据在但可视化/话术弱；与 About 承诺落差 | 叙事 / 体验 | B,F | `Detail.tsx` sentiment 区 | 2–4h（最小展示） | 需 `sentiment.json`（已在仓） |
| P1-5 | Navigator 无打开入口（组件在、入口无） | 叙事 / 体验 | B,F | `Navigator.tsx` / `App` / store | 0.5–1h **或**删文档承诺 | 无 |
| P1-6 | `#/profile` `#/about` 缺导航入口 | 体验瑕疵 | B,F | 导航 / Account | 0.5h | 无 |
| P1-7 | Profile 收藏数误用 `discovered` | 体验瑕疵 | B | `Profile.tsx` | 10min | 无 |
| P1-8 | `comments_fts.db` 缺失 | 演示阻断（条件） | D,E | `data/enriched/` | 拷回 0.5h | 无 |
| P1-9 | chat L309 `_conn()` 未关闭 + 无 WAL | 技术债（可成稳定性） | A,E | `main.py` api_chat；`_conn` | 0.5–1h | 无 |
| P1-10 | 统一鉴权：token querystring、游客 token 可被同 `device_id` 覆盖、chat 只认 device | 安全合规 | A | auth / chat / personality | 3–6h | **赛前只做最小：演示路径只用注册合并，不深改双轨** |
| P1-11 | LLM 总超时/熔断（报告 90s）→ 演示假死 | 体验瑕疵 | C,E | `llm.py` | 1h | P0-4 |
| P1-12 | 银河颜色被地区色覆写 vs 「情绪着色」话术 | 叙事 | F | `PlanetLayer.tsx` REGION_COLORS | **改话术优先**；改着色 2h+ | 勿与布局大改并行 |
| P1-13 | tags 字段在但 `mood/scene` 实质空 | 叙事 | D,F | `movies_core.json` tags | 隐藏 UI 或改文案 0.5h | 勿现填 tags |

## P2（有空再做）

- echarts/`EChart` 闲置；≤860px 藏星图筛选；overlay 下 Canvas+Bloom 常驻  
- `CameraRig` 每帧 `new Vector3`；`buildLayout` 主线程重；suggest 无防抖；重复请求  
- galaxy 每次重算无缓存；`movies limit=100000` 内存过滤  
- 密码 sha256 无盐；`sms_codes` 无 UNIQUE（`INSERT OR REPLACE` 形同虚设）；CORS `*`；chat 无长度上限；unfav 无 token  
- quotes/egg 剧透与质量；sentiment `n` 封顶 150；文档 Quickstart/README 与仓不一致；gitignore 资产  
- 人格 localStorage 与服务端双源；Chat 剧透开关不写回（Account 会写）；WatchIntro `onDone`；错误吞掉  
- validate_rec_ids 宽松；LLM 全局锁可观测性差  

## 冲突与待核实

1. **tags「0%」vs 字段「全有」**  
   - D：tags 0%；本机核实：590 条均有 `tags` dict，但 `mood`/`scene` 多为 `[]` → **「结构有、内容空」**。  
   - **5 分钟核实：**  
     `python -c "import json;m=json.load(open('data/enriched/movies_core.json',encoding='utf-8'));print(sum(1 for x in m if (x.get('tags') or {}).get('mood') or (x.get('tags') or {}).get('scene')), '/', len(m))"`  

2. **README「D3 全空」vs brief/warn/egg 高填充**  
   - 本机：brief 空 1.5%、warn 14.9%、egg 36.4% → README 过时。  
   - **5 分钟：** 同上脚本对 `brief`/`warn`/`egg` 做 falsy 计数。  

3. **`spoiler` 布尔语义是否反了**  
   - UI：`spoiler===true` 显示「无剧透已开」；后端 talk 分支 `if spoiler: SAFE`。与 C「无剧透仍灌 summary」一致，但 citations 在 `spoiler=True` 时更少引用差评——命名易混。  
   - **5 分钟：** 开无剧透问「剧情讲什么」，抓 `/api/chat` body 的 `spoiler` 与 prompt 是否含「简介:」。  

4. **Agent A「sms 无 UNIQUE」vs `INSERT OR REPLACE`**  
   - schema `sms_codes(phone TEXT, ...)` 无 UNIQUE → OR REPLACE **不会**替换。  
   - **5 分钟：** 连续两次 `/api/auth/sms` 同号，查库行数是否 >1。  

5. **评论「150 万」从何而来**  
   - About 已写 ≈11.7 万；若讲稿/README 仍写 150 万则冲突在文档非代码。  
   - **5 分钟：** `rg -n "150|万条|117" reports About.tsx README*`  

6. **BootScene「已修」是否彻底**  
   - 仍有 16ms 蓄力 timer；若现网无连环音效可结案。  
   - **5 分钟：** 冷启动按住蓄力，听是否每 tick 响。  

## 48小时修复序列（按小时排序）

**前提：先拿到资产包路径（海报、thumb、npz、FTS、llm_config、可选 dist）。无资产则只做代码项，演示仍可能挂。**

| 时段 | 动作 | 完成标准 |
|---|---|---|
| **H0–1** | 拷回 `posters` + `posters_thumb`；确认挂载目录存在 | `python -c "from cine.main import app"` 不因 StaticFiles 崩 |
| **H1–2** | `npm run build` 产出 `cine/web/dist`；拷/生成 `llm_config` + key；确认 env 不是唯一依赖 | 浏览器能打开 SPA；chat 非强制 offline |
| **H2–3** | 拷 `movie_vectors.npz` + `comments_fts.db`（有则拷） | embed 无「npz 不存在」；搜评论路径可点或明确禁用 |
| **H3–4** | **P0-3** Login 游客：`doGuest` 改为 `ensureGuest`/`setToken` | 游客进入后 Account 有 token、收藏可写 |
| **H4–7** | **P0-6 最小登录合并**：login 收 `device_id`，复用 register 合并块（或抽 `_merge_guest`） | 游客收藏→密码登录仍在；同 device 无双游客抢写 |
| **H7–8** | 评委口径：讲稿/About 统一 **11.7 万**；列「演示禁点」卡 | 全员背同一数字 |
| **H8–10** | **P1-1+P1-3**：无剧透剥 summary；history 消毒；总超时压到 ~12s | 无剧透问答 prompt 无完整剧情；慢请求可降级 |
| **H10–12** | **P1-2** 意图门控：「类似/像/同款」优先推荐 | 3 条金句不误进单片问答 |
| **H12–14** | **P1-9** 关 L309 泄漏 + `PRAGMA journal_mode=WAL` | 连点 chat 无连接堆积 |
| **H14–18** | **P1-4 最小情绪宇宙**（温度+关键词列表即可，不上 EChart） | 详情可指着讲「真实评论情绪」 |
| **H18–20** | Navigator：**加一个入口** 或 **文档/About 删承诺**；profile/about 链到 Account | 评委找不到入口不扣「吹牛」 |
| **H20–22** | Profile 收藏数改 `favorites.length`；藏空 tags UI；银河颜色改口播「地区星团」 | 无自打脸文案 |
| **H22–24** | 走通 **写死演示路径** 全流程 2 遍；断网 Plan B（离线文案） | 计时 <8min；AI 挂也能讲数据 |

**第 2 个 24h：** 只做回归与讲稿，不进新功能；剩余进 P2 的一律冻结。

## 明确不要动（赛前）

- 鉴权双轨「大一统重构」、CORS/密码加盐/sms 表迁移等安全大改  
- 银河着色算法重做、Canvas/Bloom 架构、`buildLayout` 性能大修、主线程布局重写  
- 填 tags / 重跑 D3 / 重训向量 / 扩库到 5k 演示  
- 引入 EChart 情绪大屏、重做 Navigator 产品形态  
- 动 BootScene 时间轴/音效「再优化」  
- 改推荐防幻觉主路径的核心约束（除非只剥 summary）  
- 为「登录合并」重写用户表模型；只允许复用 register 已验证合并逻辑  
- 无必要的依赖升级、目录三套 static 大清理  

## 已确认亮点（答辩保留）

- **590 三 JSON 对齐完好**；DNA / 相似近满分级可用  
- **brief / warn / egg 高填充**（勿说「D3 全空」）  
- **推荐路径防幻觉中上**：程序喂卡片 + 引用可溯源叙事成立  
- **注册路径游客合并已修**（可讲「注册后记忆延续」；勿夸「登录也合并」除非 P0-6 完成）  
- **会话归属校验已有**；负载侧 galaxy/movies API 本身很快（非当前瓶颈）  
- About 已具备较诚实的评论规模表述（11.7 万）——与讲稿对齐即加分  

## 演示剧本约束（禁止点哪些 / 必须备什么）

**必须备齐**

- 海报原图 + thumb、`web/dist`、`llm_config`+可用 key、`movie_vectors.npz`  
- 尽量备 `comments_fts.db`；否则台词写明「本场不演示评论检索」  
- 预热：1 个已注册账号 +（若已修合并）1 条游客收藏/人格；2–3 部金片详情已打开过  
- 断网/Key 挂：离线模板话术 30 秒版  

**必须走的路径（写死）**

1. 银河 → 点高分核心片 → 详情（评分/DNA/简报）  
2. 聊天：「推荐一部…」（避免「类似《X》」直到 P1-2 修好）  
3. 若合并已修：游客收藏 → **注册**合并（不要用「登录」演示合并，除非 P0-6 完成）  
4. 情绪：只讲详情里已有温度/关键词（P1-4 后），不承诺动效宇宙  

**禁止点 / 禁止说**

- Navigator（无入口修好前）、窄屏依赖星图筛选、闲置 EChart  
- 「无剧透绝对不泄剧情」（summary 未剥前）、「语义向量检索」（npz 未备齐前）  
- 「tags 情绪标签体系」、评论「150 万」、登录自动合并（未修前）  
- 人格测完 → 密码登录「看云端人设」（未修 P0-6 前）  
- 库外片深聊、egg 彩蛋逐条展示、搜冷门梗（无 FTS 时）  
- 投屏打开返回 `dev_code` 的 Network 面板  

---

**执行原则：** 资产与游客 token（P0-1～5、P0-3）→ 登录合并最小补丁（P0-6）→ 口径与禁点（P0-7）→ AI 无剧透/意图/超时 → 详情情绪最小可见 → 入口/文案去吹牛。其余一律冻结。
