"""
Beatstep_Q — MIDI Remote Script for the Arturia BeatStep.

Boots directly into Mix Mode (CMix).  Hardware is configured via sysex on
every connection so controller state is always deterministic.

See DESIGN.md for the full specification and SIGNALS.md for measured hardware behaviour.
"""

import Live

from _Framework.ControlSurface import ControlSurface
from _Framework import Task

from . import QSetup
from .CMix import CMix

# ---------------------------------------------------------------------------
# MIDI constants
# ---------------------------------------------------------------------------

# Everything the script uses is on CH10 after setup. The BeatStep sequencer
# sends notes on CH1, which must never reach the pad handler.
_CHANNEL         = 9
_STATUS_NOTE_ON  = 0x90 | _CHANNEL
_STATUS_NOTE_OFF = 0x80 | _CHANNEL
_STATUS_CC       = 0xB0 | _CHANNEL

# Function button CC numbers (programmed via sysex on every connection).
BTN_SHIFT_CC  = 7
BTN_RECALL_CC = 5

# Encoder CC numbers (programmed via sysex on every connection).
# Encoders 0–15 → CC 10–25; transpose encoder → CC 27.
ENCODER_CC_BASE  = 10
TRANSPOSE_CC     = 27

# Note numbers programmed into the hardware via sysex (note gate mode).
# Row-major: index 0–7 = top row, 8–15 = bottom row, left to right.
PAD_MSG_IDS = [
    44, 45, 46, 47, 48, 49, 50, 51,   # hw 0x70–0x77
    36, 37, 38, 39, 40, 41, 42, 43,   # hw 0x78–0x7F
]

# Reverse-lookup map built once at import time for O(1) dispatch.
_PAD_NOTE_TO_INDEX = {note: i for i, note in enumerate(PAD_MSG_IDS)}


# ---------------------------------------------------------------------------
# ControlSurface
# ---------------------------------------------------------------------------

class Beatstep_Q(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._hw_task = None
        # No try/except: if CMix fails, Live should show the error instead of a silent, dead controller.
        self._cmix = CMix(
            song         = self.song(),
            show_message = self.show_message,
            send_midi    = self._send_midi,
        )
        self._schedule_hardware_setup()
        self.request_rebuild_midi_map()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def port_settings_changed(self):
        ControlSurface.port_settings_changed(self)
        self._schedule_hardware_setup()

    def disconnect(self):
        self._cmix.cleanup()
        ControlSurface.disconnect(self)

    def update_display(self):
        ControlSurface.update_display(self)
        self._cmix.tick()

    def build_midi_map(self, midi_map_handle):
        """Register MIDI addresses so receive_midi is called for them."""
        ControlSurface.build_midi_map(self, midi_map_handle)
        h = self._c_instance.handle()
        for note in PAD_MSG_IDS:
            Live.MidiMap.forward_midi_note(h, midi_map_handle, _CHANNEL, note)
        for cc in [BTN_SHIFT_CC, BTN_RECALL_CC, TRANSPOSE_CC] + [ENCODER_CC_BASE + i for i in range(16)]:
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, _CHANNEL, cc)

    # ------------------------------------------------------------------
    # Hardware setup
    # ------------------------------------------------------------------

    def _schedule_hardware_setup(self):
        if self._hw_task is not None:
            self._hw_task.kill()
        steps = [Task.wait(2.1), Task.run(self._send_setup_sysex)]
        self._hw_task = self._task_group.add(Task.sequence(*steps))

    def _send_setup_sysex(self):
        # Note and CC numbers are set explicitly so a different preset in the BeatStep can't break the mapping.
        messages = []
        for i, note in enumerate(PAD_MSG_IDS):
            messages += QSetup.setup_pad(i, note)
        messages += QSetup.setup_button(QSetup.RECALL_HW_INDEX, BTN_RECALL_CC)
        messages += QSetup.setup_button(QSetup.SHIFT_HW_INDEX, BTN_SHIFT_CC)
        for i in range(16):
            messages += QSetup.setup_encoder(i, ENCODER_CC_BASE + i)
        messages += QSetup.setup_transpose_encoder(TRANSPOSE_CC)

        for msg in messages:
            self._send_midi(msg)
        self.log_message('BeatStep_Q: %d setup sysex sent' % len(messages))
        self._cmix.update_leds()

    # ------------------------------------------------------------------
    # MIDI receive
    # ------------------------------------------------------------------

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) < 3:
            return
        status, data1, data2 = midi_bytes[0], midi_bytes[1], midi_bytes[2]

        if status == _STATUS_NOTE_ON:
            self._handle_pad_note(data1, data2)
        elif status == _STATUS_NOTE_OFF:
            self._handle_pad_note(data1, 0)
        elif status == _STATUS_CC:
            self._handle_cc(data1, data2)

    def _handle_pad_note(self, note, velocity):
        """Pad presses and releases in note gate mode."""
        if note not in _PAD_NOTE_TO_INDEX:
            return
        idx = _PAD_NOTE_TO_INDEX[note]
        if velocity > 0:
            self._cmix.on_pad_press(idx)
        else:
            self._cmix.on_pad_release(idx)

    def _handle_cc(self, cc, value):
        """Encoders and function buttons."""
        if ENCODER_CC_BASE <= cc < ENCODER_CC_BASE + 16:
            self._cmix.on_encoder(cc - ENCODER_CC_BASE, value)
        elif cc == TRANSPOSE_CC:
            self._cmix.on_transpose_encoder(value)
        elif cc == BTN_SHIFT_CC:
            if value > 0:
                self._cmix.on_shift_press()
            else:
                self._cmix.on_shift_release()
        elif cc == BTN_RECALL_CC and value > 0:
            self._cmix.on_recall_press()
