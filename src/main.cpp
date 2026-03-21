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

// Hostname storage in EEPROM
#define HOSTNAME_MAX 32
#define EEPROM_SIZE 64
#define EEPROM_MAGIC 0xAB  // byte 0: magic, bytes 1-32: hostname

char hostname[HOSTNAME_MAX] = "minitv";

void loadHostname() {
  EEPROM.begin(EEPROM_SIZE);
  if (EEPROM.read(0) == EEPROM_MAGIC) {
    for (int i = 0; i < HOSTNAME_MAX - 1; i++) {
      char c = EEPROM.read(1 + i);
      hostname[i] = c;
      if (c == '\0') break;
    }
    hostname[HOSTNAME_MAX - 1] = '\0';
  }
  EEPROM.end();
}

void saveHostname(const char* name) {
  EEPROM.begin(EEPROM_SIZE);
  EEPROM.write(0, EEPROM_MAGIC);
  for (int i = 0; i < HOSTNAME_MAX - 1; i++) {
    EEPROM.write(1 + i, name[i]);
    if (name[i] == '\0') break;
  }
  EEPROM.write(HOSTNAME_MAX, '\0');
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
    struct { char text[MAX_TEXT_LEN]; uint8_t size; Align align; uint16_t fixedW; } t;
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
      // maxWidth: sample string defining the fixed bounding width
      if (item["maxWidth"].is<const char*>()) {
        cmd.t.fixedW = strlen(item["maxWidth"].as<const char*>()) * 6 * cmd.t.size;
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
  uint16_t textW = strlen(cmd.t.text) * 6 * cmd.t.size;
  tw = cmd.t.fixedW > 0 ? cmd.t.fixedW : textW;
  th = 8 * cmd.t.size;
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
void getTextCursor(DrawCmd& cmd, int16_t boxX, uint16_t boxW, int16_t &cursorX) {
  uint16_t textW = strlen(cmd.t.text) * 6 * cmd.t.size;
  if (cmd.t.align == ALIGN_RIGHT) {
    cursorX = boxX + (int)boxW - (int)textW;
  } else if (cmd.t.align == ALIGN_CENTER) {
    cursorX = boxX + ((int)boxW - (int)textW) / 2;
  } else {
    cursorX = boxX;
  }
}

LayoutKey computeLayoutKey(DrawCmd& cmd) {
  switch (cmd.type) {
    case CMD_TEXT: {
      int16_t cx, cy; uint16_t tw, th;
      getTextPos(cmd, cx, cy, tw, th);
      return {cmd.type, cx, cy, (int16_t)tw, (int16_t)th};
    }
    case CMD_PROGRESS:
      return {cmd.type, cmd.x, cmd.y, cmd.p.w, cmd.p.h};
    case CMD_RECT:
      return {cmd.type, cmd.x, cmd.y, cmd.r.w, cmd.r.h};
    case CMD_LINE:
      return {cmd.type, cmd.x, cmd.y, cmd.l.x2, cmd.l.y2};
    case CMD_CIRCLE:
      return {cmd.type, cmd.x, cmd.y, cmd.c.r, 0};
    default:
      return {cmd.type, 0, 0, 0, 0};
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
        key.w != prevLayout[i].w || key.h != prevLayout[i].h) {
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
        int16_t cursorX;
        getTextCursor(cmd, cx, tw, cursorX);
        int16_t textCursorInCanvas = cursorX - cx;
        if (tw > 0 && th > 0 && tw <= 240 && (uint32_t)tw * th * 2 <= 4096) {
          // Render to off-screen canvas, then blit in one SPI burst
          GFXcanvas16 canvas(tw, th);
          canvas.fillScreen(bgColor);
          canvas.setTextSize(cmd.t.size);
          canvas.setTextColor(cmd.color);
          canvas.setCursor(textCursorInCanvas, 0);
          canvas.print(cmd.t.text);
          tft.drawRGBBitmap(cx, cy, canvas.getBuffer(), tw, th);
        } else {
          tft.setTextSize(cmd.t.size);
          tft.setTextColor(cmd.color, bgColor);
          tft.setCursor(cursorX, cy);
          tft.print(cmd.t.text);
        }
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

  // Load saved hostname from EEPROM
  loadHostname();

  // WiFiManager with custom hostname parameter
  showStatus("Connecting...");
  WiFiManager wm;
  WiFiManagerParameter hostnameParam("hostname", "Device name (mDNS)", hostname, HOSTNAME_MAX - 1);
  wm.addParameter(&hostnameParam);
  wm.setConfigPortalTimeout(180);

  wm.setSaveParamsCallback([&hostnameParam]() {
    strncpy(hostname, hostnameParam.getValue(), HOSTNAME_MAX - 1);
    hostname[HOSTNAME_MAX - 1] = '\0';
    saveHostname(hostname);
    Serial.printf("Hostname saved: %s\n", hostname);
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

void loop() {
  MDNS.update();
  server.handleClient();

  if (drawPending) {
    drawPending = false;
    renderDrawList();
  }

  yield();
}
