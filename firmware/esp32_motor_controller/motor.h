/**
 * motor.h - DC motor driver abstraction for ESP32.
 *
 * Controls a single brushed DC motor through an H-bridge driver (L298N or
 * BTS7960).  Uses the ESP32 LEDC peripheral for PWM generation.
 */

#ifndef MOTOR_H
#define MOTOR_H

#include <Arduino.h>

class Motor {
public:
    /**
     * Construct a Motor instance.
     *
     * @param pwm_pin      GPIO used for PWM speed control.
     * @param dir1_pin     GPIO for direction signal 1 (IN1 / R_EN).
     * @param dir2_pin     GPIO for direction signal 2 (IN2 / L_EN).
     * @param pwm_channel  ESP32 LEDC channel (0-15).
     * @param pwm_freq     PWM frequency in Hz.
     * @param pwm_res_bits PWM resolution in bits (e.g. 8 for 0-255).
     */
    Motor(uint8_t pwm_pin, uint8_t dir1_pin, uint8_t dir2_pin,
          uint8_t pwm_channel, uint32_t pwm_freq, uint8_t pwm_res_bits);

    /** Initialise GPIO modes and LEDC channel.  Call once in setup(). */
    void begin();

    /**
     * Set motor speed and direction.
     *
     * @param speed  Value from -255 to +255.
     *               Positive = forward, negative = reverse, 0 = coast.
     */
    void setSpeed(int16_t speed);

    /** Hard-stop the motor (both direction pins LOW, PWM = 0). */
    void stop();

    /** Enable or disable the motor driver output. */
    void setEnabled(bool enabled);

    /** Returns true if the motor is currently enabled. */
    bool isEnabled() const;

private:
    uint8_t  _pwm_pin;
    uint8_t  _dir1_pin;
    uint8_t  _dir2_pin;
    uint8_t  _pwm_channel;
    uint32_t _pwm_freq;
    uint8_t  _pwm_res_bits;
    bool     _enabled;
};

#endif // MOTOR_H
