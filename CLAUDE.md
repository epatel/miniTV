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

Single-file Arduino project (`src/main.cpp`) using PlatformIO with the Arduino framework.

**Libraries:** Adafruit GFX, Adafruit ST7735/ST7789, ArduinoJson v7, ESP8266WebServer, ESP8266mDNS.

**Rendering pipeline:**
1. HTTP POST receives JSON → parsed into flat `DrawCmd` struct array (max 32 items)
2. HTTP response sent immediately (before drawing)
3. Layout fingerprint compared to previous frame
4. If layout unchanged: items overdraw in place (no flicker)
5. If layout changed: one `fillScreen` clear, then draw all items
6. Text rendered via `GFXcanvas16` off-screen buffer for fast SPI blitting (up to 4KB)
7. All drawing wrapped in `startWrite()/endWrite()` for batched SPI

**Network:** mDNS advertised as `minitv.local`, HTTP server on port 80.

## Key Conventions

- Use `PROGMEM` for constant data (lookup tables) to save RAM
- Use `(int16_t)pgm_read_word(...)` when reading signed values from PROGMEM
- Never use `memcmp` on structs with mixed field sizes — padding bytes cause false mismatches; compare field-by-field instead
- WiFi uses WiFiManager — credentials stored in flash, configured via captive portal AP "miniTV-Setup"
- Use `/usr/bin/curl` on macOS — Homebrew curl has routing issues with local network devices
- Serial baud rate: 74880 (matches ESP8266 boot loader output)
