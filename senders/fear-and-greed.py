#!/usr/bin/env python3
"""Send Crypto Fear & Greed Index to miniTV display. Updates every 5 minutes."""

import subprocess
import time
import json
import sys
import socket

INTERVAL = 300  # 5 minutes
API_URL = "https://api.alternative.me/fng/?limit=1"


def resolve_url():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://minitv.local/display"
    if "minitv.local" in url:
        try:
            ip = socket.getaddrinfo("minitv.local", 80, socket.AF_INET)[0][4][0]
            url = url.replace("minitv.local", ip)
            print(f"Resolved minitv.local -> {ip}")
        except socket.gaierror:
            print("Warning: could not resolve minitv.local, using as-is")
    return url


URL = resolve_url()


def fetch_fng():
    try:
        result = subprocess.run(
            ["/usr/bin/curl", "-s", API_URL],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        entry = data["data"][0]
        return int(entry["value"]), entry["value_classification"]
    except Exception as e:
        print(f"Fetch error: {e}")
        return None, None


def send(payload):
    data = json.dumps(payload)
    try:
        subprocess.run(
            ["/usr/bin/curl", "-s", "-X", "POST", URL,
             "-H", "Content-Type: application/json", "-d", "@-"],
            input=data.encode(), timeout=5, capture_output=True
        )
    except Exception as e:
        print(f"Send error: {e}")


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


def build_gauge(value, classification):
    color = value_color(value)

    # Gauge bar segments (5 zones)
    zones = [
        ("#FF4444", "Extreme Fear"),
        ("#FF8844", "Fear"),
        ("#FFCC00", "Neutral"),
        ("#88CC44", "Greed"),
        ("#44CC44", "Extreme Greed"),
    ]
    zone_w = 44  # each zone width
    gauge_x = 10
    gauge_y = 145

    items = [
        # Title
        {"type": "text", "x": 120, "y": 8, "text": "FEAR & GREED", "size": 2,
         "color": "#FFFFFF", "align": "center"},
        {"type": "text", "x": 120, "y": 30, "text": "INDEX", "size": 1,
         "color": "#888888", "align": "center"},

        # Big number
        {"type": "text", "x": 120, "y": 55, "text": str(value), "size": 4,
         "color": color, "align": "center", "maxWidth": "100"},

        # Classification
        {"type": "text", "x": 120, "y": 105, "text": classification, "size": 2,
         "color": color, "align": "center", "maxWidth": "Extreme Fear."},

        # Gauge bar - 5 colored segments
    ]

    for i, (zone_color, _) in enumerate(zones):
        items.append({
            "type": "rect", "x": gauge_x + i * zone_w, "y": gauge_y,
            "w": zone_w - 2, "h": 12, "color": zone_color, "fill": True
        })

    # Pointer - triangle indicator using lines
    pointer_x = gauge_x + int(value / 100.0 * (zone_w * 5 - 2))
    pointer_x = max(gauge_x, min(pointer_x, gauge_x + zone_w * 5 - 2))
    items.append({"type": "rect", "x": pointer_x - 2, "y": gauge_y - 6,
                  "w": 5, "h": 6, "color": "#FFFFFF", "fill": True})
    items.append({"type": "rect", "x": pointer_x - 1, "y": gauge_y + 12,
                  "w": 3, "h": 4, "color": "#FFFFFF", "fill": True})

    # Labels under gauge
    items.append({"type": "text", "x": gauge_x, "y": gauge_y + 20,
                  "text": "Fear", "size": 1, "color": "#FF4444"})
    items.append({"type": "text", "x": gauge_x + zone_w * 5, "y": gauge_y + 20,
                  "text": "Greed", "size": 1, "color": "#44CC44", "align": "right"})

    # Scale numbers
    items.append({"type": "text", "x": gauge_x, "y": gauge_y + 32,
                  "text": "0", "size": 1, "color": "#666666"})
    items.append({"type": "text", "x": gauge_x + zone_w * 5, "y": gauge_y + 32,
                  "text": "100", "size": 1, "color": "#666666", "align": "right"})

    return {"bg": "#0A0A1A", "items": items}


def main():
    print(f"Sending Fear & Greed Index to {URL} every {INTERVAL}s (Ctrl+C to stop)")
    prev_payload = None

    while True:
        value, classification = fetch_fng()
        if value is not None:
            payload = build_gauge(value, classification)
            payload_json = json.dumps(payload, sort_keys=True)
            if payload_json != prev_payload:
                send(payload)
                prev_payload = payload_json
                print(f"Fear & Greed: {value} ({classification})")
            else:
                print(f"No change: {value} ({classification})")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
