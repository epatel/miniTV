#!/bin/bash
# miniTV MQTT Display Demo
# Usage: ./demo-mqtt.sh [device-name] [broker] [username] [password]
# Example: ./demo-mqtt.sh minitv rpi4.memention.net myuser mypass

DEVICE="${1:-minitv}"
BROKER="${2:-rpi4.memention.net}"
USER="${3:-}"
PASS="${4:-}"
TOPIC="/$DEVICE/display"

AUTH=""
if [ -n "$USER" ]; then
  AUTH="-u $USER -P $PASS"
fi

pub() {
  mosquitto_pub -h "$BROKER" $AUTH -t "$TOPIC" -m "$1"
  echo "  -> sent"
}

echo "=== miniTV MQTT Demo ==="
echo "Broker: $BROKER"
echo "Topic: $TOPIC"
echo ""

# --- Test 1: Simple text ---
echo "[1] Simple centered text"
pub '{
  "bg": "#000000",
  "items": [
    {"type": "text", "x": 120, "y": 90, "text": "Hello MQTT!", "font": "sans-18", "color": "#00FF00", "align": "center"},
    {"type": "text", "x": 120, "y": 130, "text": "miniTV", "font": "sans-12", "color": "#888888", "align": "center"}
  ]
}'
sleep 3

# --- Test 2: Custom fonts ---
echo "[2] Custom fonts showcase"
pub '{
  "bg": "#000000",
  "items": [
    {"type": "text", "x": 120, "y": 5, "text": "Sans 9pt", "font": "sans-9", "color": "#FFFFFF", "align": "center"},
    {"type": "text", "x": 120, "y": 30, "text": "Sans 12pt", "font": "sans-12", "color": "#00FF00", "align": "center"},
    {"type": "text", "x": 120, "y": 65, "text": "Sans 18pt", "font": "sans-18", "color": "#FF4444", "align": "center"},
    {"type": "text", "x": 120, "y": 105, "text": "Mono 12pt", "font": "mono-12", "color": "#00FFFF", "align": "center"},
    {"type": "text", "x": 120, "y": 140, "text": "Serif 18pt", "font": "serif-18", "color": "#FFFF00", "align": "center"},
    {"type": "text", "x": 120, "y": 185, "text": "Mono 18pt", "font": "mono-18", "color": "#FF88FF", "align": "center"},
    {"type": "text", "x": 120, "y": 220, "text": "Built-in size 2", "size": 2, "color": "#888888", "align": "center"}
  ]
}'
sleep 3

# --- Test 3: Text alignment ---
echo "[3] Text alignment"
pub '{
  "bg": "#000011",
  "items": [
    {"type": "text", "x": 10,  "y": 40,  "text": "Left",   "font": "sans-18", "color": "#FF0000"},
    {"type": "text", "x": 120, "y": 90,  "text": "Center", "font": "sans-18", "color": "#00FF00", "align": "center"},
    {"type": "text", "x": 230, "y": 140, "text": "Right",  "font": "sans-18", "color": "#0088FF", "align": "right"},
    {"type": "line", "x1": 120, "y1": 0, "x2": 120, "y2": 240, "color": "#333333"}
  ]
}'
sleep 3

# --- Test 4: Progress bars ---
echo "[4] Multiple progress bars"
pub '{
  "bg": "#000000",
  "items": [
    {"type": "text", "x": 10, "y": 5, "text": "Downloads", "font": "sans-18", "color": "#FFFFFF"},
    {"type": "line", "x1": 10, "y1": 35, "x2": 230, "y2": 35, "color": "#333333"},

    {"type": "text", "x": 10, "y": 45, "text": "File 1", "font": "sans-9", "color": "#AAAAAA"},
    {"type": "text", "x": 230, "y": 45, "text": "100%", "font": "sans-9", "color": "#00FF00", "align": "right"},
    {"type": "progress", "x": 10, "y": 62, "w": 220, "h": 14, "value": 1.0, "color": "#00CC00", "bg": "#222222", "border": "#444444"},

    {"type": "text", "x": 10, "y": 86, "text": "File 2", "font": "sans-9", "color": "#AAAAAA"},
    {"type": "text", "x": 230, "y": 86, "text": "73%", "font": "sans-9", "color": "#FFAA00", "align": "right"},
    {"type": "progress", "x": 10, "y": 103, "w": 220, "h": 14, "value": 0.73, "color": "#FFAA00", "bg": "#222222", "border": "#444444"},

    {"type": "text", "x": 10, "y": 127, "text": "File 3", "font": "sans-9", "color": "#AAAAAA"},
    {"type": "text", "x": 230, "y": 127, "text": "25%", "font": "sans-9", "color": "#FF4444", "align": "right"},
    {"type": "progress", "x": 10, "y": 144, "w": 220, "h": 14, "value": 0.25, "color": "#FF4444", "bg": "#222222", "border": "#444444"}
  ]
}'
sleep 3

