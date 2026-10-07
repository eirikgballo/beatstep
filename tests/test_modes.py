"""Moduser, encodere og transpose-knappen."""

import pytest

from conftest import OFF
from fake_song import audio_effect_rack


def _macro(track, n):
    return [d for d in track.devices if d.class_name == 'AudioEffectGroupDevice'][0].parameters[n]


# --- modusbytte ------------------------------------------------------------

def test_boots_in_rack_mode_with_chan_lit(make_rig, clock):
    from conftest import Rig
    from harness import Harness
    from fake_song import default_song
    rig = Rig(Harness(default_song()), clock)
    rig.advance(2.2)
    assert rig.mode == 'Rack'
    leds = rig.button_leds()
    assert leds['chan'] != OFF
    assert leds['recall'] == OFF and leds['store'] == OFF


@pytest.mark.parametrize('button, mode', [('recall', 'Volume'), ('store', 'Sends'), ('chan', 'Rack')])
def test_mode_buttons_switch_mode_and_light_only_their_button(rig, button, mode):
    if button == 'chan':
        rig.press('recall')
    rig.press(button)
    assert rig.mode == mode
    leds = rig.button_leds()
    for other in ('chan', 'recall', 'store'):
        assert (leds[other] != OFF) == (other == button)


def test_mode_change_shows_status_message(rig):
    rig.press('recall')
    assert 'BeatStep: Volume mode' in rig.h.messages


# --- Rack ------------------------------------------------------------------

def test_rack_encoder_moves_macro_on_selected_track(rig):
    rig.turn(3, ticks=1)
    assert _macro(rig.track(1), 3).value > 0


def test_rack_mode_uses_first_rack_after_other_devices(rig):
    rig.tap(4)                       # Spor 4: EQ, then rack
    rig.turn(1)
    assert _macro(rig.track(4), 1).value > 0


def test_rack_mode_without_rack_shows_message(rig):
    rig.tap(5)
    rig.turn(1)
    assert 'No Audio Effect Rack on selected track' in rig.h.messages


def test_rack_added_later_is_found(rig):
    rig.tap(5)
    rig.track(5).devices.append(audio_effect_rack('Ny'))
    rig.turn(1)
    assert _macro(rig.track(5), 1).value > 0


def test_rack_deleted_later_is_not_used(rig):
    rig.track(1).devices.clear()
    rig.turn(1)
    assert 'No Audio Effect Rack on selected track' in rig.h.messages


# --- Volum -----------------------------------------------------------------

def test_volume_encoder_n_controls_track_n(rig):
    rig.press('recall')
    rig.turn(3)
    assert rig.track(3).mixer_device.volume.value > 0.85
    assert rig.track(1).mixer_device.volume.value == 0.85


def test_volume_follows_the_pad_page(rig):
    rig.press('ext sync')
    rig.tap(2)
    rig.press('recall')
    rig.turn(2)
    assert rig.track(18).mixer_device.volume.value > 0.85


def test_volume_on_missing_track_is_ignored(rig):
    rig.press('ext sync')
    rig.tap(2)
    rig.press('recall')
    rig.turn(16)                      # track 32 doesn't exist
    assert rig.h.messages[-1] == 'BeatStep: Volume mode'


# --- Sends -----------------------------------------------------------------

def test_sends_encoders_1_to_8_control_send_a(rig):
    rig.press('store')
    rig.turn(3)
    sends = rig.track(3).mixer_device.sends
    assert sends[0].value > 0 and sends[1].value == 0


def test_sends_encoders_9_to_16_control_send_b_of_same_tracks(rig):
    rig.press('store')
    rig.turn(11)
    sends = rig.track(3).mixer_device.sends
    assert sends[1].value > 0 and sends[0].value == 0


def test_sends_have_own_8_track_paging(rig):
    rig.press('ext sync')
    rig.tap(2)
    rig.press('store')
    rig.turn(1)
    assert rig.track(9).mixer_device.sends[0].value > 0


# --- transpose ---------------------------------------------------------------

def test_transpose_controls_selected_track_volume(rig):
    rig.tap(2)
    rig.turn('transpose')
    assert rig.track(2).mixer_device.volume.value > 0.85


def test_shift_transpose_controls_master_volume(rig):
    rig.button_down('shift')
    rig.turn('transpose')
    rig.button_up('shift')
    assert rig.song.master_track.mixer_device.volume.value > 0.85
    assert rig.track(1).mixer_device.volume.value == 0.85
