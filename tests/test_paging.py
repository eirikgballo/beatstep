"""Spor-sider og sidevelgeren på ext sync."""

from conftest import BLUE, OFF, RED
from fake_song import default_song


def test_picker_shows_pages(rig):
    rig.press('ext sync')
    leds = rig.leds()
    assert leds[1] == RED                    # current page
    assert leds[2] == BLUE                   # 20 tracks → page 2 exists
    assert all(leds[n] == OFF for n in range(3, 17))
    assert rig.button_leds()['ext sync'] != OFF


def test_picking_a_page_shows_its_tracks(rig):
    rig.press('ext sync')
    rig.tap(2)                                           # no clear(): pads that keep their color are not resent
    leds = rig.leds()
    assert all(leds[n] == BLUE for n in range(1, 5))     # tracks 17–20
    assert all(leds[n] == OFF for n in range(5, 17))     # tracks 21–32 don't exist
    assert rig.button_leds()['ext sync'] == OFF


def test_pads_on_page_2_select_tracks_17_and_up(rig):
    rig.press('ext sync')
    rig.tap(2)
    rig.tap(1)
    assert rig.selected is rig.track(17)


def test_picker_does_not_select_tracks(rig):
    rig.press('ext sync')
    rig.tap(2)
    assert rig.selected is rig.track(1)


def test_empty_page_is_refused_and_picker_stays_open(rig):
    rig.press('ext sync')
    rig.tap(3)
    assert 'Page 3 is empty' in rig.h.messages
    rig.tap(1)
    assert rig.h.script._pads.page == 0
    assert not rig.h.script._pads.picking_page


def test_ext_sync_again_closes_picker_without_changing_page(rig):
    rig.press('ext sync')
    rig.press('ext sync')
    assert not rig.h.script._pads.picking_page
    assert rig.h.script._pads.page == 0
    assert rig.leds()[1] == RED


def test_selected_track_on_other_page_shows_no_red(rig):
    rig.tap(3)
    rig.press('ext sync')
    rig.tap(2)
    assert RED not in rig.leds().values()


def test_page_stays_when_tracks_are_removed(make_rig):
    rig = make_rig(default_song(20))
    rig.press('ext sync')
    rig.tap(2)
    for _ in range(4):
        rig.song.delete_track(19 - _)
    assert rig.h.script._pads.page == 1
    assert all(color == OFF for color in rig.leds().values())
