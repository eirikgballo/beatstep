"""Oppstart, hardware-oppsett, MIDI-kart og disconnect."""

from conftest import BLUE, OFF, PAD_NOTES, RED, Rig
from harness import Harness
from fake_song import default_song


def _setup_messages(sent):
    return [m for m in sent if len(m) == 12 and m[8] != 0x10]


def test_setup_is_sent_after_2_1_seconds(clock):
    rig = Rig(Harness(default_song()), clock)
    rig.advance(2.0)
    assert _setup_messages(rig.sent) == []
    rig.advance(0.2)
    assert len(_setup_messages(rig.sent)) > 0


def test_setup_sets_pad_notes_explicitly(clock):
    rig = Rig(Harness(default_song()), clock)
    rig.advance(2.2)
    notes = {m[9] - 0x70: m[10] for m in _setup_messages(rig.sent) if m[8] == 0x03 and 0x70 <= m[9] <= 0x7F}
    assert notes == {i: note for i, note in enumerate(PAD_NOTES)}


def test_setup_configures_every_button_as_cc(clock):
    rig = Rig(Harness(default_song()), clock)
    rig.advance(2.2)
    ccs = {m[9]: m[10] for m in _setup_messages(rig.sent) if m[8] == 0x03 and 0x58 <= m[9] <= 0x5F}
    assert ccs == {0x58: 28, 0x59: 29, 0x5A: 30, 0x5B: 31, 0x5C: 5, 0x5D: 32, 0x5E: 7, 0x5F: 33}


def test_leds_are_painted_after_setup(clock):
    rig = Rig(Harness(default_song()), clock)
    rig.advance(2.2)
    leds = rig.leds()
    assert leds[1] == RED
    assert all(leds[n] == BLUE for n in range(2, 17))


def test_midi_map_only_forwards_channel_10(rig):
    assert all(channel == 9 for channel, _ in rig.h.midi_map.notes)
    assert all(channel == 9 for channel, _ in rig.h.midi_map.ccs)


def test_disconnect_turns_off_all_leds(rig):
    rig.h.disconnect()
    assert all(color == OFF for color in rig.leds().values())
    assert all(value == OFF for value in rig.button_leds().values())
