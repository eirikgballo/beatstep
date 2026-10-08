"""Ny maling etter knappeslipp og varsel for sequencer-modus."""

import pytest

from conftest import BLUE, MAGENTA, OFF, RED


@pytest.mark.parametrize('button', ['shift', 'recall', 'play', 'stop', 'cntrl', 'ext sync', 'store', 'chan'])
def test_button_release_repaints_all_pads(rig, button):
    # The firmware shows its own overlay while a button is held and restores its own colors on release.
    rig.button_down(button)
    rig.clear()
    rig.button_up(button)
    assert all(color is not None for color in rig.leds().values())


def test_firmware_lit_buttons_are_turned_off(rig):
    rig.press('play')
    leds = rig.button_leds()
    for name in ('play', 'shift', 'ext sync', 'cntrl'):
        assert leds[name] == OFF
    assert 'stop' not in leds          # stop has no LED


# --- bytt visning med shift + ext sync --------------------------------------

def test_shift_ext_sync_toggles_between_session_and_arrangement(rig):
    view = rig.h.c.application.view
    rig.button_down('shift')
    rig.press('ext sync')
    assert view.visible == 'Session'
    rig.press('ext sync')
    assert view.visible == 'Arranger'
    rig.button_up('shift')


def test_shift_ext_sync_does_not_open_the_page_picker(rig):
    rig.button_down('shift')
    rig.press('ext sync')
    rig.button_up('shift')
    assert not rig.h.script._pads.picking_page
    assert rig.button_leds()['ext sync'] == OFF


def test_ext_sync_alone_does_not_change_the_view(rig):
    rig.press('ext sync')
    assert rig.h.c.application.view.visible == 'Arranger'


# --- spill fra markør med stop + pad ---------------------------------------

@pytest.fixture
def marker_rig(rig):
    rig.song.add_marker('Refreng', 32.0)        # lagt til i en annen rekkefølge enn de står i låta
    rig.song.add_marker('Intro', 0.0)
    rig.song.add_marker('Vers', 16.0)
    return rig


def _stop_tap(rig, pad):
    rig.button_down('stop')
    rig.tap(pad)
    rig.button_up('stop')


def test_stop_pad_plays_from_marker_counted_from_song_start(marker_rig):
    _stop_tap(marker_rig, 2)
    assert marker_rig.song.current_song_time == 16.0
    assert marker_rig.song.is_playing


def test_stop_pad_does_not_select_or_solo_the_track(marker_rig):
    _stop_tap(marker_rig, 3)
    assert marker_rig.selected is marker_rig.track(1)
    assert not marker_rig.track(3).solo


def test_stop_pad_wins_over_shift(marker_rig):
    marker_rig.button_down('shift')
    _stop_tap(marker_rig, 3)
    marker_rig.button_up('shift')
    assert marker_rig.song.current_song_time == 32.0
    assert not marker_rig.track(3).solo


def test_stop_pad_without_marker_shows_message(marker_rig):
    _stop_tap(marker_rig, 4)
    assert 'No marker 4' in marker_rig.h.messages
    assert not marker_rig.song.is_playing


def test_pads_show_markers_and_loop_start_while_stop_is_held(marker_rig):
    marker_rig.button_down('stop')
    leds = marker_rig.leds()
    assert [leds[n] for n in (1, 2, 3)] == [BLUE] * 3
    assert all(leds[n] == OFF for n in range(4, 16))
    assert leds[16] == MAGENTA
    marker_rig.button_up('stop')
    assert marker_rig.leds()[1] == RED          # back to the tracks


def test_stop_press_repaints_every_pad(marker_rig):
    # The firmware turns the pads off when stop is pressed.
    marker_rig.clear()
    marker_rig.button_down('stop')
    assert None not in marker_rig.leds().values()


def test_stop_pad_16_plays_from_loop_start(marker_rig):
    marker_rig.song.loop_start = 24.0
    _stop_tap(marker_rig, 16)
    assert marker_rig.song.current_song_time == 24.0
    assert marker_rig.song.is_playing


def test_stop_pad_16_plays_from_loop_start_after_a_stop_elsewhere(marker_rig):
    song = marker_rig.song
    song.loop_start = 24.0
    song.click_in_arrangement(8.0)
    song.start_playing()
    song.current_song_time = 40.0                              # played on to 40
    marker_rig.press('stop')
    _stop_tap(marker_rig, 16)
    assert song.is_playing and song.current_song_time == 24.0


def test_scrubbing_backwards_right_after_stop_near_the_song_start(marker_rig):
    song = marker_rig.song
    song.start_playing()                                       # started at 0
    song.current_song_time = 6.0
    marker_rig.press('stop')
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=127, ticks=2)
    marker_rig.button_up('stop')
    assert song.current_song_time == 5.5
    marker_rig.press('stop')
    assert song.is_playing and song.current_song_time == 5.5


def test_stop_alone_stops_playback_on_release(marker_rig):
    marker_rig.song.is_playing = True
    marker_rig.button_down('stop')
    assert marker_rig.song.is_playing
    marker_rig.button_up('stop')
    assert not marker_rig.song.is_playing


def test_stop_alone_starts_playback_from_the_playhead_when_stopped(marker_rig):
    marker_rig.song.current_song_time = 12.0
    marker_rig.press('stop')
    assert marker_rig.song.is_playing
    assert marker_rig.song.current_song_time == 12.0


