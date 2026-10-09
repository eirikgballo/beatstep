"""
Encoders — relative decoding and speed-based acceleration, shared by all modes.

The BeatStep encoders run in relative mode 2: 1–63 = clockwise, 65–127 = counter-clockwise.
They normally send ±1 per detent regardless of speed, so acceleration is based on how many detents
arrived lately. See SIGNALS.md for the measurements.

The sensitivity is set by the user in Innstillinger.py, which BeatStep.py reloads when it changes.
"""

from collections import deque
import time

# The speed of an encoder is the number of detents in this many seconds. The time between two single
# detents is too jittery to use: Live hands MIDI to the script in small clumps (see SIGNALS.md).
SPEED_WINDOW = 0.1


class Feel:
    """
    Tuning for one kind of encoder.

    min_step:    step per detent as a fraction of the parameter's range when turning slowly.
    max_step:    extra step added at full speed (full speed gives min_step + max_step).
    start_rate:  detents per second at or below which the encoder gets the slow step.
    full_rate:   detents per second at or above which it gets the full step. In between the step grows evenly.
    """

    def __init__(self, min_step, max_step, start_rate, full_rate):
        self.min_step   = min_step
        self.max_step   = max_step
        self.start_rate = start_rate
        self.full_rate  = full_rate


# ---------------------------------------------------------------------------
# Settings (Innstillinger.py)
# ---------------------------------------------------------------------------

# The values the user can change in Innstillinger.py, with the defaults used for names missing from the file.
DEFAULT_SETTINGS = {
    'RACK':      (3, 5),
    'VOLUM':     (3, 5),
    'TRANSPOSE': (5, 5),
    'SCRUB':     (3, 6),
    'KAST':      6,
}

# Feel name used by the script → setting name.
_FEEL_SETTINGS = {'rack': 'RACK', 'volume': 'VOLUM', 'transpose': 'TRANSPOSE', 'scrub': 'SCRUB'}

# Scrub steps are in beats instead of a fraction of a parameter range.
_SCRUB_BEATS = 125.0

_feels = {}


def slow_step(level):
    """Sensitivity level 1–10 → step per detent when turning slowly (level 3 = 0.2 %, 5 = 0.5 %)."""
    return 0.002 * 1.58 ** (level - 3)


def fast_step(level):
    """Sensitivity level 1–10 → step per detent at full speed (level 5 = 2.2 %)."""
    return 0.022 * 1.5 ** (level - 5)


def full_rate(level):
    """KAST level 1–10 → detents per second that give the full step (level 6 = 176, and acceleration
    starts at a third of that). Normal turning was measured at 10–40 detents per second and a fast spin
    at 70–900."""
    return 135.0 * 1.3 ** (level - 5)


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

    full = full_rate(number('KAST', 1, 10))
    start = full / 3.0

    feels = {}
    for feel_name, name in _FEEL_SETTINGS.items():
        levels = values[name]
        if (not isinstance(levels, (tuple, list)) or len(levels) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 1 <= v <= 10 for v in levels)):
            raise ValueError('%s must be two numbers from 1 to 10' % name)
        scale = _SCRUB_BEATS if feel_name == 'scrub' else 1.0
        min_step = slow_step(levels[0]) * scale
        max_step = max(0.0, fast_step(levels[1]) * scale - min_step)
        feels[feel_name] = Feel(min_step, max_step, start, full)
    _feels.clear()
    _feels.update(feels)


def feel(name):
    """The current Feel for 'rack', 'volume', 'transpose' or 'scrub'."""
    return _feels[name]


configure({})


class Accelerator:
    """Turns raw relative CC values into signed step fractions, tracking the speed of each encoder."""

    def __init__(self):
        # Times of the latest detents. Key: encoder index (0-15), 'transpose' or 'scrub'.
        self._detents = {}

    def delta(self, key, value, feel):
        """Signed step as a fraction of the parameter range, or None for a neutral value."""
        if value == 0 or value == 64:
            return None
        raw_delta = value if value < 64 else value - 128
        direction = 1 if raw_delta > 0 else -1

        now = time.monotonic()
        detents = self._detents.setdefault(key, deque())
        detents.append(now)
        while detents[0] < now - SPEED_WINDOW + 1e-6:  # the margin keeps a detent exactly one window old out
            detents.popleft()
        rate = len(detents) / SPEED_WINDOW   # a single detent after a pause is 10 per second: slow

        velocity = max(0.0, min(1.0, (rate - feel.start_rate) / (feel.full_rate - feel.start_rate)))
        if abs(raw_delta) > 1:
            velocity = 1.0  # the hardware's own acceleration kicked in: the knob is spun very fast
        return direction * (feel.min_step + velocity * feel.max_step)


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
