# D · 数据资产与管线审查

| 项 | 内容 |
|---|---|
| 审查日期 | 2026-08-21 |
| 仓库 | `I:\movie-yingling` |
| 项目 | 影灵 CINE |
| Agent ID | `68ecd1d5-88f7-4634-876c-9e79cb331748` |
| 方式 | 只读多角度 Sub Agent 审查 |

> 本文由并行 Sub Agent 审查产出，未改动业务代码。

---
## 摘要

当前工作区里，**590 核心库的三份 JSON（core / similarity / sentiment）主键对齐完好、DNA/相似片/情绪覆盖近满分**；但 **海报目录、向量 `movie_vectors.npz`、评论 FTS DB、原始 CSV 全部缺失**（且多被 `.gitignore`）。语义推荐会静默降级为规则推荐；海报挂载目录不存在时，**后端启动即可能失败**。`tags` 全空；`brief/warn/egg` 已有数据，与 `cine/README.md`「D3 全空」表述不一致。评论原文 CSV 不在仓，无法复核绑定，只能从 quotes/sentiment 抽样。

---

## 数据资产清单与规模（实测数字）

| 资产 | 状态 | 规模 |
|---|---|---|
| `data/enriched/movies_core.json` | 存在 | **590** 部，~2.9 MB，`build_version=core-2026-08-20` |
| `data/enriched/similarity.json` | 存在 | **590** 键，每片 **8** 条相似，共 4720 边，**0 悬空 id** |
| `data/enriched/sentiment.json` | 存在 | **590** 键，与 core 一一对应 |
| `data/enriched/movie_vectors.npz` | **缺失** | README 称 ~1.2 MB；代码期望 `ids`+`vectors` |
| `data/enriched/comments_fts.db` | **缺失** | README 称 ~81 MB |
| `data/enriched/posters_thumb/` | **缺失** | 路径写在 JSON：`posters_thumb/{id}.webp` |
| `data/posters/` | **缺失** | 路径写在 JSON：`posters/{id}.jpg` |
| `data/movies.csv` / `movie_comments.csv` / `movie_reviews.csv` / `movies_info_clean.csv` | **缺失** | 被 gitignore；管线与 QC 依赖它们 |
| `cine/data/lookup.db` | **缺失** | 目录亦不存在 → 库外 4410 星球不可用 |
| `data/task/*.csv` | 存在 | movie/comment/review 各 **590**（status 全 done）；explore_list **481** |

任务表备注：comment 任务有 **4** 条带 error 但仍标 done（fallback/抽样不足：姊姊妹妹站起来仅 5 条等）。

---

## 覆盖率表（字段 × 完整度）

基于 `movies_core.json` + `sentiment.json` 实测（n=590）：

| 字段 | 完整度 | 说明 |
|---|---|---|
| movie_id / title / year / genres / region / rating / rating_count | **100%** | year 1921–2026；rating 8.0–9.7 |
| countries / director / runtime / summary / first_lang | **100%** | |
| writer / actors | **99.8%** | 各缺 1：`3037329` / `35603727` |
| DNA 五维（剧情/演技/情感/视听/节奏） | **100%** | 值域约 6.2–9.2，均值 ~8.0–8.3 |
| brief | **98.5%**（581） | 9 部为 null（含美丽人生、沉默的羔羊等） |
| warn.text | **85.1%**（502） | |
| egg.text | **63.6%**（375） | |
| tags.mood / tags.scene | **0%** | 结构在，数组全空 |
| quotes.up1 | **100%** | dn1 **589/590**（姊姊妹妹站起来无差评） |
| stats.comments/reviews | **100%** 有值 | comments 中位 **150**（分层抽样上限） |
| similarity（独立 JSON） | **100%** 且与 `similar_top` 一致 | 无自环、无重复、无孤儿 |
| sentiment：n/temp/avg_star/freq/ai_summary | **100%** | emotions **96.4%**（21 部空，有 freq 兜底） |
| poster 路径字段 | **100% 有相对路径** | 磁盘文件 **0/590** |
| movie 级 citation 字段 | **0** | 聊天 citation 来自 quotes/FTS，非 core 字段 |

地区分布：欧美 360 / 华语 152 / 日本 57 / 韩国 21。source_channel：normal 586 + fallback 4。

---

## Critical / High / Medium / Low

### Critical

