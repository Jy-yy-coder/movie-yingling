# B · 前端体验与 3D 银河审查

| 项 | 内容 |
|---|---|
| 审查日期 | 2026-08-21 |
| 仓库 | `I:\movie-yingling` |
| 项目 | 影灵 CINE |
| Agent ID | `e20b7296-c420-4e56-8d0f-a9083142be63` |
| 方式 | 只读多角度 Sub Agent 审查 |

> 本文由并行 Sub Agent 审查产出，未改动业务代码。

---
## 摘要

`cine/web` 视觉叙事完整（Boot → 地球仪银河 → 探索/聊天/人格），技术选型与演示气质匹配。但演示链路里仍有多处「看起来通、点进去断」：登录页游客入口丢 token、AI 导航员组件零入口、≤860px 星图筛选被 CSS 整块关掉、情绪宇宙/EChart 有类型与样式却无页面接线。旧报告的 BootScene 16ms 音效狂触发**已修复**；仍建议答辩前优先修游客登录与移动端星图可达性。

---

## 按页面走查结论（首页/列表/详情/聊天/人格/账号/银河）

| 面 | 结论 |
|---|---|
| **首页（银河 + HUD）** | 开场蓄力叙事强；星域筛选与粒子色一致。移动端 `hud-filter` 直接 `display:none`，演示机几乎只能瞎点粒子。`#/profile`/`#/about`/`Navigator` 无入口。银河加载失败静默 → 空宇宙无提示。 |
| **列表（`#/list` / Explore 电影库）** | 筛选/分页/空态/加载态齐全；独立 `#/list` 只能手输 hash。注释写「年份」筛选，UI 无年份。搜索+类型依赖后端 genre（旧报告 M1 仍可能翻车）。 |
| **详情** | 海报/DNA/短评/陪看入口完整；`tags`/`brief`/`egg` 有数据才显示（符合「宁缺毋编」）。`sentiment.emotions/freq/trend` 与大量 `.emo-*` CSS **未渲染**；收藏失败静默。加载用透明占位，弱网像「卡住」。 |
| **聊天** | 双模式、离线标签、typing、引用卡、follow-up chip 体验好。剧透开关文案与后端「`spoiler=true`=无剧透开」一致，但**聊天内切换不写回** `localStorage`。`WatchIntro` 依赖不稳定的 `onDone`，父组件重渲染会重置倒计时。切模式 `clear()` 会丢会话。 |
| **人格** | 流程完整；服务端失败回落 localStorage，注册割裂时易「本地有画像、账号页/推荐读不到」。 |
| **账号/登录/游客** | 档案环、收藏、历史、剧透默认开关清楚。登录页「游客」**未 `setToken`**；Guest 页承诺「自动合并」依赖后端合并，前端无法兜底。 |
| **银河 3D** | 单 draw call 粒子 + Bloom 观感好；overlay 下 Canvas 仍全开；`CameraRig` 每帧 `new Vector3`；库外片可悬停不可进详情，提示文案有写但易被误点。 |

---

## Critical / High / Medium / Low

### Critical

**C1. 登录页「游客」丢弃 token**  
路径：`src/pages/Login.tsx` L68–73；`src/api.ts` L115  

```68:73:cine/web/src/pages/Login.tsx
  const doGuest = async () => {
    setBusy(true)
    try {
      await guest()
      tip('已以游客身份进入')
      setTimeout(() => { location.hash = '#/account' }, 600)
```

证据：`guest()` 返回 `{ token, ... }`，此处未 `setToken`；对比 `ensureGuest`/`doRegister`/`doLogin` 都会写入。  
影响：演示点「游客入口」时 toast 成功，但本地可能仍无/仍是旧 token；随后 `account()` 靠 `ensureGuest` 二次发游客请求，易与后端双用户/合并逻辑叠雷。  
修复：`const r = await guest(); setToken(r.token)`（或直接走 `ensureGuest()`）。

---

### High

**H1. `Navigator`（AI 电影导航员）完全无打开入口**  
路径：`src/components/Navigator.tsx`；`src/store.ts` L15–23,45；全仓无 `setNavigatorOpen(true)`  

