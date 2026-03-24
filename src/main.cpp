#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>
#include <ESP8266mDNS.h>
#include <WiFiManager.h>
#include <EEPROM.h>
#include <PubSubClient.h>

// Adafruit GFX custom fonts
#include <Fonts/FreeSans9pt7b.h>
#include <Fonts/FreeSans12pt7b.h>
#include <Fonts/FreeSans18pt7b.h>
#include <Fonts/FreeMono12pt7b.h>
#include <Fonts/FreeMono18pt7b.h>
#include <Fonts/FreeSerif12pt7b.h>
#include <Fonts/FreeSerif18pt7b.h>

// Font lookup table — in RAM (only ~56 bytes; PROGMEM would require pgm_read_ptr for pointers)
struct FontEntry {
  const char* name;
  const GFXfont* font;
};

#define FONT_COUNT 7

const FontEntry fontTable[FONT_COUNT] = {
  {"sans-9",   &FreeSans9pt7b},
  {"sans-12",  &FreeSans12pt7b},
  {"sans-18",  &FreeSans18pt7b},
  {"mono-12",  &FreeMono12pt7b},
  {"mono-18",  &FreeMono18pt7b},
  {"serif-12", &FreeSerif12pt7b},
  {"serif-18", &FreeSerif18pt7b},
};

// Resolve font name to fontId (1-based index into fontTable, 0 = built-in)
uint8_t lookupFontId(const char* name) {
  if (!name || name[0] == '\0') return 0;
  for (uint8_t i = 0; i < FONT_COUNT; i++) {
    if (strcmp(name, fontTable[i].name) == 0) return i + 1;
  }
  return 0;  // unknown font → fall back to built-in
}

// Get GFXfont pointer from fontId (NULL = built-in)
const GFXfont* getFontPtr(uint8_t fontId) {
  if (fontId == 0 || fontId > FONT_COUNT) return NULL;
  return fontTable[fontId - 1].font;
}

// EEPROM layout: config storage
#define HOSTNAME_MAX 32
#define MQTT_HOST_MAX 64
#define MQTT_PORT_MAX 6
#define MQTT_USER_MAX 32
#define MQTT_PASS_MAX 32
#define EEPROM_SIZE 256
#define EEPROM_MAGIC 0xAD  // bump magic to reset old configs

// byte 0: magic
// bytes 1-32: hostname
// bytes 33-96: mqtt_host
// bytes 97-102: mqtt_port
// bytes 103-134: mqtt_user
// bytes 135-166: mqtt_pass

char hostname[HOSTNAME_MAX] = "minitv";
char mqtt_host[MQTT_HOST_MAX] = "";
char mqtt_port_str[MQTT_PORT_MAX] = "1883";
char mqtt_user[MQTT_USER_MAX] = "";
char mqtt_pass[MQTT_PASS_MAX] = "";

void loadConfig() {
  EEPROM.begin(EEPROM_SIZE);
  if (EEPROM.read(0) == EEPROM_MAGIC) {
    for (int i = 0; i < HOSTNAME_MAX - 1; i++) {
      char c = EEPROM.read(1 + i);
      hostname[i] = c;
      if (c == '\0') break;
    }
    hostname[HOSTNAME_MAX - 1] = '\0';
    for (int i = 0; i < MQTT_HOST_MAX - 1; i++) {
      char c = EEPROM.read(33 + i);
      mqtt_host[i] = c;
      if (c == '\0') break;
    }
    mqtt_host[MQTT_HOST_MAX - 1] = '\0';
    for (int i = 0; i < MQTT_PORT_MAX - 1; i++) {
      char c = EEPROM.read(97 + i);
      mqtt_port_str[i] = c;
      if (c == '\0') break;
    }
    mqtt_port_str[MQTT_PORT_MAX - 1] = '\0';
    for (int i = 0; i < MQTT_USER_MAX - 1; i++) {
      char c = EEPROM.read(103 + i);
      mqtt_user[i] = c;
      if (c == '\0') break;
    }
    mqtt_user[MQTT_USER_MAX - 1] = '\0';
    for (int i = 0; i < MQTT_PASS_MAX - 1; i++) {
      char c = EEPROM.read(135 + i);
      mqtt_pass[i] = c;
      if (c == '\0') break;
    }
    mqtt_pass[MQTT_PASS_MAX - 1] = '\0';
  }
  EEPROM.end();
}

