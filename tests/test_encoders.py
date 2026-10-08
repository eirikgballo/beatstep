"""Dekoding og akselerasjon (Encoders.py), testet direkte uten Live."""

import pytest

from harness import load_script_package


class Param:

    def __init__(self, min=0.0, max=1.0, value=0.5):
        self.min, self.max, self.value = min, max, value


@pytest.fixture
def enc(clock):
    return load_script_package().Encoders


def test_clockwise_and_counter_clockwise(enc, clock):
    acc = enc.Accelerator()
    assert acc.delta(0, 1, enc.feel('rack')) > 0
    clock.now += 1
    assert acc.delta(0, 127, enc.feel('rack')) < 0


@pytest.mark.parametrize('value', [0, 64])
def test_neutral_values_are_ignored(enc, value):
    assert enc.Accelerator().delta(0, value, enc.feel('rack')) is None


def _spin(acc, clock, feel, rate, seconds=0.3, key=0):
    """Vri med jevn fart (hakk per sekund) og returner det siste steget."""
    step = None
    for _ in range(int(rate * seconds)):
        clock.now += 1.0 / rate
        step = acc.delta(key, 1, feel)
    return step


def test_first_detent_counts_as_slow(enc):
    feel = enc.feel('rack')
    assert enc.Accelerator().delta(0, 1, feel) == pytest.approx(feel.min_step)


@pytest.mark.parametrize('rate', [10, 20, 40])
def test_normal_turning_gets_the_slow_step(enc, clock, rate):
    # Measured: normal turning is 10–40 detents per second.
    feel = enc.feel('rack')
    assert _spin(enc.Accelerator(), clock, feel, rate) == pytest.approx(feel.min_step)


def test_fast_spin_gets_the_full_step(enc, clock):
    feel = enc.feel('rack')
    assert _spin(enc.Accelerator(), clock, feel, 200) == pytest.approx(feel.min_step + feel.max_step)


def test_step_grows_evenly_between_start_and_full_speed(enc, clock):
    feel = enc.feel('rack')
    steps = [_spin(enc.Accelerator(), clock, feel, rate) for rate in (80, 110, 140)]
    assert feel.min_step < steps[0] < steps[1] < steps[2] < feel.min_step + feel.max_step


def test_speed_drops_again_after_a_pause(enc, clock):
    feel = enc.feel('rack')
    acc = enc.Accelerator()
    _spin(acc, clock, feel, 200)
    clock.now += 0.5
    assert acc.delta(0, 1, feel) == pytest.approx(feel.min_step)


def test_hardware_acceleration_counts_as_full_speed(enc, clock):
    # Very fast spins make the BeatStep send larger values (measured 12).
    feel = enc.feel('rack')
    acc = enc.Accelerator()
    acc.delta(0, 1, feel)
    clock.now += 5
    assert acc.delta(0, 12, feel) == pytest.approx(feel.min_step + feel.max_step)


def test_encoders_are_timed_independently(enc, clock):
    feel = enc.feel('rack')
    acc = enc.Accelerator()
    _spin(acc, clock, feel, 200, key=0)
    assert acc.delta(1, 1, feel) == pytest.approx(feel.min_step)


def test_nudge_scales_with_range_and_clamps(enc):
    macro = Param(0, 127, 126)
    enc.nudge(macro, 0.01)
    assert macro.value == pytest.approx(127)
    vol = Param(0, 1, 0.001)
    enc.nudge(vol, -0.01)
    assert vol.value == 0
