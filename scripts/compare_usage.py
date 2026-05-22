#!/usr/bin/env python3
"""
Cursor Usage Compare Tool
对比本月与上月用量：本月（1日~今天） vs 上月同期（1日~同一日） + 上月全月参考。
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

from query_usage import aggregate, ensure_config, query_usage


def month_ranges(now):
    """计算三段日期窗口（均为本地 naive datetime）：
    - this_month:        本月 1 日 00:00 ~ 现在
    - last_month_same:   上月 1 日 ~ 上月同期日（应对短月：min(today.day, 上月天数)）
    - last_month_full:   上月 1 日 ~ 上月最后一天 23:59
    """
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_full_end = this_start - timedelta(seconds=1)
    last_start = last_full_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    same_day = min(now.day, last_full_end.day)
    last_same_end = last_start.replace(
        day=same_day, hour=23, minute=59, second=59, microsecond=0
    )

    return {
        "this_month": (this_start, now, f"本月（{this_start.month}月 1日 ~ {now.day}日）"),
        "last_month_same": (last_start, last_same_end,
                            f"上月同期（{last_start.month}月 1日 ~ {same_day}日）"),
        "last_month_full": (last_start, last_full_end,
                            f"上月全月（{last_start.month}月 1日 ~ {last_full_end.day}日）"),
    }


def fetch_segment(start, end, label, config, page_size, max_pages, verbose=True):
    """拉取一段时间窗口的数据并聚合，返回 (events, totals)。"""
    if verbose:
        print(f"→ 正在拉取 [{label}] {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')} ...")
    events, _total, _raw = query_usage(
        start, end, config, page_size=page_size, max_pages=max_pages, debug=False
    )
    _models, totals = aggregate(events)
    return events, totals


def pct_change(curr, prev):
    """返回 (绝对差值, 百分比字符串)。prev=0 时百分比标为 '∞%' 或 'N/A'。"""
    delta = curr - prev
    if prev == 0:
        pct = "N/A" if curr == 0 else "∞%"
    else:
        pct = f"{delta / prev * 100:+.2f}%"
    return delta, pct


def fmt_tokens(n):
    return f"{n:,}"


def fmt_cents(c):
    return f"${c / 100:.2f}"


def render_text(now, segments):
    this_totals = segments["this_month"]["totals"]
    last_same_totals = segments["last_month_same"]["totals"]
    last_full_totals = segments["last_month_full"]["totals"]

    print()
    print("=" * 64)
    print(f"  Cursor 月度环比报告  ({now.strftime('%Y-%m-%d %H:%M')} 本地时间)")
    print("=" * 64)

    for key in ("this_month", "last_month_same", "last_month_full"):
        seg = segments[key]
        t = seg["totals"]
        print()
        print(f"  [{seg['label']}]")
        print(f"    事件数:  {t['count']}")
        print(f"    总Token: {fmt_tokens(t['total_tokens']):>16}")
        print(f"    总费用:  {fmt_cents(t['charged']):>16}")

    tok_delta, tok_pct = pct_change(this_totals["total_tokens"], last_same_totals["total_tokens"])
    cnt_delta, cnt_pct = pct_change(this_totals["count"], last_same_totals["count"])
    fee_delta, fee_pct = pct_change(this_totals["charged"], last_same_totals["charged"])

    arrow_tok = "📈" if tok_delta > 0 else ("📉" if tok_delta < 0 else "➖")
    arrow_fee = "📈" if fee_delta > 0 else ("📉" if fee_delta < 0 else "➖")

    print()
    print("=" * 64)
    print("  环比变化（本月 vs 上月同期）")
    print("=" * 64)
    print(f"  {arrow_tok} Token:  {tok_pct:>10}   "
          f"({'+' if tok_delta >= 0 else ''}{fmt_tokens(tok_delta)})")
    print(f"  {arrow_fee} 费用:   {fee_pct:>10}   "
          f"({'+' if fee_delta >= 0 else ''}{fmt_cents(fee_delta)})")
    print(f"     事件数: {cnt_pct:>10}   "
          f"({'+' if cnt_delta >= 0 else ''}{cnt_delta})")

    full_tok_delta, full_tok_pct = pct_change(this_totals["total_tokens"], last_full_totals["total_tokens"])
    full_fee_delta, full_fee_pct = pct_change(this_totals["charged"], last_full_totals["charged"])
    print()
    print("  参考：本月 vs 上月全月（仅供参考，本月未结束）")
    print(f"     Token:  {full_tok_pct:>10}   "
          f"({'+' if full_tok_delta >= 0 else ''}{fmt_tokens(full_tok_delta)})")
    print(f"     费用:   {full_fee_pct:>10}   "
          f"({'+' if full_fee_delta >= 0 else ''}{fmt_cents(full_fee_delta)})")
    print()


def render_json(now, segments):
    this_t = segments["this_month"]["totals"]
    same_t = segments["last_month_same"]["totals"]
    full_t = segments["last_month_full"]["totals"]

    tok_delta, tok_pct = pct_change(this_t["total_tokens"], same_t["total_tokens"])
    fee_delta, _ = pct_change(this_t["charged"], same_t["charged"])
    cnt_delta, _ = pct_change(this_t["count"], same_t["count"])

    out = {
        "generated_at": now.isoformat(timespec="minutes"),
        "segments": {
            key: {
                "label": seg["label"],
                "window": {
                    "start": seg["start"].isoformat(timespec="minutes"),
                    "end": seg["end"].isoformat(timespec="minutes"),
                },
                "totals": seg["totals"],
            }
            for key, seg in segments.items()
        },
        "mom_same_period": {
            "token_delta": tok_delta,
            "token_pct": tok_pct,
            "fee_delta_cents": fee_delta,
            "count_delta": cnt_delta,
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Cursor 月度环比工具")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    config = ensure_config()
    now = datetime.now()
    ranges = month_ranges(now)

    verbose = not args.as_json
    segments = {}
    for key, (start, end, label) in ranges.items():
        _events, totals = fetch_segment(
            start, end, label, config, args.page_size, args.max_pages, verbose=verbose
        )
        segments[key] = {"label": label, "start": start, "end": end, "totals": totals}

    if args.as_json:
        render_json(now, segments)
    else:
        render_text(now, segments)


if __name__ == "__main__":
    main()
