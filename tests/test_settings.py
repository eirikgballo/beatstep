"""Innstillinger.py: følsomhet 1–10 per modus, lest på nytt mens Live kjører."""

import io
import os

import pytest

from harness import REPO, load_script_package


def _write(path, text):
    """Skriv innstillingsfila med nytt endringstidspunkt, slik en lagring i en editor gir."""
    previous = os.path.getmtime(path) if os.path.exists(path) else 0
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    os.utime(path, (previous + 10, previous + 10))


@pytest.fixture
def settings_file(clock):
    return os.environ['BEATSTEP_Q_SETTINGS']


def _macro(rig):
    return rig.track(1).devices[0].parameters[1]


def test_shipped_file_matches_the_built_in_defaults(clock):
    enc = load_script_package().Encoders
    shipped = {}
    with io.open(os.path.join(REPO, 'Innstillinger.py'), encoding='utf-8') as f:
        exec(f.read(), shipped)
    assert {name: shipped[name] for name in enc.DEFAULT_SETTINGS} == enc.DEFAULT_SETTINGS


def test_default_levels_give_the_old_feel(clock):
    enc = load_script_package().Encoders
    assert enc.feel('rack').min_step == pytest.approx(0.002)
    assert enc.feel('rack').min_step + enc.feel('rack').max_step == pytest.approx(0.022)
    assert enc.feel('transpose').min_step == pytest.approx(0.005, rel=0.01)
    assert enc.feel('scrub').min_step == pytest.approx(0.25)


def test_higher_level_gives_bigger_steps(settings_file, make_rig):
    _write(settings_file, 'RACK = (6, 6)\n')
    rig = make_rig()
    rig.turn(1)
    assert _macro(rig).value == pytest.approx(127 * 0.002 * 1.58 ** 3)


def test_file_is_reloaded_while_running(settings_file, make_rig):
    rig = make_rig()
    _write(settings_file, 'RACK = (6, 6)\n')
    rig.advance(1.0)
    assert 'BeatStep: Innstillinger.py loaded' in rig.h.messages
    rig.turn(1)
    assert _macro(rig).value == pytest.approx(127 * 0.002 * 1.58 ** 3)


def test_modes_have_separate_sensitivity(settings_file, make_rig):
    _write(settings_file, 'VOLUM = (5, 5)\n')
    rig = make_rig()
    rig.turn(1)
    assert _macro(rig).value == pytest.approx(127 * 0.002)          # Rack is unchanged
    rig.press('recall')
    rig.turn(2)
    assert rig.track(2).mixer_device.volume.value == pytest.approx(0.85 + 0.005, abs=1e-4)


@pytest.mark.parametrize('text, part', [
    ('RACK = (0, 5)\n', 'RACK must be two numbers from 1 to 10'),
    ('RACK = 5\n', 'RACK must be two numbers from 1 to 10'),
    ('KURVE = "myk"\n', 'KURVE must be a number'),
    ('RASK_TID = 0.5\n', 'RASK_TID must be lower than ROLIG_TID'),
    ('RACK = (3, 5\n', 'error in Innstillinger.py'),
])
def test_mistake_in_file_shows_message_and_keeps_old_values(settings_file, make_rig, text, part):
    rig = make_rig()
    _write(settings_file, text)
    rig.advance(1.0)
    assert any('error in Innstillinger.py' in m and part in m for m in rig.h.messages)
    rig.turn(1)
    assert _macro(rig).value == pytest.approx(127 * 0.002)


def test_same_fast_and_slow_level_turns_acceleration_off(settings_file, make_rig):
    _write(settings_file, 'RACK = (5, 1)\n')
    rig = make_rig()
    rig.turn(1, ticks=10, interval=0.02)
    assert _macro(rig).value == pytest.approx(127 * 0.005 * 10, rel=0.01)