void saveConfig() {
  EEPROM.begin(EEPROM_SIZE);
  EEPROM.write(0, EEPROM_MAGIC);
  for (int i = 0; i < HOSTNAME_MAX; i++) EEPROM.write(1 + i, hostname[i]);
  for (int i = 0; i < MQTT_HOST_MAX; i++) EEPROM.write(33 + i, mqtt_host[i]);
  for (int i = 0; i < MQTT_PORT_MAX; i++) EEPROM.write(97 + i, mqtt_port_str[i]);
  for (int i = 0; i < MQTT_USER_MAX; i++) EEPROM.write(103 + i, mqtt_user[i]);
  for (int i = 0; i < MQTT_PASS_MAX; i++) EEPROM.write(135 + i, mqtt_pass[i]);
  EEPROM.commit();
  EEPROM.end();
}

// GeekMagic SmallTV pinout
#define TFT_CS   -1
#define TFT_DC   D3     // GPIO0
#define TFT_RST  D4     // GPIO2
#define TFT_BL   D1     // GPIO5 - backlight (inverted)

Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);
ESP8266WebServer server(80);
WiFiClient mqttWifiClient;
PubSubClient mqtt(mqttWifiClient);
unsigned long lastMqttReconnect = 0;
bool mqttEnabled = false;
bool mqttWasConnected = false;
bool mqttShowingStatus = true;  // show status until first message arrives

// --- Draw list ---

enum CmdType : uint8_t {
  CMD_TEXT, CMD_PROGRESS, CMD_RECT, CMD_LINE, CMD_CIRCLE
};

enum Align : uint8_t {
  ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT
};

#define MAX_TEXT_LEN 32
#define MAX_CMDS 32

struct DrawCmd {
  CmdType type;
  int16_t x, y;
  uint16_t color;
  union {
    struct { char text[MAX_TEXT_LEN]; uint8_t size; Align align; uint16_t fixedW; uint8_t fontId; } t;
    struct { int16_t w, h; uint16_t bg, border; float value; } p;
    struct { int16_t w, h; bool fill; } r;
    struct { int16_t x2, y2; } l;
    struct { int16_t r; bool fill; } c;
  };
};

DrawCmd drawList[MAX_CMDS];
uint8_t drawCount = 0;
uint16_t bgColor = ST77XX_BLACK;
volatile bool drawPending = false;

// Layout fingerprint: type + position + size for each item
struct LayoutKey {
  CmdType type;
  int16_t x, y, w, h;
  uint8_t fontId;
};

LayoutKey prevLayout[MAX_CMDS];
uint8_t prevLayoutCount = 0;
uint16_t prevBgColor = ST77XX_BLACK;
bool firstFrame = true;

// --- Color parsing ---

uint16_t parseColor(const char* hex) {
  if (!hex || hex[0] != '#' || strlen(hex) < 7) return ST77XX_WHITE;
  uint32_t rgb = strtoul(hex + 1, nullptr, 16);
  uint8_t r = (rgb >> 16) & 0xFF;
  uint8_t g = (rgb >> 8) & 0xFF;
  uint8_t b = rgb & 0xFF;
  return tft.color565(r, g, b);
}

// --- JSON to draw list ---

