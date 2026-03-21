<a href="https://claude.ai"><img src="made-with-claude.png" height="32" alt="Made with Claude"></a>

# miniTV

A tiny HTTP-driven display server for the [GeekMagic SmallTV](https://github.com/GeekMagicClock) device — an ESP8266 (ESP-12F) with a 240x240 ST7789 TFT display.

Send JSON over HTTP to show text, progress bars, shapes, and lines on the screen.

## Quick Start

1. **Flash the firmware:**
   ```bash
   pio run -t upload
   ```

2. **Connect to WiFi:** On first boot the device creates an AP called **miniTV-Setup**. Connect to it and use the captive portal to select your WiFi network.

3. **Send something to the display:**
   ```bash
   curl -X POST http://minitv.local/display \
     -H "Content-Type: application/json" -d '{
     "bg": "#000000",
     "items": [
       {"type": "text", "x": 120, "y": 100, "text": "Hello!", "size": 3, "color": "#00FF00", "align": "center"}
     ]
   }'
   ```

4. **Run the demo:**
   ```bash
   ./demo.sh
   ```

## Display Protocol

POST JSON to `/display` with a background color and a list of draw items:

```json
{
  "bg": "#001122",
  "items": [
    {"type": "text", "x": 10, "y": 10, "text": "CPU", "size": 1, "color": "#888888"},
    {"type": "text", "x": 230, "y": 10, "text": "62%", "size": 1, "color": "#FFFFFF", "align": "right", "maxWidth": "100%"},
    {"type": "progress", "x": 10, "y": 24, "w": 220, "h": 10, "value": 0.62, "color": "#4488FF", "bg": "#111122", "border": "#222244"},
    {"type": "rect", "x": 10, "y": 50, "w": 220, "h": 2, "color": "#333333", "fill": true},
    {"type": "line", "x1": 0, "y1": 0, "x2": 240, "y2": 240, "color": "#FF0000"},
    {"type": "circle", "x": 120, "y": 170, "r": 30, "color": "#00FF00", "fill": true}
  ]
}
```

**Item types:** `text`, `progress`, `rect`, `line`, `circle`

See [API.md](API.md) for the full protocol reference.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Device info (IP, display size, uptime) |
| POST | `/display` | Render items on display |
| POST | `/reset-wifi` | Clear WiFi credentials, reboot into setup AP |

## Senders

Ready-made Python scripts that push live data to the display:

| Script | Description |
|--------|-------------|
| `senders/macos-stats.py` | macOS system monitor — CPU, memory, temperature, network rates |
| `senders/claude-usage.py` | Claude Code usage — tokens, messages, sessions, reset timer (reads local data, no API key needed) |
| `senders/fear-and-greed.py` | Crypto Fear & Greed Index with color gauge |
| `senders/winfidel.py` | [WInFiDEL](https://github.com/epatel/winfidel-sensor) filament diameter sensor — supports 1 or 2 sensors |

```bash
python3 senders/macos-stats.py                    # system monitor
python3 senders/claude-usage.py --plan max5       # Claude usage (pro/max5/max20)
python3 senders/fear-and-greed.py                 # Fear & Greed Index
python3 senders/winfidel.py --host winfidel.local # single sensor
python3 senders/winfidel.py --host s1 --host s2   # dual sensors
```

All senders auto-resolve `minitv.local` and only send updates when values change.

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
