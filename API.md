# miniTV Display Protocol

The miniTV device runs an HTTP server that accepts JSON to control what is shown on the 240x240 pixel display.

## WiFi Setup

On first boot (or after a WiFi reset), the device creates an AP called **"miniTV-Setup"**. Connect to it from your phone or laptop — a captive portal will open where you can select your WiFi network and enter the password. Credentials are saved to flash and used for subsequent boots. The config portal times out after 3 minutes and reboots if no connection is made.

## Endpoints

### `GET /`

Returns device info as JSON.

```json
{"ip":"192.168.68.128","hostname":"minitv","display":{"width":240,"height":240},"fonts":["sans-9","sans-12","sans-18","mono-12","mono-18","serif-12","serif-18"],"uptime":42}
```

### `POST /reset-wifi`

Clears saved WiFi credentials and reboots into setup mode. The device creates an AP called **"miniTV-Setup"** for reconfiguration.

```bash
/usr/bin/curl -X POST http://minitv.local/reset-wifi
```

**Response:** `{"ok":true,"msg":"WiFi reset, rebooting..."}`

### `POST /display`

Renders items on the display. Send a JSON body with a background color and a list of draw items.

```json
{
  "bg": "#000000",
  "items": [
    {"type": "text", "x": 120, "y": 10, "text": "Hello", "font": "sans-18", "color": "#FFFFFF", "align": "center"}
  ]
}
```

**Response:** `{"ok":true}` on success, `{"error":"..."}` on failure.

## Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bg` | string | `"#000000"` | Background color (hex `"#RRGGBB"`) |
| `items` | array | required | List of draw commands (max 32) |

## Item types

### `text`

Draws a text string.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | int | `0` | X position (anchor point depends on `align`) |
| `y` | int | `0` | Y position (top of text) |
| `text` | string | `""` | Text content (max 31 chars) |
| `size` | int | `1` | Font scale (1=6x8px per char, 2=12x16, 3=18x24, ...) |
| `font` | string | — | Font name (e.g. `"sans-12"`, `"mono-18"`). Omit for built-in 6x8 font. When set, `size` is ignored. |
| `color` | string | `"#FFFFFF"` | Text color |
| `align` | string | `"left"` | `"left"`, `"center"`, or `"right"` — determines how `x` is used |
| `maxWidth` | string | — | Sample string defining fixed bounding width (e.g. `"100%"` for a percentage that changes). Prevents layout recalculation when text content changes. |

**Alignment behavior:**
- `"left"`: `x` is the left edge of the text
- `"center"`: `x` is the center point
- `"right"`: `x` is the right edge

### `progress`

Draws a horizontal progress bar with border.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | int | `0` | Left edge |
| `y` | int | `0` | Top edge |
| `w` | int | `100` | Width in pixels |
| `h` | int | `16` | Height in pixels |
| `value` | float | `0.0` | Progress value, 0.0 to 1.0 |
| `color` | string | `"#7F00FF"` | Fill color |
| `bg` | string | `"#333333"` | Background color (unfilled area) |
| `border` | string | `"#FFFFFF"` | Border color |

### `rect`

Draws a rectangle (filled or outline).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | int | `0` | Left edge |
| `y` | int | `0` | Top edge |
| `w` | int | `10` | Width |
| `h` | int | `10` | Height |
| `color` | string | `"#FFFFFF"` | Color |
| `fill` | bool | `false` | Fill the rectangle |

### `line`

Draws a line between two points.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x1` | int | `0` | Start X |
| `y1` | int | `0` | Start Y |
| `x2` | int | `0` | End X |
| `y2` | int | `0` | End Y |
| `color` | string | `"#FFFFFF"` | Color |

### `circle`

Draws a circle (filled or outline).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | int | `0` | Center X |
| `y` | int | `0` | Center Y |
| `r` | int | `10` | Radius |
| `color` | string | `"#FFFFFF"` | Color |
| `fill` | bool | `false` | Fill the circle |

## Available fonts

Custom fonts are selected per text item via the `font` field. When omitted, the built-in 6x8 monospaced font is used with the `size` multiplier.

| Name | Family | Size | Approx Height |
|------|--------|------|---------------|
| `sans-9` | FreeSans | 9pt | ~13px |
| `sans-12` | FreeSans | 12pt | ~17px |
| `sans-18` | FreeSans | 18pt | ~25px |
| `mono-12` | FreeMono | 12pt | ~17px |
| `mono-18` | FreeMono | 18pt | ~25px |
| `serif-12` | FreeSerif | 12pt | ~17px |
| `serif-18` | FreeSerif | 18pt | ~25px |

Query `GET /` for the `"fonts"` array to discover available fonts at runtime.

## Colors

All colors are hex strings in `"#RRGGBB"` format. They are converted to 16-bit RGB565 internally.

## Performance notes

- **Layout caching:** The device compares the structural layout (item types, positions, sizes) between frames. If only values change (text content, progress value, colors), items are overdrawn in place with no screen clear — this eliminates flicker.
- **`maxWidth` field:** For text that changes content but should keep a stable bounding box (e.g. a percentage counter), set `maxWidth` to a sample string representing the widest expected value. This prevents layout changes that trigger a full screen redraw.
- **Canvas blitting:** Text is rendered to an off-screen buffer and pushed to the display in a single SPI transfer, which is significantly faster than pixel-by-pixel rendering.
- **Item limit:** Maximum 32 items per frame.
- **Text length:** Maximum 31 characters per text item.

## Example: animated progress

```bash
/usr/bin/curl -X POST http://minitv.local/display \
  -H "Content-Type: application/json" -d '{
  "bg": "#000000",
  "items": [
    {"type": "text", "x": 120, "y": 55, "text": "Uploading...", "font": "sans-18", "color": "#FFFFFF", "align": "center", "maxWidth": "Uploading..."},
    {"type": "progress", "x": 20, "y": 100, "w": 200, "h": 24, "value": 0.42, "color": "#7F00FF", "bg": "#222222", "border": "#FFFFFF"},
    {"type": "text", "x": 120, "y": 135, "text": "42%", "font": "sans-12", "color": "#FFFFFF", "align": "center", "maxWidth": "100%"}
  ]
}'
```

## Demo

Run the included demo scripts to see all features:

```bash
./demo.sh                                          # HTTP, uses minitv.local
./demo.sh 192.168.1.42                             # HTTP, explicit IP
./demo-mqtt.sh minitv broker.example.com user pass  # MQTT
```
