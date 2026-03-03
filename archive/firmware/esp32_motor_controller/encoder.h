/**
 * encoder.h - Quadrature encoder reader for ESP32.
 *
 * Uses hardware interrupts on both A and B channels for full x4
 * quadrature decoding, giving maximum resolution from the encoder.
 *
 * Because ISRs must be free functions (not member methods), each
 * Encoder instance registers a static trampoline that forwards to
 * the correct object.  Up to 4 encoder instances are supported.
 */

#ifndef ENCODER_H
#define ENCODER_H

#include <Arduino.h>

// Maximum number of encoder instances the ISR routing table supports.
#define MAX_ENCODERS 4

class Encoder {
public:
    /**
     * Construct an Encoder.
     *
     * @param pin_a  GPIO for channel A.
     * @param pin_b  GPIO for channel B.
     */
    Encoder(uint8_t pin_a, uint8_t pin_b);

    /**
     * Initialise pins, attach interrupts.  Call once in setup().
     * Returns false if the maximum number of encoders has been exceeded.
     */
    bool begin();

    /** Return the cumulative tick count (signed, wraps at int32 limits). */
    volatile int32_t getTicks() const;

    /** Reset the tick counter to zero. */
    void reset();

    /**
     * Compute velocity in ticks per second.
     *
     * Call this at a regular interval (e.g. every control loop iteration).
     * It uses the elapsed time since the previous call to calculate the
     * rate of change.
     *
     * @return Velocity in ticks/second.
     */
    float getVelocity();

private:
    uint8_t         _pin_a;
    uint8_t         _pin_b;
    volatile int32_t _ticks;

    // For velocity calculation
    int32_t  _prev_ticks;
    uint32_t _prev_time_us;

    // ISR routing
    uint8_t _index;                      // Slot in the static table

    /** Actual ISR work -- called from the static trampoline. */
    void IRAM_ATTR _handleInterruptA();
    void IRAM_ATTR _handleInterruptB();

    // ---- Static ISR routing table ----
    static Encoder* _instances[MAX_ENCODERS];
    static uint8_t  _instance_count;

    // Trampoline functions (one pair per slot).
    static void IRAM_ATTR _isrA0(); static void IRAM_ATTR _isrB0();
    static void IRAM_ATTR _isrA1(); static void IRAM_ATTR _isrB1();
    static void IRAM_ATTR _isrA2(); static void IRAM_ATTR _isrB2();
    static void IRAM_ATTR _isrA3(); static void IRAM_ATTR _isrB3();
};

#endif // ENCODER_H
