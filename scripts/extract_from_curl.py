#!/usr/bin/env python3
"""
从 curl 命令中提取 Cursor API 配置
用法: python3 extract_from_curl.py
然后粘贴 curl 命令，按 Ctrl+D 结束输入
"""
import json
import os
import re
import sys
import urllib.parse


def _extract_quoted_values(curl_cmd: str, flags: tuple) -> list:
    """从 curl 命令里提取指定 flag 后面的引号包裹值（支持 ' " 和 $'...' ）。"""
    values = []
    for flag in flags:
        pattern = rf"{re.escape(flag)}\s+(\$?'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
        for m in re.finditer(pattern, curl_cmd):
            raw = m.group(1)
            if raw.startswith("$'") and raw.endswith("'"):
                inner = raw[2:-1]
            elif raw.startswith("'") and raw.endswith("'"):
                inner = raw[1:-1]
            else:
                inner = raw[1:-1]
            inner = inner.encode("utf-8").decode("unicode_escape", errors="ignore")
            values.append(inner)
    return values


def _find_data_raw_body(curl_cmd: str) -> str:
    """定位 --data-raw / --data / -d 后面的 JSON body，使用括号配对避免正则脆弱。"""
    for flag in ("--data-raw", "--data-binary", "--data", "-d"):
        idx = 0
        while True:
            pos = curl_cmd.find(flag, idx)
            if pos == -1:
                break
            idx = pos + len(flag)
            tail = curl_cmd[idx:].lstrip()
            if not tail:
                continue
            start = tail.find("{")
            if start == -1 or start > 5:
                continue
            depth = 0
            for i, c in enumerate(tail[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return tail[start : i + 1]
    return ""


def parse_curl(curl_cmd: str) -> dict:
    config = {}

    url_match = re.search(r"['\"](https?://[^'\"]+)['\"]", curl_cmd)
    if url_match:
        config["api_url"] = url_match.group(1).split("?")[0]

    cookie_pairs = {}

    for h in _extract_quoted_values(curl_cmd, ("-H", "--header")):
        if ":" not in h:
            continue
        key, val = h.split(":", 1)
        if key.strip().lower() != "cookie":
            continue
        for part in val.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookie_pairs[k.strip()] = v.strip()

    for cookie_str in _extract_quoted_values(curl_cmd, ("-b", "--cookie")):
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookie_pairs[k.strip()] = v.strip()

    body_str = _find_data_raw_body(curl_cmd)
    if body_str:
        cleaned = body_str.replace('\\"', '"').replace("\\'", "'")
        try:
            config["_body"] = json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    def decode_token(s: str) -> str:
        try:
            return urllib.parse.unquote(s)
        except Exception:
            return s

    config["workos_session_token"] = decode_token(cookie_pairs.get("WorkosCursorSessionToken", ""))
    config["workos_id"] = cookie_pairs.get("workos_id", "")
    config["team_id"] = cookie_pairs.get("team_id", "")
    config["user_id"] = cookie_pairs.get("cursor-web-target-synced-user", "")
    config["cursor_anonymous_id"] = cookie_pairs.get("cursor_anonymous_id", "")
    config["statsig_stable_id"] = cookie_pairs.get("statsig_stable_id", "")

    body = config.get("_body", {})
    if body:
        config["body_team_id"] = str(body.get("teamId", ""))
        config["body_user_id"] = str(body.get("userId", ""))
        config["body_start_date"] = body.get("startDate", "")
        config["body_end_date"] = body.get("endDate", "")

    return config


def print_config(config: dict):
    print("\n=== 提取到的配置 ===\n")

    important = [
        ("workos_session_token", "WorkosCursorSessionToken（认证 Token）"),
        ("workos_id", "workos_id"),
        ("team_id", "team_id（来自 Cookie）"),
        ("user_id", "cursor-web-target-synced-user（来自 Cookie）"),
        ("cursor_anonymous_id", "cursor_anonymous_id"),
        ("statsig_stable_id", "statsig_stable_id"),
    ]

    for key, _label in important:
        val = config.get(key, "")
        if len(val) > 60:
            print(f"  {key}: {val[:20]}...{val[-15:]}")
        elif val:
            print(f"  {key}: {val}")
        else:
            print(f"  {key}: (未找到)")

    print()
    if config.get("body_team_id"):
        print(f"  body_team_id:  {config['body_team_id']} ← 请求体中的 teamId（优先使用）")
    if config.get("body_user_id"):
        print(f"  body_user_id:  {config['body_user_id']} ← 请求体中的 userId（优先使用）")
    if config.get("body_start_date"):
        print(f"  start_date:    {config['body_start_date']}")
    if config.get("body_end_date"):
        print(f"  end_date:      {config['body_end_date']}")

    print()


def save_config(config: dict, path: str):
    save_data = {
        "workos_session_token": config.get("workos_session_token", ""),
        "workos_id": config.get("workos_id", ""),
        "team_id": config.get("body_team_id") or config.get("team_id", ""),
        "user_id": config.get("body_user_id") or config.get("user_id", ""),
        "cursor_anonymous_id": config.get("cursor_anonymous_id", ""),
        "statsig_stable_id": config.get("statsig_stable_id", ""),
    }
    save_data = {k: v for k, v in save_data.items() if v}

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(save_data, f, indent=2)
    print(f"\n✅ 配置已保存到: {path}")


def main():
    print("请粘贴 curl 命令（粘贴完成后按 Ctrl+D 结束输入）：")
    curl_cmd = sys.stdin.read().strip()
    curl_cmd = " ".join(line.strip() for line in curl_cmd.splitlines() if line.strip())

    if not curl_cmd:
        print("未输入 curl 命令")
        sys.exit(1)

    config = parse_curl(curl_cmd)
    print_config(config)

    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "config.json")
    )
    save_config(config, config_path)

    uid = config.get("body_user_id") or config.get("user_id", "")
    if uid and not uid.isdigit():
        print(f"\n⚠️  user_id 不是纯数字（当前值: {uid[:30]}...）")
        print("   查询会失败。请确保 curl 命令包含完整的请求体（含 userId）。")


if __name__ == "__main__":
    main()
