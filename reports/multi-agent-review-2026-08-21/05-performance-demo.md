# E · 性能、部署与演示稳定性审查

| 项 | 内容 |
|---|---|
| 审查日期 | 2026-08-21 |
| 仓库 | `I:\movie-yingling` |
| 项目 | 影灵 CINE |
| Agent ID | `0c1b7d45-1404-4117-bb83-62a5a07f54cb` |
| 方式 | 只读多角度 Sub Agent 审查 |

> 本文由并行 Sub Agent 审查产出，未改动业务代码。

---
## 摘要

当前工作区**无法启动**：`import cine.main` 在挂载 `StaticFiles` 时即因 `data/enriched/posters_thumb` 缺失抛 `RuntimeError`（实测）。即便补上海报，`cine/web/dist` 亦缺失且**无**落到 `static` / `static_legacy` 的代码路径；注释中的 fallback 名存实亡。

数据层仅剩 `movies_core.json` / `similarity` / `sentiment`；`movie_comments.csv`、`comments_fts.db`、`movie_vectors.npz`、`movies_info_clean.csv`、`lookup.db`、LLM 配置与 key 均缺失（多被 `.gitignore`）。在此残缺集上：`data.load()` ≈ **48 ms**；`/api/galaxy` 逻辑（仅 590）≈ **2.8 ms**；模拟 5000 星球 ≈ **18 ms**、JSON ≈ **1.0 MB**。服务未在 8010 监听，热路径 HTTP 延迟无法 curl。

旧结论核实：**短评已内存化** ✓；**galaxy 每次重算、无缓存** ✓；**SQLite 无 WAL** ✓；**chat 连接泄漏（L309）** ✓；**Boot 音效用 `useCallback` 已修** ✓。新发现：`llm_config.json` 缺失时**环境变量 key 被完全忽略**；海报目录缺失比 dist 更早致命；React 侧 `suggest` API 未使用、无防抖搜索；overlay 下 **Canvas 常驻**。

---

## 启动与失败模式

| 阶段 | 行为 | 失败模式 | 实测/证据 |
|------|------|----------|-----------|
| 模块导入 | `app.mount("/posters_thumb")` → `/posters` → `/`（`web/dist`） | 目录不存在 → **进程起不来** | `RuntimeError: Directory '...posters_thumb' does not exist` |
| 静态 SPA | `STATIC_DIR` 恒为 `web/dist`；`if index.exists` 只赋值同路径 | dist 缺失同样崩；`static`/`static_legacy` **从未被选中** | `main.py` L24–28、L793；`web/dist` = MISSING；两套 static 各约 0.06 MB |
| `startup` | `data.load()` + `_init_db()` | JSON 缺则未捕获会崩；lookup 无 CSV/无 db → 空库外；短评 CSV 无 → 空评论；sentiment 失败吞掉 | 当前 `load` ≈ **48.4 ms**，core=590，ext=0 |
| 向量 | `embed` 懒加载 + 锁 | npz/模型失败 → warning，降级关键词 | 当前 `embed.available()` ≈ **0.7 ms**，`False` |
| LLM | `_cfg()` 读 `llm_config.json` 再拼 key | **配置文件不存在 → `cfg=None`，`CINE_LLM_API_KEY` 无效** | 设 env key 后 `_cfg()`=`None`，`chat_reply`→`(None,None)` |
| `start_server.bat` | 读 `llm_key.local.txt`，`uvicorn --port 8010` | 无 key 文件可静默离线；但缺 config 时连 env 也救不了 | bat L6–10 |

冷启动在**完整数据机**上的额外成本（代码注释/结构，本机无大文件未复测）：首次建 `lookup.db` 约 10–15s；`movie_comments.csv` 全量进内存；`bge-small-zh` 首次下载/加载可能数十秒～分钟，失败仅日志、推荐仍可用规则。

---

## 热路径耗时表（能测则测）

服务未启动，下列为**进程内**等价逻辑；HTTP 端到端未测。

| 路径/操作 | 复杂度 | 本机实测 | 完整 5k 估测 | 缓存 |
|-----------|--------|----------|--------------|------|
| `data.load()` | 读 JSON + 可选 CSV/SQLite | **48.4 ms** | + 短评 CSV + lookup | 进程级全局 |
| `GET /api/galaxy` → `galaxy_rows()` | O(核心+库外)，无缓存 | n=590：**avg 2.82 ms**；JSON **130 KB** | n=5000：**avg 18.3 ms**；JSON **~1029 KB** | **无** |
| `GET /api/movies`（无 q） | `recommend(limit=1e5)` + 过滤排序 + 分页 | **1.1 ms**（590） | 仍 O(590) | **无** |
| `GET /api/movies?q=` | 全库线性标题/类型/演职员匹配 | 同量级 | 同 | **无** |
| `GET /api/movies/{id}` | 字典 O(1) + similar + sentiment + `top_comments` 内存排序 | `top_comments` **0.0 ms**（无评论数据） | 有评论时仍内存，轻 | 电影在内存；评论索引启动预载 |
| `GET /api/search` / suggest | 标题扫库；FTS 需 db | titles **1.06 ms**；suggest **0.94 ms**；fts **0.08 ms**（db 无） | FTS 通常 ms 级 | FTS 连接线程本地 |
| `POST /api/chat` | 多段 SQLite + 规则/向量 + LLM（timeout 90s，全局 1s 节流） | 无服务/无 LLM | 弱网/无 key → 离线文案；双人会被 `_lock` 串行化 | 会话在 SQLite |
| 前端 `buildLayout(5000)` | 最多 60 轮网格松弛 | Python 近似 **~2.7 s** | JS 更快但仍可能卡首屏数百 ms～秒 | 仅同引用跳过 |

