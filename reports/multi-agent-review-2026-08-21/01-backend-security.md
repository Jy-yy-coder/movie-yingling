# A · 后端正确性与安全审查

| 项 | 内容 |
|---|---|
| 审查日期 | 2026-08-21 |
| 仓库 | `I:\movie-yingling` |
| 项目 | 影灵 CINE |
| Agent ID | `0683f61f-c89e-4160-a126-8ea9127ab2d7` |
| 方式 | 只读多角度 Sub Agent 审查 |

> 本文由并行 Sub Agent 审查产出，未改动业务代码。

---
## 摘要（3–5 句）

旧报告中的注册双行、详情重读 30MB CSV、会话越权、FTS 全局单连接，当前代码里**均已修复或显著缓解**；但**登录路径仍未做游客合并**，且聊天仍只认 `device_id`、账号能力认 `token`，已注册用户「再登录」时数据割裂会再次出现。演示期固定短信码 `246810` 并在响应中回传 `dev_code`，等于公开 OTP。SQLite 业务库无 WAL/超时、`api_chat` 有连接未关闭，并发写仍脆弱。热路径上详情短评已内存化，但 `/api/galaxy` 与 `/api/movies` 仍偏重算。

---

## Critical

### 1. 固定短信验证码 + 接口明文回传 | `cine/main.py` `api_sms` L567–576；`api_login` L636–642
**证据**：`code = "246810"`，响应含 `"dev_code": code`；`api_login` 在 `body.code` 分支仅校验该码即可发正式 `token`（无需密码）。  
**影响**：任意人可对已注册手机号完成验证码登录，接管收藏/反馈/账号页；答辩演示时也可被旁人复现。  
**修复**：演示可保留固定码，但勿在 JSON 回传；正式路径改为随机码+频控；验证码登录成功后立即作废该码。

### 2. 登录不合并游客数据，身份双轨复活 | `cine/main.py` `api_login` L633–652 vs `api_register` L604–624；`api_chat` L294 + `_resolve_user_id` L369–381
**证据**：注册会迁移 `chats/favorites/user_personality/user_signals/conversations` 并 `DELETE` 游客行；`api_login` 只换 `token`，不传/不绑 `device_id`、不做合并。前端登录成功后聊天仍只发 `device_id`（`cine/web/src/api.ts` L36–42），收藏走 `token`。  
**影响**：游客聊完 → 登录已有账号 → 聊天/人格仍挂游客行，账号页收藏挂注册行，答辩「越用越懂我」演示易翻车。  
**修复**：登录入参带 `device_id`，复用注册同一套 merge；或聊天/人格统一改为 `token` 鉴权。

---

## High

### 3. 聊天/人格只认 device_id，与 token 鉴权分裂 | `ChatIn` L197–199；`api_chat` L292–294；`api_personality_test` L461–469；对比 `api_fav` L674–679
**证据**：敏感写操作（收藏/反馈）需 `token`；会话与人格测试仅 `_resolve_user_id(device_id)`。`deviceId` 为 `d`+约 8 位 base36（`api.ts` L46–49），熵低。  
**影响**：知悉/猜测 `device_id` 即可读写会话与人格，无需登录；与账号体系脱节。  
**修复**：`/api/chat`、`/api/personality/*` 优先 `Authorization`/`token`，`device_id` 仅作未登录兜底。

### 4. 游客 token 可被同 device_id 覆盖劫持 | `api_guest` L555–562
**证据**：任意 `POST /api/auth/guest {device_id}` 会 `UPDATE users SET token=?`，旧 token 立即失效。  
**影响**：拿到 `cine_device` 即可踢掉原游客会话并接管其收藏/反馈。  
**修复**：已有游客行则复用未过期 token，或要求证明持有旧 token 再轮换。

### 5. Token 放在 QueryString | `api_account`/`api_explorer`/`api_fav`/`api_feedback` 等；前端 `api.ts` L76–87
**证据**：`?token=` 查询参数传凭据。  
**影响**：进访问日志、代理日志、浏览器历史、Referer，易泄露会话。  
**修复**：改为 `Authorization: Bearer` 或 POST body；日志脱敏。

### 6. 业务 SQLite 无 WAL/busy_timeout，且 chat 路径连接泄漏 | `_conn` L37–39；`api_chat` L309
**证据**：`sqlite3.connect(DB_PATH)` 无 `timeout`、未 `PRAGMA journal_mode=WAL`；`row = _conn().execute(...).fetchone()` 未 `close()`。单次 chat 还多次开关连接写 `conversations/chats`。  
**影响**：演示多人并发点「发送」易 `database is locked`；泄漏连接加重锁与句柄压力。  
**修复**：统一连接工厂（WAL + busy_timeout + 上下文管理）；L309 必须关闭；热点路径合并事务。

---

## Medium

### 7. sms_codes 表无 UNIQUE，INSERT OR REPLACE 实际只是追加 | `_init_db` L48–49；`api_sms` L573–574
**证据**：`sms_codes(phone, code, expires_at)` 无主键/唯一约束；`INSERT OR REPLACE` 无冲突目标时等价于 INSERT；`SELECT` 取任意一行。  
**影响**：验证成功不稳定，或旧过期码抢先匹配。  
**修复**：`phone PRIMARY KEY` 或先 `DELETE` 再插入；校验后删除。

### 8. `/api/galaxy` 每次全量重算约 5000 星球 | `api_galaxy` L141–145；`data.galaxy_rows` L241–287
**证据**：无进程级缓存，每次遍历核心+库外算半径/亮度/颜色。  
**影响**：首屏/刷新卡顿，CPU 尖峰，挤压 chat/LLM。  
**修复**：`load()` 后缓存结果，数据变更再失效。

