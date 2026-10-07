"""Ny maling etter knappeslipp og varsel for sequencer-modus."""

import pytest

from conftest import BLUE, OFF, RED


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
