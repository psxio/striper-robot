-- =============================================================================
-- motor_bridge.lua - Hoverboard UART Motor Bridge for ArduRover
-- =============================================================================
-- Reads ArduRover SERVO1 (ThrottleLeft) and SERVO3 (ThrottleRight) PWM outputs,
-- converts them to the hoverboard FOC firmware UART protocol, and sends them
-- over Serial2 (SERIAL2_PROTOCOL=28, Scripting).
--
-- Hoverboard FOC UART protocol (from EFeru/hoverboard-firmware-hack-FOC):
--   Byte 0-1: Start frame (0xABCD, little-endian: 0xCD, 0xAB)
--   Byte 2-3: Steer command (int16, little-endian)
--   Byte 4-5: Speed command (int16, little-endian)
--   Byte 6-7: Checksum (XOR of start frame, steer, speed as uint16, little-endian)
--
-- ArduRover SERVO outputs: 1000-2000 PWM, 1500 = center/stop
-- FOC firmware input range: -1000 to +1000
--
-- Serial2 must be configured as:
--   SERIAL2_PROTOCOL = 28 (Scripting)
--   SERIAL2_BAUD = 115200
-- =============================================================================

-- Configuration
local SEND_RATE_HZ    = 50       -- Send motor commands at 50Hz
local SEND_INTERVAL   = 1000 / SEND_RATE_HZ  -- ms between sends
local PWM_MIN         = 1000
local PWM_MAX         = 2000
local PWM_CENTER      = 1500
local FOC_MAX         = 1000     -- Max FOC command value
local DEADBAND        = 15       -- PWM deadband around center (prevents drift)
local RAMP_LIMIT      = 50       -- Max FOC command change per tick (acceleration limit)

-- Servo function numbers for differential drive
local SERVO_LEFT  = 1  -- SERVO1 = ThrottleLeft (function 73)
local SERVO_RIGHT = 3  -- SERVO3 = ThrottleRight (function 74)

-- State
local last_speed = 0
local last_steer = 0
local port = nil
local send_count = 0
local error_count = 0

-- Find the scripting serial port (Serial2 with protocol 28)
local function find_port()
    port = serial:find_serial(0)  -- First scripting-protocol serial port
    if port then
        port:begin(115200)
        port:set_flow_control(0)
        gcs:send_text(5, "motor_bridge: Serial port found, 115200 baud")
        return true
    end
    gcs:send_text(4, "motor_bridge: No scripting serial port found! Check SERIAL2_PROTOCOL=28")
    return false
end

-- Map PWM (1000-2000) to FOC range (-1000 to +1000) with deadband
local function pwm_to_foc(pwm)
    if pwm == nil then return 0 end
    local centered = pwm - PWM_CENTER
    -- Apply deadband
    if math.abs(centered) < DEADBAND then
        return 0
    end
    -- Remove deadband offset
    if centered > 0 then
        centered = centered - DEADBAND
    else
        centered = centered + DEADBAND
    end
    -- Scale to FOC range
    local half_range = (PWM_MAX - PWM_MIN) / 2 - DEADBAND
    local foc = math.floor((centered / half_range) * FOC_MAX + 0.5)
    -- Clamp
    if foc > FOC_MAX then foc = FOC_MAX end
    if foc < -FOC_MAX then foc = -FOC_MAX end
    return foc
end

-- Apply rate limiting (smooth acceleration)
local function ramp(current, target)
    local diff = target - current
    if diff > RAMP_LIMIT then
        return current + RAMP_LIMIT
    elseif diff < -RAMP_LIMIT then
        return current - RAMP_LIMIT
    end
    return target
end

-- Pack int16 as two bytes (little-endian)
local function int16_le(val)
    -- Convert signed to unsigned 16-bit for byte packing
    if val < 0 then
        val = val + 65536
    end
    local lo = val % 256
    local hi = math.floor(val / 256) % 256
    return lo, hi
end

-- Send a motor command packet to the hoverboard FOC firmware
local function send_command(steer, speed)
    if not port then return false end

    -- Start frame: 0xABCD (little-endian: 0xCD, 0xAB)
    local start = 0xABCD
    local start_lo = start % 256        -- 0xCD
    local start_hi = math.floor(start / 256)  -- 0xAB

    local steer_lo, steer_hi = int16_le(steer)
    local speed_lo, speed_hi = int16_le(speed)

    -- Checksum: XOR of start, steer, speed as uint16 values
    local steer_u16 = steer
    if steer_u16 < 0 then steer_u16 = steer_u16 + 65536 end
    local speed_u16 = speed
    if speed_u16 < 0 then speed_u16 = speed_u16 + 65536 end

    -- XOR is done on the uint16 values
    local checksum = start ~ steer_u16 ~ speed_u16
    local check_lo = checksum % 256
    local check_hi = math.floor(checksum / 256) % 256

    -- Write 8 bytes
    port:write(start_lo)
    port:write(start_hi)
    port:write(steer_lo)
    port:write(steer_hi)
    port:write(speed_lo)
    port:write(speed_hi)
    port:write(check_lo)
    port:write(check_hi)

    return true
end

-- Main update function
function update()
    -- Initialize port on first run
    if not port then
        if not find_port() then
            return update, 1000  -- Retry in 1 second
        end
    end

    -- Read ArduRover servo outputs
    local pwm_left  = SRV_Channels:get_output_pwm(SERVO_LEFT)
    local pwm_right = SRV_Channels:get_output_pwm(SERVO_RIGHT)

    -- Convert to FOC commands
    -- For differential drive: speed = average, steer = difference
    local foc_left  = pwm_to_foc(pwm_left)
    local foc_right = pwm_to_foc(pwm_right)

    -- Hoverboard FOC expects: speed (forward/back) and steer (turn)
    -- speed = (left + right) / 2, steer = (left - right) / 2
    local target_speed = math.floor((foc_left + foc_right) / 2)
    local target_steer = math.floor((foc_left - foc_right) / 2)

    -- Apply rate limiting for smooth acceleration
    local cmd_speed = ramp(last_speed, target_speed)
    local cmd_steer = ramp(last_steer, target_steer)
    last_speed = cmd_speed
    last_steer = cmd_steer

    -- Send command to hoverboard
    if send_command(cmd_steer, cmd_speed) then
        send_count = send_count + 1
    else
        error_count = error_count + 1
    end

    -- Log every 5 seconds (every 250 ticks at 50Hz)
    if send_count % 250 == 0 and send_count > 0 then
        gcs:send_text(6, string.format("motor_bridge: spd=%d str=%d (L=%d R=%d) pkts=%d",
            cmd_speed, cmd_steer, foc_left, foc_right, send_count))
    end

    -- Publish motor commands as named floats for telemetry
    gcs:send_named_float('MSPD', cmd_speed)
    gcs:send_named_float('MSTR', cmd_steer)

    return update, SEND_INTERVAL
end

-- Startup
gcs:send_text(5, "motor_bridge.lua loaded - hoverboard FOC UART bridge")
gcs:send_text(5, string.format("  Rate=%dHz, Deadband=%d, RampLimit=%d", SEND_RATE_HZ, DEADBAND, RAMP_LIMIT))
return update, 1000  -- Initial 1 second delay before first send
