-- =============================================================================
-- obstacle_avoid.lua - Ultrasonic Obstacle Avoidance for Line Striper
-- =============================================================================
-- Reads two HC-SR04 ultrasonic sensors via ArduPilot scripting rangefinder
-- backend (RNGFND_TYPE=36). An Arduino Nano bridge converts HC-SR04
-- pulse-width signals to a simple serial protocol that ArduPilot reads.
--
-- Behavior:
--   - If either sensor reads < STOP_DIST_CM: force HOLD mode, kill paint
--   - If both sensors read > CLEAR_DIST_CM: allow resume (if was in AUTO)
--   - Sensor fault (no data for FAULT_COUNT frames): warn but don't stop
--
-- Rangefinder assignment:
--   Rangefinder 1 (RNGFND1) = Front-Left HC-SR04
--   Rangefinder 2 (RNGFND2) = Front-Right HC-SR04
--
-- Arduino Nano bridge (see comments at bottom for sketch):
--   Reads 2x HC-SR04, sends distance via UART to Pixhawk Serial4
-- =============================================================================

-- Configuration
local STOP_DIST_CM      = 100       -- stop if obstacle closer than 1.0m
local CLEAR_DIST_CM     = 130       -- resume if obstacle farther than 1.3m (hysteresis)
local PAINT_RELAY       = 0         -- relay index for paint solenoid
local PUMP_RELAY        = 1         -- relay index for pump
local CHECK_INTERVAL_MS = 50        -- 20Hz update rate
local FAULT_COUNT_MAX   = 10        -- consecutive no-data readings before fault warning
local MODE_AUTO         = 10        -- ArduRover AUTO mode number
local MODE_HOLD         = 4         -- ArduRover HOLD mode number

-- State
local obstacle_active   = false     -- true when we've forced a stop
local was_auto          = false     -- true if we interrupted AUTO mode
local fault_count_fl    = 0         -- consecutive fault frames (front-left)
local fault_count_fr    = 0         -- consecutive fault frames (front-right)
local last_warn_ms      = 0         -- throttle GCS warnings

-- Helper: kill paint system
local function paint_off()
    relay:off(PAINT_RELAY)
    relay:off(PUMP_RELAY)
end

-- Main update
function update()
    -- Read rangefinder distances (returns meters, -1 if no data)
    local dist_fl = rangefinder:distance_cm_orient(0)  -- RNGFND1
    local dist_fr = rangefinder:distance_cm_orient(1)  -- RNGFND2

    -- Handle sensor faults
    local fl_valid = dist_fl ~= nil and dist_fl >= 0
    local fr_valid = dist_fr ~= nil and dist_fr >= 0

    if not fl_valid then
        fault_count_fl = fault_count_fl + 1
    else
        fault_count_fl = 0
    end

    if not fr_valid then
        fault_count_fr = fault_count_fr + 1
    else
        fault_count_fr = 0
    end

    -- Warn on sensor fault (throttled to once per 5 seconds)
    local now = millis():toint()
    if (fault_count_fl >= FAULT_COUNT_MAX or fault_count_fr >= FAULT_COUNT_MAX) then
        if now - last_warn_ms > 5000 then
            local which = ""
            if fault_count_fl >= FAULT_COUNT_MAX then which = which .. "FL " end
            if fault_count_fr >= FAULT_COUNT_MAX then which = which .. "FR " end
            gcs:send_text(3, "OBSTACLE: sensor fault - " .. which .. "no data")
            last_warn_ms = now
        end
    end

    -- Get minimum valid distance
    local min_dist = 9999
    if fl_valid then min_dist = math.min(min_dist, dist_fl) end
    if fr_valid then min_dist = math.min(min_dist, dist_fr) end

    -- Publish telemetry
    if fl_valid then gcs:send_named_float('OBFL', dist_fl) end
    if fr_valid then gcs:send_named_float('OBFR', dist_fr) end

    local mode = vehicle:get_mode()

    -- TRIGGER: obstacle detected within stop distance
    if min_dist < STOP_DIST_CM and not obstacle_active then
        obstacle_active = true
        was_auto = (mode == MODE_AUTO)

        -- Kill paint immediately
        paint_off()

        -- Force HOLD mode to stop the robot
        if was_auto then
            vehicle:set_mode(MODE_HOLD)
        end

        gcs:send_text(2, string.format(
            "OBSTACLE STOP: %.0fcm (FL=%.0f FR=%.0f)",
            min_dist,
            fl_valid and dist_fl or -1,
            fr_valid and dist_fr or -1))
    end

    -- CLEAR: obstacle moved away past hysteresis threshold
    if obstacle_active and min_dist > CLEAR_DIST_CM then
        obstacle_active = false

        -- Resume AUTO mode if that's where we came from
        if was_auto then
            vehicle:set_mode(MODE_AUTO)
            gcs:send_text(5, string.format(
                "OBSTACLE CLEAR: %.0fcm - resuming AUTO", min_dist))
        else
            gcs:send_text(5, string.format(
                "OBSTACLE CLEAR: %.0fcm", min_dist))
        end
        was_auto = false
    end

    -- Log obstacle state
    gcs:send_named_float('OBST', obstacle_active and 1 or 0)

    return update, CHECK_INTERVAL_MS
