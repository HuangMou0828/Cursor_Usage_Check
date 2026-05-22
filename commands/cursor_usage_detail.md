---
description: 对比本月与上月 Cursor 用量（环比变化、百分比、绝对差值）
allowed-tools: Bash(python3:*)
---

请执行以下命令计算 Cursor 月度环比详情，然后用简洁中文总结环比变化（突出：本月 vs 上月同期的 Token / 费用增减、百分比、趋势判断）：

```bash
python3 ~/.openclaw/skills/cursor-usage/scripts/compare_usage.py
```

说明：
- 「本月」= 本月 1 日 ~ 今天
- 「上月同期」= 上月 1 日 ~ 上月同一日（更公平的对比基准，因为本月尚未结束）
- 「上月全月」= 上月 1 日 ~ 上月最后一天（仅供参考）
- 环比涨跌以「上月同期」为基准
