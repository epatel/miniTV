<a href="https://claude.ai"><img src="made-with-claude.png" height="32" alt="Made with Claude"></a>

# miniTV

A tiny display server for the [GeekMagic SmallTV](https://github.com/GeekMagicClock) device — an ESP8266 (ESP-12F) with a 240x240 ST7789 TFT display.

Send JSON over **HTTP** or **MQTT** to show text, progress bars, shapes, and lines on the screen. Includes 7 built-in fonts (FreeSans, FreeMono, FreeSerif at multiple sizes) for clean, proportional text rendering.

## Quick Start

1. **Flash the firmware:**
   ```bash
   pio run -t upload
   ```

2. **Connect to WiFi:** On first boot the device creates an AP called **miniTV-Setup**. Connect to it and use the captive portal to configure:
   - WiFi network
   - Device name (mDNS hostname, default: `minitv`)
   - MQTT broker, port, username, password (optional)

3. **Send something to the display:**

   Via HTTP:
   ```bash
   curl -X POST http://minitv.local/display \
     -H "Content-Type: application/json" -d '{
     "bg": "#000000",
     "items": [
       {"type": "text", "x": 120, "y": 100, "text": "Hello!", "font": "sans-18", "color": "#00FF00", "align": "center"}
     ]
   }'
   ```

   Via MQTT:
   ```bash
   mosquitto_pub -h broker.example.com -t /minitv/display -m '{
     "bg": "#000000",
     "items": [
       {"type": "text", "x": 120, "y": 100, "text": "Hello!", "font": "sans-18", "color": "#00FF00", "align": "center"}
     ]
   }'
   ```

4. **Run the demo:**
   ```bash
   ./demo.sh                                          # HTTP demo
   ./demo-mqtt.sh minitv broker.example.com user pass  # MQTT demo
   ```

## Display Protocol

POST JSON to `/display` (HTTP) or publish to `/<device-name>/display` (MQTT):

```json
{
  "bg": "#001122",
  "items": [
    {"type": "text", "x": 10, "y": 10, "text": "CPU", "font": "sans-9", "color": "#888888"},
    {"type": "text", "x": 230, "y": 10, "text": "62%", "font": "sans-9", "color": "#FFFFFF", "align": "right", "maxWidth": "100%"},
    {"type": "progress", "x": 10, "y": 24, "w": 220, "h": 10, "value": 0.62, "color": "#4488FF", "bg": "#111122", "border": "#222244"},
    {"type": "rect", "x": 10, "y": 50, "w": 220, "h": 2, "color": "#333333", "fill": true},
    {"type": "line", "x1": 0, "y1": 0, "x2": 240, "y2": 240, "color": "#FF0000"},
    {"type": "circle", "x": 120, "y": 170, "r": 30, "color": "#00FF00", "fill": true}
  ]
}
```

**Item types:** `text`, `progress`, `rect`, `line`, `circle`

**Available fonts:** `sans-9`, `sans-12`, `sans-18`, `mono-12`, `mono-18`, `serif-12`, `serif-18` — select per text item via the `font` field. Omit for the built-in 6x8 pixel font.

See [API.md](API.md) for the full protocol reference.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Device info (IP, hostname, display size, available fonts, uptime) |
| POST | `/display` | Render items on display |
| POST | `/reset-wifi` | Clear WiFi and MQTT credentials, reboot into setup AP |

## Senders

Ready-made Python scripts that push live data to the display. All senders support both HTTP and MQTT:

| Script | Description |
|--------|-------------|
| `senders/macos-stats.py` | macOS system monitor — CPU, memory, temperature, network rates |
| `senders/claude-usage.py` | Claude Code usage — tokens, messages, sessions, reset timer (reads local data, no API key needed) |
| `senders/fear-and-greed.py` | Crypto Fear & Greed Index with color gauge |
| `senders/winfidel.py` | [WInFiDEL](https://github.com/epatel/winfidel-sensor) filament diameter sensor — supports 1 or 2 sensors |

```bash
# HTTP (default)
python3 senders/macos-stats.py
python3 senders/macos-stats.py http://minitv2.local/display

# MQTT
python3 senders/macos-stats.py --mqtt-broker rpi4.example.com --mqtt-device minitv
python3 senders/macos-stats.py --mqtt-broker rpi4.example.com --mqtt-device minitv --mqtt-user user --mqtt-pass pass

# Other senders
python3 senders/claude-usage.py --plan max5
python3 senders/fear-and-greed.py
python3 senders/winfidel.py --host winfidel.local
python3 senders/winfidel.py --host s1 --host s2
```

All senders auto-resolve `.local` hostnames and only send updates when values change.

## Hardware

- **MCU:** ESP8266 (ESP-12F)
- **Display:** ST7789, 240x240px, SPI
- **Device:** GeekMagic SmallTV (non-pro version)

## Building

Requires [PlatformIO](https://platformio.org/).

```bash
pio run              # Build
pio run -t upload    # Build and flash
pio device monitor -b 74880  # Serial monitor
```
