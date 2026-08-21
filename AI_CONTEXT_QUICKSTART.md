# AI 上下文记忆功能 - 快速启动指南

## 功能概述

本次升级为影灵 CINE 平台带来了真正的多轮对话能力：

✅ **AI 能够理解追问** - 用户说"为什么？"时，AI 知道是在问上一轮推荐的内容
✅ **AI 陪看模式** - 从电影详情页进入聊天，AI 自动知道在讨论哪部电影
✅ **会话管理** - 清空聊天自动创建新会话，不同话题互不干扰

---

## 快速启动

### 1. 启动后端服务

```powershell
# 设置环境变量（首次需要）
$env:HF_ENDPOINT = "https://hf-mirror.com"

# 启动服务
D:\anaconda\python.exe -m uvicorn cine.main:app --port 8010
```

服务启动后会自动创建新的数据库表（conversations、conversation_messages）。

### 2. 访问前端

打开浏览器访问：`http://127.0.0.1:8010`

---

## 使用示例

### 示例 1：多轮对话追问

1. 打开"问影灵"聊天页
2. 输入："推荐一部类似《花样年华》的电影"
3. AI 回复推荐结果
4. 输入："为什么？"
5. AI 能够理解是在问"为什么推荐这部电影"，并给出解释

### 示例 2：AI 陪看模式

1. 浏览电影，进入任意电影详情页（如《花样年华》）
2. 点击"🍿 AI 陪看"按钮
3. 自动跳转到聊天页，AI 已知晓当前讨论的电影
4. 输入："这个结局是不是很遗憾？"
5. AI 能够理解"这个结局"指的是《花样年华》的结局

### 示例 3：清空聊天创建新会话

1. 在聊天页进行一轮对话
2. 点击"清空"按钮
3. 开始新的对话话题
4. 系统自动创建新会话，历史不会混淆

---

## 运行测试

```powershell
# 确保后端已启动
D:\anaconda\python.exe test_ai_context.py
```

测试包含三个场景：
- 多轮对话上下文
- 电影上下文（AI 陪看）
- 清空聊天创建新会话

---

## 技术细节

### 后端改动

**新增数据库表：**
- `conversations` - 存储会话信息
- `conversation_messages` - 存储会话内的消息

**新增 API 参数：**
- `conversation_id` (可选) - 会话 ID，不传则自动创建
- `movie_id` (可选) - 当前讨论电影 ID

**新增函数：**
- `_create_conversation()` - 创建会话
- `_load_conversation_history()` - 加载会话历史
- `_load_movie_context()` - 加载电影上下文
- `_save_conversation_message()` - 保存消息

### 前端改动

**新增状态：**
- `conversationId` - 当前会话 ID
- `movieId` - 当前讨论电影 ID

**新增 UI：**
- 详情页"AI 陪看"按钮

**URL 参数支持：**
- `#/chat?movie_id=xxx` - 从详情页跳转时携带电影 ID

---

## 兼容性说明

### 向后兼容
- 所有新参数均为可选
- 旧版前端仍能正常工作
- 不传 `conversation_id` 时自动创建新会话

### 数据兼容
- 保留原有 `chats` 表
- 新消息双写（新表 + 旧表）
- 账号页历史展示不受影响

---

## 常见问题

### Q: 刷新页面后 conversationId 丢失怎么办？
A: 刷新后会话会重置，但不影响已保存的消息。可以后续优化为将 conversationId 存入 localStorage 或 URL 参数。

### Q: 如何查看数据库中的会话记录？
A: 使用 SQLite 客户端打开 `cine/data/cine.db`，查询：
```sql
SELECT * FROM conversations ORDER BY created_at DESC;
SELECT * FROM conversation_messages WHERE conversation_id = 1;
```

### Q: AI 陪看按钮样式如何修改？
A: 编辑 `cine/web/src/index.css` 中的 `.detail-ai-talk` 样式。

### Q: 如何禁用追问检测？
A: 编辑 `cine/chat.py` 中的 `_is_followup()` 函数，返回 `False` 即可。

---

## 后续优化方向

### 第三阶段：用户电影画像（未实施）
- 记录用户喜欢的类型、导演、地区
- 从收藏和聊天中自动提取偏好
- 推荐时注入用户偏好到 Prompt

### 第四阶段：优化推荐算法（未实施）
- 排除对话中已推荐的电影
- 融入用户偏好信号
- 查询改写利用完整上下文

---

## 文件清单

### 修改的文件
- `cine/main.py` - 后端 API 和数据库
- `cine/chat.py` - 聊天逻辑
- `cine/web/src/types.ts` - 类型定义
- `cine/web/src/api.ts` - API 客户端
- `cine/web/src/pages/Chat.tsx` - 聊天页
- `cine/web/src/pages/Detail.tsx` - 详情页
- `cine/web/src/index.css` - 样式

### 新增的文件
- `test_ai_context.py` - 功能测试脚本
- `AI_CONTEXT_IMPLEMENTATION.md` - 实施总结文档
- `AI_CONTEXT_QUICKSTART.md` - 本快速启动指南

---

## 技术支持

如有问题，请查看：
- `AI_CONTEXT_IMPLEMENTATION.md` - 详细实施文档
- `cine/main.py` - 后端实现
- `cine/chat.py` - 聊天层实现

---

**祝使用愉快！** 🎬✨
