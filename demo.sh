#!/bin/bash
# miniTV Display Demo Script
# Usage: ./demo.sh <device-ip>
# Example: ./demo.sh 192.168.1.42

IP="${1:-minitv.local}"
URL="http://$IP/display"

post() {
  /usr/bin/curl -s -X POST "$URL" -H "Content-Type: application/json" -d "$1" > /dev/null
  echo "  -> sent"
}

echo "=== miniTV Demo ==="
echo "Target: $IP"
echo ""

# --- Test 1: Device info ---
echo "[1] Device info (GET /)"
/usr/bin/curl -s "http://$IP/" | python3 -m json.tool 2>/dev/null || /usr/bin/curl -s "http://$IP/"
echo ""
sleep 1

# --- Test 2: Simple text ---
echo "[2] Simple centered text"
post '{
  "bg": "#000000",
  "items": [
    {"type": "text", "x": 120, "y": 100, "text": "Hello!", "size": 4, "color": "#00FF00", "align": "center"},
    {"type": "text", "x": 120, "y": 150, "text": "miniTV", "size": 2, "color": "#888888", "align": "center"}
  ]
}'
sleep 3

# --- Test 3: Text alignment ---
echo "[3] Text alignment (left, center, right)"
post '{
  "bg": "#000011",
  "items": [
    {"type": "text", "x": 10,  "y": 40,  "text": "Left",   "size": 2, "color": "#FF0000"},
    {"type": "text", "x": 120, "y": 80,  "text": "Center", "size": 2, "color": "#00FF00", "align": "center"},
    {"type": "text", "x": 230, "y": 120, "text": "Right",  "size": 2, "color": "#0088FF", "align": "right"},
    {"type": "line", "x1": 120, "y1": 0, "x2": 120, "y2": 240, "color": "#333333"}
  ]
}'
sleep 3

# --- Test 4: Progress bars ---
echo "[4] Multiple progress bars"
post '{
  "bg": "#000000",
  "items": [
    {"type": "text", "x": 10, "y": 10, "text": "Downloads", "size": 2, "color": "#FFFFFF"},
    {"type": "line", "x1": 10, "y1": 32, "x2": 230, "y2": 32, "color": "#333333"},

    {"type": "text", "x": 10, "y": 45, "text": "File 1", "size": 1, "color": "#AAAAAA"},
    {"type": "text", "x": 230, "y": 45, "text": "100%", "size": 1, "color": "#00FF00", "align": "right"},
    {"type": "progress", "x": 10, "y": 58, "w": 220, "h": 14, "value": 1.0, "color": "#00CC00", "bg": "#222222", "border": "#444444"},

    {"type": "text", "x": 10, "y": 82, "text": "File 2", "size": 1, "color": "#AAAAAA"},
    {"type": "text", "x": 230, "y": 82, "text": "73%", "size": 1, "color": "#FFAA00", "align": "right"},
    {"type": "progress", "x": 10, "y": 95, "w": 220, "h": 14, "value": 0.73, "color": "#FFAA00", "bg": "#222222", "border": "#444444"},

    {"type": "text", "x": 10, "y": 119, "text": "File 3", "size": 1, "color": "#AAAAAA"},
    {"type": "text", "x": 230, "y": 119, "text": "25%", "size": 1, "color": "#FF4444", "align": "right"},
    {"type": "progress", "x": 10, "y": 132, "w": 220, "h": 14, "value": 0.25, "color": "#FF4444", "bg": "#222222", "border": "#444444"}
  ]
}'
sleep 3

# --- Test 5: Shapes ---
echo "[5] Shapes demo"
post '{
  "bg": "#000000",
  "items": [
    {"type": "rect", "x": 10, "y": 10, "w": 220, "h": 220, "color": "#333333"},
    {"type": "rect", "x": 30, "y": 30, "w": 60, "h": 60, "color": "#FF0000", "fill": true},
    {"type": "rect", "x": 150, "y": 30, "w": 60, "h": 60, "color": "#0000FF", "fill": true},
    {"type": "circle", "x": 60, "y": 170, "r": 30, "color": "#00FF00", "fill": true},
    {"type": "circle", "x": 180, "y": 170, "r": 30, "color": "#FF00FF", "fill": true},
    {"type": "circle", "x": 120, "y": 120, "r": 25, "color": "#FFFF00", "fill": true},
    {"type": "line", "x1": 10, "y1": 10, "x2": 230, "y2": 230, "color": "#FFFFFF"},
    {"type": "line", "x1": 230, "y1": 10, "x2": 10, "y2": 230, "color": "#FFFFFF"}
  ]
}'
sleep 3

