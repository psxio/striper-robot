/**
 * config.h - Hardware configuration for ESP32 motor controller.
 *
 * All pin assignments, PID gains, physical parameters, and timing
 * constants are defined here. Adjust these values to match your
 * specific hardware wiring and robot geometry.
 *
 * This firmware is designed for the autonomous line-striping robot and
 * communicates with the ROS 2 motor_driver_node via serial.
 */

#ifndef CONFIG_H
#define CONFIG_H

// ---------------------------------------------------------------------------
// Serial Communication
// ---------------------------------------------------------------------------
// Must match the baud_rate parameter in motor_driver_node.py (default 115200).
#define SERIAL_BAUD_RATE 115200

// ---------------------------------------------------------------------------
// Motor Driver Pins  (L298N or BTS7960)
// ---------------------------------------------------------------------------
// Left motor
#define LEFT_MOTOR_PWM_PIN   25   // PWM output (ENA on L298N / RPWM on BTS7960)
#define LEFT_MOTOR_DIR1_PIN  26   // Direction pin 1 (IN1 on L298N / R_EN on BTS7960)
#define LEFT_MOTOR_DIR2_PIN  27   // Direction pin 2 (IN2 on L298N / L_EN on BTS7960)

// Right motor
#define RIGHT_MOTOR_PWM_PIN  14   // PWM output (ENB on L298N / RPWM on BTS7960)
#define RIGHT_MOTOR_DIR1_PIN 12   // Direction pin 1 (IN3 on L298N / R_EN on BTS7960)
#define RIGHT_MOTOR_DIR2_PIN 13   // Direction pin 2 (IN4 on L298N / L_EN on BTS7960)

// ---------------------------------------------------------------------------
// ESP32 LEDC PWM Configuration
// ---------------------------------------------------------------------------
#define PWM_FREQUENCY   20000   // 20 kHz - above audible range
#define PWM_RESOLUTION  8       // 8-bit resolution (0-255)
#define LEFT_PWM_CHANNEL  0
#define RIGHT_PWM_CHANNEL 1

// ---------------------------------------------------------------------------
// Encoder Pins  (Quadrature A/B per motor)
// ---------------------------------------------------------------------------
// Choose GPIO pins that support interrupts (most ESP32 GPIOs do).
#define LEFT_ENCODER_A_PIN   34   // Channel A (must be input-capable)
#define LEFT_ENCODER_B_PIN   35   // Channel B
#define RIGHT_ENCODER_A_PIN  36   // Channel A (VP)
#define RIGHT_ENCODER_B_PIN  39   // Channel B (VN)

// ---------------------------------------------------------------------------
// Encoder Physical Parameters
// ---------------------------------------------------------------------------
// Counts per revolution of the motor shaft *after* quadrature decoding.
// For a 360-CPR encoder with x4 decoding: 1440.  Adjust to your hardware.
#define ENCODER_TICKS_PER_REV 1440

// ---------------------------------------------------------------------------
// Robot Physical Parameters
// ---------------------------------------------------------------------------
// These must match the values in motor_driver_node.py so that the rad/s
// setpoints translate correctly to real-world motion.
#define WHEEL_RADIUS_M       0.075f   // metres
#define WHEEL_SEPARATION_M   0.40f    // metres (centre-to-centre)

// ---------------------------------------------------------------------------
// PID Gains
// ---------------------------------------------------------------------------
// Tune these on your actual hardware.  Start with Kp only, then add Ki/Kd.
#define PID_KP   2.0f
#define PID_KI   5.0f
#define PID_KD   0.01f

// Output limits for PID (maps to PWM range -255..255)
#define PID_OUTPUT_MIN -255.0f
#define PID_OUTPUT_MAX  255.0f

// Anti-windup: maximum accumulated integral term
#define PID_INTEGRAL_MAX  200.0f

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------
// Control loop interval in milliseconds.  50 ms = 20 Hz, matching the
// default cmd_rate in motor_driver_node.py.
#define CONTROL_LOOP_INTERVAL_MS  50

// Watchdog timeout: if no serial command is received within this many
// milliseconds the motors are stopped for safety.
#define WATCHDOG_TIMEOUT_MS       500

// ---------------------------------------------------------------------------
// Status LED
// ---------------------------------------------------------------------------
#define STATUS_LED_PIN  2   // Built-in LED on most ESP32 dev boards

#endif // CONFIG_H
