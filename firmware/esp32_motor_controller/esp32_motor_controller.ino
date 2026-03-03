/**
 * esp32_motor_controller.ino
 *
 * Main firmware for the autonomous line-striping robot's ESP32 motor
 * controller.  This sketch:
 *
 *   1. Receives wheel-speed commands (rad/s) from the ROS 2
 *      motor_driver_node over serial.
 *   2. Reads quadrature encoders on both drive motors via interrupts.
 *   3. Runs a PID loop to regulate each motor's speed.
 *   4. Sends cumulative encoder tick counts back to the host.
 *   5. Implements a watchdog that stops the motors if no command
 *      arrives within WATCHDOG_TIMEOUT_MS.
 *
 * Serial protocol (must match motor_driver_node.py):
 *   Host  -> ESP32:  "M,<left_rad_s>,<right_rad_s>\n"
 *   ESP32 -> Host:   "E,<left_ticks>,<right_ticks>\n"
 *
 * Hardware: ESP32 dev board + L298N or BTS7960 dual H-bridge + two DC
 * motors with quadrature encoders.
 */

#include "config.h"
#include "motor.h"
#include "encoder.h"
#include "pid.h"

// ---------------------------------------------------------------------------
// Global objects
// ---------------------------------------------------------------------------

// Motors
Motor leftMotor(LEFT_MOTOR_PWM_PIN,  LEFT_MOTOR_DIR1_PIN,  LEFT_MOTOR_DIR2_PIN,
                LEFT_PWM_CHANNEL,  PWM_FREQUENCY, PWM_RESOLUTION);
Motor rightMotor(RIGHT_MOTOR_PWM_PIN, RIGHT_MOTOR_DIR1_PIN, RIGHT_MOTOR_DIR2_PIN,
                 RIGHT_PWM_CHANNEL, PWM_FREQUENCY, PWM_RESOLUTION);

// Encoders
Encoder leftEncoder(LEFT_ENCODER_A_PIN,  LEFT_ENCODER_B_PIN);
Encoder rightEncoder(RIGHT_ENCODER_A_PIN, RIGHT_ENCODER_B_PIN);

// PID controllers (one per motor)
PID leftPID(PID_KP, PID_KI, PID_KD, PID_OUTPUT_MIN, PID_OUTPUT_MAX, PID_INTEGRAL_MAX);
PID rightPID(PID_KP, PID_KI, PID_KD, PID_OUTPUT_MIN, PID_OUTPUT_MAX, PID_INTEGRAL_MAX);

// ---------------------------------------------------------------------------
// State variables
// ---------------------------------------------------------------------------

// Desired wheel angular velocities in rad/s, received from the host.
float targetLeftRadS  = 0.0f;
float targetRightRadS = 0.0f;

// Timestamp of the last valid motor command (for watchdog).
unsigned long lastCommandTimeMs = 0;

// Timestamp of the last control-loop execution.
unsigned long lastLoopTimeMs = 0;

// Serial input buffer.
static const uint8_t SERIAL_BUF_SIZE = 64;
char serialBuffer[SERIAL_BUF_SIZE];
uint8_t serialBufIndex = 0;

// Watchdog state (true = motors stopped due to timeout).
bool watchdogTripped = false;

// LED blink timing.
unsigned long lastLedToggleMs = 0;
bool ledState = false;

// ---------------------------------------------------------------------------
// Conversion helpers
// ---------------------------------------------------------------------------

/**
 * Convert encoder ticks/second to rad/s.
 *
 *   rad/s = (ticks_per_sec / ticks_per_rev) * 2 * PI
 */
inline float ticksPerSecToRadS(float ticksPerSec)
{
    return (ticksPerSec / (float)ENCODER_TICKS_PER_REV) * TWO_PI;
}

// ---------------------------------------------------------------------------
// Serial command parser
// ---------------------------------------------------------------------------

/**
 * Parse a complete line from the serial buffer.
 *
 * Expected format: "M,<left_rad_s>,<right_rad_s>"
 */
void parseCommand(const char* line)
{
    // Must start with 'M,'
    if (line[0] != 'M' || line[1] != ',') {
        return;
    }

    // Find the second comma.
    const char* p = &line[2];
    char* comma = strchr(p, ',');
    if (comma == nullptr) {
        return;
    }

    // Parse left speed.
    *comma = '\0';  // Temporarily null-terminate the left portion.
    float left = atof(p);

    // Parse right speed.
    float right = atof(comma + 1);

    // Restore comma (not strictly necessary since buffer will be reset).
    *comma = ',';

    // Store new setpoints.
    targetLeftRadS  = left;
    targetRightRadS = right;

    // Reset watchdog timer.
    lastCommandTimeMs = millis();
    watchdogTripped = false;
}

/**
 * Read available serial bytes and process complete lines.
 */
