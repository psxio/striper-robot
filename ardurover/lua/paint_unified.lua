-- =============================================================================
-- paint_unified.lua - Unified Paint Control for Parking Lot Line Striper
-- =============================================================================
-- Replaces both paint_control.lua and paint_speed_sync.lua with a single
-- script that owns all relay state. This eliminates the race condition where
-- two scripts independently read/write the same relay.
--
-- Features:
--   - DO_SET_RELAY edge detection with lead/lag compensation
--   - Speed-synchronized paint: rolling average + hysteresis band
--   - Single boolean merge: relay = mission_paint_cmd AND speed_ok
--   - paint_paused_by_speed prevents false falling-edge detection
--   - PSYN dataflash logging (same format as old paint_speed_sync)
--   - Reads SPRAY_SPEED_MIN param for threshold
--
-- Relay assignments:
--   Relay 0 (RELAY1_PIN) = Paint solenoid valve
--   Relay 1 (RELAY2_PIN) = Diaphragm pump
--
-- Mission usage:
--   DO_SET_RELAY(0,1) to start painting, DO_SET_RELAY(0,0) to stop.
--   Pump is slaved to paint: on when painting, off when not.
-- =============================================================================

-- ===========================
-- CONFIGURATION
-- ===========================
local PAINT_RELAY       = 0          -- relay index for paint solenoid
local PUMP_RELAY        = 1          -- relay index for diaphragm pump
local LEAD_TIME_MS      = 50         -- open solenoid this many ms early
local LAG_TIME_MS       = 30         -- keep solenoid open this many ms after off
local SCRIPT_INTERVAL   = 20         -- 50Hz update rate

-- Speed thresholds (read from param at startup)
local SPEED_MIN_DEFAULT = 0.10       -- m/s fallback
local SPEED_HYSTERESIS  = 0.05       -- m/s band above threshold for re-enable
local SPEED_AVG_SAMPLES = 5          -- rolling average window

-- Logging
local LOG_INTERVAL      = 5          -- log every N updates (~100ms at 50Hz)

-- ArduRover mode
local MODE_AUTO = 10

-- Shared global: fence_check.lua sets this to true on geofence breach
_G.fence_kill_paint = _G.fence_kill_paint or false

-- ===========================
-- STATE
-- ===========================
local speed_min            = SPEED_MIN_DEFAULT
local speed_samples        = {}
local sample_index         = 1
local speed_ok             = false    -- true if averaged speed is above threshold
local mission_paint_cmd    = false    -- true when mission has commanded relay ON
local paint_paused_by_speed = false   -- true if we turned off relay due to speed
local paint_active         = false    -- true when relay is physically energized
local lead_timer           = 0        -- countdown for lead compensation (ms)
local lag_timer            = 0        -- countdown for lag compensation (ms)
local update_count         = 0
local last_avg_speed       = 0.0
local initialized          = false

-- ===========================
-- HELPERS
-- ===========================

local function read_speed_param()
    local val = param:get("SPRAY_SPEED_MIN")
    if val then
        speed_min = val
        gcs:send_text(6, string.format("paint_unified: SPRAY_SPEED_MIN=%.2f", speed_min))
    else
        speed_min = SPEED_MIN_DEFAULT
        gcs:send_text(4, "paint_unified: SPRAY_SPEED_MIN not found, using default")
    end
end

local function get_ground_speed()
    local vel = ahrs:get_velocity_NED()
    if vel then
        return math.sqrt(vel:x() * vel:x() + vel:y() * vel:y())
    end
    return 0.0
end

local function update_speed_average(speed)
    speed_samples[sample_index] = speed
    sample_index = sample_index + 1
    if sample_index > SPEED_AVG_SAMPLES then
        sample_index = 1
    end
    local sum = 0.0
    local count = 0
    for i = 1, SPEED_AVG_SAMPLES do
        if speed_samples[i] then
            sum = sum + speed_samples[i]
            count = count + 1
        end
    end
    if count > 0 then
        last_avg_speed = sum / count
    else
        last_avg_speed = speed
    end
    return last_avg_speed
end

local function set_paint(state)
    if state then
        relay:on(PAINT_RELAY)
        relay:on(PUMP_RELAY)
    else
        relay:off(PAINT_RELAY)
        relay:off(PUMP_RELAY)
    end
    paint_active = state
end

local function log_state(raw_speed, avg_speed)
    if logger then
        logger:write('PSYN', 'Spd,ASpd,Thr,POk,PPau,PCmd',
            'fffBBB',
            raw_speed,
            avg_speed,
            speed_min,
            speed_ok and 1 or 0,
            paint_paused_by_speed and 1 or 0,
            mission_paint_cmd and 1 or 0)
    end
end