void parseDrawList(JsonDocument& doc) {
  bgColor = parseColor(doc["bg"] | "#000000");
  drawCount = 0;

  JsonArray items = doc["items"];
  for (JsonObject item : items) {
    if (drawCount >= MAX_CMDS) break;

    DrawCmd& cmd = drawList[drawCount];
    const char* type = item["type"] | "";

    if (strcmp(type, "text") == 0) {
      cmd.type = CMD_TEXT;
      cmd.x = item["x"] | 0;
      cmd.y = item["y"] | 0;
      cmd.color = parseColor(item["color"] | "#FFFFFF");
      cmd.t.size = item["size"] | 1;
      const char* align = item["align"] | "left";
      if (align[0] == 'r') cmd.t.align = ALIGN_RIGHT;
      else if (align[0] == 'c') cmd.t.align = ALIGN_CENTER;
      else cmd.t.align = ALIGN_LEFT;
      strncpy(cmd.t.text, item["text"] | "", MAX_TEXT_LEN - 1);
      cmd.t.text[MAX_TEXT_LEN - 1] = '\0';

      // Font must be resolved before maxWidth measurement
      cmd.t.fontId = lookupFontId(item["font"] | "");

      // maxWidth: sample string defining the fixed bounding width
      if (item["maxWidth"].is<const char*>()) {
        const char* sample = item["maxWidth"].as<const char*>();
        if (cmd.t.fontId > 0) {
          // GFXfont: measure sample string with actual font
          const GFXfont* font = getFontPtr(cmd.t.fontId);
          tft.setFont(font);
          int16_t x1, y1;
          uint16_t sw, sh;
          tft.getTextBounds(sample, 0, 0, &x1, &y1, &sw, &sh);
          cmd.t.fixedW = sw;
          tft.setFont(NULL);
        } else {
          cmd.t.fixedW = strlen(sample) * 6 * cmd.t.size;
        }
      } else {
        cmd.t.fixedW = 0;
      }

    } else if (strcmp(type, "progress") == 0) {
      cmd.type = CMD_PROGRESS;
      cmd.x = item["x"] | 0;
      cmd.y = item["y"] | 0;
      cmd.p.w = item["w"] | 100;
      cmd.p.h = item["h"] | 16;
      cmd.p.value = item["value"] | 0.0f;
      if (cmd.p.value < 0.0f) cmd.p.value = 0.0f;
      if (cmd.p.value > 1.0f) cmd.p.value = 1.0f;
      cmd.color = parseColor(item["color"] | "#7F00FF");
      cmd.p.bg = parseColor(item["bg"] | "#333333");
      cmd.p.border = parseColor(item["border"] | "#FFFFFF");

    } else if (strcmp(type, "rect") == 0) {
      cmd.type = CMD_RECT;
      cmd.x = item["x"] | 0;
      cmd.y = item["y"] | 0;
      cmd.r.w = item["w"] | 10;
      cmd.r.h = item["h"] | 10;
      cmd.color = parseColor(item["color"] | "#FFFFFF");
      cmd.r.fill = item["fill"] | false;

    } else if (strcmp(type, "line") == 0) {
      cmd.type = CMD_LINE;
      cmd.x = item["x1"] | 0;
      cmd.y = item["y1"] | 0;
      cmd.l.x2 = item["x2"] | 0;
      cmd.l.y2 = item["y2"] | 0;
      cmd.color = parseColor(item["color"] | "#FFFFFF");

    } else if (strcmp(type, "circle") == 0) {
      cmd.type = CMD_CIRCLE;
      cmd.x = item["x"] | 0;
      cmd.y = item["y"] | 0;
      cmd.c.r = item["r"] | 10;
      cmd.color = parseColor(item["color"] | "#FFFFFF");
      cmd.c.fill = item["fill"] | false;

    } else {
      continue;
    }
    drawCount++;
  }
}

// --- Render from draw list ---

// Compute bounding box for a command, clear it with bg, then draw.
// This avoids full-screen fillScreen flash.

