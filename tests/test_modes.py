"""Moduser, encodere og transpose-knappen."""

import pytest

from conftest import BLUE, MAGENTA, OFF, RED
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


# --- variasjonsvelger (chan en gang til i Rack-modus) -----------------------

@pytest.fixture
def variation_rig(rig):
    """Rack-et på spor 1 har tre variasjoner med makro 1 = 10, 20 og 30. Den siste er valgt."""
    rack = rig.track(1).devices[0]
    for value in (10, 20, 30):
        rack.parameters[1].value = value
        rack.store_variation()
    return rig


def test_chan_in_rack_mode_opens_the_variation_picker(variation_rig):
    variation_rig.press('chan')
    leds = variation_rig.leds()
    assert [leds[n] for n in (1, 2, 3)] == [MAGENTA, MAGENTA, RED]      # the third is selected
    assert all(leds[n] == OFF for n in range(4, 17))


def test_pad_recalls_variation_and_picker_stays_open(variation_rig):
    variation_rig.press('chan')
    variation_rig.tap(1)
    assert _macro(variation_rig.track(1), 1).value == 10
    assert variation_rig.leds()[1] == RED
    variation_rig.tap(2)
    assert _macro(variation_rig.track(1), 1).value == 20
    assert variation_rig.selected is variation_rig.track(1)             # pads did not select tracks


def test_chan_again_closes_the_picker(variation_rig):
    variation_rig.press('chan')
    variation_rig.press('chan')
    assert variation_rig.leds()[1] == RED and variation_rig.leds()[2] == BLUE    # tracks again
    variation_rig.tap(2)
    assert variation_rig.selected is variation_rig.track(2)


def test_empty_variation_pad_shows_message(variation_rig):
    variation_rig.press('chan')
    variation_rig.tap(5)
    assert 'Variation 5 is empty' in variation_rig.h.messages


def test_picker_on_track_without_rack_shows_message(variation_rig):
    variation_rig.tap(6)
    variation_rig.press('chan')
    assert all(color == OFF for color in variation_rig.leds().values())
    variation_rig.tap(1)
    assert 'No Audio Effect Rack on selected track' in variation_rig.h.messages


def test_changing_mode_closes_the_picker(variation_rig):
    variation_rig.press('chan')
    variation_rig.press('recall')
    assert variation_rig.mode == 'Volume'
    assert variation_rig.leds()[2] == BLUE
    variation_rig.press('chan')                                          # back to Rack: picker is closed
    assert variation_rig.leds()[2] == BLUE


def test_chan_from_another_mode_only_changes_mode(variation_rig):
    variation_rig.press('recall')
    variation_rig.press('chan')
    assert variation_rig.mode == 'Rack'
    assert not variation_rig.h.script._pads.picking_variation


def test_shift_pad_does_not_solo_in_the_picker(variation_rig):
    variation_rig.press('chan')
    variation_rig.shift_tap(2)
    assert not variation_rig.track(2).solo


def test_picker_follows_variations_stored_in_live(variation_rig):
    variation_rig.press('chan')
    variation_rig.track(1).devices[0].store_variation()
    variation_rig.advance(0.7)
    assert variation_rig.leds()[4] == RED


def test_page_picker_and_variation_picker_exclude_each_other(variation_rig):
    variation_rig.press('chan')
    variation_rig.press('ext sync')
    pads = variation_rig.h.script._pads
    assert pads.picking_page and not pads.picking_variation


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


# --- nullstilling med shift + encoder ----------------------------------------

def _shift_turn(rig, encoder, **kwargs):
    rig.button_down('shift')
    rig.turn(encoder, **kwargs)
    rig.button_up('shift')


def test_shift_encoder_resets_macro_to_default(rig):
    rig.turn(3, ticks=20, interval=0.02)
    assert _macro(rig.track(1), 3).value > 0
    _shift_turn(rig, 3)
    assert _macro(rig.track(1), 3).value == 0


def test_shift_encoder_resets_in_either_direction_and_stays_there(rig):
    rig.turn(3, ticks=20, interval=0.02)
    _shift_turn(rig, 3, value=127, ticks=5, interval=0.02)
    assert _macro(rig.track(1), 3).value == 0
    _shift_turn(rig, 3, value=1, ticks=5, interval=0.02)
    assert _macro(rig.track(1), 3).value == 0


def test_shift_encoder_leaves_other_macros_alone(rig):
    rig.turn(3, ticks=5)
    rig.turn(4, ticks=5)
    _shift_turn(rig, 3)
    assert _macro(rig.track(1), 4).value > 0


def test_shift_encoder_resets_volume_to_default_not_zero(rig):
    rig.press('recall')
    rig.turn(3, value=127, ticks=20, interval=0.02)
    assert rig.track(3).mixer_device.volume.value < 0.85
    _shift_turn(rig, 3)
    assert rig.track(3).mixer_device.volume.value == 0.85


def test_shift_encoder_resets_send(rig):
    rig.press('store')
    rig.turn(11, ticks=5)
    _shift_turn(rig, 11)
    assert rig.track(3).mixer_device.sends[1].value == 0


def test_shift_encoder_without_rack_still_shows_message(rig):
    rig.track(1).devices[:] = []
    _shift_turn(rig, 3)
    assert 'No Audio Effect Rack on selected track' in rig.h.messages


# --- transpose ---------------------------------------------------------------

def test_transpose_controls_selected_track_volume(rig):
    rig.tap(2)
    rig.turn('transpose')
    assert rig.track(2).mixer_device.volume.value > 0.85


def test_shift_transpose_resets_selected_track_volume(rig):
    rig.tap(2)
    rig.turn('transpose', value=127, ticks=10, interval=0.02)
    assert rig.track(2).mixer_device.volume.value < 0.85
    rig.button_down('shift')
    rig.turn('transpose')
    rig.button_up('shift')
    assert rig.track(2).mixer_device.volume.value == 0.85
    assert rig.song.master_track.mixer_device.volume.value == 0.85
    assert rig.track(1).mixer_device.volume.value == 0.85