1. **海报静态目录缺失 → 启动风险**  
   - 位置：`cine/main.py` 挂载 `data/posters`、`data/enriched/posters_thumb`；JSON 全员指向相对路径。  
   - 证据：两目录 `exists=False`；590 张文件 hit=0。Starlette `StaticFiles` 对不存在目录通常直接报错。  
   - 影响：演示环境可能无法起服务；即使强行绕过，详情/列表/银河贴图全空白。  
   - 修复：恢复 `posters/` + `posters_thumb/`（或赛前改为可选挂载 + 占位图）。

2. **`movie_vectors.npz` 不存在**  
   - 位置：`cine/embed.py`；消费于 `cine/chat.py` 推荐第二层（规则不足时 `embed.retrieve`）。  
   - 证据：全仓 `**/*.npz` = 0；embed 打 warning 后 `available()=False`，返回 `[]`。  
   - 影响：模糊语义问句（「想哭但不压抑」等）无法语义召回，只能靠 DNA/类型规则；人格/路线推荐仍可用规则层。  
   - 修复：在有依赖的机器上跑 `python -m cine.build_vectors`（需模型下载）；产物勿丢。

### High

3. **评论管线产物缺失（CSV + FTS）**  
   - 位置：`data.py` 读 `movie_comments.csv` → `top_comments`；`comments_fts.db` → 搜索/陪看引用。  
   - 证据：二者皆无；详情页会降级到 core 内 `quotes` 各 1 条。  
   - 影响：详情「真实短评」变薄；`/api/search` 短评检索、聊天 FTS citation 失效。  
   - 修复：恢复大数据文件或明确演示范围「仅 quotes」。

4. **文档与代码事实冲突（易误判交付）**  
   - `cine/README.md`：「tags/brief/warn/egg/citation 当前 590 全空」——**错误**（brief 581、warn 502、egg 375；仅 tags/citation 空）。  
   - 根 `README.md`：把 `posters_thumb/` 写成「已包含」，实际 gitignore + 工作区缺失；`movie_vectors`/`comments_fts` 标为「可缺仍可运行」，但海报挂载更硬。  
   - 修复：改文档口径；演示清单与 `.gitignore` 对齐。

5. **原始爬取 CSV 不在仓 → 管线不可复现**  
   - `build_core_db.py` / `build_sentiment.py` / `qc_d1d2.py` / `scan_quality.py` 均依赖 `movies.csv` 等。  
   - 影响：无法从零重跑 DNA/相似/情绪/QC；只能消费已固化 JSON。  
   - 修复：赛后归档加密离线包；赛前接受「只读 JSON 交付」。

### Medium

6. **`tags` 全空 + 推荐解释依赖标签**  
   - `recommend.explain_card` 用 mood/scene 做关键词回响；`Detail.tsx` 有条件渲染故不崩，但能力空洞。  
   - 注释已写「P1 无 tags，用 DNA+类型近似」——产品降级已知，但赛报里仍有人标 P0，需统一口径。

7. **quotes 剧透风险**  
   - 启发式命中约 **150** 条（含结局/爆头等）；例：无间道 up1 写电梯爆头。  
   - 陪看有剧透开关，但详情页 quotes **无遮罩**。  
   - 修复：详情默认折叠差评/高风险句；或关键词过滤后入 quotes。

8. **egg 质量不稳**  
   - ~27 条可疑（过短、像影评残句：「就知道远在美利坚…」「也不例外…」）。  
   - 影响：冷知识可信度；易被评委当成幻觉/错绑。  
   - 修复：规则清扫长度/主语残缺；或赛前隐藏低分 egg。

9. **sentiment 口径易误解**  
   - `n` 大量封顶 150（分层抽样）；`avg_star` 被压到 ~3.x，与豆瓣 8–9 并存，前端若展示易误导。  
   - `build_sentiment.py` 已说明；UI 需避免把 avg_star 当「全站均分」。

10. **fallback 片评论稀疏**  
    - `2208890` 仅 5 条评论、无 dn1、emotions 弱；DNA/情绪置信低。  
    - 影响：个别卡片体验差，非整库崩溃。

### Low

11. **explore_list 与 core 不完全重合**（481 中 4 不在 core）——探索清单与正式库略脱节。  
12. **跨片名出现在评论**（如背靠背提到霸王别姬）——多为正常影史对比，非错绑证据。  
13. **库外 lookup CSV 缺失**——银河停在 590，无 5000 扩展（文档已预期降级）。

