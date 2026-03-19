"""
Beatstep_Q — MIDI Remote Script for the Arturia BeatStep.

Boots directly into Mix Mode (CMix).  Hardware is configured via sysex on
every connection so controller state is always deterministic.

See DESIGN.md for the full specification.
"""

from _Framework.ControlSurface import ControlSurface
from _Framework import Task

from . import QSetup
from .CMix import CMix

# ---------------------------------------------------------------------------
# MIDI constants
# ---------------------------------------------------------------------------

# All pad / encoder / transpose traffic arrives on MIDI channel 10 (index 9).
_STATUS_CC_CH10 = 0xB9  # 0xB0 | 9

# Function buttons — channel and CC values need hardware verification.
# TODO: confirm with a MIDI monitor (may be CH1 or a different channel).
_STATUS_CC_CH1 = 0xB0
BTN_SHIFT_CC  = 49
BTN_RECALL_CC = 5

# CC IDs programmed into the hardware via sysex.
# Top row = pads 0-7, bottom row = pads 8-15.
PAD_MSG_IDS = [
    44, 45, 46, 47, 48, 49, 50, 51,   # top row   (pads 1-8  / index 0-7)
    36, 37, 38, 39, 40, 41, 42, 43,   # bottom row (pads 9-16 / index 8-15)
]

ENCODER_MSG_IDS = [
    10, 11, 12, 13, 14, 15, 16, 17,
    18, 19, 20, 21, 22, 23, 24, 25,
]

TRANSPOSE_ENCODER_CC = 4

# Reverse-lookup maps built once at import time for O(1) dispatch.
_PAD_CC_TO_INDEX     = {cc: i for i, cc in enumerate(PAD_MSG_IDS)}
_ENCODER_CC_TO_INDEX = {cc: i for i, cc in enumerate(ENCODER_MSG_IDS)}


# ---------------------------------------------------------------------------
# ControlSurface
# ---------------------------------------------------------------------------

class Beatstep_Q(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self.log_message('BeatStep_Q: __init__ start')
        self._cmix = None
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

    # ------------------------------------------------------------------
    # Hardware setup
    # ------------------------------------------------------------------

    def _schedule_hardware_setup(self):
        self.log_message('BeatStep_Q: scheduling hardware setup')
        self._task_group.add(
            Task.sequence(Task.wait(2.1), Task.run(self._setup_hardware))
        )

    def _setup_hardware(self):
        self.log_message('BeatStep_Q: _setup_hardware running')
        try:
            for i, cc in enumerate(PAD_MSG_IDS):
                for msg in QSetup.setup_pad(i, cc):
                    self._send_midi(msg)

            for i, cc in enumerate(ENCODER_MSG_IDS):
                for msg in QSetup.setup_encoder(i, cc):
                    self._send_midi(msg)

            for msg in QSetup.setup_transpose_encoder(TRANSPOSE_ENCODER_CC):
                self._send_midi(msg)

            self.log_message('BeatStep_Q: sysex sent OK')

            if self._cmix:
                self._cmix.update_leds()
                self.log_message('BeatStep_Q: LEDs painted')
            else:
                self.log_message('BeatStep_Q: _cmix is None, skipping LEDs')
        except Exception as e:
            self.log_message('BeatStep_Q: ERROR in _setup_hardware: %s' % str(e))

    # ------------------------------------------------------------------
    # MIDI receive
    # ------------------------------------------------------------------

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) < 3:
            return
        status = midi_bytes[0]
        cc     = midi_bytes[1]
        value  = midi_bytes[2]

        if status == _STATUS_CC_CH10:
            self._handle_ch10(cc, value)
        elif status == _STATUS_CC_CH1:
            self._handle_ch1(cc, value)

    def _handle_ch10(self, cc, value):
        if cc in _PAD_CC_TO_INDEX:
            if value > 0:
                self._cmix.on_pad_press(_PAD_CC_TO_INDEX[cc])
            return
        if cc in _ENCODER_CC_TO_INDEX:
            self._cmix.on_encoder_turn(_ENCODER_CC_TO_INDEX[cc], value)
            return
        if cc == TRANSPOSE_ENCODER_CC:
            self._cmix.on_transpose_turn(value)

    def _handle_ch1(self, cc, value):
        is_press = value > 0
        if cc == BTN_SHIFT_CC:
            if is_press:
                self._cmix.on_shift_press()
            else:
                self._cmix.on_shift_release()
        elif cc == BTN_RECALL_CC and is_press:
            self._cmix.on_recall_press()

    # ------------------------------------------------------------------
    # LED helpers
    # ------------------------------------------------------------------

    def _send_led(self, hw_index, color):
        self._send_midi(QSetup.set_led(hw_index, color))

    def _clear_leds(self):
        for i in range(16):
            self._send_midi(QSetup.set_led(i, QSetup.OFF))
        self._send_midi(QSetup.set_led(QSetup.RECALL_LED_INDEX, QSetup.OFF))