curl：`127.0.0.1:8010` / `8000` → 连接失败（http=000）。

---

## Critical / High / Medium（路径+证据+影响+修复）

### Critical

1. **海报目录缺失 → 导入即崩**  
   - 路径：`cine/main.py` L791–793  
   - 证据：实测 `RuntimeError`；本机 `posters_thumb`/`posters` MISSING  
   - 影响：`start_server.bat` 无法演示  
   - 修复：赛前恢复目录；或挂载前 `mkdir` / 条件 mount；缺海报时勿硬依赖存在性  

2. **`web/dist` 缺失 + fallback 名存实亡**  
   - 路径：`main.py` L24–28、L793；`static`/`static_legacy` 有旧 SPA  
   - 证据：`dist` MISSING；`STATIC_DIR` 永不指向 `static`；`.gitignore` 忽略 `dist/`  
   - 影响：补海报后仍可能在挂载 `/` 崩溃；克隆仓库默认无前端产物  
   - 修复：`npm run build` 纳入发布清单；真正 fallback：`dist` → `static` → `static_legacy`  

3. **无 `llm_config.json` 时环境变量/本地 key 全部失效**  
   - 路径：`cine/llm.py` `_cfg()`  
   - 证据：`CINE_LLM_API_KEY=test...` 时 `cfg is None`，`chat_reply` 直接 `(None,None)`  
   - 影响：演示「AI 挂了」实为配置结构问题，与额度无关；bat 读 key 也救不了  
   - 修复：配置缺失时仍组装 keys + 默认 `base_url`；或提交脱敏 `llm_config.example.json` 并复制为本地 config  

### High

4. **`/api/chat` SQLite 连接泄漏**  
   - 路径：`main.py` L309：`_conn().execute(...).fetchone()` 未 `close`  
   - 影响：多轮对话/双人并发泄漏句柄，Windows 上易拖垮演示  
   - 修复：赋值后显式 close，或 `with`/`contextmanager`  

5. **SQLite 默认 journal、无 WAL，chat 单请求多次 open/write**  
   - 路径：`_conn()`；chat 约 8–10 次 connect/commit  
   - 证据：临时库 `journal_mode=delete`；无 `PRAGMA journal_mode=WAL`  
   - 影响：两人同时收藏/聊天易 `database is locked`  
   - 修复：WAL + `busy_timeout`；合并事务；连接池或请求级单连接  

6. **`/api/galaxy` 无缓存 + 首包 ~1MB（5k）**  
   - 路径：`data.galaxy_rows()`；`App.tsx` 首屏必拉  
   - 证据：5000 次调用均 ~18 ms；JSON ~1 MB；无 ETag/Cache-Control  
   - 影响：弱网首屏慢；重复进页重复算（前端有 store，刷新仍重拉）  
   - 修复：启动算一次缓存；`Cache-Control`/`ETag`；可考虑 gzip  

7. **演示数据资产被 gitignore，工作区现状残缺**  
   - 证据：csv/db/npz/海报/dist/llm_config 均 ignore；本机大量 MISSING  
   - 影响：换机/交卷环境「能跑」依赖未文档化的 U 盘/网盘包  
   - 修复：赛前检查清单 + 打包脚本校验必需文件  

### Medium

8. **Canvas 在 overlay 下常驻**  
   - 路径：`App.tsx` 始终渲染 `<GalaxyScene />`；Bloom + dpr≤2 + ~5000 Points + 星空  
   - 影响：详情/聊天时仍烧 GPU；弱显卡风扇噪、掉帧  
   - 修复：overlay 时降 `dpr`/关 Bloom/暂停 `useFrame`，或 `frameloop="demand"`  

9. **首屏主线程 `buildLayout` 重**  
   - 路径：`layout.ts` ITER=60；`App` 在 `galaxy()` 后同步调用  
   - 证据：5k Python 近似松弛 ~2.7 s  
   - 影响：星图「卡住再出现」  
   - 修复：`requestIdleCallback`/Worker；预计算坐标随 API 下发  

10. **详情/探索重复请求**  
    - `Detail`：`movie` + `explorer`（全收藏列表）+ `feedback`  
    - `Explore` Home：两次 `movies()`  
    - 影响：弱网瀑布；explorer 过重只为判断是否收藏  
    - 修复：收藏态轻量 API；合并 rail/recs  

