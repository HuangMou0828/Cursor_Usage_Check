---
description: 查询 Cursor AI 本周使用量（周一至今）
allowed-tools: Bash(python3:*)
---

请执行以下命令查询本周（周一至今）Cursor 用量，然后用简洁的中文总结输出（按模型分类列出 Token 与费用，并给出总计）：

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --preset week
```
