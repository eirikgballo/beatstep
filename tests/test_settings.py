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


def test_the_real_settings_file_is_valid_and_complete(clock):
    # Brukeren justerer verdiene i fila, så testen sjekker bare at den lar seg lese og har alle navnene.
    enc = load_script_package().Encoders
    real = {}
    with io.open(os.path.join(REPO, 'Innstillinger.py'), encoding='utf-8') as f:
        exec(f.read(), real)
    assert set(enc.DEFAULT_SETTINGS) <= set(real)
    enc.configure(real)


def test_default_levels_give_the_old_feel(clock):
    enc = load_script_package().Encoders
    assert enc.feel('rack').min_step == pytest.approx(0.002)
    assert enc.feel('rack').min_step + enc.feel('rack').max_step == pytest.approx(0.022)
    assert enc.feel('transpose').min_step == pytest.approx(0.005, rel=0.01)
    assert enc.feel('scrub').min_step == pytest.approx(0.25)
    assert enc.feel('rack').start_rate > 40          # normal turning (measured 10–40 detents/s) stays slow


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
    ('KAST = "hardt"\n', 'KAST must be a number'),
    ('KAST = 11\n', 'KAST must be a number from 1 to 10'),
    ('RACK = (3, 5\n', 'error in Innstillinger.py'),
])
def test_mistake_in_file_shows_message_and_keeps_old_values(settings_file, make_rig, text, part):
    rig = make_rig()
    _write(settings_file, text)
    rig.advance(1.0)
    assert any('error in Innstillinger.py' in m and part in m for m in rig.h.messages)
    rig.turn(1)
    assert _macro(rig).value == pytest.approx(127 * 0.002)


def test_fast_level_not_above_slow_turns_acceleration_off(settings_file, make_rig):
    _write(settings_file, 'RACK = (5, 1)\n')
    rig = make_rig()
    rig.turn(1, ticks=10, interval=0.005)
    assert _macro(rig).value == pytest.approx(127 * 0.005 * 10, rel=0.01)


def test_lower_kast_makes_the_fast_step_easier_to_reach(settings_file, make_rig):
    _write(settings_file, 'KAST = 1\n')
    rig = make_rig()
    rig.turn(1, ticks=6, interval=0.02)                     # 50 detents per second: full speed at KAST 1
    easy = _macro(rig).value
    _write(settings_file, 'KAST = 10\n')
    rig = make_rig()
    rig.turn(1, ticks=6, interval=0.02)
    assert _macro(rig).value == pytest.approx(127 * 0.002 * 6)     # still the slow step at KAST 10
    assert easy > _macro(rig).value


def test_old_setting_names_are_ignored(settings_file, make_rig):
    _write(settings_file, 'ROLIG_TID = 2.0\nRASK_TID = 0.05\nKURVE = 1.0\n')
    rig = make_rig()
    rig.advance(1.0)
    assert not any('error' in m for m in rig.h.messages)
