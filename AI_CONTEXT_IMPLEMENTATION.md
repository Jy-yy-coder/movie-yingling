# AI 上下文记忆改造实施总结

## 实施日期
2026-08-18

## 实施内容概览

已成功完成影灵 CINE 平台 AI 上下文记忆系统的第一阶段和第二阶段改造：

### ✅ 第一阶段：解决 AI 多轮上下文问题
### ✅ 第二阶段：完善 AI 陪看状态

---

## 一、后端改造

### 1. 数据库新增表（cine/main.py）

#### conversations 表
```sql
CREATE TABLE IF NOT EXISTS conversations(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    movie_id TEXT,              -- 关联电影（可选，陪看场景）
    mode TEXT DEFAULT 'rec',    -- rec / talk
    title TEXT,                 -- 会话标题（自动生成）
    created_at TEXT,
    updated_at TEXT
);
```

#### conversation_messages 表
```sql
CREATE TABLE IF NOT EXISTS conversation_messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,          -- user / assistant
    content TEXT NOT NULL,
    movie_ids TEXT,              -- assistant 推荐的电影 ID 列表（JSON）
    created_at TEXT,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
```

### 2. 新增后端函数（cine/main.py）

- `_create_conversation()` - 创建新会话
- `_load_conversation_history()` - 加载会话内历史消息
- `_load_movie_context()` - 加载电影上下文（含完整信息、DNA、好评、差评预警）
- `_save_conversation_message()` - 保存消息到会话

### 3. 修改 API 接口（cine/main.py）

#### ChatIn 模型新增字段
```python
class ChatIn(BaseModel):
    message: str
    device_id: str = "guest"
    mode: str = "rec"
    spoiler: bool = True
    conversation_id: int | None = None   # 新增：会话 ID
    movie_id: str | None = None          # 新增：当前讨论电影
```

#### api_chat() 函数改造
- 支持 conversation_id 参数（可选，不传则自动创建）
- 支持 movie_id 参数（从详情页带入）
- 加载会话内历史（而非全局历史）
- 加载电影上下文
- 双写消息（新表 + 旧 chats 表兼容）
- 返回 conversation_id 给前端

### 4. 聊天层增强（cine/chat.py）

#### 新增追问检测
```python
def _is_followup(msg: str) -> bool:
    """判断消息是否为追问/跟进"""
    # 检测短消息 + 追问关键词
    # 检测代词引用（这个、那个、结局、最后等）
```

#### 新增电影上下文注入
```python
def _build_enhanced_system(base_system: str, movie_context: dict | None = None) -> str:
    """构建增强版系统提示词，注入电影上下文"""
```

#### build_reply() 函数增强
- 新增 `movie_context` 参数
- 优先处理有电影上下文的追问
- 支持从历史中提取上一轮推荐的电影
- 所有 `_answer_movie()` 调用都传入 movie_context

---

## 二、前端改造

### 1. 类型定义（cine/web/src/types.ts）

```typescript
export interface ChatReply {
  text: string
  offline: boolean
  citations: Citation[]
  kind: string
  model?: string | null
  movie_id?: string
  movie?: RecCard
  movies?: RecCard[]
  conversation_id?: number  // 新增
}
```

### 2. API 客户端（cine/web/src/api.ts）

```typescript
export const chat = (
  message: string,
  mode: 'rec' | 'talk' = 'rec',
  spoiler = true,
  conversationId?: number,  // 新增
  movieId?: string          // 新增
) => post<ChatReply>('/api/chat', {
  message,
  device_id: deviceId(),
  mode,
  spoiler,
  conversation_id: conversationId,
  movie_id: movieId
})
```

### 3. 聊天页面（cine/web/src/pages/Chat.tsx）

#### ChatPanel 组件增强
- 新增 `conversationId` state
- 新增 `movieId` state（从 initialMovieId 初始化）
- 发送消息时传入 conversationId 和 movieId
- 保存后端返回的 conversation_id
- 清空聊天时重置 conversationId（创建新会话）

#### Chat 默认导出增强
- 读取 URL 中的 `movie_id` 参数（从详情页跳转时）
- 传递给 ChatPanel 作为 initialMovieId

### 4. 电影详情页（cine/web/src/pages/Detail.tsx）

新增"AI 陪看"按钮：
```tsx
<a className="detail-ai-talk" href={`#/chat?movie_id=${id}`}>
  🍿 AI 陪看
</a>
```

### 5. 样式（cine/web/src/index.css）

新增 `.detail-ai-talk` 样式（紫色主题，与收藏按钮并列）

---

## 三、核心功能实现

### 1. 短期对话记忆

**实现方式：**
- 前端维护 conversationId state
- 首次发送消息时，后端自动创建 conversation
- 后续消息携带 conversation_id
- 后端按 conversation_id 加载历史（最近 8 条 = 4 轮）
- LLM 收到的是当前会话内的连续对话

**效果：**
```
用户：推荐一部类似《花样年华》的电影
AI：推荐《重庆森林》……
用户：为什么？
AI：能够理解是在问"为什么推荐《重庆森林》"
```

### 2. 当前电影状态记忆

**实现方式：**
- 详情页增加"AI 陪看"按钮
- 点击后跳转 `#/chat?movie_id=xxx`
- 聊天页读取 URL 参数，设置 movieId
- 每次发送消息都携带 movie_id
- 后端加载电影完整信息（标题、导演、主演、类型、简介、DNA、好评、差评预警）
- 注入到系统 Prompt 中

