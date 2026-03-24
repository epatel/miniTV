#!/usr/bin/env python3
"""Send latest RSS headlines to miniTV display."""

import argparse
import subprocess
import time
import xml.etree.ElementTree as ET
from minitv import add_display_args, display_from_args, run_loop

DEFAULT_RSS = "https://rss.aftonbladet.se/rss2/small/pages/sections/senastenytt/"
DEFAULT_TITLE = "AFTONBLADET"
DEFAULT_COLOR = "#FFCC00"
INTERVAL = 60

# Layout constants for 240x240 display
HEADER_H = 30
TEXT_FONT = "serif-12"  # proportional, ~10-12px wide, ~17px tall
LINE_H = 21            # line height for serif-12 + 1px breathing room
CHARS_PER_LINE = 19    # conservative for proportional font to stay under 240px
MAX_Y = 236
MARGIN_X = 6

# Track last-modified / etag for conditional requests
_last_modified = None
_etag = None


def fetch_rss(rss_url):
    """Fetch RSS feed with conditional GET. Returns (titles, changed)."""
    global _last_modified, _etag
    try:
        # Use -w to get HTTP status, -o for body, headers via stderr trick
        cmd = ["/usr/bin/curl", "-s", "-L", "-w", "%{http_code}", rss_url]
        if _last_modified:
            cmd += ["-H", f"If-Modified-Since: {_last_modified}"]
        if _etag:
            cmd += ["-H", f"If-None-Match: {_etag}"]

        result = subprocess.run(cmd, capture_output=True, timeout=15)
        output = result.stdout

        # Last 3 bytes are the HTTP status code
        status = output[-3:].decode()
        body = output[:-3]

        if status == "304":
            return [], False

        # Fetch headers separately for caching (only on success)
        hdr_result = subprocess.run(
            ["/usr/bin/curl", "-s", "-L", "-I", rss_url],
            capture_output=True, text=True, timeout=15
        )
        for line in hdr_result.stdout.split("\r\n"):
            lower = line.lower()
            if lower.startswith("last-modified:"):
                _last_modified = line.split(":", 1)[1].strip()
            elif lower.startswith("etag:"):
                _etag = line.split(":", 1)[1].strip()

        root = ET.fromstring(body)
        titles = []
        for item in root.iter("item"):
            title_el = item.find("title")
            if title_el is not None and title_el.text:
                titles.append(asciify(title_el.text.strip()))
        return titles, True
    except Exception as e:
        print(f"RSS fetch error: {e}")
        return [], False


def asciify(text):
    """Replace Swedish/common non-ASCII chars with ASCII equivalents."""
    replacements = {
        "å": "a", "ä": "a", "ö": "o",
        "Å": "A", "Ä": "A", "Ö": "O",
        "é": "e", "è": "e", "ê": "e",
        "ü": "u", "á": "a", "à": "a",
        "\u2013": "-", "\u2014": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "\u2026": "...",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text


def wrap_text(text, max_chars):
    """Word-wrap text into lines of at most max_chars characters."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        elif not current:
            current = word[:max_chars]
        else:
            current += " " + word
    if current:
        lines.append(current)
    return lines


def build(titles, header_title, header_color):
    """Build display payload fitting as many headlines as possible."""
    items = [
        {"type": "rect", "x": 0, "y": 0, "w": 240, "h": HEADER_H,
         "color": "#1A1A2A", "fill": True},
        {"type": "text", "x": 120, "y": 4, "text": header_title[:31],
         "font": "sans-12", "color": header_color, "align": "center"},
    ]

    y = HEADER_H + 4
    headline_num = 0

    for title in titles:
        lines = wrap_text(title, CHARS_PER_LINE)

        # Check if this headline fits
        if y + len(lines) * LINE_H > MAX_Y:
            break

        # Separator line between headlines
        if headline_num > 0:
            items.append({"type": "line", "x1": MARGIN_X, "y1": y - 3,
                          "x2": 240 - MARGIN_X, "y2": y - 3, "color": "#444444"})

        for line in lines:
            if y + LINE_H > MAX_Y or len(items) >= 31:
                break
            items.append({
                "type": "text", "x": MARGIN_X, "y": y,
                "text": line[:31], "font": TEXT_FONT, "color": "#FFFFFF",
                "maxWidth": "M" * min(CHARS_PER_LINE, 31),
            })
            y += LINE_H

        y += 6  # gap after headline
        headline_num += 1

        if len(items) >= 30:
            break

    if not titles:
        items.append({"type": "text", "x": 120, "y": 120, "text": "No headlines",
                      "font": "sans-12", "color": "#888888", "align": "center"})

    return {"bg": "#000000", "items": items}


def main():
    parser = argparse.ArgumentParser(description="RSS headlines on miniTV")
    add_display_args(parser)
    parser.add_argument("--rss", default=DEFAULT_RSS, help=f"RSS feed URL (default: {DEFAULT_RSS})")
    parser.add_argument("--title", default=DEFAULT_TITLE, help=f"Header title (default: {DEFAULT_TITLE})")
    parser.add_argument("--color", default=DEFAULT_COLOR, help=f"Header color (default: {DEFAULT_COLOR})")
    parser.add_argument("--interval", type=int, default=INTERVAL,
                        help=f"Poll interval in seconds (default: {INTERVAL})")
    args = parser.parse_args()

    display = display_from_args(args)
    rss_url = args.rss
    header_title = asciify(args.title)
    header_color = args.color

    print(f"RSS: {rss_url}")
    print(f"Display: {display.describe()} (every {args.interval}s)")

    prev_fp = None
    while True:
        titles, changed = fetch_rss(rss_url)
        if changed and titles:
            fp = tuple(titles[:10])
            if fp != prev_fp:
                payload = build(titles, header_title, header_color)
                display.send(payload)
                prev_fp = fp
                print(f"Updated: {len(titles)} headlines, showing top {sum(1 for i in payload['items'] if i['type'] == 'text') - 1}")
            else:
                print("Feed fetched but headlines unchanged")
        elif not changed:
            print("Feed not modified (304)")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
