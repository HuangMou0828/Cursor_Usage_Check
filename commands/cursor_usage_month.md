---
description: 查询 Cursor AI 本月使用量（1 日至今）
allowed-tools: Bash(python3:*)
---

请执行以下命令查询本月（1 日至今）Cursor 用量，然后用简洁的中文总结输出（按模型分类列出 Token 与费用，并给出总计；如果使用了多个模型，请按总 Token 降序排列）：

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/query_usage.py --preset month
```
