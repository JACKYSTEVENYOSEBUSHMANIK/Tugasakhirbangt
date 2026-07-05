/*
 * BLE Room Positioning System - Anchor Scanner 02
 * Optimized for ESP32-C3 using NimBLE library
 * VERBOSE LOGGING: Shows WiFi status, backend connectivity, memory usage
 * 
 * Required Libraries (install via Arduino Library Manager):
 *   - NimBLE Arduino (by h2zero)
 *   - ArduinoJson (by Benoit Blanchon)
 * 
 * Board: ESP32C3 Dev Module
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <NimBLEDevice.h>
#include <ArduinoJson.h>
#include <time.h>

// ============================================================
// ANCHOR CONFIGURATION - UNIQUE TO SCANNER-02
// ============================================================
const char* anchorId = "scanner-02";
const float anchorX = 10.0;   // Position in meters (X-axis)
const float anchorY = 0.0;    // Position in meters (Y-axis)

// ============================================================
// WIFI & NETWORK
// ============================================================
const char* ssid = "gadakuotaya";
const char* wifiPassword = "44332211";
const char* backendUrl = "http://192.168.43.51:5000/api/scan";
const char* backendHealthUrl = "http://192.168.43.51:5000/api/health";

// ============================================================
// NTP TIME SYNC
// ============================================================
const char* ntpServer = "pool.ntp.org";
const long gmtOffsetSec = 7 * 3600;    // UTC+7 (WIB)
const int daylightOffsetSec = 0;

// ============================================================
// SCAN SETTINGS
// ============================================================
// NimBLE-Arduino 2.x uses milliseconds for the scan duration.
const uint32_t scanDurationMs = 5000;
const int scanIntervalMs = 5000;       // Normal mode: 5s between scans
const int calibIntervalMs = 1000;      // Calibration mode: 1s between scans
const unsigned long wifiTimeoutMs = 15000;

// Default TX power of beacons (adjust during calibration)
const int defaultTxPower = -59;

// Calibration mode - set true for faster scanning during setup
bool calibrationMode = false;

// ============================================================
// GLOBALS
// ============================================================
NimBLEScan* pBLEScan;
bool timeSynced = false;
unsigned long scanCycle = 0;
bool backendReachable = false;

// ============================================================
// VERBOSE LOG HELPER - prints timestamp + tag
// ============================================================
void logVerbose(const char* tag, const char* msg) {
  Serial.printf("[%8lu][%s] %s\n", millis(), tag, msg);
}

void logVerboseF(const char* tag, const char* fmt, ...) {
  char buf[256];
  va_list args;
  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  Serial.printf("[%8lu][%s] %s\n", millis(), tag, buf);
}

// ============================================================
// WiFi Connection with timeout and verbose logging
// ============================================================
bool connectWiFi() {
  logVerbose("WIFI", "Connecting to WiFi...");
  logVerboseF("WIFI", "  SSID: %s", ssid);
  
  WiFi.begin(ssid, wifiPassword);

  unsigned long startTime = millis();
  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    dots++;
    if (dots % 2 == 0) {
      Serial.printf("[%8lu][WIFI] Attempt %d...\n", millis(), dots / 2);
    }
    if (millis() - startTime > wifiTimeoutMs) {
      logVerbose("WIFI", "CONNECTION TIMEOUT after 15s!");
      return false;
    }
  }
  
  logVerbose("WIFI", "CONNECTED!");
  logVerboseF("WIFI", "  IP Address: %s", WiFi.localIP().toString().c_str());
  logVerboseF("WIFI", "  Gateway:    %s", WiFi.gatewayIP().toString().c_str());
  logVerboseF("WIFI", "  DNS:        %s", WiFi.dnsIP().toString().c_str());
  logVerboseF("WIFI", "  Signal:     %d dBm", WiFi.RSSI());
  return true;
}

// ============================================================
// Check if backend is reachable (health check)
// ============================================================
bool checkBackendConnection() {
  if (WiFi.status() != WL_CONNECTED) {
    logVerbose("BACKEND", "WiFi not connected - cannot check backend");
    backendReachable = false;
    return false;
  }

  HTTPClient http;
  http.begin(backendHealthUrl);
  http.setTimeout(3000);  // 3 second timeout for health check

  int httpCode = http.GET();

  if (httpCode == 200) {
    String response = http.getString();
    logVerbose("BACKEND", "CONNECTED to backend server!");
    logVerboseF("BACKEND", "  Health response: %s", response.c_str());
    backendReachable = true;
  } else if (httpCode > 0) {
    logVerboseF("BACKEND", "Server responded with code: %d", httpCode);
    backendReachable = false;
  } else {
    logVerboseF("BACKEND", "CANNOT REACH backend: %s", http.errorToString(httpCode).c_str());
    logVerboseF("BACKEND", "  Target URL: %s", backendHealthUrl);
    backendReachable = false;
  }

  http.end();
  return backendReachable;
}

// ============================================================
// NTP Time Sync
// ============================================================
void syncTime() {
  logVerbose("NTP", "Syncing time with NTP server...");
  logVerboseF("NTP", "  Server: %s", ntpServer);
  configTime(gmtOffsetSec, daylightOffsetSec, ntpServer);

  struct tm timeinfo;
  int retries = 0;
  while (!getLocalTime(&timeinfo) && retries < 10) {
    delay(500);
    retries++;
  }

  if (retries < 10) {
    char timeStr[64];
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", &timeinfo);
    logVerboseF("NTP", "Time synced: %s", timeStr);
    timeSynced = true;
  } else {
    logVerbose("NTP", "TIME SYNC FAILED - using millis() fallback");
    timeSynced = false;
  }
}

// ============================================================
// Get current timestamp in milliseconds
// ============================================================
unsigned long long getTimestampMs() {
  if (timeSynced) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (unsigned long long)tv.tv_sec * 1000 + tv.tv_usec / 1000;
  }
  return millis();
}

// ============================================================
// Send scan data to backend via HTTP POST (verbose)
// ============================================================
bool sendScanData(const String& jsonPayload) {
  if (WiFi.status() != WL_CONNECTED) {
    logVerbose("HTTP", "WiFi disconnected - cannot send data");
    return false;
  }

  logVerboseF("HTTP", "POST to: %s", backendUrl);
  logVerboseF("HTTP", "Payload size: %d bytes", jsonPayload.length());

  HTTPClient http;
  http.begin(backendUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  int httpCode = http.POST(jsonPayload);

  if (httpCode > 0) {
    String response = http.getString();
    logVerboseF("HTTP", "Response code: %d", httpCode);
    if (httpCode == 200) {
      logVerboseF("HTTP", "SUCCESS! Backend says: %s", response.c_str());
    } else {
      logVerboseF("HTTP", "Server error %d: %s", httpCode, response.c_str());
    }
    backendReachable = true;
  } else {
    logVerboseF("HTTP", "FAILED: %s", http.errorToString(httpCode).c_str());
    logVerboseF("HTTP", "  Check if backend is running at: %s", backendUrl);
    backendReachable = false;
  }

  http.end();
  return httpCode > 0;
}

// ============================================================
// BLE Scan and process results (verbose)
// ============================================================
void performBLEScan() {
  scanCycle++;
  logVerboseF("SCAN", "===== Cycle #%lu =====", scanCycle);
  logVerboseF("SCAN", "Free heap: %d bytes", ESP.getFreeHeap());
  logVerboseF("SCAN", "WiFi signal: %d dBm", WiFi.RSSI());

  // Check backend connectivity before scanning
  if (scanCycle % 5 == 1) {  // Check every 5 cycles
    checkBackendConnection();
    if (!backendReachable) {
      logVerbose("SCAN", "Backend not reachable - will still scan and retry later");
    }
  }

  logVerboseF("SCAN", "Starting BLE scan for %lu ms...", scanDurationMs);
  pBLEScan->clearResults();
  
  // start() is non-blocking in this NimBLE version
  // Must start, wait, then stop and get results
  bool scanStarted = pBLEScan->start(scanDurationMs, false, true);
  if (!scanStarted) {
    logVerbose("SCAN", "BLE SCAN FAILED to start!");
    return;
  }
  
  // Wait for the scan duration to actually collect devices
  logVerboseF("SCAN", "Scanning... (waiting %lu ms)", scanDurationMs);
  delay(scanDurationMs + 100);
  
  // The timed scan stops automatically; retrieve the collected results.
  NimBLEScanResults foundDevices = pBLEScan->getResults();
  int deviceCount = foundDevices.getCount();

  logVerboseF("SCAN", "Found %d BLE devices", deviceCount);

  if (deviceCount > 0) {
    DynamicJsonDocument doc(2048);
    doc["anchor_id"] = anchorId;

    JsonArray anchorPos = doc.createNestedArray("anchor_pos");
    anchorPos.add(anchorX);
    anchorPos.add(anchorY);

    doc["timestamp"] = getTimestampMs();
    doc["calibration_mode"] = calibrationMode;

    JsonArray beacons = doc.createNestedArray("beacons");

    for (int i = 0; i < deviceCount; i++) {
      const NimBLEAdvertisedDevice* device = foundDevices.getDevice(i);

      String beaconId = String(device->getAddress().toString().c_str());
      int rssi = device->getRSSI();

      int txPower = defaultTxPower;
      if (device->haveTXPower()) {
        int advertisedTxPower = device->getTXPower();
        // Some BLE advertisements expose controller power values such as
        // +11/+17 dBm, not calibrated RSSI-at-1m values. Do not feed those
        // values into the positioning distance formula.
        if (advertisedTxPower >= -100 && advertisedTxPower <= -20) {
          txPower = advertisedTxPower;
        }
      }

      JsonObject beacon = beacons.createNestedObject();
      beacon["beacon_id"] = beaconId;
      beacon["rssi"] = rssi;
      beacon["tx_power"] = txPower;

      if (device->haveName() && device->getName().length() > 0) {
        beacon["name"] = String(device->getName().c_str());
        logVerboseF("BLE", "  [%d] %s (%s) | RSSI: %d | TX: %d",
                    i + 1, beaconId.c_str(), device->getName().c_str(), rssi, txPower);
      } else {
        logVerboseF("BLE", "  [%d] %s | RSSI: %d | TX: %d",
                    i + 1, beaconId.c_str(), rssi, txPower);
      }
    }

    String payload;
    serializeJson(doc, payload);
    sendScanData(payload);
  } else {
    logVerbose("SCAN", "No BLE devices found in range");
  }

  // Clear results to prevent memory leak on C3 (limited RAM)
  pBLEScan->clearResults();
  
  logVerboseF("SCAN", "Cycle #%lu complete. Free heap: %d bytes", scanCycle, ESP.getFreeHeap());
  Serial.println();
}

// ============================================================
// Setup
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("###################################################");
  Serial.println("#  BLE Room Positioning System - Anchor Scanner   #");
  Serial.println("###################################################");
  logVerboseF("INIT", "Anchor ID:  %s", anchorId);
  logVerboseF("INIT", "Position:   (%.2f, %.2f) meters", anchorX, anchorY);
  logVerboseF("INIT", "Board:      ESP32-C3 (NimBLE)");
  logVerboseF("INIT", "Backend:    %s", backendUrl);
  logVerboseF("INIT", "Free heap:  %d bytes", ESP.getFreeHeap());
  logVerboseF("INIT", "Chip model: %s", ESP.getChipModel());
  logVerboseF("INIT", "CPU freq:   %d MHz", ESP.getCpuFreqMHz());
  Serial.println("###################################################");
  Serial.println();

  // Step 1: Connect WiFi
  logVerbose("INIT", "Step 1/3: Connecting to WiFi...");
  if (!connectWiFi()) {
    logVerbose("INIT", "WiFi FAILED! Restarting in 5 seconds...");
    delay(5000);
    ESP.restart();
  }

  // Step 2: Sync time
  logVerbose("INIT", "Step 2/3: Syncing time...");
  syncTime();

  // Step 3: Check backend
  logVerbose("INIT", "Step 3/3: Checking backend connection...");
  checkBackendConnection();
  if (!backendReachable) {
    logVerbose("INIT", "WARNING: Backend not reachable yet!");
    logVerboseF("INIT", "  Make sure backend is running at: %s", backendHealthUrl);
    logVerbose("INIT", "  Will keep retrying during scan loop...");
  }

  // Initialize NimBLE (lightweight, optimized for C3)
  NimBLEDevice::init("");
  pBLEScan = NimBLEDevice::getScan();
  pBLEScan->setActiveScan(true);
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(99);

  Serial.println();
  logVerbose("INIT", "All systems ready! Starting scan loop...");
  logVerboseF("INIT", "Scan every %d ms (normal) / %d ms (calibration)", scanIntervalMs, calibIntervalMs);
  Serial.println("===================================================");
  Serial.println();
  delay(1000);
}

// ============================================================
// Loop
// ============================================================
void loop() {
  // Reconnect WiFi with cooldown
  static unsigned long lastWifiCheck = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiCheck > 10000) {
    lastWifiCheck = millis();
    logVerbose("WIFI", "WiFi LOST! Attempting reconnect...");
    WiFi.disconnect();
    if (!connectWiFi()) {
      logVerbose("WIFI", "Reconnect failed! Will retry in 10s...");
    }
  }

  performBLEScan();

  int delayMs = calibrationMode ? calibIntervalMs : scanIntervalMs;
  delay(delayMs);
}