# --- Test 5: Dashboard ---
echo "[5] Dashboard layout"
pub '{
  "bg": "#0A0A1A",
  "items": [
    {"type": "rect", "x": 0, "y": 0, "w": 240, "h": 30, "color": "#1A1A3A", "fill": true},
    {"type": "text", "x": 120, "y": 3, "text": "SYSTEM", "font": "sans-18", "color": "#4488FF", "align": "center"},

    {"type": "text", "x": 10, "y": 40, "text": "CPU", "font": "sans-9", "color": "#888888"},
    {"type": "text", "x": 230, "y": 40, "text": "62%", "font": "sans-9", "color": "#FFFFFF", "align": "right"},
    {"type": "progress", "x": 10, "y": 56, "w": 220, "h": 10, "value": 0.62, "color": "#4488FF", "bg": "#111122", "border": "#222244"},

    {"type": "text", "x": 10, "y": 76, "text": "MEM", "font": "sans-9", "color": "#888888"},
    {"type": "text", "x": 230, "y": 76, "text": "84%", "font": "sans-9", "color": "#FFFFFF", "align": "right"},
    {"type": "progress", "x": 10, "y": 92, "w": 220, "h": 10, "value": 0.84, "color": "#FF4466", "bg": "#111122", "border": "#222244"},

    {"type": "text", "x": 10, "y": 112, "text": "DISK", "font": "sans-9", "color": "#888888"},
    {"type": "text", "x": 230, "y": 112, "text": "41%", "font": "sans-9", "color": "#FFFFFF", "align": "right"},
    {"type": "progress", "x": 10, "y": 128, "w": 220, "h": 10, "value": 0.41, "color": "#44CC88", "bg": "#111122", "border": "#222244"},

    {"type": "line", "x1": 10, "y1": 148, "x2": 230, "y2": 148, "color": "#222244"},

    {"type": "text", "x": 10,  "y": 158, "text": "Temp:", "font": "sans-9", "color": "#888888"},
    {"type": "text", "x": 100, "y": 158, "text": "58C",  "font": "sans-9", "color": "#FFAA00"},
    {"type": "text", "x": 10,  "y": 178, "text": "Load:", "font": "sans-9", "color": "#888888"},
    {"type": "text", "x": 100, "y": 178, "text": "2.4",  "font": "sans-9", "color": "#44CC88"}
  ]
}'
sleep 3

# --- Test 6: Animated progress ---
echo "[6] Animated progress (0-100%)"
for i in $(seq 0 5 100); do
  val=$(echo "scale=2; $i/100" | bc)
  printf "\r  Progress: %3d%%" "$i"
  pub '{
    "bg": "#000000",
    "items": [
      {"type": "text", "x": 120, "y": 55, "text": "Installing...", "font": "sans-18", "color": "#FFFFFF", "align": "center", "maxWidth": "Installing..."},
      {"type": "progress", "x": 20, "y": 100, "w": 200, "h": 24, "value": '"$val"', "color": "#7F00FF", "bg": "#222222", "border": "#FFFFFF"},
      {"type": "text", "x": 120, "y": 135, "text": "'"$i"'%", "font": "sans-12", "color": "#FFFFFF", "align": "center", "maxWidth": "100%"}
    ]
  }' 2>/dev/null
  sleep 1
done
echo ""
sleep 2

# --- Done ---
echo "[7] Done"
pub '{
  "bg": "#001100",
  "items": [
    {"type": "circle", "x": 120, "y": 100, "r": 40, "color": "#00FF00"},
    {"type": "text", "x": 120, "y": 85, "text": "OK", "font": "sans-18", "color": "#00FF00", "align": "center"},
    {"type": "text", "x": 120, "y": 160, "text": "All tests passed", "font": "sans-9", "color": "#888888", "align": "center"}
  ]
}'

echo ""
echo "=== Demo complete ==="