end

gcs:send_text(5, "obstacle_avoid.lua loaded - stop=" ..
    STOP_DIST_CM .. "cm clear=" .. CLEAR_DIST_CM .. "cm")
return update, 2000  -- initial 2-second delay to let rangefinders initialize

-- =============================================================================
-- ARDUINO NANO BRIDGE SKETCH (flash to Arduino Nano / Nano Every)
-- =============================================================================
-- Wiring:
--   Arduino D2 → HC-SR04 #1 TRIG (front-left)
--   Arduino D3 → HC-SR04 #1 ECHO (front-left)
--   Arduino D4 → HC-SR04 #2 TRIG (front-right)
--   Arduino D5 → HC-SR04 #2 ECHO (front-right)
--   Arduino TX  → Pixhawk SERIAL4 RX (via voltage divider 5V→3.3V)
--   Arduino VCC → 5V from Pixhawk servo rail or DC-DC converter
--   Arduino GND → Common ground with Pixhawk
--
-- Protocol: sends 6-byte binary packets at 20Hz:
--   [0xAA] [0x55] [FL_lo] [FL_hi] [FR_lo] [FR_hi]
--   where FL/FR are distance in millimeters as uint16 little-endian
--
-- /*
-- #define TRIG1 2
-- #define ECHO1 3
-- #define TRIG2 4
-- #define ECHO2 5
--
-- void setup() {
--   Serial.begin(115200);
--   pinMode(TRIG1, OUTPUT); pinMode(ECHO1, INPUT);
--   pinMode(TRIG2, OUTPUT); pinMode(ECHO2, INPUT);
-- }
--
-- uint16_t readHCSR04(int trigPin, int echoPin) {
--   digitalWrite(trigPin, LOW);  delayMicroseconds(2);
--   digitalWrite(trigPin, HIGH); delayMicroseconds(10);
--   digitalWrite(trigPin, LOW);
--   long duration = pulseIn(echoPin, HIGH, 30000); // 30ms timeout (~5m max)
--   if (duration == 0) return 0xFFFF; // no echo = fault
--   return (uint16_t)(duration * 0.1715); // mm = us * 343/2 / 1000
-- }
--
-- void loop() {
--   uint16_t d1 = readHCSR04(TRIG1, ECHO1);
--   uint16_t d2 = readHCSR04(TRIG2, ECHO2);
--   uint8_t packet[6] = {0xAA, 0x55,
--     (uint8_t)(d1 & 0xFF), (uint8_t)(d1 >> 8),
--     (uint8_t)(d2 & 0xFF), (uint8_t)(d2 >> 8)};
--   Serial.write(packet, 6);
--   delay(50); // 20Hz
-- }
-- */
-- =============================================================================
