---
name: cursor-usage
description: 查询 Cursor AI 使用量（Token 消耗、费用统计）。当用户说"查 Cursor 用量"、"Cursor usage"、"Cursor token 统计"、"我的 Cursor 用了多少"、"Cursor 费用查询"时使用此技能。也适用于"把 Cursor 用量做成 Skill" 等请求。
---

# Cursor Usage Skill

查询用户在指定时间范围内的 Cursor AI 使用量，按模型分类统计 Token 消耗和费用。

## 首次配置

### Step 1：获取 curl 命令

1. 登录 [cursor.com](https://cursor.com) 并打开用量页 `https://cursor.com/cn/dashboard/usage`
2. 按 F12 → Network 标签
3. 刷新页面，过滤 `get-filtered-usage-events`
4. 点开该请求 → 右键 → Copy → **Copy as cURL (bash)**

### Step 2：解析配置（二选一）

**方式 A：本地脚本（推荐，离线、不依赖 AI）**

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/extract_from_curl.py
# 粘贴 curl 命令，按 Ctrl+D 结束输入
```

脚本会自动从 Cookie 和请求体中提取所有必要字段（包括正确的**数字格式** `team_id` / `user_id`），写入 `config.json`。

**方式 B：交给 AI**

```
帮我解析这个 curl 并配置 cursor-usage skill：
<粘贴你的 curl 命令>
```

### Step 3：验证

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --start 2026-05-01 --end 2026-05-21
```

---

## 手动配置（备选）

如果自动解析失败，编辑配置文件：

```bash
open ~/.openclaw/skills/cursor-usage/config.json
```

| 字段 | 说明 | 来源 |
|------|------|------|
| `workos_session_token` | 认证 Token（URL 解码后） | Cookie: `WorkosCursorSessionToken` |
| `workos_id` | WorkOS ID | Cookie: `workos_id` |
| `team_id` | 团队 ID（**数字**） | 请求体 `teamId` |
| `user_id` | 用户 ID（**数字**） | 请求体 `userId` |
| `cursor_anonymous_id` | 匿名 ID（可选） | Cookie: `cursor_anonymous_id` |
| `statsig_stable_id` | Statsig ID（可选） | Cookie: `statsig_stable_id` |

> ⚠️ `team_id` 和 `user_id` 必须是**纯数字**（如 `14351401`），不是字符串格式（如 `user_01HR84...`）。脚本会做严格校验，非数字直接报错退出。

---

## 查询命令

```bash
# 默认查最近 30 天（本地时区）
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py

# 指定日期范围
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --start 2026-05-01 --end 2026-05-21

# JSON 输出（适合 pipeline / 二次处理）
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --json

# 调试模式（打印分页进度和原始返回）
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --debug
```

脚本会**自动分页**拉取所有事件，并在数据不完整时给出警告。

---

## Token 计算方式

每个事件的总 Token = `inputTokens + cacheWriteTokens + cacheReadTokens + outputTokens`

四类 token 在 Cursor 的计费模型中是并列字段：
- `inputTokens` 未命中缓存的输入
- `cacheWriteTokens` 写入缓存的输入
- `cacheReadTokens` 命中缓存的输入
- `outputTokens` 模型输出

费用以接口返回的 `chargedCents` 为准（单位：美分）。

---

## 常见问题

**Q: 返回 401 Unauthorized？**
→ Cookie 已过期，重新登录 cursor.com 并复制新的 curl 命令，再跑一次 `extract_from_curl.py`。

**Q: 报错 "team_id / user_id 必须是纯数字"？**
→ 你 Cookie 里拿到的是字符串格式 ID。确保 curl 命令包含完整的请求体（含数字 `teamId` / `userId`），重新运行 `extract_from_curl.py`。

**Q: 数据不全（看到 "数据不完整：缺少 N 条事件"）？**
→ 脚本已自动分页（默认上限 50 页 × 500 条）。若仍不全，可加大 `--max-pages` 或缩小时间范围。

**Q: 想重新配置？**
→ 删除 `~/.openclaw/skills/cursor-usage/config.json` 后重新走配置流程。

---

## 安全提示

`config.json` 包含**有效的 Cursor 会话 Token**，请勿提交到 git 或共享给他人。如果你把 `~/.openclaw/` 纳入版本控制，记得把 `config.json` 加入 `.gitignore`。
