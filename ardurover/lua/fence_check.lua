-- =============================================================================
-- fence_check.lua - Enhanced Geofence Safety for Line Striper
-- =============================================================================
-- If the robot breaches the geofence, this script immediately:
--   1. Turns off the paint solenoid relay
--   2. Turns off the pump relay
--   3. Sends a warning to the GCS
--
-- This provides an extra safety layer beyond ArduRover's built-in FENCE_ACTION.
-- =============================================================================

local PAINT_RELAY = 0
local PUMP_RELAY  = 1
local CHECK_INTERVAL_MS = 100  -- check fence status every 100ms
local fence_breached_last = false

function update()
    -- Check if fence is breached (returns true if ANY fence boundary is violated)
    local breached = fence:get_breaches() ~= 0

    if breached and not fence_breached_last then
        -- Fence just breached: kill paint and pump immediately
        relay:off(PAINT_RELAY)
        relay:off(PUMP_RELAY)
        gcs:send_text(2, "FENCE BREACH: paint and pump disabled!")
    end

    if not breached and fence_breached_last then
        gcs:send_text(5, "FENCE: back inside boundary")
    end

    fence_breached_last = breached
    return update, CHECK_INTERVAL_MS
end

gcs:send_text(5, "fence_check.lua loaded - monitoring geofence")
return update, 2000  -- initial 2-second delay to let fence initialize
