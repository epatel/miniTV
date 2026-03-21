# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ESP8266-based "miniTV" display server targeting the **GeekMagic SmallTV** device — a small display gadget with an ESP-12F (ESP8266) and a 240x240 ST7789 display. It runs an HTTP server that accepts JSON to render text, progress bars, shapes, and lines on the display.

## Hardware Details

- **MCU:** ESP8266 (ESP-12F), board: `esp12e`
- **Display:** ST7789, 240x240, connected via SPI
- **Display pinout (hardwired on the GeekMagic SmallTV PCB):**
  - CS: tied to GND (pass -1 to driver)
  - DC: GPIO0 (D3)
  - RST: GPIO2 (D4)
  - SCK: GPIO14 (D5, default SPI)
  - MOSI: GPIO13 (D7, default SPI)
  - Backlight: GPIO5 (D1), **inverted** via P-MOSFET (LOW = on)
- **SPI mode:** SPI_MODE3 required (non-default clock idle state)
- **RAM constraint:** ~40KB free — no framebuffer/double-buffering possible for 240x240

## Build Commands

```bash
pio run              # Build
pio run -t upload    # Build and flash via USB
pio device monitor -b 74880  # Serial monitor
```

## Architecture

### Firmware (`src/main.cpp`)

Single-file Arduino project using PlatformIO with the Arduino framework.

**Libraries:** Adafruit GFX, Adafruit ST7735/ST7789, ArduinoJson v7, ESP8266WebServer, ESP8266mDNS, WiFiManager.

**Rendering pipeline:**
1. HTTP POST receives JSON → parsed into flat `DrawCmd` struct array (max 32 items)
2. HTTP response sent immediately (before drawing)
3. Layout fingerprint compared to previous frame (type, position, size per item)
4. If layout unchanged: items overdraw in place (no flicker)
5. If layout changed: one `fillScreen` clear, then draw all items
6. Text rendered via `GFXcanvas16` off-screen buffer for fast SPI blitting (up to 4KB)
7. All drawing wrapped in `startWrite()/endWrite()` for batched SPI

**Network:** WiFiManager captive portal AP "miniTV-Setup", mDNS as `minitv.local`, HTTP on port 80.

**Endpoints:** `GET /` (device info), `POST /display` (render JSON), `POST /reset-wifi` (clear credentials + reboot).

### Senders (`senders/`)

Python scripts that push live data to the display. All senders share common patterns:
- Resolve `minitv.local` via `socket.getaddrinfo()` once at startup to avoid repeated mDNS lookups
- Use `/usr/bin/curl` for HTTP (Homebrew curl has routing issues with local network devices on macOS)
- Fingerprint-based change detection — only send when display content actually changes
- Use `maxWidth` JSON field for text that changes content but should keep stable bounding boxes

See [API.md](API.md) for the full display protocol reference.

## Key Conventions

### Firmware (C++)
- Use `PROGMEM` for constant data (lookup tables) to save RAM
- Use `(int16_t)pgm_read_word(...)` when reading signed values from PROGMEM — `pgm_read_word` returns `uint16_t` and will mangle negative values without the cast
- Never use `memcmp` on structs with mixed field sizes — padding bytes cause false mismatches; compare field-by-field instead
- Layout comparison uses `LayoutKey` structs with type + position + dimensions; text uses fixed-width bounds (`strlen * 6 * size`) or `fixedW` from `maxWidth` to prevent layout thrashing
- Serial baud rate: 74880 (matches ESP8266 boot loader output)

### Senders (Python)
- No external dependencies beyond Python stdlib — use `subprocess` to call `/usr/bin/curl` instead of `requests`/`urllib`
- Pass POST body via `stdin` (`-d @-`) to avoid command-line length limits
- Round values before fingerprinting to avoid noise-triggered updates