def test_play_after_scrubbing_while_stopped_starts_from_the_new_position(marker_rig):
    song = marker_rig.song
    song.current_song_time = 16.0
    song.is_playing = True
    marker_rig.press('stop')                                   # stopped at 16
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=1, ticks=4)             # scrub one beat forward
    marker_rig.button_up('stop')
    assert not song.is_playing
    marker_rig.press('stop')
    assert song.is_playing and song.current_song_time == 17.0


def test_scrubbing_after_stop_starts_from_where_it_stopped(marker_rig):
    # Seen in Live: play from A, scrub to B while playing, stop. Scrubbing then jumped back to A first.
    song = marker_rig.song
    song.click_in_arrangement(8.0)                             # A
    song.start_playing()
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=1, ticks=4)             # to B = 9 while playing
    marker_rig.button_up('stop')
    marker_rig.press('stop')                                   # stop at B
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=1, ticks=1)
    marker_rig.button_up('stop')
    assert song.current_song_time == 9.25
    marker_rig.press('stop')
    assert song.is_playing and song.current_song_time == 9.25


def test_play_without_scrubbing_continues_where_it_stopped(marker_rig):
    song = marker_rig.song
    song.current_song_time = 16.0
    song.is_playing = True
    marker_rig.press('stop')
    marker_rig.press('stop')
    assert song.is_playing and song.current_song_time == 16.0


def test_scrub_is_forgotten_when_playback_was_started_from_live(marker_rig):
    song = marker_rig.song
    song.current_song_time = 16.0
    song.is_playing = True
    marker_rig.press('stop')
    marker_rig.button_down('stop')
    marker_rig.turn('transpose')
    marker_rig.button_up('stop')
    song.start_playing()                                       # space bar in Live
    marker_rig.advance(0.2)
    assert marker_rig.h.script._stopped_target is None


def test_several_scrub_detents_before_live_catches_up_all_count(marker_rig, monkeypatch):
    # Live carries out a move after the script returns, so the time read back in between is the old one.
    song = marker_rig.song
    song.current_song_time = 16.0
    setter = type(song).current_song_time.fset
    moves = []
    monkeypatch.setattr(type(song), 'current_song_time',
                        property(lambda self: 16.0, lambda self, time: moves.append(time)))
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=1, ticks=4)
    marker_rig.button_up('stop')
    assert moves == [16.25, 16.5, 16.75, 17.0]


def test_playback_that_starts_in_the_wrong_place_is_moved(marker_rig):
    # Seen in Live: after scrubbing, playback started at the green start marker instead.
    song = marker_rig.song
    song.current_song_time = 16.0
    song.is_playing = True
    marker_rig.press('stop')
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=1, ticks=4)             # to 17
    marker_rig.button_up('stop')
    song.start_playing = lambda: (setattr(song, '_time', 3.0), setattr(song, 'is_playing', True))
    marker_rig.press('stop')
    assert song.current_song_time == 3.0                       # Live went somewhere else
    marker_rig.advance(0.1)
    assert song.current_song_time == pytest.approx(17.0 + 0.1 * 120 / 60)


def test_scrubbing_while_stopped_does_not_start_playback(marker_rig):
    marker_rig.button_down('stop')
    marker_rig.turn('transpose')
    marker_rig.button_up('stop')
    assert not marker_rig.song.is_playing


def test_stop_release_after_a_pad_keeps_playing(marker_rig):
    _stop_tap(marker_rig, 1)
    assert marker_rig.song.is_playing


def test_stop_transpose_scrubs_the_timeline_and_not_the_volume(marker_rig):
    marker_rig.song.current_song_time = 16.0
    marker_rig.song.is_playing = True
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=1, ticks=2)
    assert marker_rig.song.current_song_time == 16.5          # slow detents: a quarter of a beat each
    marker_rig.turn('transpose', value=127, ticks=1)
    assert marker_rig.song.current_song_time == 16.25
    marker_rig.button_up('stop')
    assert marker_rig.song.is_playing                          # scrubbing is not a stop
    assert marker_rig.track(1).mixer_device.volume.value == 0.85


def test_scrub_stops_at_the_start_of_the_song(marker_rig):
    marker_rig.song.current_song_time = 0.3
    marker_rig.button_down('stop')
    marker_rig.turn('transpose', value=127, ticks=3)
    assert marker_rig.song.current_song_time == 0.0


# --- sequencer-modus -------------------------------------------------------

def test_cntrl_enters_sequencer_mode_with_warning(rig):
    rig.press('cntrl')
    assert 'BeatStep in sequencer mode, press cntrl/seq to return' in rig.h.messages
    assert rig.button_leds()['cntrl'] == RED


def test_all_pads_blink_red_in_sequencer_mode(rig):
    rig.press('cntrl')
    rig.clear()
    rig.advance(2.0)
    for pad in range(1, 17):
        colors = {m[10] for m in rig.sent if len(m) == 12 and m[8] == 0x10 and m[9] == 0x70 + pad - 1}
        assert colors == {RED, OFF}


def test_live_changes_do_not_paint_tracks_in_sequencer_mode(rig):
    rig.press('cntrl')
    rig.clear()
    rig.song.view.selected_track = rig.track(5)
    assert BLUE not in rig.leds().values()


def test_cntrl_again_restores_track_colors(rig):
    rig.press('cntrl')
    rig.press('cntrl')
    leds = rig.leds()
    assert leds[1] == RED
    assert all(leds[n] == BLUE for n in range(2, 17))
    assert rig.button_leds()['cntrl'] == OFF
