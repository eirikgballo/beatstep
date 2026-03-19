from __future__ import absolute_import, print_function, unicode_literals
import Live

from _Framework.ControlSurface import ControlSurface
from _Framework import Task

from .QSetup import QSetup
from .CMix import CMix, BUTTON_CC

# CC IDs for the 16 encoders (hardware default)
ENCODER_MSG_IDS = (10, 74, 71, 76, 77, 93, 73, 75, 114, 18, 19, 16, 17, 91, 79, 72)
# CC IDs for the 16 pads: pads 1-8 = CC 44-51, pads 9-16 = CC 36-43
PAD_MSG_IDS = list(range(44, 52)) + list(range(36, 44))

CHANNEL = 9       # MIDI channel 10 (0-indexed)
MEMORY_SLOT = 8   # BeatStep bank 9 (0-indexed)
SETUP_HARDWARE_DELAY = 2.1


class BeatStep_Q(ControlSurface):

    def __init__(self, *a, **k):
        super(BeatStep_Q, self).__init__(*a, **k)
        self.QS = QSetup()

        with self.component_guard():
            self._setup_task = self._tasks.add(
                Task.sequence(Task.wait(SETUP_HARDWARE_DELAY),
                              Task.run(self._setup_hardware)))
            self._setup_task.kill()
            self._setup_task.restart()

            self._mix_mode = CMix(self)

    # ── MIDI receive ────────────────────────────────────────────────────────
    # No InputControlElements registered for pads/encoders, so ALL CC messages
    # arrive here unfiltered.

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) == 3:
            status, cc, val = midi_bytes
            if (status & 0xF0) == 0xB0:   # CC on any channel
                if cc in ENCODER_MSG_IDS:
                    self._mix_mode.handle_encoder(ENCODER_MSG_IDS.index(cc), val)
                    return
                if cc in PAD_MSG_IDS:
                    self._mix_mode.handle_pad(PAD_MSG_IDS.index(cc), val)
                    return
                self._mix_mode.handle_button(cc, val)
                return
        super(BeatStep_Q, self).receive_midi(midi_bytes)

    def handle_sysex(self, midi_bytes):
        super(BeatStep_Q, self).handle_sysex(midi_bytes)

    def port_settings_changed(self):
        super(BeatStep_Q, self).port_settings_changed()
        self._setup_task.kill()
        self._setup_task.restart()

    def disconnect(self):
        self._mix_mode.disconnect()
        super(BeatStep_Q, self).disconnect()

    # ── Hardware setup ──────────────────────────────────────────────────────

    def _setup_hardware(self):
        """Send all sysex configuration, staggered 1 message per tick."""
        tick = 1

        def q(msg):
            nonlocal tick
            self.schedule_message(tick, self._make_sender(msg))
            tick += 1

        # Function buttons — CC mode, channel 10, explicit CC IDs
        # cntrl = toggle (behaviour 0); all others = gate (behaviour 1)
        for btn, cc_id in BUTTON_CC.items():
            q(self.QS.set_B_mode(btn, 8))
            q(self.QS.set_B_channel(btn, CHANNEL))
            q(self.QS.set_B_cc(btn, cc_id))
            q(self.QS.set_B_behaviour(btn, 0 if btn == 'cntrl' else 1))

        # Transpose encoder
        q(self.QS.set_E_channel('transpose', CHANNEL))
        q(self.QS.set_E_behaviour('transpose', 2))
        q(self.QS.set_E_cc('transpose', 4))

        # Pads and encoders 1-16
        for i in range(1, 17):
            q(self.QS.set_B_mode(i, 8))                       # pad: CC mode
            q(self.QS.set_B_channel(i, CHANNEL))
            q(self.QS.set_B_behaviour(i, 1))                  # gate
            q(self.QS.set_B_cc(i, PAD_MSG_IDS[i - 1]))        # explicit CC ID
            q(self.QS.set_E_channel(i, CHANNEL))
            q(self.QS.set_E_mode(i, 1))                       # encoder: CC mode
            q(self.QS.set_E_behaviour(i, 2))                  # relative mode 2
            q(self.QS.set_E_cc(i, ENCODER_MSG_IDS[i - 1]))

        q(self.QS.set_B_velocity(0))      # linear velocity
        q(self.QS.set_E_acceleration(0))  # slow acceleration

        # Startup blink: pads 1-8 flash red 3 times, then paint Mix Mode LEDs
        blink_base = tick
        for blink in range(3):
            for pad in range(1, 9):
                self.schedule_message(blink_base + blink * 18 + pad,
                                      self._make_color_sender(pad, 1))   # red
                self.schedule_message(blink_base + blink * 18 + pad + 9,
                                      self._make_color_sender(pad, 0))   # off
        self.schedule_message(blink_base + 3 * 18 + 2, self._mix_mode._update_leds)

    def _make_sender(self, msg):
        def f():
            self._send_midi(msg)
        return f

    def _make_color_sender(self, button_id, color_value):
        def f():
            self._send_midi(self.QS.set_B_color(button_id, color_value))
        return f
