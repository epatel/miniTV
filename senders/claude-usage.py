#!/usr/bin/env python3
"""Send Claude Code usage (5h window) to miniTV display.

Reads local JSONL files from ~/.claude/projects/ — no API calls needed.
Based on geekmagic-stats/claude_monitor.py collection logic.

Usage: python3 claude-usage.py [--plan max5|pro|max20] [--mqtt host] [url]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from minitv import send, add_display_args, display_from_args

INTERVAL = 30  # seconds

PLAN_LIMITS = {
    "pro":   {"tokens": 19_000,  "messages": 250},
    "max5":  {"tokens": 88_000,  "messages": 1_000},
    "max20": {"tokens": 220_000, "messages": 2_000},
}



def format_k(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def format_duration(minutes):
    if minutes is None:
        return "--"
    total = max(0, round(minutes))
    h = total // 60
    m = total % 60
    if h == 0:
        return f"{m}m"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


def collect_usage(plan):
    limits = PLAN_LIMITS.get(plan)
    if not limits:
        return None

    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None

    now = datetime.now(timezone.utc)

    entries = []
    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        for jsonl_file in proj_dir.glob("*.jsonl"):
            try:
                if jsonl_file.stat().st_mtime < (now - timedelta(hours=24)).timestamp():
                    continue
                with open(jsonl_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            ts_str = entry.get("timestamp", "")
                            if not isinstance(ts_str, str) or not ts_str:
                                continue
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            entries.append((ts, entry))
                        except Exception:
                            continue
            except Exception:
                continue

    if not entries:
        return None

    entries.sort(key=lambda x: x[0])

    # Group into 5h blocks
    blocks = []
    current_block = None
    for ts, entry in entries:
        if current_block is None:
            bs = ts.replace(minute=0, second=0, microsecond=0)
            current_block = (bs, bs + timedelta(hours=5), [(ts, entry)])
        elif ts >= current_block[1]:
            blocks.append(current_block)
            bs = ts.replace(minute=0, second=0, microsecond=0)
            current_block = (bs, bs + timedelta(hours=5), [(ts, entry)])
        else:
            current_block[2].append((ts, entry))
    if current_block:
        blocks.append(current_block)

    # Find active block
    active = None
    for block in reversed(blocks):
        if block[1] > now:
            active = block
            break
    if not active:
        return None

    _, block_end, block_entries = active
    total_input = total_output = total_cache_read = total_cache_create = 0
    total_messages = 0
    session_ids = set()
    model_counts = {}

    for ts, entry in block_entries:
        sid = entry.get("sessionId")
        if sid:
            session_ids.add(sid)
        if entry.get("type") == "user":
            total_messages += 1
        if entry.get("type") == "assistant":
            msg = entry.get("message", {})
            usage = msg.get("usage", {})
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)
            total_cache_read += usage.get("cache_read_input_tokens", 0)
            total_cache_create += usage.get("cache_creation_input_tokens", 0)
            model = msg.get("model", "")
            if model:
                model_counts[model] = model_counts.get(model, 0) + 1

    total_tokens = total_input + total_output
    total_all_input = total_input + total_cache_read + total_cache_create
    token_limit = limits["tokens"]
    msg_limit = limits["messages"]

    return {
        "tokens_used": total_tokens,
        "tokens_limit": token_limit,
        "tokens_pct": min(100, total_tokens / token_limit * 100) if token_limit else 0,
        "messages_used": total_messages,
        "messages_limit": msg_limit,
        "messages_pct": min(100, total_messages / msg_limit * 100) if msg_limit else 0,
        "sessions": len(session_ids),
        "model": max(model_counts, key=model_counts.get) if model_counts else None,
        "reset_min": max(0, (block_end - datetime.now(timezone.utc)).total_seconds() / 60),
        "cache_pct": total_cache_read / total_all_input * 100 if total_all_input > 0 else 0,
    }


def bar_color(pct):
    if pct >= 85:
        return "#EF4444"
    if pct >= 60:
        return "#EAB308"
    return "#3B82F6"


def build_display(usage, plan):
    if not usage:
        return {
            "bg": "#0C0C10",
            "items": [
                {"type": "text", "x": 120, "y": 110, "text": "No usage data",
                 "size": 2, "color": "#888888", "align": "center"}
            ]
        }

    tk_pct = usage["tokens_pct"]
    msg_pct = usage["messages_pct"]
    tk_color = bar_color(tk_pct)
    msg_color = bar_color(msg_pct)
    model_short = usage["model"].split("claude-")[-1] if usage["model"] else "—"

    items = [
        # Header
        {"type": "rect", "x": 0, "y": 0, "w": 240, "h": 26, "color": "#16162A", "fill": True},
        {"type": "text", "x": 120, "y": 5, "text": f"CLAUDE {plan.upper()}", "size": 2,
         "color": "#D4A574", "align": "center"},

        # Tokens section
        {"type": "rect", "x": 8, "y": 32, "w": 224, "h": 48, "color": "#16161E", "fill": True},
        {"type": "text", "x": 14, "y": 35, "text": "TOKENS", "size": 1, "color": "#717178"},
        {"type": "text", "x": 226, "y": 35, "text": f"{tk_pct:.0f}%", "size": 1,
         "color": tk_color, "align": "right", "maxWidth": "100%"},
        {"type": "progress", "x": 14, "y": 48, "w": 212, "h": 8,
         "value": min(tk_pct / 100, 1.0), "color": tk_color, "bg": "#282832", "border": "#282832"},
        {"type": "text", "x": 14, "y": 60, "text": f"{format_k(usage['tokens_used'])}/{format_k(usage['tokens_limit'])}",
         "size": 1, "color": "#A1A1AA", "maxWidth": "000.0K/000.0K"},

        # Messages section
        {"type": "rect", "x": 8, "y": 86, "w": 224, "h": 48, "color": "#16161E", "fill": True},
        {"type": "text", "x": 14, "y": 89, "text": "MESSAGES", "size": 1, "color": "#717178"},
        {"type": "text", "x": 226, "y": 89, "text": f"{msg_pct:.0f}%", "size": 1,
         "color": msg_color, "align": "right", "maxWidth": "100%"},
        {"type": "progress", "x": 14, "y": 102, "w": 212, "h": 8,
         "value": min(msg_pct / 100, 1.0), "color": msg_color, "bg": "#282832", "border": "#282832"},
        {"type": "text", "x": 14, "y": 114, "text": f"{usage['messages_used']}/{usage['messages_limit']}",
         "size": 1, "color": "#A1A1AA", "maxWidth": "0000/0000"},

        # Info grid - 2x2
        # Sessions
        {"type": "rect", "x": 8, "y": 140, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 14, "y": 143, "text": "Sessions", "size": 1, "color": "#717178"},
        {"type": "text", "x": 14, "y": 156, "text": str(usage["sessions"]), "size": 1,
         "color": "#F0F0F5", "maxWidth": "000"},

        # Model
        {"type": "rect", "x": 122, "y": 140, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 128, "y": 143, "text": "Model", "size": 1, "color": "#717178"},
        {"type": "text", "x": 128, "y": 156, "text": model_short, "size": 1,
         "color": "#F0F0F5", "maxWidth": "opus-4-6[1m]"},

        # Reset
        {"type": "rect", "x": 8, "y": 178, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 14, "y": 181, "text": "Resets in", "size": 1, "color": "#717178"},
        {"type": "text", "x": 14, "y": 194, "text": format_duration(usage["reset_min"]), "size": 1,
         "color": "#F0F0F5", "maxWidth": "00h 00m"},

        # Cache
        {"type": "rect", "x": 122, "y": 178, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 128, "y": 181, "text": "Cache", "size": 1, "color": "#717178"},
        {"type": "text", "x": 128, "y": 194, "text": f"{usage['cache_pct']:.0f}%", "size": 1,
         "color": "#F0F0F5", "maxWidth": "100%"},

        # Timestamp
        {"type": "text", "x": 120, "y": 222, "text": datetime.now().strftime("%H:%M:%S"),
         "size": 1, "color": "#4A4A52", "align": "center", "maxWidth": "00:00:00"},
    ]

    return {"bg": "#0C0C10", "items": items}


def fingerprint(usage):
    if not usage:
        return None
    return (
        round(usage["tokens_pct"]),
        usage["tokens_used"],
        round(usage["messages_pct"]),
        usage["messages_used"],
        usage["sessions"],
        usage["model"],
        round(usage["cache_pct"]),
        round(usage["reset_min"]),
    )


def main():
    parser = argparse.ArgumentParser(description="Claude Code usage monitor for miniTV")
    parser.add_argument("--plan", choices=PLAN_LIMITS.keys(), default="max5")
    add_display_args(parser)
    args = parser.parse_args()

    display = display_from_args(args)
    print(f"Plan: {args.plan} | Target: {display.describe()} | Interval: {INTERVAL}s (Ctrl+C to stop)")

    prev_fp = "INITIAL"  # ensure first send always happens
    while True:
        usage = collect_usage(args.plan)
        fp = fingerprint(usage)
        if fp != prev_fp:
            payload = build_display(usage, args.plan)
            display.send(payload)
            prev_fp = fp
            if usage:
                print(f"Tokens: {usage['tokens_pct']:.0f}% | Msgs: {usage['messages_used']}/{usage['messages_limit']} | Reset: {format_duration(usage['reset_min'])}")
            else:
                print("No active usage block")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
