# AI 影评修复 - 重要提示

## 问题已修复 ✅

`cine/data.py` 中的 `top_comments()` 函数已修改，从 CSV 读取原文而非 FTS 的分词文本。

## ⚠️ 必须重启后端服务

后端服务仍在运行旧代码，需要重启才能生效：

### 方法 1: 停止并重启（推荐）

```powershell
# 1. 按 Ctrl+C 停止当前运行的 uvicorn 服务

# 2. 重新启动
$env:HF_ENDPOINT = "https://hf-mirror.com"
D:\anaconda\python.exe -m uvicorn cine.main:app --port 8010
```

### 方法 2: 使用任务管理器强制结束

1. 打开任务管理器 (Ctrl+Shift+Esc)
2. 找到 python.exe 进程（uvicorn）
3. 右键 → 结束任务
4. 重新运行启动命令

## 验证修复

重启后访问任意电影详情页，评论应该显示正常原文，例如：

**之前（错误）：**
```
出 了 电 影 院，我 的 手 机 就 丢 了。
```

**现在（正确）：**
```
出了电影院，我的手机就丢了。
```

## 技术细节

- **原因**: FTS 数据库的 body 字段存储的是 jieba 分词文本（用于搜索）
- **修复**: `top_comments()` 改为从 CSV 读取原始评论内容
- **文件**: `cine/data.py` 第 190-245 行

## 清理临时文件

```powershell
Remove-Item _tmp_*.py, _tmp_*.json -ErrorAction SilentlyContinue
```

---

**重启后即可看到正确的影评内容！** 