// Use fixed-width bounds based on string length, not actual glyph widths.
// Built-in font: 6px wide, 8px tall per char at size 1.
// This keeps bounding box stable when text content changes (e.g. "49%" -> "50%").
void getTextPos(DrawCmd& cmd, int16_t &cx, int16_t &cy, uint16_t &tw, uint16_t &th) {
  if (cmd.t.fontId > 0) {
    // GFXfont: use getTextBounds for width, yAdvance for stable height
    const GFXfont* font = getFontPtr(cmd.t.fontId);
    tft.setFont(font);
    tft.setTextSize(1);
    int16_t x1, y1;
    uint16_t textW, textH;
    tft.getTextBounds(cmd.t.text, 0, 0, &x1, &y1, &textW, &textH);
    // Canvas renders from cursor 0, but bounding box starts at x1 offset
    // Need x1 + textW total width to avoid clipping rightmost glyphs
    uint16_t fullW = (x1 > 0) ? (uint16_t)(x1 + textW) : textW;
    tw = cmd.t.fixedW > 0 ? cmd.t.fixedW : fullW;
    th = pgm_read_byte(&font->yAdvance);  // PROGMEM: stable height regardless of glyph content
    tft.setFont(NULL);
  } else {
    // Built-in font: fixed 6x8 per char at size 1
    uint16_t textW = strlen(cmd.t.text) * 6 * cmd.t.size;
    tw = cmd.t.fixedW > 0 ? cmd.t.fixedW : textW;
    th = 8 * cmd.t.size;
  }

  if (cmd.t.align == ALIGN_RIGHT) {
    cx = cmd.x - (int)tw;
  } else if (cmd.t.align == ALIGN_CENTER) {
    cx = cmd.x - (int)tw / 2;
  } else {
    cx = cmd.x;
  }
  cy = cmd.y;
}

// Get cursor position for text within its fixed-width box
void getTextCursor(DrawCmd& cmd, int16_t boxX, uint16_t boxW, int16_t &cursorX, int16_t &cursorY) {
  if (cmd.t.fontId > 0) {
    // GFXfont: measure actual text width for alignment within box
    const GFXfont* font = getFontPtr(cmd.t.fontId);
    tft.setFont(font);
    tft.setTextSize(1);
    int16_t x1, y1;
    uint16_t textW, textH;
    tft.getTextBounds(cmd.t.text, 0, 0, &x1, &y1, &textW, &textH);
    if (cmd.t.align == ALIGN_RIGHT) {
      cursorX = boxX + (int)boxW - (int)textW;
    } else if (cmd.t.align == ALIGN_CENTER) {
      cursorX = boxX + ((int)boxW - (int)textW) / 2;
    } else {
      cursorX = boxX;
    }
    // Baseline correction: y1 is negative offset from baseline to top
    // cmd.y is desired top, so cursor_y (baseline) = cmd.y - y1
    cursorY = cmd.y - y1;
    tft.setFont(NULL);
  } else {
    // Built-in font: fixed-width math
    uint16_t textW = strlen(cmd.t.text) * 6 * cmd.t.size;
    if (cmd.t.align == ALIGN_RIGHT) {
      cursorX = boxX + (int)boxW - (int)textW;
    } else if (cmd.t.align == ALIGN_CENTER) {
      cursorX = boxX + ((int)boxW - (int)textW) / 2;
    } else {
      cursorX = boxX;
    }
    cursorY = cmd.y;
  }
}

LayoutKey computeLayoutKey(DrawCmd& cmd) {
  switch (cmd.type) {
    case CMD_TEXT: {
      int16_t cx, cy; uint16_t tw, th;
      getTextPos(cmd, cx, cy, tw, th);
      return {cmd.type, cx, cy, (int16_t)tw, (int16_t)th, cmd.t.fontId};
    }
    case CMD_PROGRESS:
      return {cmd.type, cmd.x, cmd.y, cmd.p.w, cmd.p.h, 0};
    case CMD_RECT:
      return {cmd.type, cmd.x, cmd.y, cmd.r.w, cmd.r.h, 0};
    case CMD_LINE:
      return {cmd.type, cmd.x, cmd.y, cmd.l.x2, cmd.l.y2, 0};
    case CMD_CIRCLE:
      return {cmd.type, cmd.x, cmd.y, cmd.c.r, 0, 0};
    default:
      return {cmd.type, 0, 0, 0, 0, 0};
  }
}

