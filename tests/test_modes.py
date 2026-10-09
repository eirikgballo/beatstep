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


@pytest.mark.parametrize('button, mode', [('recall', 'Volume'), ('store', 'Record'), ('chan', 'Rack')])
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


# --- Record ----------------------------------------------------------------

def test_record_mode_encoders_still_control_macros(rig):
    rig.press('store')
    rig.turn(3)
    assert _macro(rig.track(1), 3).value > 0


def test_record_mode_pads_show_actions(rig):
    rig.song.undo_steps = 1
    rig.press('store')
    leds = rig.leds()
    assert leds[1] == BLUE and leds[2] == BLUE and leds[3] == OFF
    assert all(leds[n] == BLUE for n in range(4, 9))
    assert leds[9] == MAGENTA and leds[10] == MAGENTA
    assert all(leds[n] == BLUE for n in range(11, 15))
    assert leds[15] == OFF and leds[16] == OFF


def test_record_pad_toggles_arrangement_record_without_starting_playback(rig):
    rig.press('store')
    rig.tap(1)
    assert rig.song.record_mode and not rig.song.is_playing
    rig.tap(1)
    assert not rig.song.record_mode
    assert rig.leds()[1] == BLUE


def test_record_pad_blinks_red_while_recording_is_on(rig):
    rig.press('store')
    rig.tap(1)
    seen = set()
    for _ in range(8):
        rig.advance(0.1)
        seen.add(rig.leds()[1])
    assert seen == {RED, OFF}


def test_record_mode_pad_does_not_select_track(rig):
    rig.press('store')
    rig.tap(15)
    assert rig.selected is rig.track(1)


def test_undo_and_redo_pads(rig):
    rig.song.undo_steps = 2
    rig.press('store')
    rig.tap(2)
    assert (rig.song.undo_steps, rig.song.redo_steps) == (1, 1)
    assert rig.leds()[3] == BLUE
    rig.tap(3)
    assert (rig.song.undo_steps, rig.song.redo_steps) == (2, 0)


def test_undo_with_nothing_to_undo_shows_message(rig):
    rig.press('store')
    rig.tap(2)
    assert 'Nothing to undo' in rig.h.messages
    rig.tap(3)
    assert 'Nothing to redo' in rig.h.messages


def test_metronome_pad_toggles_metronome(rig):
    rig.press('store')
    rig.tap(4)
    assert rig.song.metronome and rig.leds()[4] == RED
    rig.tap(4)
    assert not rig.song.metronome


def test_marker_pad_adds_a_marker_at_the_needle_and_removes_it_again(rig):
    rig.song.click_in_arrangement(12.0)
    rig.press('store')
    rig.tap(5)
    assert [cue.time for cue in rig.song.cue_points] == [12.0]
    assert rig.leds()[5] == RED
    rig.tap(5)
    assert rig.song.cue_points == ()
    assert rig.leds()[5] == BLUE


def test_loop_pad_toggles_loop(rig):
    rig.press('store')
    rig.tap(6)
    assert rig.song.loop and rig.leds()[6] == RED
    rig.tap(6)
    assert not rig.song.loop


def test_loop_start_pad_moves_the_start_and_keeps_the_end(rig):
    rig.song.loop_start, rig.song.loop_length = 8.0, 8.0
    rig.song.click_in_arrangement(12.0)
    rig.press('store')
    rig.tap(7)
    assert (rig.song.loop_start, rig.song.loop_length) == (12.0, 4.0)
    rig.song.click_in_arrangement(4.0)
    rig.tap(7)
    assert (rig.song.loop_start, rig.song.loop_length) == (4.0, 12.0)


def test_loop_start_pad_past_the_end_moves_the_whole_loop(rig):
    rig.song.loop_start, rig.song.loop_length = 8.0, 8.0
    rig.song.click_in_arrangement(20.0)
    rig.press('store')
    rig.tap(7)
    assert (rig.song.loop_start, rig.song.loop_length) == (20.0, 8.0)


