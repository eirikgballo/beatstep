"""Velge spor, solo og pad-lys."""

from conftest import BLUE, MAGENTA, OFF, RED
from fake_song import Song, Track


def _colors_over(rig, pad, seconds):
    """Alle farger sendt til en pad mens tiden går."""
    rig.clear()
    rig.advance(seconds)
    return {m[10] for m in rig.sent if len(m) == 12 and m[8] == 0x10 and m[9] == 0x70 + pad - 1}


def test_tap_selects_track_immediately(rig):
    rig.pad_down(3)
    assert rig.selected is rig.track(3)


def test_selected_pad_is_red_and_previous_blue(rig):
    rig.tap(3)
    leds = rig.leds()
    assert leds[3] == RED
    assert leds[1] == BLUE


def test_pad_color_is_resent_on_release(rig):
    # The firmware turns the pad off on release, so the script must send the color again.
    rig.pad_down(3)
    rig.clear()
    rig.pad_up(3)
    assert rig.leds()[3] == RED


def test_pad_16_is_a_regular_track(rig):
    rig.tap(16)
    assert rig.selected is rig.track(16)


def test_pad_without_track_does_nothing(make_rig):
    rig = make_rig(Song([Track('Spor %d' % i) for i in range(1, 4)]))
    rig.tap(10)
    assert rig.selected is rig.track(1)
    assert rig.leds()[10] == OFF


def test_sequencer_note_on_channel_1_is_not_forwarded(rig):
    assert rig.h.receive((0x90, 40, 64)) is False
    assert rig.selected is rig.track(1)


def test_script_ignores_channel_1_notes_even_if_they_arrive(rig):
    rig.h.script.receive_midi((0x90, 40, 64))
    assert rig.selected is rig.track(1)


def test_shift_pad_toggles_solo_without_selecting(rig):
    rig.tap(3)
    rig.shift_tap(8)
    assert rig.track(8).solo
    assert rig.selected is rig.track(3)
    rig.shift_tap(8)
    assert not rig.track(8).solo


def test_solo_is_additive(rig):
    rig.shift_tap(2)
    rig.shift_tap(5)
    assert rig.track(2).solo and rig.track(5).solo


def test_soloed_track_blinks_magenta_and_off(rig):
    rig.shift_tap(5)
    assert _colors_over(rig, 5, 1.0) == {MAGENTA, OFF}


def test_selected_and_soloed_track_blinks_red_and_magenta(rig):
    rig.shift_tap(1)
    assert _colors_over(rig, 1, 1.0) == {RED, MAGENTA}


def test_tracks_without_solo_do_not_blink(rig):
    rig.shift_tap(5)
    assert _colors_over(rig, 2, 1.0) == set()


def test_solo_changed_in_live_updates_leds(rig):
    rig.track(4).solo = True
    assert rig.leds()[4] in (MAGENTA, OFF)


def test_selection_changed_in_live_updates_leds(rig):
    rig.song.view.selected_track = rig.track(7)
    leds = rig.leds()
    assert leds[7] == RED
    assert leds[1] == BLUE
