---
description: 查询 Cursor AI 今日使用量（Token + 费用）
allowed-tools: Bash(python3:*)
---

请执行以下命令查询今日 Cursor 用量，然后用简洁的中文总结输出（突出总 Token、总费用、使用的模型）：

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --preset today
```