-- ===========================
-- MAIN UPDATE
-- ===========================
function update()
    -- One-time init
    if not initialized then
        read_speed_param()
        for i = 1, SPEED_AVG_SAMPLES do
            speed_samples[i] = 0.0
        end
        initialized = true
    end

    local mode = vehicle:get_mode()
    local raw_speed = get_ground_speed()
    local avg_speed = update_speed_average(raw_speed)
    update_count = update_count + 1

    -- SAFETY: geofence kill signal from fence_check.lua
    if _G.fence_kill_paint then
        if paint_active or mission_paint_cmd then
            set_paint(false)
            mission_paint_cmd = false
            paint_paused_by_speed = false
            lag_timer = 0
            gcs:send_text(2, "PAINT: KILLED by geofence breach")
        end
        gcs:send_named_float('PAINT', 0)
        return update, SCRIPT_INTERVAL
    end

    -- SAFETY: not in AUTO → force everything off (send telemetry only on state change)
    if mode ~= MODE_AUTO then
        if paint_active or mission_paint_cmd then
            set_paint(false)
            mission_paint_cmd = false
            paint_paused_by_speed = false
            lead_timer = 0
            lag_timer = 0
            gcs:send_text(4, "PAINT: OFF (not in AUTO)")
            gcs:send_named_float('PAINT', 0)
        end
        return update, SCRIPT_INTERVAL
    end

    -- -----------------------------------------------------------------
    -- SPEED CHECK WITH HYSTERESIS (on averaged speed)
    -- -----------------------------------------------------------------
    local prev_speed_ok = speed_ok
    if speed_ok then
        if avg_speed < speed_min then
            speed_ok = false
        end
    else
        if avg_speed >= (speed_min + SPEED_HYSTERESIS) then
            speed_ok = true
        end
    end

    -- -----------------------------------------------------------------
    -- DO_SET_RELAY EDGE DETECTION
    -- Read relay state set by mission commands. We detect edges to track
    -- what the mission wants, but we OWN the actual relay output.
    -- When paint_paused_by_speed is true, we ignore apparent falling
    -- edges because WE turned the relay off, not the mission.
    -- -----------------------------------------------------------------
    local relay_state = relay:get(PAINT_RELAY)

    -- Rising edge: mission commanded paint ON
    if relay_state and not mission_paint_cmd and not paint_paused_by_speed then
        mission_paint_cmd = true
        -- Start lead timer: defer relay activation by LEAD_TIME_MS
        lead_timer = LEAD_TIME_MS
        gcs:send_text(5, string.format("PAINT: mission CMD ON, lead=%dms (spd=%.2f)", LEAD_TIME_MS, raw_speed))
    end

    -- Falling edge: mission commanded paint OFF
    -- Only detect if we didn't pause it ourselves
    if not relay_state and mission_paint_cmd and not paint_paused_by_speed then
        mission_paint_cmd = false
        -- Start lag timer
        if paint_active then
            lag_timer = LAG_TIME_MS
            gcs:send_text(5, string.format("PAINT: lag started (%dms)", LAG_TIME_MS))
        end
    end

    -- -----------------------------------------------------------------
    -- SPEED PAUSE / RESUME
    -- -----------------------------------------------------------------
    -- Speed dropped: pause paint if mission wants it on
    if prev_speed_ok and not speed_ok and mission_paint_cmd then
        if paint_active then
            set_paint(false)
            paint_paused_by_speed = true
            lag_timer = 0  -- cancel any pending lag
            gcs:send_text(4, string.format(
                "PAINT: paused (avg=%.2f < min=%.2f)", avg_speed, speed_min))
        end
    end

    -- Speed recovered: resume if mission still wants paint
    if not prev_speed_ok and speed_ok and paint_paused_by_speed then
        paint_paused_by_speed = false
        if mission_paint_cmd then
            set_paint(true)
            gcs:send_text(5, string.format(
                "PAINT: resumed (avg=%.2f > %.2f)", avg_speed, speed_min + SPEED_HYSTERESIS))
        end
    end

    -- -----------------------------------------------------------------
    -- PAINT OUTPUT LOGIC: relay = mission_paint_cmd AND speed_ok
    -- -----------------------------------------------------------------
    local want_paint = mission_paint_cmd and speed_ok

    -- Process lead timer: count down before activating relay
    if lead_timer > 0 then
        lead_timer = lead_timer - SCRIPT_INTERVAL
        if lead_timer <= 0 then
            lead_timer = 0
            if want_paint and not paint_active then
                set_paint(true)
                gcs:send_text(5, string.format("PAINT: ON (lead done, spd=%.2f)", raw_speed))
            end
        end
    end

    -- Activate paint if lead timer already expired
    if want_paint and not paint_active and not paint_paused_by_speed and lag_timer <= 0 and lead_timer <= 0 then
        set_paint(true)
        gcs:send_text(5, string.format("PAINT: ON (spd=%.2f)", raw_speed))
    end

    -- Process lag timer
    if lag_timer > 0 then
        lag_timer = lag_timer - SCRIPT_INTERVAL
        if lag_timer <= 0 then
            lag_timer = 0
            if not mission_paint_cmd then
                set_paint(false)
                gcs:send_text(5, "PAINT: OFF (lag complete)")
            end
        end
    end

    -- If mission turned off and no lag pending, ensure paint is off
    if not mission_paint_cmd and not paint_active and lag_timer <= 0 then
        -- Already off, no action needed
    elseif not mission_paint_cmd and paint_active and lag_timer <= 0 then
        set_paint(false)
    end

    -- Publish telemetry
    gcs:send_named_float('PAINT', paint_active and 1 or 0)

    -- Logging (rate-limited, always log on state change)
    local state_changed = (prev_speed_ok ~= speed_ok)
    if state_changed or (update_count % LOG_INTERVAL == 0) then
        log_state(raw_speed, avg_speed)
    end

    return update, SCRIPT_INTERVAL
end

-- ===========================
-- INIT
-- ===========================
gcs:send_text(5, "paint_unified.lua loaded — relay-based paint control")
gcs:send_text(5, string.format("  Lead=%dms, Lag=%dms, Hyst=%.2f, Rate=%dHz",
    LEAD_TIME_MS, LAG_TIME_MS, SPEED_HYSTERESIS, 1000 / SCRIPT_INTERVAL))

return update, 1000
