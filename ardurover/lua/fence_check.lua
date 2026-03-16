-- =============================================================================
-- fence_check.lua - Enhanced Geofence Safety for Line Striper
-- =============================================================================
-- If the robot breaches the geofence, this script signals paint_unified.lua
-- to kill paint via a shared Lua global (_G.fence_kill_paint). It does NOT
-- directly toggle relays — paint_unified.lua owns all relay state.
--
-- This provides an extra safety layer beyond ArduRover's built-in FENCE_ACTION.
-- =============================================================================

local CHECK_INTERVAL_MS = 100  -- check fence status every 100ms
local fence_breached_last = false

-- Shared global for paint_unified.lua to read
_G.fence_kill_paint = false

function update()
    -- Check if fence is breached (returns true if ANY fence boundary is violated)
    local breached = fence:get_breaches() ~= 0

    if breached and not fence_breached_last then
        -- Fence just breached: signal paint_unified to kill paint
        _G.fence_kill_paint = true
        gcs:send_text(2, "FENCE BREACH: paint kill signaled!")
    end

    if not breached and fence_breached_last then
        _G.fence_kill_paint = false
        gcs:send_text(5, "FENCE: back inside boundary")
    end

    fence_breached_last = breached
    return update, CHECK_INTERVAL_MS
end

gcs:send_text(5, "fence_check.lua loaded - monitoring geofence")
return update, 2000  -- initial 2-second delay to let fence initialize
