"""
Encoders — relative decoding and time-based acceleration, shared by all modes.

The BeatStep encoders run in relative mode 2: 1–63 = clockwise, 65–127 = counter-clockwise.
They normally send ±1 per detent regardless of speed, so acceleration is based on the time
between ticks. See SIGNALS.md for the measurements.

The sensitivity is set by the user in Innstillinger.py, which BeatStep.py reloads when it changes.
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


# ---------------------------------------------------------------------------
# Settings (Innstillinger.py)
# ---------------------------------------------------------------------------

# The values the user can change in Innstillinger.py. These defaults must match the file as shipped.
DEFAULT_SETTINGS = {
    'RACK':      (3, 5),
    'VOLUM':     (3, 5),
    'SENDS':     (3, 5),
    'TRANSPOSE': (5, 5),
    'SCRUB':     (3, 6),
    'ROLIG_TID': 0.30,
    'RASK_TID':  0.08,
    'KURVE':     2.0,
}

# Feel name used by the script → setting name.
_FEEL_SETTINGS = {'rack': 'RACK', 'volume': 'VOLUM', 'sends': 'SENDS', 'transpose': 'TRANSPOSE', 'scrub': 'SCRUB'}

# Scrub steps are in beats instead of a fraction of a parameter range.
_SCRUB_BEATS = 125.0

_feels = {}


def slow_step(level):
    """Sensitivity level 1–10 → step per detent when turning slowly (level 3 = 0.2 %, 5 = 0.5 %)."""
    return 0.002 * 1.58 ** (level - 3)


def fast_step(level):
    """Sensitivity level 1–10 → step per detent at full speed (level 5 = 2.2 %)."""
    return 0.022 * 1.5 ** (level - 5)


def configure(settings):
    """Build the feels from the names in `settings` (the contents of Innstillinger.py). Missing names keep
    their default. Raises ValueError with a message for the user, and then nothing is changed."""
    values = dict(DEFAULT_SETTINGS)
    values.update((name, settings[name]) for name in DEFAULT_SETTINGS if name in settings)

    def number(name, low, high):
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError('%s must be a number from %s to %s' % (name, low, high))
        return float(value)

    slow, fast, accel = number('ROLIG_TID', 0.01, 5), number('RASK_TID', 0.001, 5), number('KURVE', 0.1, 10)
    if fast >= slow:
        raise ValueError('RASK_TID must be lower than ROLIG_TID')

    feels = {}
    for feel_name, name in _FEEL_SETTINGS.items():
        levels = values[name]
        if (not isinstance(levels, (tuple, list)) or len(levels) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 1 <= v <= 10 for v in levels)):
            raise ValueError('%s must be two numbers from 1 to 10' % name)
        scale = _SCRUB_BEATS if feel_name == 'scrub' else 1.0
        min_step = slow_step(levels[0]) * scale
        max_step = max(0.0, fast_step(levels[1]) * scale - min_step)
        feels[feel_name] = Feel(min_step, max_step, accel, fast, slow)
    _feels.clear()
    _feels.update(feels)


def feel(name):
    """The current Feel for 'rack', 'volume', 'sends', 'transpose' or 'scrub'."""
    return _feels[name]


configure({})


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
