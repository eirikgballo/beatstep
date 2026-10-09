"""
Kjører BeatStep uendret mot falsk Live.

Etterligner det Live gjør rundt scriptet:
  - bare MIDI som er registrert i build_midi_map når receive_midi (resten filtreres bort)
  - request_rebuild_midi_map er utsatt: kartet bygges på nytt etter neste hendelse/tick
  - update_display kalles hvert 100 ms og driver Task-køen
"""

import glob
import importlib.util
import os
import sys

_FAKE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(_FAKE_DIR))
PACKAGE = 'beatstep_q'
SCRIPT_FILES = sorted(glob.glob(os.path.join(REPO, '*.py')))

if _FAKE_DIR not in sys.path:
    sys.path.insert(0, _FAKE_DIR)

from fake_song import default_song  # noqa: E402


def load_script_package():
    """Last (eller last på nytt) repoet som pakke, slik Live laster remote scripts."""
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + '.')]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, os.path.join(REPO, '__init__.py'), submodule_search_locations=[REPO])
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


class MidiMapRecord:

    def __init__(self):
        self.notes = set()
        self.ccs = set()


class FakeApplicationView:
    """Hovedvinduet i Live: enten Session eller Arrangement ('Arranger') er framme."""

    def __init__(self):
        self.visible = 'Arranger'
        self.zooms = []  # (retning, visning) for hvert zoom_view-kall

    def is_view_visible(self, name):
        return name == self.visible

    def show_view(self, name):
        if name not in ('Session', 'Arranger'):
            raise RuntimeError('Unknown view %r' % name)
        self.visible = name

    def zoom_view(self, direction, view_name, modifier_pressed):
        self.zooms.append((direction, view_name))


class FakeApplication:

    def __init__(self):
        self.view = FakeApplicationView()


class FakeCInstance:

    def __init__(self, song, send_midi, show_message, log_message):
        self._song = song
        self.application = FakeApplication()
        self.send_midi = send_midi
        self.show_message = show_message
        self.log_message = log_message
        self.rebuild_requested = False

    def song(self):
        return self._song

    def request_rebuild_midi_map(self):
        self.rebuild_requested = True

    def handle(self):
        return self


class Harness:

    def __init__(self, song=None, send_midi=None, show_message=None, log_message=None):
        self.song = song or default_song()
        self.sent = []
        self.messages = []
        self.logs = []
        self._send = send_midi
        self._show = show_message
        self._log = log_message
        self.c = FakeCInstance(self.song, self._on_send, self._on_show, self._on_log)
        self.script = load_script_package().create_instance(self.c)
        self.midi_map = MidiMapRecord()
        self._flush_rebuild()

    def _on_send(self, midi_bytes):
        self.sent.append(tuple(midi_bytes))
        if self._send:
            self._send(midi_bytes)

    def _on_show(self, message):
        self.messages.append(message)
        if self._show:
            self._show(message)

    def _on_log(self, message):
        self.logs.append(message)
        if self._log:
            self._log(message)

    def _flush_rebuild(self):
        if self.c.rebuild_requested:
            self.c.rebuild_requested = False
            self.midi_map = MidiMapRecord()
            self.script.build_midi_map(self.midi_map)

    def is_forwarded(self, midi_bytes):
        status = midi_bytes[0]
        if status == 0xF0:
            return True
        kind, channel = status & 0xF0, status & 0x0F
        if kind in (0x80, 0x90):
            return (channel, midi_bytes[1]) in self.midi_map.notes
        if kind == 0xB0:
            return (channel, midi_bytes[1]) in self.midi_map.ccs
        return False

    def receive(self, midi_bytes):
        """Lever innkommende MIDI som Live ville gjort. Returnerer om den nådde scriptet."""
        if not self.is_forwarded(midi_bytes):
            return False
        self.script.receive_midi(tuple(midi_bytes))
        self._flush_rebuild()
        return True

    def tick(self):
        self.script.update_display()
        self._flush_rebuild()

    def advance(self, seconds):
        for _ in range(int(round(seconds / 0.1))):
            self.tick()

    def disconnect(self):
        self.script.disconnect()