void processSerial()
{
    while (Serial.available() > 0) {
        char c = Serial.read();

        if (c == '\n' || c == '\r') {
            if (serialBufIndex > 0) {
                serialBuffer[serialBufIndex] = '\0';
                parseCommand(serialBuffer);
                serialBufIndex = 0;
            }
        } else {
            if (serialBufIndex < SERIAL_BUF_SIZE - 1) {
                serialBuffer[serialBufIndex++] = c;
            } else {
                // Buffer overflow -- discard and reset.
                serialBufIndex = 0;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Encoder feedback transmitter
// ---------------------------------------------------------------------------

/**
 * Send the current cumulative encoder ticks to the host.
 *
 * Format: "E,<left_ticks>,<right_ticks>\n"
 */
void sendEncoderFeedback()
{
    int32_t leftTicks  = leftEncoder.getTicks();
    int32_t rightTicks = rightEncoder.getTicks();

    Serial.print("E,");
    Serial.print(leftTicks);
    Serial.print(",");
    Serial.println(rightTicks);
}

// ---------------------------------------------------------------------------
// Status LED
// ---------------------------------------------------------------------------

/**
 * Update the status LED based on the current operating state.
 *
 * Blink patterns:
 *   - Watchdog tripped (no commands): fast blink  (100 ms)
 *   - Normal operation, moving:       slow blink  (500 ms)
 *   - Normal operation, stopped:      solid ON
 */
void updateStatusLED()
{
    unsigned long now = millis();
    uint16_t interval;

    if (watchdogTripped) {
        // Fast blink -- something is wrong (lost communication).
        interval = 100;
    } else if (targetLeftRadS == 0.0f && targetRightRadS == 0.0f) {
        // Solid ON -- idle, connected.
        digitalWrite(STATUS_LED_PIN, HIGH);
        return;
    } else {
        // Slow blink -- actively driving.
        interval = 500;
    }

    if (now - lastLedToggleMs >= interval) {
        lastLedToggleMs = now;
        ledState = !ledState;
        digitalWrite(STATUS_LED_PIN, ledState ? HIGH : LOW);
    }
}

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------
void setup()
{
    // --- Serial ---
    Serial.begin(SERIAL_BAUD_RATE);

    // Wait briefly for the serial port to initialise.
    delay(100);

    // --- Status LED ---
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);

    // --- Motors ---
    leftMotor.begin();
    rightMotor.begin();

    // --- Encoders ---
    leftEncoder.begin();
    rightEncoder.begin();

    // --- PID controllers start in reset state (already done by constructor) ---

    // --- Initialise timing ---
    lastCommandTimeMs = millis();
    lastLoopTimeMs    = millis();

    // Signal that we are alive.
    Serial.println("# ESP32 Motor Controller Ready");
}

// ---------------------------------------------------------------------------
// loop()
// ---------------------------------------------------------------------------
void loop()
{
    // ----- 1. Process incoming serial data -----
    processSerial();

    // ----- 2. Run control loop at fixed interval -----
    unsigned long now = millis();
    if (now - lastLoopTimeMs < CONTROL_LOOP_INTERVAL_MS) {
        return;  // Not time yet.
    }

    float dt = (float)(now - lastLoopTimeMs) / 1000.0f;  // seconds
    lastLoopTimeMs = now;

    // ----- 3. Watchdog check -----
    if (now - lastCommandTimeMs > WATCHDOG_TIMEOUT_MS) {
        // No command received within the timeout window -- stop motors.
        if (!watchdogTripped) {
            targetLeftRadS  = 0.0f;
            targetRightRadS = 0.0f;
            leftMotor.stop();
            rightMotor.stop();
            leftPID.reset();
            rightPID.reset();
            watchdogTripped = true;
        }
    }

    // ----- 4. Read encoder velocities -----
    float leftVelTPS  = leftEncoder.getVelocity();   // ticks/sec
    float rightVelTPS = rightEncoder.getVelocity();   // ticks/sec

    // Convert to rad/s for PID comparison with the setpoint.
    float leftVelRadS  = ticksPerSecToRadS(leftVelTPS);
    float rightVelRadS = ticksPerSecToRadS(rightVelTPS);

    // ----- 5. PID computation -----
    float leftOutput  = leftPID.compute(targetLeftRadS,  leftVelRadS,  dt);
    float rightOutput = rightPID.compute(targetRightRadS, rightVelRadS, dt);

    // ----- 6. Drive motors -----
    // The PID output is in the range [-255, 255] and maps directly to
    // the Motor::setSpeed() input.
    if (!watchdogTripped) {
        leftMotor.setSpeed((int16_t)leftOutput);
        rightMotor.setSpeed((int16_t)rightOutput);
    }

    // ----- 7. Send encoder feedback -----
    sendEncoderFeedback();

    // ----- 8. Status LED -----
    updateStatusLED();
}
