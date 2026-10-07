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
    assert acc.delta(0, 1, enc.KNOB_FEEL) > 0
    clock.now += 1
    assert acc.delta(0, 127, enc.KNOB_FEEL) < 0


@pytest.mark.parametrize('value', [0, 64])
def test_neutral_values_are_ignored(enc, value):
    assert enc.Accelerator().delta(0, value, enc.KNOB_FEEL) is None


def test_first_tick_counts_as_slow(enc):
    feel = enc.KNOB_FEEL
    assert enc.Accelerator().delta(0, 1, feel) == pytest.approx(feel.min_step)


def test_fast_ticks_get_full_step(enc, clock):
    feel = enc.KNOB_FEEL
    acc = enc.Accelerator()
    acc.delta(0, 1, feel)
    clock.now += feel.fast / 2
    assert acc.delta(0, 1, feel) == pytest.approx(feel.min_step + feel.max_step)


def test_slow_ticks_get_minimum_step(enc, clock):
    feel = enc.KNOB_FEEL
    acc = enc.Accelerator()
    acc.delta(0, 1, feel)
    clock.now += feel.slow * 2
    assert acc.delta(0, 1, feel) == pytest.approx(feel.min_step)


def test_hardware_acceleration_counts_as_full_speed(enc, clock):
    # Very fast spins make the BeatStep send larger values (measured 12).
    feel = enc.KNOB_FEEL
    acc = enc.Accelerator()
    acc.delta(0, 1, feel)
    clock.now += 5
    assert acc.delta(0, 12, feel) == pytest.approx(feel.min_step + feel.max_step)


def test_encoders_are_timed_independently(enc, clock):
    feel = enc.KNOB_FEEL
    acc = enc.Accelerator()
    acc.delta(0, 1, feel)
    clock.now += 0.01
    assert acc.delta(1, 1, feel) == pytest.approx(feel.min_step)


def test_nudge_scales_with_range_and_clamps(enc):
    macro = Param(0, 127, 126)
    enc.nudge(macro, 0.01)
    assert macro.value == pytest.approx(127)
    vol = Param(0, 1, 0.001)
    enc.nudge(vol, -0.01)
    assert vol.value == 0
