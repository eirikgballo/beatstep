"""Utgående MIDI-kø: BeatStepen mister sysex som kommer for tett, så scriptet sender med pause og maks N per tick."""

import sys

from conftest import PAD_NOTES, RED, Rig
from harness import Harness, load_script_package
from fake_song import default_song

load_script_package()
PER_TICK = sys.modules['beatstep_q.BeatStep'].MIDI_MESSAGES_PER_TICK


def _sent_per_tick(h, clock, seconds):
    """Antall meldinger Live fikk per update_display-tick, uten å tømme køen."""
    counts = []
    for _ in range(int(round(seconds / 0.1))):
        before = len(h.sent)
        clock.now += 0.1
        h.tick()
        counts.append(len(h.sent) - before)
    return counts


def test_never_more_than_limit_per_tick_during_setup(clock):
    h = Harness(default_song())
    counts = _sent_per_tick(h, clock, 8.0)
    assert max(counts) <= PER_TICK
    assert sum(counts) > 150                       # setup and LEDs did go out


def test_whole_setup_arrives_within_a_few_seconds(clock):
    h = Harness(default_song())
    _sent_per_tick(h, clock, 2.1 + 6.0)
    assert not h.script._midi_queue
    notes = {m[9] - 0x70: m[10] for m in h.sent if m[8] == 0x03 and 0x70 <= m[9] <= 0x7F}
    assert notes == {i: note for i, note in enumerate(PAD_NOTES)}


def test_setup_is_sent_before_leds(clock):
    h = Harness(default_song())
    _sent_per_tick(h, clock, 8.0)
    kinds = ['led' if m[8] == 0x10 else 'setup' for m in h.sent]
    assert 'setup' not in kinds[kinds.index('led'):]


def test_newer_value_for_same_led_replaces_queued_one(make_rig):
    rig = make_rig()
    q = rig.h.script._midi_queue
    rig.h.script._queue_midi((0xF0, 0, 0x20, 0x6B, 0x7F, 0x42, 2, 0, 0x10, 0x70, 16, 0xF7))
    rig.h.script._queue_midi((0xF0, 0, 0x20, 0x6B, 0x7F, 0x42, 2, 0, 0x10, 0x70, 1, 0xF7))
    assert len(q) == 1
    assert list(q.values())[0][10] == RED


def test_tap_feedback_goes_out_on_next_tick(make_rig):
    rig = make_rig()
    rig.tap(3)
    before = len(rig.h.sent)
    rig.clock.now += 0.1
    rig.h.tick()
    assert len(rig.h.sent) > before


def test_released_pad_gets_its_color_without_waiting_for_a_tick(make_rig):
    rig = make_rig()
    rig.pad_down(3)                                 # selecting the track queues a repaint of all 16 pads
    before = len(rig.h.sent)
    rig.h.receive((0x89, PAD_NOTES[2], 0))
    assert [m[8:11] for m in rig.h.sent[before:]] == [(0x10, 0x72, RED)]


def test_disconnect_sends_everything_immediately(clock):
    rig = Rig(Harness(default_song()), clock)
    rig.advance(2.2)                                # setup queued, most of it not yet sent
    rig.h.disconnect()
    assert not rig.h.script._midi_queue


def test_sequencer_warning_blink_keeps_up_with_the_rate_limit(make_rig):
    rig = make_rig()
    rig.press('cntrl')
    start = len(rig.h.sent)
    for _ in range(30):                          # 3 s of real ticks, queue not drained by the test
        rig.clock.now += 0.1
        rig.h.tick()
    for pad in range(16):
        colors = {m[10] for m in rig.h.sent[start:] if m[8] == 0x10 and m[9] == 0x70 + pad}
        assert colors == {0, RED}, 'pad %d' % (pad + 1)
