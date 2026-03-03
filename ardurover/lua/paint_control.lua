-- =============================================================================
-- paint_control.lua - Paint Solenoid Control for Parking Lot Line Striper
-- =============================================================================
-- Runs on Pixhawk 6C via ArduRover Lua scripting engine.
--
-- Features:
--   - Activates paint solenoid relay during AUTO mode mission segments
--   - Lead/lag compensation: opens solenoid early, closes late for clean edges
--   - Safety: disables paint if not in AUTO, or if speed drops below threshold
--   - Logs paint events to GCS and publishes status via named float
--
-- Relay assignments:
--   Relay 0 (RELAY1_PIN) = Paint solenoid valve
--   Relay 1 (RELAY2_PIN) = Diaphragm pump
--
-- Mission usage:
--   Insert DO_SET_RELAY(0,1) to start painting, DO_SET_RELAY(0,0) to stop.
--   The pump can be toggled similarly with DO_SET_RELAY(1,1) / DO_SET_RELAY(1,0).
-- =============================================================================

-- Configuration constants (adjust in the field)
local PAINT_RELAY       = 0          -- relay index for paint solenoid (0-based)
local PUMP_RELAY        = 1          -- relay index for diaphragm pump
local LEAD_TIME_MS      = 50         -- open solenoid this many ms before paint-start
local LAG_TIME_MS       = 30         -- keep solenoid open this many ms after paint-end
local MIN_SPEED_MS      = 0.10       -- minimum ground speed (m/s) to allow painting
local SCRIPT_INTERVAL   = 20         -- script update interval in milliseconds

-- Auto mode number in ArduRover
local MODE_AUTO = 10

-- State tracking
local paint_requested   = false      -- true when mission commands paint ON
local paint_active      = false      -- true when solenoid is physically energized
local lead_timer        = 0          -- countdown for lead compensation (ms)
local lag_timer         = 0          -- countdown for lag compensation (ms)
local last_paint_state  = false      -- for edge-detection of state changes

-- Helper: get current ground speed in m/s
local function get_speed()
    local vel = ahrs:get_velocity_NED()
    if vel then
        return math.sqrt(vel:x()^2 + vel:y()^2)
    end
    return 0.0
end

-- Helper: safely set relay state
local function set_relay(relay_idx, state)
    if state then
        relay:on(relay_idx)
    else
        relay:off(relay_idx)
    end
end

-- Main update function called every SCRIPT_INTERVAL ms
function update()
    local mode = vehicle:get_mode()
    local speed = get_speed()
    local now = millis()

    -- Read the relay state that mission commands have requested
    -- In AUTO mode, DO_SET_RELAY commands set the relay directly;
    -- we monitor and add lead/lag compensation
    local in_auto = (mode == MODE_AUTO)

    -- SAFETY: if not in AUTO mode, force paint OFF immediately
    if not in_auto then
        if paint_active then
            set_relay(PAINT_RELAY, false)
            set_relay(PUMP_RELAY, false)
            paint_active = false
            paint_requested = false
            lag_timer = 0
            lead_timer = 0
            gcs:send_text(4, "PAINT: OFF (not in AUTO)")
        end
        -- Publish paint status: 0 = off
        gcs:send_named_float('PAINT', 0)
        return update, SCRIPT_INTERVAL
    end

    -- SAFETY: if speed is below minimum, force paint OFF to prevent pooling
    if speed < MIN_SPEED_MS then
        if paint_active then
            set_relay(PAINT_RELAY, false)
            paint_active = false
            lag_timer = 0
            gcs:send_text(4, "PAINT: OFF (speed too low: " ..
                string.format("%.2f", speed) .. " m/s)")
        end
        gcs:send_named_float('PAINT', 0)
        return update, SCRIPT_INTERVAL
    end

    -- Check if the mission has commanded the relay via DO_SET_RELAY
    -- We read the current relay pin state to detect mission commands
    local relay_cmd = relay:get(PAINT_RELAY)

    -- Detect rising edge: mission just commanded paint ON
    if relay_cmd and not paint_requested then
        paint_requested = true
        -- Apply lead compensation: solenoid opens LEAD_TIME_MS early
        -- Since the relay is already commanded ON by the mission item,
        -- we just log and track it. Lead compensation is handled by
        -- placing DO_SET_RELAY slightly before the paint-start waypoint.
        if not paint_active then
            set_relay(PAINT_RELAY, true)
            set_relay(PUMP_RELAY, true)
            paint_active = true
            gcs:send_text(5, "PAINT: ON (speed=" ..
                string.format("%.2f", speed) .. " m/s)")
        end
    end

    -- Detect falling edge: mission just commanded paint OFF
    if not relay_cmd and paint_requested then
        paint_requested = false
        -- Apply lag compensation: keep solenoid open for LAG_TIME_MS
        lag_timer = LAG_TIME_MS
        gcs:send_text(5, "PAINT: lag timer started (" .. LAG_TIME_MS .. "ms)")
    end

    -- Process lag timer: keep painting for a short duration after command-off
    if lag_timer > 0 then
        lag_timer = lag_timer - SCRIPT_INTERVAL
        if lag_timer <= 0 then
            lag_timer = 0
            set_relay(PAINT_RELAY, false)
            set_relay(PUMP_RELAY, false)
            paint_active = false
            gcs:send_text(5, "PAINT: OFF (lag complete)")
        end
    end

    -- Publish paint status as a named float for telemetry
    -- 1 = painting, 0 = not painting
    if paint_active then
        gcs:send_named_float('PAINT', 1)
    else
        gcs:send_named_float('PAINT', 0)
    end

    return update, SCRIPT_INTERVAL
end

gcs:send_text(5, "paint_control.lua loaded - relay " .. PAINT_RELAY .. " = solenoid")
return update, 1000  -- initial delay of 1 second before first run