def test_loop_end_pad_sets_the_end_at_the_needle(rig):
    rig.song.loop_start, rig.song.loop_length = 8.0, 8.0
    rig.song.click_in_arrangement(12.0)
    rig.press('store')
    rig.tap(8)
    assert (rig.song.loop_start, rig.song.loop_length) == (8.0, 4.0)


def test_loop_end_pad_before_the_loop_start_shows_message(rig):
    rig.song.loop_start, rig.song.loop_length = 8.0, 8.0
    rig.song.click_in_arrangement(4.0)
    rig.press('store')
    rig.tap(8)
    assert (rig.song.loop_start, rig.song.loop_length) == (8.0, 8.0)
    assert 'The loop end must be after the loop start' in rig.h.messages


def test_zoom_pads_zoom_the_arrangement_in_and_out(rig):
    rig.press('store')
    rig.tap(9)
    rig.tap(10)
    assert rig.h.c.application.view.zooms == [(3, 'Arranger'), (2, 'Arranger')]   # right = in, left = out


class _FakeSocket:

    def __init__(self):
        self.sent = []

    def sendto(self, data, address):
        self.sent.append((data, address))


def test_pan_pads_send_scroll_messages_to_the_helper(rig):
    helper = rig.h.script._scroll_socket = _FakeSocket()
    rig.press('store')
    for pad in (11, 12, 13, 14):
        rig.tap(pad)
    assert [data for data, _ in helper.sent] == [b'scroll -200 0', b'scroll 200 0', b'scroll 0 -200', b'scroll 0 200']
    assert helper.sent[0][1] == ('127.0.0.1', 9817)
    assert rig.h.c.application.view.zooms == []


def test_record_started_in_live_shows_on_the_pad(rig):
    rig.press('store')
    rig.clear()
    rig.song.record_mode = True
    seen = set()
    for _ in range(8):
        rig.advance(0.1)
        seen.add(rig.leds()[1])
    assert RED in seen


def test_shift_pad_selects_and_arms_track_in_record_mode(rig):
    rig.press('store')
    rig.shift_tap(5)
    assert rig.selected is rig.track(5)
    assert rig.track(5).arm and not rig.track(5).solo


def test_shift_held_in_record_mode_shows_the_tracks(rig):
    rig.press('store')
    rig.clear()
    rig.button_down('shift')
    leds = rig.leds()
    assert leds[1] == RED and leds[16] == BLUE
    rig.button_up('shift')
    assert rig.leds()[16] == OFF


def test_leaving_record_mode_gives_the_pads_back_to_the_tracks(rig):
    rig.press('store')
    rig.press('chan')
    rig.tap(5)
    assert rig.selected is rig.track(5)
    assert rig.leds()[5] == RED


def test_page_picker_works_in_record_mode(rig):
    rig.press('store')
    rig.press('ext sync')
    rig.tap(2)
    assert not rig.song.record_mode
    rig.shift_tap(1)
    assert rig.selected is rig.track(17)


# --- arming ved sporvalg -----------------------------------------------------

def test_selecting_a_track_in_rack_mode_arms_only_that_track(rig):
    rig.tap(3)
    rig.tap(5)
    assert [t.arm for t in rig.song.tracks].count(True) == 1 and rig.track(5).arm


def test_selecting_a_track_in_volume_mode_does_not_arm(rig):
    rig.press('recall')
    rig.tap(5)
    assert not rig.track(5).arm


def test_track_that_cannot_be_armed_is_selected_and_arming_left_alone(rig):
    rig.tap(3)
    rig.track(5).can_be_armed = False
    rig.tap(5)
    assert rig.selected is rig.track(5)
    assert rig.track(3).arm and not rig.track(5).arm


def test_track_selected_in_live_is_not_armed(rig):
    rig.song.view.selected_track = rig.track(6)
    assert not rig.track(6).arm


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