**效果：**
```
（用户从《花样年华》详情页点击"AI 陪看"）
用户：这个结局是不是很遗憾？
AI：知道在讨论《花样年华》，能理解"这个结局"指的是该电影的结局
```

### 3. 追问处理增强

**实现方式：**
- `_is_followup()` 检测追问消息
- 有电影上下文时，追问直接走电影问答逻辑
- 无电影上下文时，从历史中提取上一轮推荐的电影
- 支持代词引用（这个、那个、结局、最后等）

**检测模式：**
- 短消息（<20字）+ 追问关键词
- 含代词（这个、那个、它、这部等）
- 含省略式追问（为什么、然后呢、什么意思等）

---

## 四、兼容性保证

### 1. 向后兼容
- `conversation_id` 和 `movie_id` 均为可选参数
- 不传时自动创建新会话（降级为旧逻辑）
- 旧版前端仍能正常工作

### 2. 数据兼容
- 保留原有 `chats` 表
- 新消息双写（conversations_messages + chats）
- 账号页历史展示不受影响

### 3. API 兼容
- ChatReply 新增字段为可选
- 前端不使用时不报错

---

## 五、测试验证

### 测试脚本
已创建 `test_ai_context.py`，包含三个测试：

1. **test_conversation()** - 测试多轮对话上下文
   - 第一轮：推荐类似《花样年华》的电影
   - 第二轮：追问"为什么？"
   - 验证 AI 是否理解上下文

2. **test_movie_context()** - 测试电影上下文
   - 从详情页带 movie_id 进入 AI 陪看
   - 问"这个结局是不是很遗憾？"
   - 验证 AI 是否知道当前电影

3. **test_new_conversation()** - 测试清空聊天创建新会话
   - 第一次对话（不传 conversation_id）
   - 第二次对话（不传 conversation_id）
   - 验证是否创建了不同的 conversation_id

### 运行测试
```bash
# 1. 启动后端
$env:HF_ENDPOINT = "https://hf-mirror.com"
D:\anaconda\python.exe -m uvicorn cine.main:app --port 8010

# 2. 运行测试
D:\anaconda\python.exe test_ai_context.py
```

---

## 六、文件修改清单

### 后端
- `cine/main.py` - 新增表、函数、修改 API
- `cine/chat.py` - 增强追问处理、电影上下文注入

### 前端
- `cine/web/src/types.ts` - ChatReply 增加 conversation_id
- `cine/web/src/api.ts` - chat() 增加参数
- `cine/web/src/pages/Chat.tsx` - 维护 conversationId、读取 movie_id
- `cine/web/src/pages/Detail.tsx` - 增加 AI 陪看按钮
- `cine/web/src/index.css` - 增加 detail-ai-talk 样式

### 测试
- `test_ai_context.py` - 功能测试脚本

---

## 七、后续优化建议

### 第三阶段：用户电影画像（未实施）
- 新增 `user_movie_profiles` 表
- 从收藏和聊天中提取偏好
- 推荐时注入用户偏好到 Prompt

### 第四阶段：优化推荐算法（未实施）
- 排除对话中已推荐的电影
- 融入用户偏好信号
- 查询改写利用完整上下文

---

## 八、技术亮点

1. **三层记忆架构**：短期对话记忆 + 电影状态记忆 + 用户长期偏好（第三层待实施）
2. **无侵入式改造**：保留原有代码结构，新增功能模块化
3. **向后兼容**：旧版前端仍能正常工作
4. **双写过渡**：新旧表同时写入，平滑迁移
5. **智能追问检测**：多种模式识别追问消息
6. **电影上下文注入**：将电影信息融入系统 Prompt，而非作为消息

---

## 九、已知限制

1. **Token 消耗增加**：电影上下文注入会增加 Prompt 长度
   - 缓解：控制历史条数（8 条 = 4 轮），电影信息精简到关键字段

2. **追问检测非 100% 准确**：基于规则的模式匹配
   - 缓解：覆盖常见追问模式，后续可引入 LLM 辅助判断

3. **前端状态管理**：conversationId 在页面刷新后丢失
   - 缓解：可考虑存入 localStorage 或 URL 参数

---

## 十、总结

本次改造成功实现了 AI 上下文记忆系统的核心功能：

✅ **AI 能够理解多轮对话中的追问**
✅ **从详情页进入 AI 陪看时，AI 自动知道讨论哪部电影**
✅ **支持清空聊天创建新会话**
✅ **完全向后兼容，不影响现有功能**

系统已具备真正的多轮对话能力，用户体验显著提升。
