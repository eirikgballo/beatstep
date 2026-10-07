"""
Felles rigg for testene: BeatStep-scriptet kjører uendret mot falsk Live med falsk klokke.

Testene sjekker oppførselen beskrevet i DESIGN.md ved å se på MIDI scriptet sender og tilstanden i falsk Live.
"""

import os
import sys
import time

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, 'tools', 'fakelive'))

from harness import Harness  # noqa: E402
from fake_song import default_song  # noqa: E402

RED, BLUE, MAGENTA, OFF = 1, 16, 17, 0

BUTTON_CC = {'shift': 7, 'recall': 5, 'play': 28, 'stop': 29, 'cntrl': 30,
             'ext sync': 31, 'store': 32, 'chan': 33}
BUTTON_HW = {'play': 0x58, 'stop': 0x59, 'cntrl': 0x5A, 'ext sync': 0x5B,
             'recall': 0x5C, 'store': 0x5D, 'shift': 0x5E, 'chan': 0x5F}
PAD_NOTES = [44, 45, 46, 47, 48, 49, 50, 51, 36, 37, 38, 39, 40, 41, 42, 43]


class Clock:

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Rig:
    """Styrer BeatStepen som en bruker ville gjort, og leser av hva scriptet sendte."""

    def __init__(self, harness, clock):
        self.h = harness
        self.clock = clock
        self.song = harness.song

    # --- tid -------------------------------------------------------------

    def advance(self, seconds):
        """La tiden gå, med update_display hvert 100 ms som i Live."""
        end = self.clock.now + seconds
        while self.clock.now + 0.1 <= end + 1e-9:
            self.clock.now += 0.1
            self.h.tick()
        self.clock.now = end

    # --- input -----------------------------------------------------------

    def pad_down(self, n):
        return self.h.receive((0x99, PAD_NOTES[n - 1], 127))

    def pad_up(self, n):
        return self.h.receive((0x89, PAD_NOTES[n - 1], 0))

    def tap(self, n):
        self.pad_down(n)
        self.advance(0.05)
        self.pad_up(n)

    def button_down(self, name):
        self.h.receive((0xB9, BUTTON_CC[name], 127))

    def button_up(self, name):
        self.h.receive((0xB9, BUTTON_CC[name], 0))

    def press(self, name):
        self.button_down(name)
        self.advance(0.1)
        self.button_up(name)

    def shift_tap(self, n):
        self.button_down('shift')
        self.tap(n)
        self.button_up('shift')

    def turn(self, encoder, value=1, ticks=1, interval=0.5):
        """Vri encoder 1–16 (eller 'transpose') `ticks` hakk med `interval` sekunder mellom."""
        cc = 27 if encoder == 'transpose' else 9 + encoder
        for _ in range(ticks):
            self.advance(interval)
            self.h.receive((0xB9, cc, value))

    # --- output ----------------------------------------------------------

    def clear(self):
        del self.h.sent[:]
        del self.h.messages[:]

    def leds(self):
        """Siste farge sendt til hver pad 1–16 (None hvis ingen er sendt siden clear())."""
        colors = {n: None for n in range(1, 17)}
        for m in self.h.sent:
            if len(m) == 12 and m[8] == 0x10 and 0x70 <= m[9] <= 0x7F:
                colors[m[9] - 0x70 + 1] = m[10]
        return colors

    def button_leds(self):
        """Siste verdi sendt til hvert knappelys, etter navn."""
        names = {hw: name for name, hw in BUTTON_HW.items()}
        state = {}
        for m in self.h.sent:
            if len(m) == 12 and m[8] == 0x10 and m[9] in names:
                state[names[m[9]]] = m[10]
        return state

    def track(self, n):
        return self.song.tracks[n - 1]

    @property
    def selected(self):
        return self.song.view.selected_track

    @property
    def mode(self):
        return self.h.script._mode.name


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(time, 'monotonic', c)
    return c


@pytest.fixture
def make_rig(clock):
    """Lag en rigg med valgfri sang. Oppsettet er sendt og listene tømt før testen starter."""
    def _make(song=None):
        rig = Rig(Harness(song or default_song()), clock)
        rig.advance(2.2)
        rig.clear()
        return rig
    return _make


@pytest.fixture
def rig(make_rig):
    return make_rig()
