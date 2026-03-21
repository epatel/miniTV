#!/usr/bin/env python3
"""Send Crypto Fear & Greed Index to miniTV display. Updates every 5 minutes."""

import sys
from minitv import resolve_url, fetch, run_loop

INTERVAL = 300  # 5 minutes
API_URL = "https://api.alternative.me/fng/?limit=1"


def value_color(value):
    if value <= 25:
        return "#FF4444"  # Extreme Fear
    if value <= 45:
        return "#FF8844"  # Fear
    if value <= 55:
        return "#FFCC00"  # Neutral
    if value <= 75:
        return "#88CC44"  # Greed
    return "#44CC44"      # Extreme Greed


def collect():
    data = fetch(API_URL)
    if data and "data" in data:
        entry = data["data"][0]
        return int(entry["value"]), entry["value_classification"]
    return None, None


def build(data):
    value, classification = data
    if value is None:
        return {"bg": "#0A0A1A", "items": [
            {"type": "text", "x": 120, "y": 110, "text": "No data", "size": 2,
             "color": "#888888", "align": "center"}
        ]}

    color = value_color(value)
    zones = ["#FF4444", "#FF8844", "#FFCC00", "#88CC44", "#44CC44"]
    zone_w = 44
    gauge_x, gauge_y = 10, 145

    items = [
        {"type": "text", "x": 120, "y": 8, "text": "FEAR & GREED", "size": 2,
         "color": "#FFFFFF", "align": "center"},
        {"type": "text", "x": 120, "y": 30, "text": "INDEX", "size": 1,
         "color": "#888888", "align": "center"},
        {"type": "text", "x": 120, "y": 55, "text": str(value), "size": 4,
         "color": color, "align": "center", "maxWidth": "100"},
        {"type": "text", "x": 120, "y": 105, "text": classification, "size": 2,
         "color": color, "align": "center", "maxWidth": "Extreme Fear."},
    ]

    for i, zc in enumerate(zones):
        items.append({"type": "rect", "x": gauge_x + i * zone_w, "y": gauge_y,
                      "w": zone_w - 2, "h": 12, "color": zc, "fill": True})

    pointer_x = gauge_x + int(value / 100.0 * (zone_w * 5 - 2))
    pointer_x = max(gauge_x, min(pointer_x, gauge_x + zone_w * 5 - 2))
    items.append({"type": "rect", "x": pointer_x - 2, "y": gauge_y - 6,
                  "w": 5, "h": 6, "color": "#FFFFFF", "fill": True})
    items.append({"type": "rect", "x": pointer_x - 1, "y": gauge_y + 12,
                  "w": 3, "h": 4, "color": "#FFFFFF", "fill": True})

    items.append({"type": "text", "x": gauge_x, "y": gauge_y + 20,
                  "text": "Fear", "size": 1, "color": "#FF4444"})
    items.append({"type": "text", "x": gauge_x + zone_w * 5, "y": gauge_y + 20,
                  "text": "Greed", "size": 1, "color": "#44CC44", "align": "right"})
    items.append({"type": "text", "x": gauge_x, "y": gauge_y + 32,
                  "text": "0", "size": 1, "color": "#666666"})
    items.append({"type": "text", "x": gauge_x + zone_w * 5, "y": gauge_y + 32,
                  "text": "100", "size": 1, "color": "#666666", "align": "right"})

    return {"bg": "#0A0A1A", "items": items}


if __name__ == "__main__":
    url = resolve_url(sys.argv[1] if len(sys.argv) > 1 else "http://minitv.local/display")
    print(f"Fear & Greed -> {url} every {INTERVAL}s (Ctrl+C to stop)")
    run_loop(url, collect, build, INTERVAL)
