# Cursor Usage Check

查询 Cursor AI 在指定时间范围内的使用量，按模型分类统计 Token 消耗和费用。

支持作为 [openclaw](https://github.com/openclaw) / Claude Skills 的 Skill 直接调用，也可以单独作为 CLI 工具使用。

---

## ✨ 功能

- 📊 按模型分类统计 Token 消耗（`inputTokens` / `cacheWriteTokens` / `cacheReadTokens` / `outputTokens`）
- 💰 汇总 Cursor 计费金额（来自接口返回的 `chargedCents`）
- 📅 灵活的时间窗口（默认最近 30 天，本地时区）
- 🔄 自动分页（默认上限 50 页 × 500 条，覆盖大时间窗口）
- 🧾 支持 JSON 输出，方便接 pipeline / webhook
- 🤖 提供 curl 自动解析脚本，一次粘贴完成配置

---

## 📦 安装

仅依赖 Python 3 标准库；可选 `certifi` 用于 SSL 证书校验：

```bash
git clone https://github.com/HuangMou0828/Cursor_Usage_Check.git ~/.openclaw/skills/cursor-usage
pip3 install certifi  # 可选
```

> 如果作为 Skill 使用，路径必须是 `~/.openclaw/skills/cursor-usage/`。
> 单独作为 CLI 使用可放在任意位置。

---

## 🚀 首次配置

### Step 1：获取 curl 命令

1. 登录 [cursor.com](https://cursor.com) → 打开用量页 [https://cursor.com/cn/dashboard/usage](https://cursor.com/cn/dashboard/usage)
2. 按 `F12` 打开开发者工具 → `Network` 标签
3. 刷新页面，过滤 `get-filtered-usage-events`
4. 点开该请求 → 右键 → **Copy → Copy as cURL (bash)**

### Step 2：解析配置

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/extract_from_curl.py
# 粘贴 curl 命令，按 Ctrl+D 结束输入
```

脚本会自动：
- 从 Cookie 解析 `WorkosCursorSessionToken`、`workos_id` 等字段
- 从请求体提取**数字格式**的 `teamId` / `userId`（这一步很关键，Cookie 里的 `cursor-web-target-synced-user` 是字符串格式，直接用会 401）
- 写入 `config.json`

### Step 3：验证

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --start 2026-05-01 --end 2026-05-21
```

---

## 🛠️ 使用

```bash
# 默认查最近 30 天
python3 scripts/query_usage.py

# 指定日期范围（本地时区）
python3 scripts/query_usage.py --start 2026-05-01 --end 2026-05-21

# 查今日
python3 scripts/query_usage.py --start 2026-05-22 --end 2026-05-22

# JSON 输出（适合二次处理）
python3 scripts/query_usage.py --json

# 调试（打印分页进度和原始返回）
python3 scripts/query_usage.py --debug

# 自定义分页参数
python3 scripts/query_usage.py --page-size 1000 --max-pages 100
```

### 输出示例

```
============================================================
  Cursor 使用量报告
============================================================
  查询窗口: 2026-05-22 00:00 ~ 2026-05-22 23:59
  数据范围: 2026-05-22 ~ 2026-05-22
  事件数:   13 / 13 已拉取

=== 按模型分类 ===

  [claude-opus-4-7-thinking-high]
    次数:        13
    input:                  110
    cacheWrite:         375,650
    cacheRead:        3,284,683
    output:              47,597
    总Token:          3,708,040
    费用:      $6.11

============================================================
  合计
============================================================
  input:                  110
  cacheWrite:         375,650
  cacheRead: 	      3,284,683
  output:              47,597
  总Token:          3,708,040
  总费用:    $6.11
```

---

## ⚙️ 配置项说明

`config.json` 字段：

| 字段 | 必填 | 说明 | 来源 |
|------|:---:|------|------|
| `workos_session_token` | ✅ | 认证 Token（URL 解码后） | Cookie: `WorkosCursorSessionToken` |
| `team_id` | ✅ | 团队 ID（**纯数字**） | 请求体 `teamId` |
| `user_id` | ✅ | 用户 ID（**纯数字**） | 请求体 `userId` |
| `workos_id` |  | WorkOS ID | Cookie: `workos_id` |
| `cursor_anonymous_id` |  | 匿名 ID | Cookie: `cursor_anonymous_id` |
| `statsig_stable_id` |  | Statsig ID | Cookie: `statsig_stable_id` |

> ⚠️ `team_id` 和 `user_id` **必须是纯数字**（如 `14351401`），不是 `user_01HR84...` 字符串。脚本启动时会严格校验。

参考 `config.json.example`。

---

## 🧮 Token 计算

每个事件的总 Token = `inputTokens + cacheWriteTokens + cacheReadTokens + outputTokens`

四类 token 在 Cursor 的计费模型中是并列字段：

| 字段 | 含义 |
|------|------|
| `inputTokens` | 未命中缓存的输入 |
| `cacheWriteTokens` | 写入缓存的输入 |
| `cacheReadTokens` | 命中缓存的输入 |
| `outputTokens` | 模型输出 |

费用以接口返回的 `chargedCents` 为准（单位：美分）。

---

## 🧩 作为 Skill 使用

本仓库是符合 [Claude Skills](https://www.anthropic.com/claude) 规范的 Skill，可以让支持 Skills 的 AI 客户端直接调用。

触发关键词包括：

- "查 Cursor 用量"
- "Cursor usage / Cursor token 统计"
- "我的 Cursor 用了多少"
- "Cursor 费用查询"

完整说明见 [`SKILL.md`](./SKILL.md)。

---

## ❓ 常见问题

**Q: 返回 `401 Unauthorized`？**
→ Cookie 已过期。重新登录 cursor.com 并复制新的 curl 命令，再跑一次 `extract_from_curl.py`。

**Q: 报错 "team_id / user_id 必须是纯数字"？**
→ 你 Cookie 里拿到的是字符串格式 ID（`user_01HR...`）。确保 curl 命令包含**完整的请求体**（含数字 `teamId` / `userId`），重新运行 `extract_from_curl.py`。

**Q: 输出里看到 "⚠️ 数据不完整：缺少 N 条事件"？**
→ 默认分页上限是 50 页 × 500 条 = 25,000 事件。加大 `--max-pages` 或缩小时间窗口即可。

**Q: 想重新配置？**
→ 删除 `config.json` 后重新走 [首次配置](#-首次配置) 流程。

---

## 🔒 安全提示

- `config.json` 包含**有效的 Cursor 会话 Token**，等同于你的登录态。
- 仓库 `.gitignore` 已默认排除 `config.json`，**请勿移除该条规则**。
- 切勿在 Issue / PR / 截图中粘贴 `config.json` 内容。

---

## 📁 项目结构

```
cursor-usage/
├── SKILL.md                       # Skill 元信息与使用文档
├── README.md                      # 本文件
├── config.json.example            # 配置示例
├── .gitignore
└── scripts/
    ├── extract_from_curl.py       # curl 命令解析器
    └── query_usage.py             # 用量查询主脚本
```

---

## 📄 License

MIT
