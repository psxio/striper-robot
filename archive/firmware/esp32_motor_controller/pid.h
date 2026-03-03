/**
 * pid.h - PID controller with anti-windup and output clamping.
 *
 * Standard discrete-time PID suitable for motor speed control.
 */

#ifndef PID_H
#define PID_H

#include <Arduino.h>

class PID {
public:
    /**
     * Construct a PID controller.
     *
     * @param kp           Proportional gain.
     * @param ki           Integral gain.
     * @param kd           Derivative gain.
     * @param output_min   Minimum output value (clamp).
     * @param output_max   Maximum output value (clamp).
     * @param integral_max Maximum absolute value of the integral accumulator
     *                     (anti-windup limit).
     */
    PID(float kp, float ki, float kd,
        float output_min, float output_max,
        float integral_max);

    /**
     * Compute the PID output.
     *
     * @param setpoint  Desired value (e.g. target rad/s).
     * @param measured  Actual measured value (e.g. current rad/s).
     * @param dt        Time step in seconds since last call.
     * @return          Control output, clamped to [output_min, output_max].
     */
    float compute(float setpoint, float measured, float dt);

    /** Reset integral accumulator and previous error. */
    void reset();

    /** Update gains at runtime (e.g. for tuning over serial). */
    void setGains(float kp, float ki, float kd);

    /** Read back current gains. */
    float getKp() const { return _kp; }
    float getKi() const { return _ki; }
    float getKd() const { return _kd; }

private:
    float _kp, _ki, _kd;
    float _output_min, _output_max;
    float _integral_max;
    float _integral;
    float _prev_error;
    bool  _first_run;
};

#endif // PID_H
