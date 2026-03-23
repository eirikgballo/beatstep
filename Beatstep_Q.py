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

# Pads send Note On/Off on CH10 (note gate mode).
_STATUS_NOTE_ON_CH10  = 0x99   # 0x90 | 9

# Encoders, transpose encoder, and function buttons send CC.
# After sysex setup, all are on CH10. Before sysex (factory state), function
# buttons may be on CH1, so we handle both.
_STATUS_CC_CH10 = 0xB9  # 0xB0 | 9
_STATUS_CC_CH1  = 0xB0

# Function button CC numbers (confirmed from raphaelquast reference).
BTN_SHIFT_CC  = 7
BTN_RECALL_CC = 5

# Note numbers programmed into the hardware via sysex (note gate mode).
# Physical layout (column-major in hardware): indices 0-3 = column 1, etc.
PAD_MSG_IDS = [
    44, 45, 46, 47, 48, 49, 50, 51,   # hw 0x70–0x77
    36, 37, 38, 39, 40, 41, 42, 43,   # hw 0x78–0x7F
]

ENCODER_MSG_IDS = [
    10, 11, 12, 13, 14, 15, 16, 17,
    18, 19, 20, 21, 22, 23, 24, 25,
]

TRANSPOSE_ENCODER_CC = 4

# Reverse-lookup maps built once at import time for O(1) dispatch.
_PAD_NOTE_TO_INDEX   = {note: i for i, note in enumerate(PAD_MSG_IDS)}
_ENCODER_CC_TO_INDEX = {cc: i for i, cc in enumerate(ENCODER_MSG_IDS)}


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
                song         = self.song(),
                send_led     = self._send_led,
                show_message = self.show_message,
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
        self._clear_leds()
        ControlSurface.disconnect(self)

    def build_midi_map(self, midi_map_handle):
        """Register MIDI addresses so receive_midi is called for them."""
        self.log_message('BeatStep_Q: build_midi_map called')
        ControlSurface.build_midi_map(self, midi_map_handle)
        try:
            h = self._c_instance.handle()
            for note in PAD_MSG_IDS:
                Live.MidiMap.forward_midi_note(h, midi_map_handle, 9, note)
            for cc in ENCODER_MSG_IDS:
                Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, cc)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, TRANSPOSE_ENCODER_CC)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, BTN_SHIFT_CC)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 9, BTN_RECALL_CC)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 0, BTN_SHIFT_CC)
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, 0, BTN_RECALL_CC)
            self.log_message('BeatStep_Q: MIDI map built OK')
        except Exception as e:
            self.log_message('BeatStep_Q: build_midi_map ERROR: %s' % str(e))

    # ------------------------------------------------------------------
    # Hardware setup — two-stage: sysex first, LEDs 1.5s later
    # ------------------------------------------------------------------

    def _schedule_hardware_setup(self):
        self.log_message('BeatStep_Q: scheduling hardware setup')
        if self._hw_task is not None:
            self._hw_task.kill()
        # Stagger initial LED paint: 4 LEDs per batch, 0.15 s between batches.
        # BeatStep drops LED sysex if too many arrive in one burst (~4 max).
        self._hw_task = self._task_group.add(
            Task.sequence(
                Task.wait(2.1),
                Task.run(self._send_setup_sysex),
                Task.wait(1.5),
                Task.run(lambda: self._send_leds_batch(0)),
                Task.wait(0.15),
                Task.run(lambda: self._send_leds_batch(1)),
                Task.wait(0.15),
                Task.run(lambda: self._send_leds_batch(2)),
                Task.wait(0.15),
                Task.run(lambda: self._send_leds_batch(3)),
                Task.wait(0.15),
                Task.run(lambda: self._send_leds_batch(4)),
            )
        )

    def _send_setup_sysex(self):
        self.log_message('BeatStep_Q: _send_setup_sysex running')
        try:
            # Pads only: mode=9 (note gate), channel=CH10, behaviour=gate.
            # Note numbers are NOT re-configured — factory defaults match PAD_MSG_IDS.
            for i in range(16):
                for msg in QSetup.setup_pad(i):
                    self._send_midi(msg)

            self.log_message('BeatStep_Q: pad sysex sent (%d pads, 3 msgs each)' % 16)

            for i, cc in enumerate(ENCODER_MSG_IDS):
                for msg in QSetup.setup_encoder(i, cc):
                    self._send_midi(msg)

            for msg in QSetup.setup_transpose_encoder(TRANSPOSE_ENCODER_CC):
                self._send_midi(msg)

            for msg in QSetup.setup_button(QSetup.RECALL_HW_INDEX):
                self._send_midi(msg)

            for msg in QSetup.setup_button(QSetup.SHIFT_HW_INDEX):
                self._send_midi(msg)

            self.log_message('BeatStep_Q: all sysex sent OK')
        except Exception as e:
            self.log_message('BeatStep_Q: ERROR in _send_setup_sysex: %s' % str(e))

    def _send_leds_batch(self, batch):
        """
        Send one batch of 4 LED sysex messages for the initial paint.
        Batches 0-3: pad LEDs 0-15 (4 per batch).
        Batch 4: recall button LED.
        Each batch is called 0.15 s apart so the BeatStep buffer doesn't overflow.
        """
        if not self._cmix:
            return
        try:
            if batch < 4:
                start = batch * 4
                for i in range(start, start + 4):
                    self._cmix.paint_led(i)
                if batch == 3:
                    self.log_message('BeatStep_Q: pad LEDs batches done')
            elif batch == 4:
                self._cmix.paint_led(QSetup.RECALL_LED_INDEX)
                self.log_message('BeatStep_Q: all LEDs painted')
        except Exception as e:
            self.log_message('BeatStep_Q: ERROR in _send_leds_batch %d: %s' % (batch, str(e)))

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

        if status == _STATUS_NOTE_ON_CH10:
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
        """Handle CC CH10 — encoders, transpose, and function buttons (post-sysex)."""
        if cc in _ENCODER_CC_TO_INDEX:
            self._cmix.on_encoder_turn(_ENCODER_CC_TO_INDEX[cc], value)
            return
        if cc == TRANSPOSE_ENCODER_CC:
            self._cmix.on_transpose_turn(value)
            return
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

    # ------------------------------------------------------------------
    # LED helpers
    # ------------------------------------------------------------------

    def _send_led(self, index, color):
        """
        Send LED color via sysex (cmd 0x10).
        index 0-15: pad LED at hw_index = PAD_HW_OFFSET + index.
        index == QSetup.RECALL_LED_INDEX (16): recall button at hw 0x5C.
        """
        if 0 <= index < 16:
            self._send_midi(QSetup.set_led(index + QSetup.PAD_HW_OFFSET, color))
        elif index == QSetup.RECALL_LED_INDEX:
            self._send_midi(QSetup.set_led(QSetup.RECALL_HW_INDEX, color))

    def _clear_leds(self):
        for i in range(16):
            self._send_midi(QSetup.set_led(i + QSetup.PAD_HW_OFFSET, QSetup.OFF))
        self._send_midi(QSetup.set_led(QSetup.RECALL_HW_INDEX, QSetup.OFF))
