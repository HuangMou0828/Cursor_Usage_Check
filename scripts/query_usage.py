#!/usr/bin/env python3
"""
Cursor Usage Query Tool
查询 Cursor AI 使用量，按模型分类统计 Token 和费用
"""

import argparse
import json
import os
import ssl
import sys
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import certifi
except ImportError:
    certifi = None

CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "config.json")
)
EXTRACT_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "extract_from_curl.py")
)
API_URL = "https://cursor.com/api/dashboard/get-filtered-usage-events"


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def ensure_config():
    """校验必需配置存在；team_id / user_id 必须为纯数字。"""
    config = load_config()
    required = ["workos_session_token", "team_id", "user_id"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        print("❌ 缺少配置，请先生成 config.json：")
        print(f"  python3 {EXTRACT_SCRIPT}")
        print(f"  （粘贴 cursor.com 用量页面的 curl 命令，Ctrl+D 结束）")
        print()
        print(f"或手动编辑: {CONFIG_PATH}")
        print("必填字段：")
        print("  workos_session_token  - Cookie: WorkosCursorSessionToken（URL 解码后）")
        print("  team_id               - 请求体 teamId（数字）")
        print("  user_id               - 请求体 userId（数字，不是 user_01HR... 字符串）")
        sys.exit(1)

    for key in ("team_id", "user_id"):
        val = str(config[key])
        if not val.isdigit():
            print(f"❌ 配置项 {key} 必须是纯数字（当前值: {val[:30]}）")
            print(f"   请重新运行: python3 {EXTRACT_SCRIPT}")
            sys.exit(1)
    return config


def ts_to_datetime(ts):
    return datetime.fromtimestamp(int(ts) / 1000)


def parse_date(date_str):
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {date_str}")


def resolve_preset(preset, now):
    """根据预设关键字返回 (start_date, end_date, label)，均为本地 naive datetime。"""
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    if preset == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, end, "今日"
    if preset == "week":
        start_day = now - timedelta(days=now.weekday())
        start = start_day.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, end, "本周（周一至今）"
    if preset == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, end, "本月（1日至今）"
    raise ValueError(f"未知 preset: {preset}（支持 today/week/month）")


def _build_request(start_ts, end_ts, page, page_size, config):
    cookies = [
        f"WorkosCursorSessionToken={config['workos_session_token']}",
        f"workos_id={config.get('workos_id', '')}",
        f"team_id={config['team_id']}",
        f"cursor-web-target-synced-user={config['user_id']}",
        f"cursor_anonymous_id={config.get('cursor_anonymous_id', '')}",
        f"statsig_stable_id={config.get('statsig_stable_id', '')}",
    ]
    cookie_str = "; ".join(c for c in cookies if not c.endswith("="))

    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "origin": "https://cursor.com",
        "referer": "https://cursor.com/cn/dashboard/usage",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        ),
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

    body = {
        "teamId": int(config["team_id"]),
        "userId": int(config["user_id"]),
        "startDate": str(start_ts),
        "endDate": str(end_ts),
        "page": page,
        "pageSize": page_size,
    }

    req = Request(API_URL, data=json.dumps(body).encode(), headers=headers)
    req.add_header("Cookie", cookie_str)
    return req


def _do_request(req, timeout=30):
    if certifi:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode())
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def query_usage(start_date, end_date, config, page_size=500, debug=False, max_pages=50):
    """分页拉取所有 events，返回合并后的 (events, total_count, raw_pages)。"""
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    all_events = []
    total_count = 0
    raw_pages = []

    for page in range(1, max_pages + 1):
        req = _build_request(start_ts, end_ts, page, page_size, config)
        try:
            data = _do_request(req)
        except HTTPError as e:
            print(f"❌ HTTP Error: {e.code} {e.reason}")
            try:
                print(f"   响应: {json.loads(e.read().decode())}")
            except Exception:
                print(f"   响应: {e.read().decode()[:500]}")
            sys.exit(1)
        except URLError as e:
            print(f"❌ 网络错误: {e.reason}")
            sys.exit(1)

        raw_pages.append(data)
        events = data.get("usageEventsDisplay", []) or []
        total_count = data.get("usageEventsDisplayCount", total_count)
        all_events.extend(events)

        if debug:
            print(f"[debug] page={page} got={len(events)} accumulated={len(all_events)} total={total_count}")

        if len(events) < page_size:
            break
        if total_count and len(all_events) >= total_count:
            break
    else:
        print(f"⚠️  达到最大分页数 {max_pages}，可能仍有未拉取数据")

    return all_events, total_count, raw_pages


