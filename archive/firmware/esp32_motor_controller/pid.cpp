/**
 * pid.cpp - PID controller implementation.
 */

#include "pid.h"

PID::PID(float kp, float ki, float kd,
         float output_min, float output_max,
         float integral_max)
    : _kp(kp), _ki(ki), _kd(kd),
      _output_min(output_min), _output_max(output_max),
      _integral_max(integral_max),
      _integral(0.0f),
      _prev_error(0.0f),
      _first_run(true)
{
}

float PID::compute(float setpoint, float measured, float dt)
{
    // Avoid division by zero or negative time steps.
    if (dt <= 0.0f) {
        return 0.0f;
    }

    float error = setpoint - measured;

    // --- Proportional term ---
    float p_term = _kp * error;

    // --- Integral term with anti-windup ---
    _integral += error * dt;

    // Clamp integral to prevent windup.
    if (_integral > _integral_max) {
        _integral = _integral_max;
    } else if (_integral < -_integral_max) {
        _integral = -_integral_max;
    }

    float i_term = _ki * _integral;

    // --- Derivative term ---
    float d_term = 0.0f;
    if (!_first_run) {
        float derivative = (error - _prev_error) / dt;
        d_term = _kd * derivative;
    }
    _first_run = false;
    _prev_error = error;

    // --- Sum and clamp output ---
    float output = p_term + i_term + d_term;

    if (output > _output_max) {
        output = _output_max;
    } else if (output < _output_min) {
        output = _output_min;
    }

    return output;
}

void PID::reset()
{
    _integral   = 0.0f;
    _prev_error = 0.0f;
    _first_run  = true;
}

void PID::setGains(float kp, float ki, float kd)
{
    _kp = kp;
    _ki = ki;
    _kd = kd;

    // Reset state when gains change to avoid transients from stale integral.
    reset();
}
