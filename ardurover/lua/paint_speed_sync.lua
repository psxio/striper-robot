-- =============================================================================
-- paint_speed_sync.lua - Speed-Synchronized Paint Control
-- =============================================================================
-- Platform: Pixhawk 6C running ArduRover 4.5+ with Lua scripting enabled
--
-- Purpose:
--   Monitors ground speed and synchronizes paint relay state with vehicle
--   movement. This script works alongside paint_control.lua to provide
--   an additional safety layer:
--
--   - If the robot slows below SPRAY_SPEED_MIN, paint is paused
--   - If the robot stops (e.g., at a pivot turn), paint is cut immediately
--   - When the robot resumes moving, paint is re-enabled if the mission
--     still commands it
--   - All speed and paint state transitions are logged for post-mission
--     analysis and debugging
--
-- This script is OPTIONAL. paint_control.lua has its own speed check,
-- but this script adds:
--   1. More granular speed monitoring at a configurable rate
--   2. Detailed speed/paint state logging to the dataflash log
--   3. Speed averaging to prevent rapid on/off cycling from GPS jitter
--   4. Configurable hysteresis band to prevent oscillation at threshold
--
-- Installation:
--   Copy to SD card: /APM/scripts/paint_speed_sync.lua
--   Ensure SCR_ENABLE=1 in parameters
--   Reboot the Pixhawk
--
-- Note: This script reads SPRAY_SPEED_MIN from ArduRover parameters,
-- so it automatically stays in sync with the parameter file.
-- =============================================================================

-- ===========================
-- CONFIGURATION
-- ===========================

-- Relay index for paint solenoid (must match paint_control.lua and params)
local PAINT_RELAY       = 0

-- Speed thresholds
-- These are read from parameters at startup, but we define defaults here
local SPEED_MIN_DEFAULT = 0.10       -- m/s, fallback if param read fails
local SPEED_HYSTERESIS  = 0.05       -- m/s, band above threshold for re-enable
-- Paint turns off at SPEED_MIN, turns back on at SPEED_MIN + SPEED_HYSTERESIS
-- This prevents rapid toggling when speed hovers near the threshold

-- Speed averaging
local SPEED_AVG_SAMPLES = 5          -- number of speed samples to average
-- Averaging smooths GPS speed noise. At 10Hz update rate with 5 samples,
-- the average covers 0.5 seconds of data.

-- Script timing
local SCRIPT_INTERVAL   = 100        -- update interval in ms (10Hz)

-- Logging interval: log speed data every N updates to avoid flooding the log
local LOG_INTERVAL      = 5          -- log every 5th update (once per 500ms)

-- ArduRover mode numbers
local MODE_AUTO = 10

-- ===========================
-- STATE VARIABLES
-- ===========================
local speed_min         = SPEED_MIN_DEFAULT  -- actual threshold from params
local speed_samples     = {}                  -- circular buffer for averaging
local sample_index      = 1                   -- current position in circular buffer
local speed_ok          = false               -- true if speed is above threshold
local paint_paused      = false               -- true if we paused paint due to speed
local update_count      = 0                   -- counter for log rate limiting
local last_avg_speed    = 0.0                 -- last computed average speed
local initialized       = false               -- flag for one-time init

-- ===========================
-- HELPER FUNCTIONS
-- ===========================

--- Read the SPRAY_SPEED_MIN parameter from ArduRover
-- Called once at startup and can be called again if params change
local function read_speed_param()
    local val = param:get("SPRAY_SPEED_MIN")
    if val then
        speed_min = val
        gcs:send_text(6, string.format("paint_speed_sync: SPRAY_SPEED_MIN=%.2f m/s", speed_min))
    else
        speed_min = SPEED_MIN_DEFAULT
        gcs:send_text(4, "paint_speed_sync: could not read SPRAY_SPEED_MIN, using default")
    end
end

--- Get current ground speed from EKF velocity estimate
local function get_ground_speed()
    local vel = ahrs:get_velocity_NED()
    if vel then
        return math.sqrt(vel:x() * vel:x() + vel:y() * vel:y())
    end
    return 0.0
end

--- Add a speed sample and return the rolling average
-- Uses a circular buffer to avoid table resizing
-- @param speed: current speed in m/s
-- @return average speed over the last SPEED_AVG_SAMPLES readings
local function update_speed_average(speed)
    speed_samples[sample_index] = speed
    sample_index = sample_index + 1
    if sample_index > SPEED_AVG_SAMPLES then
        sample_index = 1
    end

    -- Calculate average
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

--- Check if the mission currently wants paint to be on
-- We check the relay state to see if paint_control.lua or the mission
-- has commanded the relay on
local function is_paint_commanded()
    return relay:get(PAINT_RELAY)