def aggregate(events):
    """聚合 events 为 (models, totals) 两个 dict。"""
    models = {}
    for e in events:
        model = e.get("model", "unknown")
        tu = e.get("tokenUsage", {}) or {}
        input_tokens = tu.get("inputTokens", 0)
        cache_write = tu.get("cacheWriteTokens", 0)
        cache_read = tu.get("cacheReadTokens", 0)
        output = tu.get("outputTokens", 0)
        total_tokens = input_tokens + cache_write + cache_read + output

        m = models.setdefault(
            model,
            {"count": 0, "input": 0, "cacheWrite": 0, "cacheRead": 0,
             "output": 0, "total_tokens": 0, "charged": 0},
        )
        m["count"] += 1
        m["input"] += input_tokens
        m["cacheWrite"] += cache_write
        m["cacheRead"] += cache_read
        m["output"] += output
        m["total_tokens"] += total_tokens
        m["charged"] += e.get("chargedCents", 0)

    totals = {
        "input": sum(m["input"] for m in models.values()),
        "cacheWrite": sum(m["cacheWrite"] for m in models.values()),
        "cacheRead": sum(m["cacheRead"] for m in models.values()),
        "output": sum(m["output"] for m in models.values()),
        "total_tokens": sum(m["total_tokens"] for m in models.values()),
        "charged": sum(m["charged"] for m in models.values()),
        "count": sum(m["count"] for m in models.values()),
    }
    return models, totals


def print_summary(events, total_count, start_date, end_date):
    if not events:
        print("⚠️  未查询到数据，请检查时间范围或凭证是否正确")
        return

    timestamps = [int(e.get("timestamp", 0)) for e in events if e.get("timestamp")]
    span_start = ts_to_datetime(min(timestamps)) if timestamps else start_date
    span_end = ts_to_datetime(max(timestamps)) if timestamps else end_date

    models, totals = aggregate(events)

    print()
    print("=" * 60)
    print("  Cursor 使用量报告")
    print("=" * 60)
    print(f"  查询窗口: {start_date.strftime('%Y-%m-%d %H:%M')} ~ {end_date.strftime('%Y-%m-%d %H:%M')}")
    print(f"  数据范围: {span_start.strftime('%Y-%m-%d')} ~ {span_end.strftime('%Y-%m-%d')}")
    print(f"  事件数:   {len(events)} / {total_count or len(events)} 已拉取")
    if total_count and len(events) < total_count:
        print(f"  ⚠️  数据不完整：缺少 {total_count - len(events)} 条事件")
    print()

    print("=== 按模型分类 ===")
    for model, s in sorted(models.items(), key=lambda x: -x[1]["total_tokens"]):
        print(f"\n  [{model}]")
        print(f"    次数:        {s['count']}")
        print(f"    input:     {s['input']:>16,}")
        print(f"    cacheWrite:{s['cacheWrite']:>16,}")
        print(f"    cacheRead: {s['cacheRead']:>16,}")
        print(f"    output:    {s['output']:>16,}")
        print(f"    总Token:   {s['total_tokens']:>16,}")
        print(f"    费用:      ${s['charged']/100:.2f}")

    print()
    print("=" * 60)
    print("  合计")
    print("=" * 60)
    print(f"  input:     {totals['input']:>16,}")
    print(f"  cacheWrite:{totals['cacheWrite']:>16,}")
    print(f"  cacheRead: {totals['cacheRead']:>16,}")
    print(f"  output:    {totals['output']:>16,}")
    print(f"  总Token:   {totals['total_tokens']:>16,}")
    print(f"  总费用:    ${totals['charged']/100:.2f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Cursor 使用量查询工具")
    parser.add_argument("--start", default="30 days ago", help="起始日期 YYYY-MM-DD（本地时区）")
    parser.add_argument("--end", default="today", help="截止日期 YYYY-MM-DD（本地时区）")
    parser.add_argument(
        "--preset",
        choices=["today", "week", "month"],
        help="预设时间窗口；指定时会覆盖 --start / --end",
    )
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--max-pages", type=int, default=50, help="最大分页数，防御性上限")
    parser.add_argument("--debug", action="store_true", help="打印分页进度并输出原始数据")
    parser.add_argument("--json", dest="as_json", action="store_true", help="以 JSON 输出聚合结果")
    args = parser.parse_args()

    config = ensure_config()

    now = datetime.now()
    preset_label = None

    if args.preset:
        start_date, end_date, preset_label = resolve_preset(args.preset, now)
    else:
        if args.start == "30 days ago":
            start_date = now - timedelta(days=30)
        else:
            start_date = parse_date(args.start)
            if " " not in args.start and ":" not in args.start:
                start_date = start_date.replace(hour=0, minute=0, second=0)

        if args.end == "today":
            end_date = now
        else:
            end_date = parse_date(args.end)
            if " " not in args.end and ":" not in args.end:
                end_date = end_date.replace(hour=23, minute=59, second=59)

    if not args.as_json:
        prefix = f"[{preset_label}] " if preset_label else ""
        print(f"{prefix}查询时间范围: {start_date.strftime('%Y-%m-%d %H:%M')} ~ {end_date.strftime('%Y-%m-%d %H:%M')}")

    events, total_count, raw_pages = query_usage(
        start_date, end_date, config,
        page_size=args.page_size, debug=args.debug, max_pages=args.max_pages,
    )

    if args.debug and not args.as_json:
        print(json.dumps(raw_pages, indent=2, ensure_ascii=False))
        return

    if args.as_json:
        models, totals = aggregate(events)
        out = {
            "window": {
                "start": start_date.isoformat(timespec="minutes"),
                "end": end_date.isoformat(timespec="minutes"),
            },
            "event_count": len(events),
            "event_count_total": total_count or len(events),
            "incomplete": bool(total_count and len(events) < total_count),
            "totals": totals,
            "by_model": models,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print_summary(events, total_count, start_date, end_date)


if __name__ == "__main__":
    main()