证据：组件已挂在 `App`，`open` 默认 `false`，仓库内 **零处** `setNavigatorOpen(true)`。  
影响：答辩若讲「心情点亮探索路线」，现场打不开；与 Explore/Chat 能力重复却像半成品。  
修复：在 HUD/Explore 加入口，或删路由级挂载避免虚假能力。

**H2. ≤860px 隐藏星图筛选，演示机银河「只能瞎点」**  
路径：`src/index.css` L421–423,1402–1404  

```421:423:cine/web/src/index.css
@media (max-width: 860px) {
  .hud-filter { display: none; }
  .hud-hint { display: none; }
```

证据：同时隐藏引导；底部只剩「进入探索」。  
影响：平板/笔记本窄窗/投屏裁切后无法按地区飞向星域，3D 卖点与列表联动断裂。  
修复：改为可折叠底栏/抽屉，勿整块 `display:none`。

**H3. Overlay 下银河 Canvas + Bloom 常驻**  
路径：`src/App.tsx` L74–91；`src/scenes/GalaxyScene.tsx` L80–101  

证据：`Detail`/`Explore`/`Chat` 打开时仍渲染全屏 R3F + `EffectComposer`/`Bloom`。  
影响：演示机切探索/详情后风扇狂转、掉帧、触控卡顿；像「页面卡死」。  
修复：有全屏 overlay 时降 `dpr`、关 Bloom，或 `frameloop="demand"` / 卸载 Canvas。

**H4. 「观众情绪宇宙」数据与样式在、详情页不展示**  
路径：`src/types.ts` L19–28；`src/index.css` L349–377；`src/pages/Detail.tsx` L35–92（只用 `s.temp`）；`src/pages/About.tsx` L16  

证据：`emotions`/`freq`/`trend` 与 `.emo-grid` 等 CSS 完整，Detail 零引用；About 仍宣称情绪关键词与趋势。  
影响：评委打开详情对不上 About 话术；EChart 本可接 trend 却闲置。  
修复：接线情绪区，或砍 About 文案与死 CSS。

**H5. 人格画像 localStorage 与服务端双源，注册后易「假同步」**  
路径：`src/api.ts` L91–104；`src/pages/Personality.tsx` L22–25  

证据：提交写 `cine_personality`；读档 `personalityProfile().catch(() => loadLocalPersonality())`。配合后端游客/注册割裂时，前端会长期展示本地画像，而推荐/账号侧读另一 user。  
影响：测完人格 → 注册 → 「查看我的画像」有，AI 推荐像没测过。  
修复：注册成功清/迁移本地键；profile 404 时勿无条件用本地冒充已登录态。

---

### Medium

**M1. `echarts` + `EChart` 死依赖**  
路径：`package.json` L16；`src/components/EChart.tsx`（无任何 import）  
影响：打包体积与「数据可视化」承诺落空。  
修复：接详情趋势/情绪，或移除依赖。

**M2. 探索档案收藏标题用错字段**  
路径：`src/pages/Profile.tsx` L56  

证据：`我的收藏 · {data.discovered}`，应为 `favorites.length`（`discovered` 是探索进度）。  
影响：数字与列表对不上。  

**M3. `#/profile`、`#/about`、独立 `#/list` 无导航入口**  
路径：`src/App.tsx` L80–87；HUD/Explore 无对应链接  
影响：About 数据口径、探索档案只能手输 hash，演示找不到。  

**M4. 聊天剧透开关不持久化**  
路径：`Chat.tsx` L28,136–138 vs `Account.tsx` L29–32  
证据：Account 写 `cine_spoiler_default`；Chat 仅初始读，点击只改本地 state。  
影响：设置页与聊天页状态打架。  

**M5. `WatchIntro` 的 `onDone` 未稳定，倒计时可被重置**  
路径：`WatchIntro.tsx` L16–20；`Chat.tsx` L107–112  

```16:20:cine/web/src/scenes/../components/WatchIntro.tsx
  useEffect(() => {
    if (step >= PHASES.length) { onDone(); return }
    const t = setTimeout(() => setStep((s) => s + 1), PHASES[step].ms)
    return () => clearTimeout(t)
  }, [step, onDone])
```

影响：父组件任意重渲染清 timeout，陪看开场忽快忽慢或卡住。  
修复：`useEffectEvent` / ref 存 `onDone`，或 `useCallback`。

