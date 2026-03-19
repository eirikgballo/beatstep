"""
BeatStep_Q — MIDI Remote Script for the Arturia BeatStep.

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

# Function buttons arrive on MIDI channel 1 (index 0).
# TODO: confirm channel and CC values against hardware / MIDI monitor.
_STATUS_CC_CH1 = 0xB0

# CC IDs programmed into the hardware via sysex.
# Top row = pads 0-7, bottom row = pads 8-15 (index into these lists).
PAD_MSG_IDS = [
    44, 45, 46, 47, 48, 49, 50, 51,   # top row   (pads 1-8  / index 0-7)
    36, 37, 38, 39, 40, 41, 42, 43,   # bottom row (pads 9-16 / index 8-15)
]

ENCODER_MSG_IDS = [
    10, 11, 12, 13, 14, 15, 16, 17,
    18, 19, 20, 21, 22, 23, 24, 25,
]

TRANSPOSE_ENCODER_CC = 4  # CC 4, CH10, relative mode 2

# Function button CC IDs on CH1.
# TODO: verify all values against hardware using a MIDI monitor.
# The BeatStep may also send these on a different channel depending on firmware
# version and MIDI Control Center settings.
BTN_SHIFT_CC  = 49   # TODO: verify
BTN_RECALL_CC = 5    # TODO: verify
BTN_PLAY_CC   = 70   # reserved (no function); TODO: verify or may be MMC
BTN_STOP_CC   = 71   # reserved (no function); TODO: verify or may be MMC

# Reverse-lookup maps built once at import time for O(1) dispatch.
_PAD_CC_TO_INDEX     = {cc: i for i, cc in enumerate(PAD_MSG_IDS)}
_ENCODER_CC_TO_INDEX = {cc: i for i, cc in enumerate(ENCODER_MSG_IDS)}


# ---------------------------------------------------------------------------
# ControlSurface
# ---------------------------------------------------------------------------

class BeatStep_Q(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._cmix = None
        with self.component_guard():
            self._cmix = CMix(
                song         = self.song(),
                send_led     = self._send_led,
                show_message = self.show_message,
            )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def port_settings_changed(self):
        """Called when MIDI ports connect or disconnect."""
        ControlSurface.port_settings_changed(self)
        if self._ports_are_active():
            # Delay hardware setup ~2 s; BeatStep needs time after connection.
            self._tasks.add(
                Task.sequence(Task.wait(2.1), Task.run(self._setup_hardware))
            )
        else:
            self._clear_leds()

    def disconnect(self):
        if self._cmix:
            self._cmix.cleanup()
        self._clear_leds()
        ControlSurface.disconnect(self)

    # ------------------------------------------------------------------
    # Hardware setup (called after connection delay)
    # ------------------------------------------------------------------

    def _setup_hardware(self):
        # Program pad CC numbers
        for i, cc in enumerate(PAD_MSG_IDS):
            self._send_midi(QSetup.set_pad_cc(i, cc))

        # Program encoder CC numbers
        for i, cc in enumerate(ENCODER_MSG_IDS):
            self._send_midi(QSetup.set_encoder_cc(i, cc))

        # Set all 16 encoders to relative mode 2
        for i in range(16):
            hw_index = i + 16  # encoders start at hardware index 16
            self._send_midi(QSetup.set_encoder_relative_mode(hw_index))

        # Set transpose encoder to relative mode 2
        self._send_midi(
            QSetup.set_encoder_relative_mode(QSetup.TRANSPOSE_ENC_HW_INDEX)
        )

        # Paint initial LEDs
        if self._cmix:
            self._cmix.update_leds()

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
        # Pads: fire on press (value > 0) only
        if cc in _PAD_CC_TO_INDEX:
            if value > 0:
                self._cmix.on_pad_press(_PAD_CC_TO_INDEX[cc])
            return

        # Encoders
        if cc in _ENCODER_CC_TO_INDEX:
            self._cmix.on_encoder_turn(_ENCODER_CC_TO_INDEX[cc], value)
            return

        # Transpose encoder
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ports_are_active(self):
        """Return True if both input and output ports are available."""
        return (
            self._input_midi_port  is not None and
            self._output_midi_port is not None
        )