end

--- Log speed and paint state to the dataflash log
-- Creates a custom log message type "PSYN" (Paint Speed Sync)
-- Fields:
--   Spd  = current instantaneous ground speed (m/s)
--   ASpd = averaged ground speed (m/s)
--   Thr  = speed threshold (m/s)
--   POk  = paint speed ok (1/0)
--   PPau = paint paused by this script (1/0)
--   PCmd = paint commanded by mission (1/0)
local function log_state(speed, avg_speed, paint_cmd)
    if logger then
        logger:write('PSYN', 'Spd,ASpd,Thr,POk,PPau,PCmd',
            'fffBBB',
            speed,
            avg_speed,
            speed_min,
            speed_ok and 1 or 0,
            paint_paused and 1 or 0,
            paint_cmd and 1 or 0)
    end
end

-- ===========================
-- MAIN UPDATE FUNCTION
-- ===========================
function update()
    -- One-time initialization: read parameters
    if not initialized then
        read_speed_param()
        -- Pre-fill the speed sample buffer with zeros
        for i = 1, SPEED_AVG_SAMPLES do
            speed_samples[i] = 0.0
        end
        initialized = true
    end

    local mode = vehicle:get_mode()
    local raw_speed = get_ground_speed()
    local avg_speed = update_speed_average(raw_speed)
    local paint_cmd = is_paint_commanded()

    update_count = update_count + 1

    -- Only act in AUTO mode; other modes are handled by paint_control.lua
    if mode ~= MODE_AUTO then
        -- Reset state when not in auto
        if paint_paused then
            paint_paused = false
            speed_ok = false
        end
        return update, SCRIPT_INTERVAL
    end

    -- -----------------------------------------------------------------
    -- SPEED CHECK WITH HYSTERESIS
    -- Uses averaged speed to prevent jitter-induced toggling.
    -- Hysteresis band: paint turns off at speed_min, back on at
    -- speed_min + SPEED_HYSTERESIS
    -- -----------------------------------------------------------------
    local prev_speed_ok = speed_ok

    if speed_ok then
        -- Currently above threshold: drop below speed_min to trigger off
        if avg_speed < speed_min then
            speed_ok = false
        end
    else
        -- Currently below threshold: must exceed speed_min + hysteresis to re-enable
        if avg_speed >= (speed_min + SPEED_HYSTERESIS) then
            speed_ok = true
        end
    end

    -- -----------------------------------------------------------------
    -- PAINT PAUSE/RESUME LOGIC
    -- If the mission commands paint on but speed is too low, we pause.
    -- When speed recovers, we let paint_control.lua handle re-enabling.
    -- -----------------------------------------------------------------

    -- Speed just dropped below threshold while paint is commanded
    if prev_speed_ok and not speed_ok and paint_cmd then
        -- Pause paint: turn off relay
        relay:off(PAINT_RELAY)
        paint_paused = true
        gcs:send_text(4, string.format(
            "SPEED_SYNC: paint paused (avg=%.2f m/s < min=%.2f m/s)",
            avg_speed, speed_min))
    end

    -- Speed just recovered above threshold while paint was paused
    if not prev_speed_ok and speed_ok and paint_paused then
        -- Resume paint: turn relay back on (mission still wants it)
        if paint_cmd then
            relay:on(PAINT_RELAY)
            gcs:send_text(5, string.format(
                "SPEED_SYNC: paint resumed (avg=%.2f m/s > min+hyst=%.2f m/s)",
                avg_speed, speed_min + SPEED_HYSTERESIS))
        end
        paint_paused = false
    end

    -- If paint is no longer commanded by the mission, clear our pause state
    if not paint_cmd and paint_paused then
        paint_paused = false
    end

    -- -----------------------------------------------------------------
    -- LOGGING
    -- Log at a reduced rate to avoid flooding the dataflash log.
    -- Always log on state transitions regardless of rate limiting.
    -- -----------------------------------------------------------------
    local state_changed = (prev_speed_ok ~= speed_ok)
    if state_changed or (update_count % LOG_INTERVAL == 0) then
        log_state(raw_speed, avg_speed, paint_cmd)
    end

    return update, SCRIPT_INTERVAL
end

-- ===========================
-- SCRIPT INITIALIZATION
-- ===========================
gcs:send_text(5, "paint_speed_sync.lua loaded")
gcs:send_text(5, string.format("  Hysteresis=%.2f m/s, Avg samples=%d, Rate=%dHz",
    SPEED_HYSTERESIS, SPEED_AVG_SAMPLES, 1000 / SCRIPT_INTERVAL))

-- Start with a 2-second delay to let paint_control.lua initialize first
return update, 2000