11. **新前端无搜索联想/防抖**  
    - `api.suggest` 导出但 `web/src` **零引用**；Explore 仅 Enter 跳转  
    - 旧 `static/js/app.js` 有 220ms debounce（但当前不托管）  
    - 影响：演示搜索体验依赖列表全量 `/api/movies?q=`  

12. **可观测性不足**  
    - 无 `basicConfig`；无请求耗时中间件；startup 不打印「FTS/向量/LLM/海报是否就绪」  
    - chat 有 `offline`/`model`（前端可用），但服务端难一眼区分「数据挂了 vs AI 挂了」  
    - 修复：startup 健康摘要；`X-Cine-Mode: offline|llm`；结构化 log  

13. **全局 LLM 节流锁**  
    - `llm._throttle` + `_lock`，`MIN_INTERVAL=1.0`  
    - 影响：两人同时问 AI 排队；再叠加 90s timeout，体感「卡死」  

---

## 赛前「演示环境检查清单」（可勾选）

- [ ] `data/enriched/posters_thumb/`、`data/posters/` 存在且非空  
- [ ] `cine/web` 执行 `npm run build`，确认 `cine/web/dist/index.html`  
- [ ] `data/enriched/movies_core.json`、`similarity.json`、`sentiment.json`  
- [ ] （推荐）`data/movie_comments.csv` 或可接受「详情无短评」  
- [ ] （推荐）`data/enriched/comments_fts.db`（台词/梗搜索）  
- [ ] （推荐）`data/enriched/movie_vectors.npz` + 已缓存的 bge 模型（语义推荐）  
- [ ] （推荐）`cine/data/lookup.db` 或 `movies_info_clean.csv`（5000 星球）  
- [ ] `data/task/llm_config.json`（含 `base_url`）+ `llm_key.local.txt` 或有效 env  
- [ ] 用 `python -c "from cine import main"` **无 RuntimeError**  
- [ ] `start_server.bat` → 浏览器 `http://127.0.0.1:8010` 出宇宙 SPA（非空白/非旧 static）  
- [ ] `GET /api/galaxy` 返回 `total` 符合预期（590 或 ~5000）  
- [ ] 无 key / 断网：聊天仍有离线推荐文案，且 UI 可见 offline  
- [ ] 有 key：一轮推荐 `offline=false`，耗时可接受（<15s）  
- [ ] 双人：一人聊天、一人收藏/翻详情，无 `database is locked`  
- [ ] 弱网：首屏 galaxy ~1MB 可接受；海报 404 时有占位不白屏  
- [ ] GPU：开详情后机器不过热到风扇炸（可接受则勾）  

---

## 不改架构前提下的快速优化项（按收益排序）

1. **赛前打包校验脚本**：缺 posters/dist/config 直接失败并打印清单（防上场翻车）。  
2. **StaticFiles 条件挂载 + 真 fallback**（`dist`→`static`），缺海报目录自动创建空目录。  
3. **`llm._cfg`：配置文件缺失仍读 env/key 文件**（一行量级逻辑修复，演示收益最大）。  
4. **修 L309 连接泄漏**；`PRAGMA journal_mode=WAL; busy_timeout=5000`。  
5. **`galaxy_rows` 启动缓存** + `Cache-Control: public, max-age=300`。  
6. **overlay 时关 Bloom / 降 dpr / 暂停旋转**（改 `GalaxyScene` 数行）。  
7. **startup 打印就绪表**：core/ext/FTS/vectors/LLM keys/海报路径。  
8. **详情收藏态**改为轻量接口，避免每次拉全量 explorer。  
9. **chat 单请求共用一个 sqlite 连接**，减少锁竞争。  
10. **Explore 搜索接上 `suggest` + 220ms 防抖**（旧 static 已有范式）。  

---

## 亮点

- **数据热路径设计清醒**：590 核心常驻内存；短评已预索引，详情不再扫大 CSV（代码与注释一致，旧问题已修）。  
- **向量懒加载 + 失败降级**：无 npz/模型不挡启动，推荐可走规则。  
- **AI 防幻觉链路完整**：清单约束、编号校验、片名白名单、失败回落 `offline` 文案。  
- **星球渲染成本可控**：5000 粒子单 `Points` draw call，比 mesh 星球克制。  
- **Boot 音效循环 bug 已修**（`useCallback` 稳定 `sound`）。  
- **离线可演示心智**：无 LLM 仍能选片；`start_server.bat` 意图正确（实现被 config 耦合拖累）。  
- **dev 体验**：Vite 代理 8010，前后端分离调试清晰。  

---

**本机结论一句话**：代码在「完整数据机」上可演示，但**当前磁盘状态 + 无条件 StaticFiles + LLM 配置耦合**会使冷启动在导入阶段失败；热路径 CPU 在 590/5000 规模可接受，真正风险是**首包体积、常驻 3D、SQLite 写放大/泄漏，以及双人+LLM 串行**。