# --- Test 6: Dashboard ---
echo "[6] Dashboard layout"
post '{
  "bg": "#0A0A1A",
  "items": [
    {"type": "rect", "x": 0, "y": 0, "w": 240, "h": 30, "color": "#1A1A3A", "fill": true},
    {"type": "text", "x": 120, "y": 7, "text": "SYSTEM", "size": 2, "color": "#4488FF", "align": "center"},

    {"type": "text", "x": 10, "y": 42, "text": "CPU", "size": 1, "color": "#888888"},
    {"type": "text", "x": 230, "y": 42, "text": "62%", "size": 1, "color": "#FFFFFF", "align": "right"},
    {"type": "progress", "x": 10, "y": 54, "w": 220, "h": 10, "value": 0.62, "color": "#4488FF", "bg": "#111122", "border": "#222244"},

    {"type": "text", "x": 10, "y": 74, "text": "MEM", "size": 1, "color": "#888888"},
    {"type": "text", "x": 230, "y": 74, "text": "84%", "size": 1, "color": "#FFFFFF", "align": "right"},
    {"type": "progress", "x": 10, "y": 86, "w": 220, "h": 10, "value": 0.84, "color": "#FF4466", "bg": "#111122", "border": "#222244"},

    {"type": "text", "x": 10, "y": 106, "text": "DISK", "size": 1, "color": "#888888"},
    {"type": "text", "x": 230, "y": 106, "text": "41%", "size": 1, "color": "#FFFFFF", "align": "right"},
    {"type": "progress", "x": 10, "y": 118, "w": 220, "h": 10, "value": 0.41, "color": "#44CC88", "bg": "#111122", "border": "#222244"},

    {"type": "line", "x1": 10, "y1": 140, "x2": 230, "y2": 140, "color": "#222244"},

    {"type": "text", "x": 10,  "y": 150, "text": "Temp:", "size": 1, "color": "#888888"},
    {"type": "text", "x": 100, "y": 150, "text": "58C",  "size": 1, "color": "#FFAA00"},
    {"type": "text", "x": 10,  "y": 165, "text": "Load:", "size": 1, "color": "#888888"},
    {"type": "text", "x": 100, "y": 165, "text": "2.4",  "size": 1, "color": "#44CC88"},
    {"type": "text", "x": 10,  "y": 180, "text": "Net:",  "size": 1, "color": "#888888"},
    {"type": "text", "x": 100, "y": 180, "text": "12Mbps", "size": 1, "color": "#4488FF"},

    {"type": "circle", "x": 200, "y": 170, "r": 6, "color": "#00FF00", "fill": true},
    {"type": "text", "x": 190, "y": 190, "text": "OK", "size": 1, "color": "#00FF00"}
  ]
}'
sleep 3

# --- Test 7: Animated progress ---
echo "[7] Animated progress (0-100%)"
for i in $(seq 0 5 100); do
  val=$(echo "scale=2; $i/100" | bc)
  printf "\r  Progress: %3d%%" "$i"
  post '{
    "bg": "#000000",
    "items": [
      {"type": "text", "x": 120, "y": 60, "text": "Installing...", "size": 2, "color": "#FFFFFF", "align": "center"},
      {"type": "progress", "x": 20, "y": 110, "w": 200, "h": 24, "value": '"$val"', "color": "#7F00FF", "bg": "#222222", "border": "#FFFFFF"},
      {"type": "text", "x": 120, "y": 145, "text": "'"$i"'%", "size": 2, "color": "#FFFFFF", "align": "center", "maxWidth": "100%"}
    ]
  }' 2>/dev/null
done
echo ""
sleep 2

# --- Done ---
echo "[8] Done - showing ready screen"
post '{
  "bg": "#001100",
  "items": [
    {"type": "circle", "x": 120, "y": 100, "r": 40, "color": "#00FF00"},
    {"type": "text", "x": 106, "y": 88, "text": "OK", "size": 3, "color": "#00FF00"},
    {"type": "text", "x": 120, "y": 170, "text": "All tests passed", "size": 1, "color": "#888888", "align": "center"}
  ]
}'

echo ""
echo "=== Demo complete ==="
