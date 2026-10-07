"""
BeatStep — MIDI Remote Script for the Arturia BeatStep.

Owns the hardware setup, MIDI routing and the active mode. Hardware is configured via sysex on
every connection so controller state is always deterministic.

See DESIGN.md for the full specification and SIGNALS.md for measured hardware behaviour.
"""

import Live

from _Framework.ControlSurface import ControlSurface
from _Framework import Task

from . import Sysex
from .Encoders import Accelerator, TRANSPOSE_FEEL, nudge
from .RackMode import RackMode
from .SendsMode import SendsMode
from .TrackPads import TrackPads
from .VolumeMode import VolumeMode

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
BTN_PLAY_CC   = 28
BTN_STOP_CC   = 29
BTN_CNTRL_CC  = 30
BTN_EXTSYNC_CC = 31
BTN_STORE_CC  = 32
BTN_CHAN_CC   = 33

# hw index → CC for every button the script configures.
_BUTTONS = [
    (Sysex.SHIFT_HW_INDEX,  BTN_SHIFT_CC),
    (Sysex.RECALL_HW_INDEX, BTN_RECALL_CC),
    (Sysex.PLAY_HW_INDEX,   BTN_PLAY_CC),
    (Sysex.STOP_HW_INDEX,   BTN_STOP_CC),
    (Sysex.CNTRL_HW_INDEX,  BTN_CNTRL_CC),
    (Sysex.EXTSYNC_HW_INDEX, BTN_EXTSYNC_CC),
    (Sysex.STORE_HW_INDEX,  BTN_STORE_CC),
    (Sysex.CHAN_HW_INDEX,   BTN_CHAN_CC),
]
_BUTTON_CCS = [cc for _, cc in _BUTTONS]

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

class BeatStep(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._hw_task = None
        self._shift_held = False
        self._seq_mode = False
        # No try/except: if a component fails, Live should show the error instead of a silent, dead controller.
        self._pads = TrackPads(
            song         = self.song(),
            show_message = self.show_message,
            send_midi    = self._send_midi,
        )
        self._accelerator = Accelerator()
        # Mode button CC → mode. The script always boots in Rack mode.
        self._modes = {
            BTN_CHAN_CC:   RackMode(self.song(), self.show_message, self._accelerator),
            BTN_RECALL_CC: VolumeMode(self.song(), self._pads, self._accelerator),
            BTN_STORE_CC:  SendsMode(self.song(), self._pads, self._accelerator),
        }
        self._mode = self._modes[BTN_CHAN_CC]
        self._schedule_hardware_setup()
        self.request_rebuild_midi_map()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def port_settings_changed(self):
        ControlSurface.port_settings_changed(self)
        self._schedule_hardware_setup()

    def disconnect(self):
        self._pads.cleanup()
        for hw, _ in _BUTTONS:
            if hw != Sysex.STOP_HW_INDEX:
                self._send_midi(Sysex.set_button_led(hw, False))
        ControlSurface.disconnect(self)

    def update_display(self):
        ControlSurface.update_display(self)
        self._pads.tick()

    def build_midi_map(self, midi_map_handle):
        """Register MIDI addresses so receive_midi is called for them."""
        ControlSurface.build_midi_map(self, midi_map_handle)
        h = self._c_instance.handle()
        for note in PAD_MSG_IDS:
            Live.MidiMap.forward_midi_note(h, midi_map_handle, _CHANNEL, note)
        for cc in _BUTTON_CCS + [TRANSPOSE_CC] + [ENCODER_CC_BASE + i for i in range(16)]:
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
            messages += Sysex.setup_pad(i, note)
        for hw, cc in _BUTTONS:
            messages += Sysex.setup_button(hw, cc)
        for i in range(16):
            messages += Sysex.setup_encoder(i, ENCODER_CC_BASE + i)
        messages += Sysex.setup_transpose_encoder(TRANSPOSE_CC)

        for msg in messages:
            self._send_midi(msg)
        self.log_message('BeatStep: %d setup sysex sent' % len(messages))
        self._update_leds()

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
            was_picking = self._pads.picking_page
            self._pads.on_pad_press(idx)
            if self._pads.picking_page != was_picking:
                self._update_button_leds()
        else:
            self._pads.on_pad_release(idx)

    def _handle_cc(self, cc, value):
        """Encoders and function buttons."""
        if ENCODER_CC_BASE <= cc < ENCODER_CC_BASE + 16:
            self._mode.on_encoder(cc - ENCODER_CC_BASE, value)
        elif cc == TRANSPOSE_CC:
            self._on_transpose_encoder(value)
        elif cc in _BUTTON_CCS:
            if cc == BTN_SHIFT_CC:
                self._shift_held = value > 0
            elif cc == BTN_EXTSYNC_CC and value > 0:
                self._pads.toggle_page_picker()
            elif cc in self._modes and value > 0 and self._modes[cc] is not self._mode:
                self._mode = self._modes[cc]
                self.show_message('BeatStep: %s mode' % self._mode.name)
            elif cc == BTN_CNTRL_CC and value > 0:
                # The firmware toggles between control and sequencer mode. The script can't read the mode,
                # so it counts presses and assumes control mode on start.
                self._seq_mode = not self._seq_mode
                self._pads.suspended = self._seq_mode
                if self._seq_mode:
                    self.show_message('BeatStep in sequencer mode, press cntrl/seq to return')
            if value == 0:
                # While a button is held the firmware shows its own overlay on the pads (or the sequencer
                # runs its step indicator), and on release it restores its own colors, not ours.
                self._update_leds()

    def _update_leds(self):
        self._pads.update_leds()
        self._update_button_leds()

    def _update_button_leds(self):
        # Every configured button is turned off (the firmware lights some of them on its own), except the
        # active mode button, ext sync while the page picker is open and cntrl/seq (red) in sequencer mode.
        for hw, cc in _BUTTONS:
            if hw == Sysex.STOP_HW_INDEX:
                continue
            if cc == BTN_CNTRL_CC:
                self._send_midi(Sysex.set_button_led(hw, self._seq_mode, Sysex.COLOR_RED))
            elif cc == BTN_EXTSYNC_CC:
                self._send_midi(Sysex.set_button_led(hw, self._pads.picking_page))
            else:
                self._send_midi(Sysex.set_button_led(hw, self._modes.get(cc) is self._mode))

    def _on_transpose_encoder(self, value):
        """Transpose encoder → volume of the selected track in every mode, or master with shift held."""
        delta = self._accelerator.delta('transpose', value, TRANSPOSE_FEEL)
        if delta is None:
            return
        if self._shift_held:
            track = self.song().master_track
        else:
            track = self.song().view.selected_track
        if track is None:
            return
        nudge(track.mixer_device.volume, delta)