### 9. `/api/movies` 先 `limit=100000` 再内存过滤分页 | `api_movies` L107–123
**证据**：`recommend(..., limit=100000)` 后多层 list 过滤/排序再切片。  
**影响**：筛片页延迟与内存抖动，尤其默认空查询。  
**修复**：过滤条件下推到排序前，分页前截断；限制 `limit` 上限（如 48）。

### 10. 密码仅 SHA-256 无盐；会话 token 为短 MD5 | `api_register` L598；`_token` L88–90
**证据**：`hashlib.sha256(password)`；`md5(f"{uid}|{phone}|{time.time()}")[:24]`。  
**影响**：库文件泄露后易撞库；token 可预测性高于标准会话方案。  
**修复**：`bcrypt`/`argon2`；`secrets.token_urlsafe` + 服务端存储哈希。

### 11. 取消收藏未登录仍返回成功 | `api_unfav` L685–693
**证据**：无 `token` 对应用户时直接 `return {"ok": True}`，不 401。  
**影响**：前端误判「已取消」；契约不诚实。  
**修复**：与 `api_fav` 一致返回 401。

### 12. Chat 消息长度无上限，可打爆 LLM 配额 | `ChatIn.message` L198；`api_chat` → `llm.chat_reply` timeout=90
**证据**：Pydantic 无 `max_length`；推荐路径 `max_tokens=2800`。  
**影响**：演示被刷接口导致 key 额度耗尽，全站掉离线。  
**修复**：`message` 限 500–1000 字；SMS/chat 简易限流。

### 13. CORS `allow_origins=["*"]` | `main.py` L22
**证据**：任意源可调 API（若浏览器带 cookie 场景更危险；当前主要是 token）。  
**影响**：配合 query token 的 XSS/恶意页可盗用。  
**修复**：演示绑定具体前端源。

---

## Low

### 14. `_save_conversation_message` 自身无属主校验 | L280–289
**证据**：仅靠 `api_chat` 入口 `_conversation_owned`；保存函数可对任意 `conversation_id` 写入。  
**影响**：后续若复用该函数易回归越权。  
**修复**：写入时 `UPDATE/INSERT` 带 `user_id` 条件或再查属主。

### 15. 人格答题只校验条数不校验题号完备 | `api_personality_test` L463–464；`personality._option` L85–91
**证据**：`len(answers) < len(QUIZ)` 即过；非法 `q/o` 被静默跳过，DNA 仍可算。  
**影响**：可提交畸形答案得到偏画像。  
**修复**：要求 `q` 覆盖 `0..11` 且选项合法，否则 400。

### 16. FTS 仍 `check_same_thread=False`（已线程局部） | `data.fts` L175–185
**证据**：每线程一连接，风险已大降；标志仍关闭。  
**影响**：线程复用池边缘情况理论残留。  
**修复**：可改为每请求短连接，或保留现状并文档化。

---

## 旧问题核实表

| 旧问题 | 状态 | 当前证据 |
|--------|------|----------|
| S1 注册后同 `device_id` 双用户行 / 数据割裂 | **已修复（注册路径）** | `_resolve_user_id`/`_personality_uid` 优先 `phone IS NOT NULL`（L372–373、L504–505）；`api_register` 迁移 chats/favorites/personality/signals/conversations 并删除游客行（L604–624） |
| S1 延伸：登录后割裂 | **仍存在（新暴露面）** | `api_login` 无 merge（L633–652）；聊天仍只靠 `device_id` |
| S2 详情每次读 30MB CSV | **已修复** | `_load_comments_index` 启动预载（`data.py` L199–225）；`top_comments` 纯内存（L228–239） |
| S3 FTS 跨线程共用单连接 | **已修复（线程局部）** | `threading.local` + 每线程惰性连接（`data.py` L33、L175–185） |
| S4 会话 `conversation_id` 越权 | **已修复** | `_conversation_owned`；非本人 404（`main.py` L219–225、L298–300、L231–232） |
| 注册未迁 personality/signals/conversations | **已修复** | 见 `api_register` L616–621 |
| LLM key 明文入库风险 | **基本受控** | `.gitignore` 排除 `llm_config.json` / `llm_key.local.txt`；`llm.py` 环境变量→本地文件→配置链（L52–62）。提交物仍须确认未夹带 `data/task` 密钥文件 |

---

## 演示前必须修的 Top 5

1. **登录合并游客数据**（或聊天改 token）：避免「游客体验 → 登录」现场数据消失/错位。  
2. **关掉响应里的 `dev_code` / 限制验证码登录滥用**：防旁人接管账号。  
3. **修好 `api_chat` L309 连接泄漏 + SQLite WAL/timeout**：防并发 `database is locked`。  
4. **统一身份**：chat/personality 与 favorites 同一套鉴权，消灭 device_id/token 双轨。  
5. **给 `/api/chat` 与短信接口加长度上限/简易限流**：保住现场 LLM 额度。

---

## 值得写进答辩的后端亮点（可选）

1. **防幻觉推荐闭环**：候选清单约束 + 编号校验 + 片名白名单 + 简介强制回填 + `offline` 诚实降级（`cine/chat.py` 推荐路径）。  
2. **游客→注册五表合并并删游客行**：针对同 `device_id` 双行的工程化修复（`api_register`）。  
3. **短评索引启动预热**：详情页从「每次 30MB CSV」变为内存 O(评论子集)（`data.top_comments`），可量化对比旧报告 0.67s → 亚毫秒级。