bool layoutChanged() {
  if (firstFrame) { Serial.println("layout: first frame"); return true; }
  if (drawCount != prevLayoutCount) { Serial.printf("layout: count %d->%d\n", prevLayoutCount, drawCount); return true; }
  if (bgColor != prevBgColor) { Serial.println("layout: bg changed"); return true; }
  for (uint8_t i = 0; i < drawCount; i++) {
    LayoutKey key = computeLayoutKey(drawList[i]);
    if (key.type != prevLayout[i].type ||
        key.x != prevLayout[i].x || key.y != prevLayout[i].y ||
        key.w != prevLayout[i].w || key.h != prevLayout[i].h ||
        key.fontId != prevLayout[i].fontId) {
      Serial.printf("layout: item %d changed type=%d x=%d,%d w=%d,%d vs x=%d,%d w=%d,%d\n",
        i, key.type, key.x, key.y, key.w, key.h,
        prevLayout[i].x, prevLayout[i].y, prevLayout[i].w, prevLayout[i].h);
      return true;
    }
  }
  return false;
}

void renderDrawList() {
  tft.startWrite();

  bool needFullClear = layoutChanged();

  if (needFullClear) {
    tft.fillScreen(bgColor);
    // Save new layout
    for (uint8_t i = 0; i < drawCount; i++) {
      prevLayout[i] = computeLayoutKey(drawList[i]);
    }
    prevLayoutCount = drawCount;
    prevBgColor = bgColor;
    firstFrame = false;
  }

  // Draw all new items
  for (uint8_t i = 0; i < drawCount; i++) {
    DrawCmd& cmd = drawList[i];

    switch (cmd.type) {
      case CMD_TEXT: {
        int16_t cx, cy;
        uint16_t tw, th;
        getTextPos(cmd, cx, cy, tw, th);
        // Cursor within the (possibly fixed-width) box
        int16_t cursorX, cursorY;
        getTextCursor(cmd, cx, tw, cursorX, cursorY);

        const GFXfont* font = getFontPtr(cmd.t.fontId);

        if (tw > 0 && th > 0 && tw <= 240 && (uint32_t)tw * th * 2 <= 4096) {
          // Render to off-screen canvas, then blit in one SPI burst
          GFXcanvas16 canvas(tw, th);
          canvas.fillScreen(bgColor);
          canvas.setFont(font);
          if (cmd.t.fontId > 0) {
            canvas.setTextSize(1);
          } else {
            canvas.setTextSize(cmd.t.size);
          }
          canvas.setTextColor(cmd.color);
          // Canvas cursor: offset from box origin
          int16_t canvasCursorX = cursorX - cx;
          int16_t canvasCursorY = cursorY - cy;
          canvas.setCursor(canvasCursorX, canvasCursorY);
          canvas.print(cmd.t.text);
          tft.drawRGBBitmap(cx, cy, canvas.getBuffer(), tw, th);
        } else {
          // Too large for canvas — direct draw with background clear
          // Note: GFXfonts don't support bg color in setTextColor, so fillRect first
          tft.fillRect(cx, cy, tw, th, bgColor);
          tft.setFont(font);
          if (cmd.t.fontId > 0) {
            tft.setTextSize(1);
            tft.setTextColor(cmd.color);
          } else {
            tft.setTextSize(cmd.t.size);
            tft.setTextColor(cmd.color, bgColor);
          }
          tft.setCursor(cursorX, cursorY);
          tft.print(cmd.t.text);
        }
        // Reset font to built-in for any subsequent non-text drawing
        tft.setFont(NULL);
        break;
      }
      case CMD_PROGRESS: {
        tft.drawRect(cmd.x, cmd.y, cmd.p.w, cmd.p.h, cmd.p.border);
        int fillW = (int)(cmd.p.value * (cmd.p.w - 2));
        if (fillW > 0)
          tft.fillRect(cmd.x + 1, cmd.y + 1, fillW, cmd.p.h - 2, cmd.color);
        if (fillW < cmd.p.w - 2)
          tft.fillRect(cmd.x + 1 + fillW, cmd.y + 1, cmd.p.w - 2 - fillW, cmd.p.h - 2, cmd.p.bg);
        break;
      }
      case CMD_RECT:
        if (cmd.r.fill)
          tft.fillRect(cmd.x, cmd.y, cmd.r.w, cmd.r.h, cmd.color);
        else
          tft.drawRect(cmd.x, cmd.y, cmd.r.w, cmd.r.h, cmd.color);
        break;
      case CMD_LINE:
        tft.drawLine(cmd.x, cmd.y, cmd.l.x2, cmd.l.y2, cmd.color);
        break;
      case CMD_CIRCLE:
        if (cmd.c.fill)
          tft.fillCircle(cmd.x, cmd.y, cmd.c.r, cmd.color);
        else
          tft.drawCircle(cmd.x, cmd.y, cmd.c.r, cmd.color);
        break;
    }
  }
  tft.endWrite();
}

