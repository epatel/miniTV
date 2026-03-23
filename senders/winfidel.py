#!/usr/bin/env python3
"""Send WInFiDEL filament diameter readings to miniTV display.

Usage:
  python3 winfidel.py --host sensor1.local
  python3 winfidel.py --host sensor1.local --host sensor2.local
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime

from minitv import resolve_host, add_display_args, display_from_args

INTERVAL = 2  # seconds
VERBOSE = False


def log(msg):
    if VERBOSE:
        print(msg)
NOMINAL = 1.75  # nominal filament diameter in mm
TOLERANCE = 0.05  # +/- mm for "good" range




def fetch_diameter(host):
    try:
        result = subprocess.run(
            ["/usr/bin/curl", "-s", f"http://{host}/api/v0/diameter/read"],
            capture_output=True, text=True, timeout=5
        )
        data = json.loads(result.stdout)
        if data.get("status") == "ok":
            return data["data"]
    except Exception as e:
        log(f"Fetch error ({host}): {e}")
    return None



def diameter_color(value):
    if value is None or value == 0:
        return "#666666"
    diff = abs(value - NOMINAL)
    if diff <= TOLERANCE:
        return "#44CC88"
    if diff <= TOLERANCE * 2:
        return "#FFAA00"
    return "#FF4444"


def sensor_items_single(data, label):
    """Full-size layout for a single sensor."""
    if not data:
        return [
            {"type": "text", "x": 120, "y": 100, "text": "No sensor data",
             "size": 2, "color": "#888888", "align": "center"},
        ]

    diameter = data.get("diameter", 0)
    d_min = data.get("min", 0)
    d_max = data.get("max", 0)
    d_avg = data.get("avg", 0)
    count = data.get("count", 0)
    color = diameter_color(diameter)
    deviation = diameter - NOMINAL
    dev_sign = "+" if deviation >= 0 else ""
    bar_val = max(0, min(1, (diameter - 1.5) / 0.5))

    return [
        {"type": "text", "x": 120, "y": 38, "text": f"{diameter:.3f}", "size": 4,
         "color": color, "align": "center", "maxWidth": "0.000"},
        {"type": "text", "x": 120, "y": 75, "text": "mm", "size": 2,
         "color": "#888888", "align": "center"},
        {"type": "text", "x": 120, "y": 98, "text": f"{dev_sign}{deviation:.3f}",
         "size": 2, "color": color, "align": "center", "maxWidth": "+0.000"},

        {"type": "progress", "x": 14, "y": 120, "w": 212, "h": 8,
         "value": bar_val, "color": color, "bg": "#282832", "border": "#282832"},
        {"type": "text", "x": 14, "y": 131, "text": "1.50", "size": 1, "color": "#4A4A52"},
        {"type": "text", "x": 120, "y": 131, "text": "1.75", "size": 1,
         "color": "#4A4A52", "align": "center"},
        {"type": "text", "x": 226, "y": 131, "text": "2.00", "size": 1,
         "color": "#4A4A52", "align": "right"},

        {"type": "rect", "x": 8, "y": 146, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 14, "y": 149, "text": "Min", "size": 1, "color": "#717178"},
        {"type": "text", "x": 14, "y": 162, "text": f"{d_min:.3f}", "size": 1,
         "color": diameter_color(d_min), "maxWidth": "0.000"},

        {"type": "rect", "x": 122, "y": 146, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 128, "y": 149, "text": "Max", "size": 1, "color": "#717178"},
        {"type": "text", "x": 128, "y": 162, "text": f"{d_max:.3f}", "size": 1,
         "color": diameter_color(d_max), "maxWidth": "0.000"},

        {"type": "rect", "x": 8, "y": 184, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 14, "y": 187, "text": "Average", "size": 1, "color": "#717178"},
        {"type": "text", "x": 14, "y": 200, "text": f"{d_avg:.3f}", "size": 1,
         "color": diameter_color(d_avg), "maxWidth": "0.000"},

        {"type": "rect", "x": 122, "y": 184, "w": 110, "h": 34, "color": "#16161E", "fill": True},
        {"type": "text", "x": 128, "y": 187, "text": "Samples", "size": 1, "color": "#717178"},
        {"type": "text", "x": 128, "y": 200, "text": str(count), "size": 1,
         "color": "#F0F0F5", "maxWidth": "000000"},
    ]


def sensor_items_dual(data, label, y_off):
    """Compact layout for one sensor in dual mode. y_off is the vertical offset."""
    if not data:
        return [
            {"type": "text", "x": 120, "y": y_off + 40, "text": "No data",
             "size": 1, "color": "#666666", "align": "center"},
        ]

    diameter = data.get("diameter", 0)
    d_min = data.get("min", 0)
    d_max = data.get("max", 0)
    d_avg = data.get("avg", 0)
    color = diameter_color(diameter)
    deviation = diameter - NOMINAL
    dev_sign = "+" if deviation >= 0 else ""
    bar_val = max(0, min(1, (diameter - 1.5) / 0.5))

    items = [
        # Label
        {"type": "rect", "x": 0, "y": y_off, "w": 240, "h": 18, "color": "#16162A", "fill": True},
        {"type": "text", "x": 120, "y": y_off + 3, "text": label, "size": 1,
         "color": "#6CB4EE", "align": "center"},

        # Big reading + deviation
        {"type": "text", "x": 80, "y": y_off + 22, "text": f"{diameter:.3f}", "size": 3,
         "color": color, "align": "center", "maxWidth": "0.000"},
        {"type": "text", "x": 80, "y": y_off + 48, "text": "mm", "size": 1,
         "color": "#888888", "align": "center"},
        {"type": "text", "x": 190, "y": y_off + 26, "text": f"{dev_sign}{deviation:.3f}",
         "size": 2, "color": color, "align": "center", "maxWidth": "+0.000"},

        # Bar
        {"type": "progress", "x": 14, "y": y_off + 60, "w": 212, "h": 6,
         "value": bar_val, "color": color, "bg": "#282832", "border": "#282832"},

        # Min / Avg / Max in a row
        {"type": "text", "x": 14, "y": y_off + 72, "text": f"Min:{d_min:.3f}", "size": 1,
         "color": diameter_color(d_min), "maxWidth": "Min:0.000"},
        {"type": "text", "x": 120, "y": y_off + 72, "text": f"Avg:{d_avg:.3f}", "size": 1,
         "color": diameter_color(d_avg), "align": "center", "maxWidth": "Avg:0.000"},
        {"type": "text", "x": 226, "y": y_off + 72, "text": f"Max:{d_max:.3f}", "size": 1,
         "color": diameter_color(d_max), "align": "right", "maxWidth": "Max:0.000"},
    ]
    return items


def build_display(readings, labels):
    """Build display for 1 or 2 sensors."""
    items = [
        # Header
        {"type": "rect", "x": 0, "y": 0, "w": 240, "h": 26, "color": "#1A1A2A", "fill": True},
        {"type": "text", "x": 120, "y": 5, "text": "WINFIDEL", "size": 2,
         "color": "#6CB4EE", "align": "center"},
    ]

    if len(readings) == 1:
        items += sensor_items_single(readings[0], labels[0])
    else:
        # Two sensors stacked
        items += sensor_items_dual(readings[0], labels[0], 28)
        {"type": "line", "x1": 10, "y1": 133, "x2": 230, "y2": 133, "color": "#282832"}
        items += sensor_items_dual(readings[1], labels[1], 120)

    # Timestamp
    items.append({"type": "text", "x": 120, "y": 226, "text": datetime.now().strftime("%H:%M:%S"),
                  "size": 1, "color": "#4A4A52", "align": "center", "maxWidth": "00:00:00"})

    return {"bg": "#0C0C10", "items": items}


def fingerprint(readings):
    parts = []
    for data in readings:
        if data:
            parts.append((
                round(data.get("diameter", 0), 3),
                round(data.get("min", 0), 3),
                round(data.get("max", 0), 3),
                data.get("count", 0),
            ))
        else:
            parts.append(None)
    return tuple(parts)


def main():
    parser = argparse.ArgumentParser(description="WInFiDEL filament sensor display for miniTV")
    parser.add_argument("--host", action="append", required=True,
                        help="WInFiDEL sensor IP or hostname (can specify twice)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    add_display_args(parser)
    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose

    if len(args.host) > 2:
        print("Error: maximum 2 hosts supported")
        sys.exit(1)

    hosts = [resolve_host(h) for h in args.host]
    labels = [args.host[i].split(".")[0].upper() for i in range(len(args.host))]
    display = display_from_args(args)
    log(f"Sensors: {', '.join(hosts)} | Display: {display.describe()} | Interval: {INTERVAL}s (Ctrl+C to stop)")

    prev_fp = None
    while True:
        readings = [fetch_diameter(h) for h in hosts]
        fp = fingerprint(readings)
        if fp != prev_fp:
            payload = build_display(readings, labels)
            display.send(payload)
            prev_fp = fp
            for i, data in enumerate(readings):
                if data:
                    log(f"[{labels[i]}] {data['diameter']:.3f}mm (min:{data['min']:.3f} max:{data['max']:.3f})")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
