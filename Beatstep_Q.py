"""
Beatstep_Q — MIDI Remote Script for the Arturia BeatStep.

Boots directly into Mix Mode (CMix).  Hardware is configured via sysex on
every connection so controller state is always deterministic.

See DESIGN.md for the full specification.
"""

import Live

from _Framework.ControlSurface import ControlSurface
from _Framework import Task

from . import QSetup
from .CMix import CMix

# ---------------------------------------------------------------------------
# MIDI constants
# ---------------------------------------------------------------------------

# Pads send Note On — channel depends on hardware config; accept any channel.
_NOTE_ON_MASK = 0x90

# Function buttons send CC.
# After sysex setup, all are on CH10. Before sysex (factory state), function
# buttons may be on CH1, so we handle both.
_STATUS_CC_CH10 = 0xB9  # 0xB0 | 9
_STATUS_CC_CH1  = 0xB0

# Function button CC numbers (confirmed from raphaelquast reference).
BTN_SHIFT_CC  = 7
BTN_RECALL_CC = 5

# Encoder CC numbers (programmed via sysex on every connection).
# Encoders 0–15 → CC 10–25; transpose encoder → CC 26.
ENCODER_CC_BASE  = 10
TRANSPOSE_CC     = 26

# Note numbers programmed into the hardware via sysex (note gate mode).
# Physical layout (column-major in hardware): indices 0-3 = column 1, etc.
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
        self.log_message('BeatStep_Q: __init__ start')
        self._cmix = None
        self._hw_task = None
        self._midi_log_count = 0  # limit noisy MIDI logging
        try:
            self._cmix = CMix(
                song                     = self.song(),
                show_message             = self.show_message,
                request_rebuild_midi_map = self.request_rebuild_midi_map,
            )
            self.log_message('BeatStep_Q: CMix created OK')
        except Exception as e:
            self.log_message('BeatStep_Q: ERROR creating CMix: %s' % str(e))
        self._schedule_hardware_setup()
        self.request_rebuild_midi_map()
        self.log_message('BeatStep_Q: __init__ done')

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def port_settings_changed(self):
        self.log_message('BeatStep_Q: port_settings_changed')
        ControlSurface.port_settings_changed(self)
        self._schedule_hardware_setup()

    def disconnect(self):
        self.log_message('BeatStep_Q: disconnect')
        if self._cmix:
            self._cmix.cleanup()
        ControlSurface.disconnect(self)

    def build_midi_map(self, midi_map_handle):
        """Register MIDI addresses so receive_midi is called for them."""
        self.log_message('BeatStep_Q: build_midi_map called')
        ControlSurface.build_midi_map(self, midi_map_handle)
        try:
            h = self._c_instance.handle()
            for note in PAD_MSG_IDS:
                Live.MidiMap.forward_midi_note(h, midi_map_handle, 0, note)  # CH1
                Live.MidiMap.forward_midi_note(h, midi_map_handle, 9, note)  # CH10
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, BTN_SHIFT_CC)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, BTN_RECALL_CC)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 0, BTN_SHIFT_CC)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 0, BTN_RECALL_CC)
            for i in range(16):
                Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, ENCODER_CC_BASE + i)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, TRANSPOSE_CC)
            self.log_message('BeatStep_Q: MIDI map built OK')
        except Exception as e:
            self.log_message('BeatStep_Q: build_midi_map ERROR: %s' % str(e))

    # ------------------------------------------------------------------
    # Hardware setup
    # ------------------------------------------------------------------

    def _schedule_hardware_setup(self):
        self.log_message('BeatStep_Q: scheduling hardware setup')
        if self._hw_task is not None:
            self._hw_task.kill()
        steps = [Task.wait(2.1), Task.run(self._send_setup_sysex)]
        self._hw_task = self._task_group.add(Task.sequence(*steps))

    def _send_setup_sysex(self):
        self.log_message('BeatStep_Q: _send_setup_sysex running')
        try:
            # Pads: mode=9 (note gate), channel=CH10, behaviour=gate.
            # Note numbers are NOT re-configured — factory defaults match PAD_MSG_IDS.
            for i in range(16):
                for msg in QSetup.setup_pad(i):
                    self._send_midi(msg)

            self.log_message('BeatStep_Q: pad sysex sent (%d pads, 3 msgs each)' % 16)

            for msg in QSetup.setup_button(QSetup.RECALL_HW_INDEX):
                self._send_midi(msg)

            for msg in QSetup.setup_button(QSetup.SHIFT_HW_INDEX):
                self._send_midi(msg)

            # Encoders: relative mode 1, CH10, CC 10–25.
            for i in range(16):
                for msg in QSetup.setup_encoder(i, ENCODER_CC_BASE + i):
                    self._send_midi(msg)

            # Transpose encoder: relative mode 1, CH10, CC 26.
            for msg in QSetup.setup_transpose_encoder(TRANSPOSE_CC):
                self._send_midi(msg)

            self.log_message('BeatStep_Q: all sysex sent OK')
            self.request_rebuild_midi_map()
        except Exception as e:
            self.log_message('BeatStep_Q: ERROR in _send_setup_sysex: %s' % str(e))

    # ------------------------------------------------------------------
    # MIDI receive
    # ------------------------------------------------------------------

    def receive_midi(self, midi_bytes):
        # Log ALL incoming calls to confirm receive_midi is being invoked
        if self._midi_log_count < 30:
            self.log_message('BeatStep_Q: receive_midi len=%d bytes=%s' % (len(midi_bytes), list(midi_bytes[:4])))
            self._midi_log_count += 1

        if len(midi_bytes) < 3:
            return
        status = midi_bytes[0]
        data1  = midi_bytes[1]
        data2  = midi_bytes[2]

        if (status & 0xF0) == _NOTE_ON_MASK:
            self._handle_pad_note(data1, data2)
        elif status == _STATUS_CC_CH10:
            self._handle_cc(data1, data2)
        elif status == _STATUS_CC_CH1:
            # Handle function buttons before sysex configures them to CH10
            self._handle_function_button(data1, data2)

    def _handle_pad_note(self, note, velocity):
        """Handle Note On CH10 — pad presses in note gate mode."""
        if note in _PAD_NOTE_TO_INDEX and velocity > 0:
            idx = _PAD_NOTE_TO_INDEX[note]
            self.log_message('BeatStep_Q: pad press index=%d note=%d' % (idx, note))
            self._cmix.on_pad_press(idx)

    def _handle_cc(self, cc, value):
        """Handle CC CH10 — encoders and function buttons."""
        if ENCODER_CC_BASE <= cc < ENCODER_CC_BASE + 16:
            self._cmix.on_encoder(cc - ENCODER_CC_BASE, value)
        elif cc == TRANSPOSE_CC:
            self._cmix.on_transpose_encoder(value)
        else:
            self._handle_function_button(cc, value)

    def _handle_function_button(self, cc, value):
        """Handle SHIFT and RECALL on any channel."""
        is_press = value > 0
        if cc == BTN_SHIFT_CC:
            if is_press:
                self._cmix.on_shift_press()
            else:
                self._cmix.on_shift_release()
        elif cc == BTN_RECALL_CC and is_press:
            self._cmix.on_recall_press()
            self._schedule_hardware_setup()  # re-configure after BeatStep firmware preset recall