// --- HTTP handlers ---

// --- MQTT ---

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Parse JSON and queue for rendering — same format as POST /display
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.printf("MQTT JSON error: %s\n", err.c_str());
    return;
  }
  parseDrawList(doc);
  drawPending = true;
  mqttShowingStatus = false;
  Serial.println("MQTT: display updated");
}

void showMqttStatus(bool connected) {
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);
  tft.setCursor(10, 30);
  tft.print("MQTT");
  tft.setTextSize(1);
  tft.setCursor(10, 55);
  tft.printf("Broker: %s:%s", mqtt_host, mqtt_port_str);
  tft.setCursor(10, 70);
  tft.printf("Topic: /%s/display", hostname);
  if (connected) {
    tft.setTextColor(ST77XX_GREEN);
    tft.setTextSize(2);
    tft.setCursor(10, 100);
    tft.print("Connected");
    tft.setTextColor(ST77XX_WHITE);
    tft.setTextSize(1);
    tft.setCursor(10, 125);
    tft.print("Waiting for data...");
  } else {
    tft.setTextColor(ST77XX_RED);
    tft.setTextSize(2);
    tft.setCursor(10, 100);
    tft.print("Disconnected");
    tft.setTextColor(ST77XX_WHITE);
    tft.setTextSize(1);
    tft.setCursor(10, 125);
    tft.print("Reconnecting...");
  }
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(1);
  tft.setCursor(10, 155);
  tft.print(WiFi.localIP());
  tft.setCursor(10, 170);
  tft.printf("%s.local", hostname);
}

void connectMqtt() {
  if (!mqttEnabled || mqtt.connected()) return;

  String clientId = String(hostname) + "-" + String(ESP.getChipId(), HEX);
  Serial.printf("MQTT connecting to %s:%s as %s...\n", mqtt_host, mqtt_port_str, clientId.c_str());

  bool connected;
  if (strlen(mqtt_user) > 0) {
    connected = mqtt.connect(clientId.c_str(), mqtt_user, mqtt_pass);
  } else {
    connected = mqtt.connect(clientId.c_str());
  }
  if (connected) {
    String topic = String("/") + hostname + "/display";
    mqtt.subscribe(topic.c_str(), 0);  // QoS 0 — drop old messages
    Serial.printf("MQTT subscribed: %s\n", topic.c_str());
  } else {
    Serial.printf("MQTT connect failed, rc=%d\n", mqtt.state());
  }
}

// --- HTTP handlers ---

void handlePost() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"no body\"}");
    return;
  }

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    String msg = "{\"error\":\"";
    msg += err.c_str();
    msg += "\"}";
    server.send(400, "application/json", msg);
    return;
  }

  // Parse first, respond, then draw
  parseDrawList(doc);
  server.send(200, "application/json", "{\"ok\":true}");
  drawPending = true;
}

