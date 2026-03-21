#!/usr/bin/env python3
"""Send macOS system stats (CPU, memory, temperature, network) to miniTV display."""

import subprocess
import time
import json
import sys
from minitv import resolve_url, send

INTERVAL = 2  # seconds

URL = resolve_url(sys.argv[1] if len(sys.argv) > 1 else "http://minitv.local/display")


def get_cpu_count():
    out = subprocess.check_output(["sysctl", "-n", "hw.logicalcpu"], text=True)
    return int(out.strip())


_cpu_count = None


def get_cpu_usage():
    global _cpu_count
    if _cpu_count is None:
        _cpu_count = get_cpu_count()
    out = subprocess.check_output(["ps", "-A", "-o", "%cpu"], text=True)
    total = sum(float(line.strip()) for line in out.strip().split("\n")[1:] if line.strip())
    # ps reports per-core percentages, divide by core count to match Activity Monitor
    return min(total / (100.0 * _cpu_count), 1.0)


def get_memory_usage():
    # Get total physical RAM
    total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())

    out = subprocess.check_output(["vm_stat"], text=True)
    # First line contains page size
    page_size = 4096
    first_line = out.strip().split("\n")[0]
    if "page size of" in first_line:
        page_size = int(first_line.split("page size of")[1].strip().split()[0])

    stats = {}
    for line in out.strip().split("\n")[1:]:
        parts = line.split(":")
        if len(parts) == 2:
            key = parts[0].strip()
            val = parts[1].strip().rstrip(".")
            try:
                stats[key] = int(val)
            except ValueError:
                pass

    # Match Activity Monitor's "Memory Used" = app + wired + compressed
    app = stats.get("Pages active", 0) - stats.get("Pages purgeable", 0)
    wired = stats.get("Pages wired down", 0)
    compressed = stats.get("Pages occupied by compressor", 0)
    used = (app + wired + compressed) * page_size
    if total == 0:
        return 0.0, 0, 0
    return used / total, used, total


def get_temperature():
    try:
        out = subprocess.check_output(
            ["sudo", "powermetrics", "--samplers", "smc", "-i", "1", "-n", "1"],
            text=True, stderr=subprocess.DEVNULL, timeout=5
        )
        for line in out.split("\n"):
            if "CPU die temperature" in line:
                temp = float(line.split(":")[1].strip().split()[0])
                return temp
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
        pass
    return None


def get_network_bytes():
    out = subprocess.check_output(["netstat", "-ib"], text=True)
    lines = out.strip().split("\n")
    total_in = 0
    total_out = 0
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 10 and parts[0].startswith("en"):
            try:
                total_in += int(parts[6])
                total_out += int(parts[9])
            except (ValueError, IndexError):
                pass
    return total_in, total_out


def format_bytes(b):
    if b >= 1_000_000_000:
        return f"{b / 1_000_000_000:.1f}G"
    if b >= 1_000_000:
        return f"{b / 1_000_000:.1f}M"
    if b >= 1_000:
        return f"{b / 1_000:.1f}K"
    return f"{b}B"


def bar_color(value):
    if value > 0.85:
        return "#FF4466"
    if value > 0.6:
        return "#FFAA00"
    return "#44CC88"


def main():
    print(f"Sending macOS stats to {URL} every {INTERVAL}s (Ctrl+C to stop)")

    prev_in, prev_out = get_network_bytes()
    prev_time = time.time()

    # Try to get temperature once to check if it works
    temp = get_temperature()
    has_temp = temp is not None

    while True:
        cpu = round(get_cpu_usage(), 2)
        mem_ratio, mem_used, mem_total = get_memory_usage()
        mem_ratio = round(mem_ratio, 2)

        now = time.time()
        cur_in, cur_out = get_network_bytes()
        dt = now - prev_time
        if dt > 0:
            rate_in = round((cur_in - prev_in) / dt)
            rate_out = round((cur_out - prev_out) / dt)
        else:
            rate_in = rate_out = 0
        prev_in, prev_out = cur_in, cur_out
        prev_time = now

        if has_temp:
            temp = get_temperature()

        items = [
            # Header
            {"type": "rect", "x": 0, "y": 0, "w": 240, "h": 28, "color": "#1A1A3A", "fill": True},
            {"type": "text", "x": 120, "y": 6, "text": "SYSTEM", "size": 2, "color": "#4488FF", "align": "center"},

            # CPU
            {"type": "text", "x": 10, "y": 38, "text": "CPU", "size": 1, "color": "#888888"},
            {"type": "text", "x": 230, "y": 38, "text": f"{cpu*100:.0f}%", "size": 1, "color": "#FFFFFF",
             "align": "right", "maxWidth": "100%"},
            {"type": "progress", "x": 10, "y": 50, "w": 220, "h": 10,
             "value": cpu, "color": bar_color(cpu), "bg": "#111122", "border": "#222244"},

            # Memory
            {"type": "text", "x": 10, "y": 68, "text": "MEM", "size": 1, "color": "#888888"},
            {"type": "text", "x": 230, "y": 68, "text": f"{mem_ratio*100:.0f}%", "size": 1, "color": "#FFFFFF",
             "align": "right", "maxWidth": "100%"},
            {"type": "progress", "x": 10, "y": 80, "w": 220, "h": 10,
             "value": mem_ratio, "color": bar_color(mem_ratio), "bg": "#111122", "border": "#222244"},

            # Separator
            {"type": "line", "x1": 10, "y1": 100, "x2": 230, "y2": 100, "color": "#222244"},
        ]

        # Stats section
        y = 110
        if has_temp and temp is not None:
            temp_color = "#FF4466" if temp > 80 else "#FFAA00" if temp > 60 else "#44CC88"
            items.append({"type": "text", "x": 10, "y": y, "text": "Temp:", "size": 1, "color": "#888888"})
            items.append({"type": "text", "x": 120, "y": y, "text": f"{temp:.0f}C", "size": 1, "color": temp_color,
                          "maxWidth": "000C"})
            y += 16

        items.append({"type": "text", "x": 10, "y": y, "text": "Mem:", "size": 1, "color": "#888888"})
        items.append({"type": "text", "x": 120, "y": y,
                      "text": f"{format_bytes(mem_used)}/{format_bytes(mem_total)}", "size": 1, "color": "#4488FF",
                      "maxWidth": "00.0G/00.0G"})
        y += 16

        # Network
        items.append({"type": "line", "x1": 10, "y1": y, "x2": 230, "y2": y, "color": "#222244"})
        y += 8
        items.append({"type": "text", "x": 10, "y": y, "text": "NET", "size": 1, "color": "#888888"})
        y += 14
        items.append({"type": "text", "x": 10, "y": y, "text": "In:", "size": 1, "color": "#888888"})
        items.append({"type": "text", "x": 120, "y": y, "text": f"{format_bytes(rate_in)}/s", "size": 1,
                      "color": "#44CC88", "maxWidth": "000.0M/s"})
        y += 14
        items.append({"type": "text", "x": 10, "y": y, "text": "Out:", "size": 1, "color": "#888888"})
        items.append({"type": "text", "x": 120, "y": y, "text": f"{format_bytes(rate_out)}/s", "size": 1,
                      "color": "#FF8844", "maxWidth": "000.0M/s"})

        payload = {"bg": "#0A0A1A", "items": items}
        payload_json = json.dumps(payload, sort_keys=True)
        if payload_json != getattr(main, '_prev_payload', None):
            send(URL, payload)
            main._prev_payload = payload_json
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
