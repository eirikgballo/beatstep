"""
Encoders — relative decoding and time-based acceleration, shared by all modes.

The BeatStep encoders run in relative mode 2: 1–63 = clockwise, 65–127 = counter-clockwise.
They normally send ±1 per detent regardless of speed, so acceleration is based on the time
between ticks. See SIGNALS.md for the measurements.
"""

import time


class Feel:
    """
    Tuning for one kind of encoder.

    min_step:  step per tick as a fraction of the parameter's range when turning very slowly.
    max_step:  extra step added at full speed (full speed gives min_step + max_step).
    accel:     curve exponent. 1.0 = linear, 2.0 = gentle, 3.0 = aggressive.
    fast:      tick interval (s) at or below which the encoder counts as full speed.
               The most impactful constant: lower it if fast spins feel sluggish.
    slow:      tick interval (s) at or above which the encoder counts as minimum speed.
    """

    def __init__(self, min_step, max_step, accel, fast, slow):
        self.min_step = min_step
        self.max_step = max_step
        self.accel    = accel
        self.fast     = fast
        self.slow     = slow


# The 16 knobs. Typical intervals: fast spin ~0.03–0.06 s/tick, slow spin ~0.2–0.5 s/tick.
KNOB_FEEL = Feel(min_step=0.002, max_step=0.02, accel=2.0, fast=0.08, slow=0.30)  # max 0.05 was good but a bit fast

# The large transpose knob (volume). 0.005 ≈ 0.2 dB per tick, 0.02 ≈ 0.8 dB.
TRANSPOSE_FEEL = Feel(min_step=0.005, max_step=0.02, accel=1.5, fast=0.08, slow=0.25)


class Accelerator:
    """Turns raw relative CC values into signed step fractions, tracking tick timing per encoder."""

    def __init__(self):
        # Last-tick timestamps. Key: encoder index (0-15) or 'transpose'.
        self._last_tick = {}

    def delta(self, key, value, feel):
        """Signed step as a fraction of the parameter range, or None for a neutral value."""
        if value == 0 or value == 64:
            return None
        raw_delta = value if value < 64 else value - 128
        direction = 1 if raw_delta > 0 else -1

        # The first tick after start has no previous tick and counts as slow (dt=inf).
        now = time.monotonic()
        dt = now - self._last_tick.get(key, float('-inf'))
        self._last_tick[key] = now

        velocity = max(0.0, min(1.0, (feel.slow - dt) / (feel.slow - feel.fast)))
        if abs(raw_delta) > 1:
            velocity = 1.0  # the hardware's own acceleration kicked in: the knob is spun very fast
        step = feel.min_step + (velocity ** feel.accel) * feel.max_step
        return direction * step


def nudge(param, fraction):
    """Move a Live parameter by a fraction of its range, clamped to [min, max]."""
    span = param.max - param.min
    param.value = max(param.min, min(param.max, param.value + fraction * span))


def turn(param, fraction, reset):
    """One encoder detent: nudge the parameter, or with `reset` (shift held) put it back to its default
    value, like a double-click in Live."""
    if reset:
        param.value = param.default_value
    else:
        nudge(param, fraction)