void handleGet() {
  String json = "{";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"hostname\":\"" + String(hostname) + "\",";
  json += "\"display\":{\"width\":240,\"height\":240},";
  json += "\"fonts\":[";
  for (uint8_t i = 0; i < FONT_COUNT; i++) {
    if (i > 0) json += ",";
    json += "\"";
    json += fontTable[i].name;
    json += "\"";
  }
  json += "],";
  json += "\"uptime\":" + String(millis() / 1000);
  json += "}";
  server.send(200, "application/json", json);
}

void showStatus(const char* msg) {
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);
  tft.setCursor(10, 110);
  tft.println(msg);
}

void setup() {
  Serial.begin(74880);
  Serial.println("miniTV Display Server");

  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, LOW);

  tft.init(240, 240, SPI_MODE3);
  tft.setRotation(2);
  tft.setSPISpeed(40000000);

  // Load saved config from EEPROM
  loadConfig();

  // Show connecting with saved SSID if available
  String savedSSID = WiFi.SSID();
  if (savedSSID.length() > 0) {
    tft.fillScreen(ST77XX_BLACK);
    tft.setTextColor(ST77XX_WHITE);
    tft.setTextSize(2);
    tft.setCursor(10, 90);
    tft.print("Connecting...");
    tft.setTextSize(1);
    tft.setCursor(10, 115);
    tft.print(savedSSID);
  } else {
    showStatus("Connecting...");
  }
  WiFiManager wm;
  WiFiManagerParameter hostnameParam("hostname", "Device name (mDNS)", hostname, HOSTNAME_MAX - 1);
  WiFiManagerParameter mqttHostParam("mqtt_host", "MQTT broker (optional)", mqtt_host, MQTT_HOST_MAX - 1);
  WiFiManagerParameter mqttPortParam("mqtt_port", "MQTT port", mqtt_port_str, MQTT_PORT_MAX - 1);
  WiFiManagerParameter mqttUserParam("mqtt_user", "MQTT username (optional)", mqtt_user, MQTT_USER_MAX - 1);
  WiFiManagerParameter mqttPassParam("mqtt_pass", "MQTT password (optional)", mqtt_pass, MQTT_PASS_MAX - 1);
  wm.addParameter(&hostnameParam);
  wm.addParameter(&mqttHostParam);
  wm.addParameter(&mqttPortParam);
  wm.addParameter(&mqttUserParam);
  wm.addParameter(&mqttPassParam);
  wm.setShowInfoUpdate(false);
  const char* menu[] = {"wifi", "param", "info", "exit"};
  wm.setMenu(menu, 4);
  wm.setConnectTimeout(15);
  wm.setConnectRetries(3);        // 3 retries x 15s = ~45s total       // 30s to connect to saved WiFi
  wm.setConfigPortalTimeout(180);  // 3 min for config portal

  wm.setAPCallback([](WiFiManager*) {
    tft.fillScreen(ST77XX_BLACK);
    tft.setTextColor(ST77XX_YELLOW);
    tft.setTextSize(2);
    tft.setCursor(10, 50);
    tft.print("WiFi Setup");
    tft.setTextColor(ST77XX_WHITE);
    tft.setTextSize(1);
    tft.setCursor(10, 80);
    tft.print("Connect to WiFi:");
    tft.setTextColor(ST77XX_GREEN);
    tft.setCursor(10, 95);
    tft.print("miniTV-Setup");
    tft.setTextColor(ST77XX_WHITE);
    tft.setCursor(10, 115);
    tft.print("Then open browser to");
    tft.setCursor(10, 130);
    tft.print("configure network.");
    Serial.println("AP mode: miniTV-Setup");
  });

  wm.setSaveParamsCallback([&hostnameParam, &mqttHostParam, &mqttPortParam, &mqttUserParam, &mqttPassParam]() {
    strncpy(hostname, hostnameParam.getValue(), HOSTNAME_MAX - 1);
    hostname[HOSTNAME_MAX - 1] = '\0';
    strncpy(mqtt_host, mqttHostParam.getValue(), MQTT_HOST_MAX - 1);
    mqtt_host[MQTT_HOST_MAX - 1] = '\0';
    strncpy(mqtt_port_str, mqttPortParam.getValue(), MQTT_PORT_MAX - 1);
    mqtt_port_str[MQTT_PORT_MAX - 1] = '\0';
    strncpy(mqtt_user, mqttUserParam.getValue(), MQTT_USER_MAX - 1);
    mqtt_user[MQTT_USER_MAX - 1] = '\0';
    strncpy(mqtt_pass, mqttPassParam.getValue(), MQTT_PASS_MAX - 1);
    mqtt_pass[MQTT_PASS_MAX - 1] = '\0';
    saveConfig();
    Serial.printf("Config saved: hostname=%s mqtt=%s:%s user=%s\n", hostname, mqtt_host, mqtt_port_str, mqtt_user);
  });

  if (!wm.autoConnect("miniTV-Setup")) {
    showStatus("WiFi failed");
    Serial.println("WiFi config portal timed out");
    delay(3000);
    ESP.restart();
  }
  Serial.println("WiFi connected");
  Serial.println(WiFi.localIP());

  if (MDNS.begin(hostname)) {
    Serial.printf("mDNS: %s.local\n", hostname);
    MDNS.addService("http", "tcp", 80);
  }

  // Setup MQTT if broker configured
  if (strlen(mqtt_host) > 0) {
    mqttEnabled = true;
    int port = atoi(mqtt_port_str);
    if (port == 0) port = 1883;
    mqtt.setServer(mqtt_host, port);
    mqtt.setCallback(mqttCallback);
    mqtt.setBufferSize(4096);  // allow large JSON payloads
    connectMqtt();
    Serial.printf("MQTT enabled: %s:%d topic=/%s/display\n", mqtt_host, port, hostname);
  }

  server.on("/", HTTP_GET, handleGet);
  server.on("/display", HTTP_POST, handlePost);
  server.on("/reset-wifi", HTTP_POST, []() {
    server.send(200, "application/json", "{\"ok\":true,\"msg\":\"WiFi reset, rebooting...\"}");
    delay(500);
    WiFiManager wm;
    wm.resetSettings();
    ESP.restart();
  });
  server.begin();
  Serial.println("HTTP server started on port 80");

  if (mqttEnabled) {
    showMqttStatus(mqtt.connected());
    mqttWasConnected = mqtt.connected();
  } else {
    tft.fillScreen(ST77XX_BLACK);
    tft.setTextColor(ST77XX_GREEN);
    tft.setTextSize(2);
    tft.setCursor(10, 70);
    tft.print("miniTV Ready");
    tft.setTextColor(ST77XX_WHITE);
    tft.setTextSize(1);
    tft.setCursor(10, 100);
    tft.print(WiFi.localIP());
    tft.setCursor(10, 115);
    tft.printf("%s.local", hostname);
    tft.setCursor(10, 135);
    tft.print("POST /display");
  }
}

void loop() {
  MDNS.update();
  server.handleClient();

  // MQTT: reconnect if needed, process messages
  if (mqttEnabled) {
    bool isConnected = mqtt.connected();
    if (!isConnected) {
      unsigned long now = millis();
      if (now - lastMqttReconnect > 5000) {
        lastMqttReconnect = now;
        connectMqtt();
        isConnected = mqtt.connected();
      }
    }
    // Update status display on connection state change
    if (isConnected != mqttWasConnected) {
      if (!isConnected || mqttShowingStatus) {
        // Always show disconnect; show connect only if no content displayed yet
        showMqttStatus(isConnected);
      }
      mqttWasConnected = isConnected;
    }
    // Drain all queued MQTT messages, only render the last one
    drawPending = false;
    mqtt.loop();
    // If messages arrived, drain any remaining in the buffer
    if (drawPending) {
      for (int i = 0; i < 10; i++) {
        bool prevPending = drawPending;
        drawPending = false;
        mqtt.loop();
        if (!drawPending) {
          drawPending = prevPending;
          break;
        }
        yield();
      }
    }
  }

  if (drawPending) {
    drawPending = false;
    renderDrawList();
  }

  yield();
}
