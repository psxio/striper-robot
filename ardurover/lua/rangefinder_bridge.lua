-- =============================================================================
-- rangefinder_bridge.lua - Arduino Nano Rangefinder Serial Bridge
-- =============================================================================
-- Parses distance data from an Arduino Nano connected on Serial4 (index 1).
-- The Nano reads two HC-SR04 ultrasonic sensors and sends 6-byte binary
-- packets over UART.
--
-- Packet format (6 bytes, little-endian):
--   [0xAA] [0x55] [FL_lo] [FL_hi] [FR_lo] [FR_hi]
--   FL = Front-Left distance in millimeters (uint16)
--   FR = Front-Right distance in millimeters (uint16)
--
-- The script writes distances to ArduPilot's rangefinder backend via
-- rangefinder:handle_script_msg(), making them available to the proximity
-- and obstacle avoidance subsystems (RNGFND1, RNGFND2 with TYPE=36).
--
-- Serial port: Serial4 (scripting serial index 1; motor_bridge uses index 0)
-- Update rate: 20Hz (50ms interval)
-- Fault timeout: 500ms with no valid packet → warning
-- =============================================================================

-- ===========================
-- CONFIGURATION
-- ===========================
local SERIAL_INDEX      = 1          -- serial:find_serial(1) = Serial4
local SCRIPT_INTERVAL   = 50         -- 50ms = 20Hz
local FAULT_TIMEOUT_MS  = 500        -- warn if no packet in this time
local HEADER_BYTE_1     = 0xAA
local HEADER_BYTE_2     = 0x55
local PACKET_SIZE       = 6

-- Rangefinder instances (0-based, matches RNGFND1/RNGFND2 config)
local RNGFND_FL         = 0          -- Front-Left
local RNGFND_FR         = 1          -- Front-Right

-- ===========================
-- STATE
-- ===========================
local port              = nil
local last_valid_ms     = 0
local fault_warned      = false
local buf               = {}
local buf_read          = 1          -- read cursor (O(1) consume instead of table.remove)
local initialized       = false

-- ===========================
-- HELPERS
-- ===========================

local function parse_uint16_le(lo, hi)
    return lo + hi * 256
end

-- ===========================
-- MAIN UPDATE
-- ===========================
function update()
    -- One-time init: find serial port
    if not initialized then
        port = serial:find_serial(SERIAL_INDEX)
        if not port then
            gcs:send_text(3, "rangefinder_bridge: Serial4 not found (index " .. SERIAL_INDEX .. ")")
            return update, 2000  -- retry in 2s
        end
        port:begin(115200)
        port:set_flow_control(0)
        initialized = true
        last_valid_ms = millis():tofloat()
        gcs:send_text(5, "rangefinder_bridge.lua loaded — Serial4 bridge active")
    end

    local now = millis():tofloat()

    -- Read all available bytes into buffer
    while port:available() > 0 do
        local byte = port:read()
        if byte >= 0 then
            buf[#buf + 1] = byte
        end
    end

    -- Number of unprocessed bytes
    local buf_len = #buf - buf_read + 1

    -- Scan buffer for valid packets using read cursor (O(1) per consume)
    local processed = false
    while buf_len >= PACKET_SIZE do
        -- Look for header
        if buf[buf_read] == HEADER_BYTE_1 and buf[buf_read + 1] == HEADER_BYTE_2 then
            -- Parse distances
            local fl_mm = parse_uint16_le(buf[buf_read + 2], buf[buf_read + 3])
            local fr_mm = parse_uint16_le(buf[buf_read + 4], buf[buf_read + 5])

            -- Convert mm to meters
            local fl_m = fl_mm / 1000.0
            local fr_m = fr_mm / 1000.0

            -- Clamp to valid HC-SR04 range (2cm–400cm)
            if fl_m >= 0.02 and fl_m <= 4.0 then
                rangefinder:handle_script_msg(RNGFND_FL, fl_m)
            end
            if fr_m >= 0.02 and fr_m <= 4.0 then
                rangefinder:handle_script_msg(RNGFND_FR, fr_m)
            end

            last_valid_ms = now
            fault_warned = false
            processed = true

            buf_read = buf_read + PACKET_SIZE
            buf_len = buf_len - PACKET_SIZE
        else
            -- Not a valid header, skip one byte
            buf_read = buf_read + 1
            buf_len = buf_len - 1
        end
    end

    -- Compact buffer when read cursor has advanced past 64 bytes
    if buf_read > 64 then
        local new_buf = {}
        local j = 1
        for i = buf_read, #buf do
            new_buf[j] = buf[i]
            j = j + 1
        end
        buf = new_buf
        buf_read = 1
    end

    -- Fault detection: no valid packet in FAULT_TIMEOUT_MS
    if (now - last_valid_ms) > FAULT_TIMEOUT_MS then
        if not fault_warned then
            gcs:send_text(4, string.format(
                "rangefinder_bridge: no data for %dms — check Arduino Nano",
                FAULT_TIMEOUT_MS))
            fault_warned = true
        end
    end

    return update, SCRIPT_INTERVAL
end

return update, 1000  -- 1s initial delay
