# 影灵 CINE · 多 Agent 综合审查（2026-08-21）

三批次并行 Sub Agent 审查归档。建议阅读顺序：**先看 `00-synthesis-verdict.md`**，再按需深入分册。

## 文件清单

| 文件 | 角度 | 批次 |
|---|---|---|
| [00-synthesis-verdict.md](./00-synthesis-verdict.md) | **G 综合裁决**（P0/P1/P2、48h 序列、演示约束） | 第 3 批 |
| [01-backend-security.md](./01-backend-security.md) | A 后端正确性与安全 | 第 1 批 |
| [02-frontend-ux.md](./02-frontend-ux.md) | B 前端体验与 3D | 第 1 批 |
| [03-ai-pipeline.md](./03-ai-pipeline.md) | C AI 推荐与防幻觉 | 第 1 批 |
| [04-data-quality.md](./04-data-quality.md) | D 数据资产与管线 | 第 2 批 |
| [05-performance-demo.md](./05-performance-demo.md) | E 性能 / 部署 / 演示稳定性 | 第 2 批 |
| [06-competition-narrative.md](./06-competition-narrative.md) | F 赛道评委 / 产品叙事 | 第 2 批 |

## 一句话结论

产品内核（590 对齐、DNA、防幻觉推荐）可答辩；**当前仓库缺海报/`dist`/向量/`llm_config`，游客登录不写 token、登录不合并游客**——不修则演示起不来。

## P0 速览（详见综合裁决）

1. 恢复 `posters` / `posters_thumb`
2. `npm run build` 产出 `cine/web/dist`
3. 修复 Login 游客入口 `setToken`
4. 准备 `llm_config.json` + key
5. 恢复 `movie_vectors.npz`
6. 登录合并游客（最小补丁）
7. 讲稿统一评论口径 ≈11.7 万

## 与旧报告关系

对照 `reports/项目全面审查报告_2026-08-21.md`：注册双行、详情 CSV、会话越权、Boot 音效等**多数已修**；本轮焦点转移到**资产完整性、登录路径、无剧透事实注入、数可视接线落差**。