**M6. `CameraRig` 每帧分配 Vector3**  
路径：`GalaxyScene.tsx` L51–64  
影响：5000 粒子 + Bloom 下额外 GC 抖动。  

**M7. 首屏 `buildLayout` 主线程重计算**  
路径：`layout.ts` L59–163；`App.tsx` L49–50  
影响：5000×松弛迭代可造成白屏/卡顿数秒，像崩溃。  

**M8. 收藏/银河加载错误被吞**  
路径：`Detail.tsx` L46；`App.tsx` L50  
影响：弱网无反馈，演示者以为功能坏了。  

---

### Low

**L1. Boot 蓄力仅 pointer，无键盘等价操作**（`BootScene.tsx` L146–148）— 无障碍缺口。  
**L2. `ExplainCard` `role="button"` 无 `tabIndex={0}`**（`ExplainCard.tsx` L14–19）— 键盘不可达。  
**L3. Login 验证码倒计时 `setInterval` 卸载未清**（`Login.tsx` L27）— 轻泄漏。  
**L4. Boot `AudioContext` 从不 `close`**（`BootScene.tsx` L7–14）— 长会话残留。  
**L5. List 注释「年份」筛选未实现**（`List.tsx` L6）。  
**L6. `prefers-reduced-motion` 只压 CSS，不关 R3F/Bloom**（`index.css` L416–418）。  
**L7. 对比度**：金渐变字 + 深空底在部分投影上偏淡；依赖 `title-gold` 透明字。  

---

## 旧问题核实

| 旧问题（报告 2026-08-21） | 现状 |
|---|---|
| **S5 BootScene 蓄力音效每 16ms 重触发** | **已修复。** `useProjectorSound` 用 `useCallback(..., [])`（`BootScene.tsx` L8–44），蓄力 effect 依赖 `sound` 引用稳定（L81–97），按住期间只会在 effect 进入时 `sound('gear')` 一次，不再每帧重建 interval/狂播。 |
| 残余风险 | React StrictMode 开发态阶段 0/`charging` 边沿可能双播一声；`AudioContext` 未释放；与「16ms 炸响」不是同一 bug。 |
| **M4 echarts/EChart 闲置** | **仍在**：`package.json` 仍含 `echarts@6`，`EChart.tsx` 无引用。 |

---

## 演示剧本里最容易翻车的 5 个前端点

1. **登录页点「游客」** — toast 成功但 token 未写入，紧接个人中心/收藏表现诡异。  
2. **笔记本/投屏窄于 860px 玩银河** — 星域筛选消失，只能随机点粒子；库外片点不动更像「坏了」。  
3. **讲「AI 导航员 / 心情路线」却找不到入口** — `Navigator` 死组件。  
4. **人格测试 → 注册 → 再聊推荐** — 本地画像还在，服务端/隐式画像可能空，推荐「没变懂你」。  
5. **详情页讲情绪宇宙 / 打开 About 对照** — About 有方法论，详情只有温度数字，情绪词云/趋势空白；弱网详情透明加载像卡死。

---

## 视觉/交互亮点（答辩可用）

1. **BootScene 胶片盘蓄力**：齿孔转盘 + conic 进度 + 大厅光束/粉尘，品牌「影灵 CINE」在爆发阶段居中，叙事完整且可跳过。  
2. **立体地球仪布局**：核心片钉国家轮廓、库外片壳层漂浮、四色粒子单 draw call + 闪烁 shader，信息密度高但不散。  
3. **防幻觉产品表达**：聊天离线标签、引用卡、ExplainCard「为什么推荐」、详情脚注「来自真实短评」——技术卖点可视化。  
4. **陪看链路**：详情 → `#/chat?movie_id=` → WatchIntro 倒数 → `watchOpening` + follow-up chips，仪式感强。  
5. **人格结果卡**：0–100 条 + 雷达换算 + MovieRoute 四站时间轴，把「测完有用」做满。  
6. **Explore 应用壳**：日/夜主题、心情 chip、Tab 指示器 spring，适合从「宇宙展陈」切到「好用的助手」。

---

*只读审查，未修改任何文件。审查基准：`cine/web/src` 全量页面/场景/组件 + `package.json` / `vite.config.ts`，并对照 `reports/项目全面审查报告_2026-08-21.md`。*