---

## 管线缺口与 QC 建议

**文档化程度（好）**  
`build_core_db.py` 头注释按 stage 列出 load→dna→quotes→similar→fts→thumbs→build；`build_sentiment.py`、`cine/build_vectors.py`、方案 `reports/电影数据库构建方案_v1.md` 形成可跟读链路。

**可重跑性（差，当前工作区）**  
缺 CSV/海报 → `python build_core_db.py --stage all`、`build_sentiment.py`、`qc_d1d2.py`、`scan_quality.py` **均无法在本仓跑通**。中间产物 `core_dna.json`/`core_quotes.json` 亦被 ignore。

**静默失败点**  
- `embed.py` / `data.py` sentiment：缺文件 → warning/空 dict，服务继续。  
- `chat` 推荐：向量空 → 静默退回规则。  
- **海报挂载**：不静默，偏硬失败。  
- 爬虫任务 status=`done` 但 error 非空（4 条）——「完成」语义含糊。

**QC 建议（只读可做、不必写报告文件）**  
1. 启动前检查：`posters`/`posters_thumb`/`movie_vectors.npz`/`comments_fts.db` 存在性断言。  
2. 固定脚本：core↔sim↔sent id 集合差、相似边孤儿、海报文件存在率。  
3. quotes 剧透词表 + egg 长度/残句规则。  
4. 任务 CSV：`status=done AND error!=''` 单独报表。  
5. 文档单测：README 覆盖率数字与实测脚本对齐。

---

## 1 天内可修补的数据项 vs 需搁置项

**1 天内可修（若有离线包/备份）**  
- 拷回 `posters/` + `posters_thumb/`（或改 main 可选挂载 + 本地占位）。  
- 跑通/拷入 `movie_vectors.npz`（~1.2 MB，收益大）。  
- 拷入 `movie_comments.csv` + `comments_fts.db`（若体积允许）。  
- 修正 `cine/README.md` D3 表述；根 README「已包含」列表。  
- 清空/隐藏可疑 egg（规则批量）；详情页 quotes 默认「可能剧透」折叠。  
- 给 9 部缺 brief 用 `summary[:80]` 回填（代码或一次性 JSON 补丁——需改文件时另开任务）。

**建议搁置**  
- 从零重爬 590×评论/重算 DNA（合规+时间）。  
- 补齐 `tags.mood/scene` 全量 LLM（成本高；规则推荐已兜底）。  
- 23 万库外 CSV / lookup.db（非核心演示路径）。  
- 彻底消解分层抽样导致的 avg_star 观感（需改产品文案，非一日数据工程）。

---

## 亮点

- **三表主键完美对齐**：590↔590↔590，相似片 **0 坏链**、每片固定 8 邻域，适合稳定演示「邻近星球」。  
- **DNA / 情绪 / quotes / ai_summary 覆盖极高**，详情「影灵解读 + 雷达」不依赖 LLM 在线。  
- **构建脚本阶段清晰**，sentiment 对抽样偏差有自觉说明；fallback 通道有显式 id 集合。  
- **前端对空 tags/warn/egg 用条件渲染**，未虚假画出空标签栏（与过时 README 相比，UI 更诚实）。  
- 向量缺失时有**明确降级路径**（规则推荐 + DNA 画像），不至于推荐全挂——但海报缺失是更硬的阻塞。

---

### 特别核实：`movie_vectors.npz`

| 项 | 结论 |
|---|---|
| 是否存在 | **否**（全项目 0 个 npz） |
| 对推荐影响 | 规则层（`recommend.recommend` / DNA 画像 / similarity）仍可用；**语义补召回关闭**；模糊自然语言需求命中率下降；聊天在规则命中 ≥2 时可几乎不察觉 |
| 重建 | `cine/build_vectors.py`，依赖已有 core+sentiment（不依赖缺失 CSV）+ `bge-small-zh-v1.5` |

### 许可与合规（点到为止）

评论/海报/元数据来自公开影评站点爬虫痕迹（任务 error 含 403/404）。参赛演示应：**注明数据来源与非商业研究/展示用途、不二次分发原始 CSV/海报包、控制公网暴露与爬取再现**；避免把用户 UGC 当平台原创金句宣传。
