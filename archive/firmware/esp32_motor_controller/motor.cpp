/**
 * motor.cpp - DC motor driver implementation for ESP32.
 */

#include "motor.h"

Motor::Motor(uint8_t pwm_pin, uint8_t dir1_pin, uint8_t dir2_pin,
             uint8_t pwm_channel, uint32_t pwm_freq, uint8_t pwm_res_bits)
    : _pwm_pin(pwm_pin),
      _dir1_pin(dir1_pin),
      _dir2_pin(dir2_pin),
      _pwm_channel(pwm_channel),
      _pwm_freq(pwm_freq),
      _pwm_res_bits(pwm_res_bits),
      _enabled(true)
{
}

void Motor::begin()
{
    // Configure direction pins as digital outputs.
    pinMode(_dir1_pin, OUTPUT);
    pinMode(_dir2_pin, OUTPUT);
    digitalWrite(_dir1_pin, LOW);
    digitalWrite(_dir2_pin, LOW);

    // Configure LEDC PWM channel on the ESP32.
    ledcSetup(_pwm_channel, _pwm_freq, _pwm_res_bits);
    ledcAttachPin(_pwm_pin, _pwm_channel);
    ledcWrite(_pwm_channel, 0);
}

void Motor::setSpeed(int16_t speed)
{
    if (!_enabled) {
        // If disabled, force outputs off regardless of requested speed.
        ledcWrite(_pwm_channel, 0);
        digitalWrite(_dir1_pin, LOW);
        digitalWrite(_dir2_pin, LOW);
        return;
    }

    // Clamp to valid range.
    if (speed > 255)  speed = 255;
    if (speed < -255) speed = -255;

    if (speed > 0) {
        // Forward: DIR1 = HIGH, DIR2 = LOW
        digitalWrite(_dir1_pin, HIGH);
        digitalWrite(_dir2_pin, LOW);
        ledcWrite(_pwm_channel, (uint32_t)speed);
    } else if (speed < 0) {
        // Reverse: DIR1 = LOW, DIR2 = HIGH
        digitalWrite(_dir1_pin, LOW);
        digitalWrite(_dir2_pin, HIGH);
        ledcWrite(_pwm_channel, (uint32_t)(-speed));
    } else {
        // Stop (coast): both direction pins LOW, PWM = 0
        digitalWrite(_dir1_pin, LOW);
        digitalWrite(_dir2_pin, LOW);
        ledcWrite(_pwm_channel, 0);
    }
}

void Motor::stop()
{
    digitalWrite(_dir1_pin, LOW);
    digitalWrite(_dir2_pin, LOW);
    ledcWrite(_pwm_channel, 0);
}

void Motor::setEnabled(bool enabled)
{
    _enabled = enabled;
    if (!_enabled) {
        stop();
    }
}

bool Motor::isEnabled() const
{
    return _enabled;
}
