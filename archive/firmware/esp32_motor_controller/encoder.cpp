/**
 * encoder.cpp - Quadrature encoder reader implementation for ESP32.
 *
 * Full x4 quadrature decoding using interrupts on both channels.
 */

#include "encoder.h"

// ---------------------------------------------------------------------------
// Static members
// ---------------------------------------------------------------------------
Encoder* Encoder::_instances[MAX_ENCODERS] = { nullptr };
uint8_t  Encoder::_instance_count = 0;

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------
Encoder::Encoder(uint8_t pin_a, uint8_t pin_b)
    : _pin_a(pin_a),
      _pin_b(pin_b),
      _ticks(0),
      _prev_ticks(0),
      _prev_time_us(0),
      _index(0)
{
}

// ---------------------------------------------------------------------------
// begin()
// ---------------------------------------------------------------------------
bool Encoder::begin()
{
    if (_instance_count >= MAX_ENCODERS) {
        return false;  // No free slots.
    }

    _index = _instance_count;
    _instances[_index] = this;
    _instance_count++;

    // Configure encoder pins as inputs with internal pull-ups.
    // Many encoders have open-collector outputs that need pull-ups.
    pinMode(_pin_a, INPUT_PULLUP);
    pinMode(_pin_b, INPUT_PULLUP);

    _prev_time_us = micros();

    // Attach the correct pair of ISR trampolines for this slot.
    switch (_index) {
        case 0:
            attachInterrupt(digitalPinToInterrupt(_pin_a), _isrA0, CHANGE);
            attachInterrupt(digitalPinToInterrupt(_pin_b), _isrB0, CHANGE);
            break;
        case 1:
            attachInterrupt(digitalPinToInterrupt(_pin_a), _isrA1, CHANGE);
            attachInterrupt(digitalPinToInterrupt(_pin_b), _isrB1, CHANGE);
            break;
        case 2:
            attachInterrupt(digitalPinToInterrupt(_pin_a), _isrA2, CHANGE);
            attachInterrupt(digitalPinToInterrupt(_pin_b), _isrB2, CHANGE);
            break;
        case 3:
            attachInterrupt(digitalPinToInterrupt(_pin_a), _isrA3, CHANGE);
            attachInterrupt(digitalPinToInterrupt(_pin_b), _isrB3, CHANGE);
            break;
    }

    return true;
}

// ---------------------------------------------------------------------------
// Tick access
// ---------------------------------------------------------------------------
volatile int32_t Encoder::getTicks() const
{
    return _ticks;
}

void Encoder::reset()
{
    noInterrupts();
    _ticks = 0;
    _prev_ticks = 0;
    interrupts();
    _prev_time_us = micros();
}

// ---------------------------------------------------------------------------
// Velocity calculation
// ---------------------------------------------------------------------------
float Encoder::getVelocity()
{
    // Snapshot tick count atomically.
    noInterrupts();
    int32_t current_ticks = _ticks;
    interrupts();

    uint32_t now_us = micros();
    uint32_t dt_us  = now_us - _prev_time_us;

    // Guard against divide-by-zero on first call or very fast loop.
    if (dt_us == 0) {
        return 0.0f;
    }

    int32_t delta_ticks = current_ticks - _prev_ticks;
    float velocity = (float)delta_ticks / ((float)dt_us * 1e-6f);  // ticks/sec

    _prev_ticks   = current_ticks;
    _prev_time_us = now_us;

    return velocity;
}

// ---------------------------------------------------------------------------
// ISR handlers (member functions, called from trampolines)
// ---------------------------------------------------------------------------

/**
 * Channel A interrupt handler.
 *
 * x4 quadrature truth table for channel A change:
 *   A_rising  && B_low  => forward   (+1)
 *   A_rising  && B_high => reverse   (-1)
 *   A_falling && B_high => forward   (+1)
 *   A_falling && B_low  => reverse   (-1)
 */
void IRAM_ATTR Encoder::_handleInterruptA()
{
    uint8_t a = digitalRead(_pin_a);
    uint8_t b = digitalRead(_pin_b);

    if (a == b) {
        _ticks--;
    } else {
        _ticks++;
    }
}

/**
 * Channel B interrupt handler.
 *
 * x4 quadrature truth table for channel B change:
 *   B_rising  && A_high => forward   (+1)
 *   B_rising  && A_low  => reverse   (-1)
 *   B_falling && A_low  => forward   (+1)
 *   B_falling && A_high => reverse   (-1)
 */
void IRAM_ATTR Encoder::_handleInterruptB()
{
    uint8_t a = digitalRead(_pin_a);
    uint8_t b = digitalRead(_pin_b);

    if (a == b) {
        _ticks++;
    } else {
        _ticks--;
    }
}

// ---------------------------------------------------------------------------
// Static ISR trampolines -- forward to the correct Encoder instance.
// These must be plain functions (no captures) for attachInterrupt().
// ---------------------------------------------------------------------------
void IRAM_ATTR Encoder::_isrA0() { if (_instances[0]) _instances[0]->_handleInterruptA(); }
void IRAM_ATTR Encoder::_isrB0() { if (_instances[0]) _instances[0]->_handleInterruptB(); }
void IRAM_ATTR Encoder::_isrA1() { if (_instances[1]) _instances[1]->_handleInterruptA(); }
void IRAM_ATTR Encoder::_isrB1() { if (_instances[1]) _instances[1]->_handleInterruptB(); }
void IRAM_ATTR Encoder::_isrA2() { if (_instances[2]) _instances[2]->_handleInterruptA(); }
void IRAM_ATTR Encoder::_isrB2() { if (_instances[2]) _instances[2]->_handleInterruptB(); }
void IRAM_ATTR Encoder::_isrA3() { if (_instances[3]) _instances[3]->_handleInterruptA(); }
void IRAM_ATTR Encoder::_isrB3() { if (_instances[3]) _instances[3]->_handleInterruptB(); }
