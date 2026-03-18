# Embedded file name: /Users/versonator/Jenkins/live/output/Live/mac_64_static/Release/python-bundle/MIDI Remote Scripts/BeatStep/BeatStep_Q.py
from __future__ import absolute_import, print_function, unicode_literals
import Live

# from _Arturia.ArturiaControlSurface import ArturiaControlSurface
from _Framework.ControlSurface import ControlSurface
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.ButtonElement import ButtonElement
from _Framework import Task

from .QSetup import QSetup
from .CMix import CMix

ENCODER_MSG_IDS = (10, 74, 71, 76, 77, 93, 73, 75, 114, 18, 19, 16, 17, 91, 79, 72)
PAD_MSG_IDS = list(range(44, 52)) + list(range(36, 44))

# the midi-channel to use for buttons and encoders
CHANNEL = 9
# the used memory-slot to store the configurations
MEMORY_SLOT = 8

SETUP_HARDWARE_DELAY = 2.1


class BeatStep_Q(ControlSurface):
    def __init__(self, *a, **k):
        super(BeatStep_Q, self).__init__(*a, **k)

        self.QS = QSetup()
        self.control_layer_active = False

        with self.component_guard():
            self._setup_hardware_task = self._tasks.add(
                Task.sequence(
                    Task.wait(SETUP_HARDWARE_DELAY), Task.run(self._setup_hardware)
                )
            )
            self._setup_hardware_task.kill()
            self._start_hardware_setup()

            self._create_controls()
            self._create_mix_mode()

            # self._create_device()  # not used in new architecture

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) == 3:
            status, cc, value = midi_bytes
            if (status & 0xF0) == 0xB0:
                if cc in ENCODER_MSG_IDS:
                    encoder_index = ENCODER_MSG_IDS.index(cc)
                    self._mix_mode.handle_encoder(encoder_index, value)
                    return
                if cc in PAD_MSG_IDS:
                    pad_index = PAD_MSG_IDS.index(cc)
                    self._mix_mode.handle_pad(pad_index, value)
                    return
        super(BeatStep_Q, self).receive_midi(midi_bytes)

    def handle_sysex(self, midi_bytes):
        # self.show_message(str(midi_bytes))
        super(BeatStep_Q, self).handle_sysex(midi_bytes)

    def port_settings_changed(self):
        super(BeatStep_Q, self).port_settings_changed()
        self._start_hardware_setup()

    def _start_hardware_setup(self):
        # kill already running setup tasks:
        self._setup_hardware_task.kill()
        self._messages_to_send = []
        self._setup_hardware_task.restart()

    def _B_color_callback(self, b, c):
        # do this to ensure callback-name closure
        def f():
            self._send_midi(self.QS.set_B_color(b, c))

        return f

    def _init_color_sequence(self):
        # Custom CMix startup animation: pads 1-8 blink red 3 times.
        # Each pad is staggered by 1 tick to avoid dropped sysex messages.
        # Blink 1: on ticks 1-8, off ticks 10-17
        # Blink 2: on ticks 20-27, off ticks 29-36
        # Blink 3: on ticks 39-46, off ticks 48-55
        # Mix Mode LEDs paint at tick 60.
        for blink in range(3):
            base = blink * 19
            for pad in range(1, 9):
                self.schedule_message(base + pad,      self._B_color_callback(pad, 1))  # red
                self.schedule_message(base + pad + 9,  self._B_color_callback(pad, 0))  # off
        self.schedule_message(60, self._mix_mode._update_leds)

    def _setup_hardware(self):
        self._setup_control_buttons_and_encoders()
        self._setup_buttons_and_encoders()

        # set pad velocity to 0 (e.g. linear) on startup
        self._send_midi(self.QS.set_B_velocity(0))
        # set encoder acceleration to "slow" on startup
        self._send_midi(self.QS.set_E_acceleration(0))

        # Switch pads to CC mode after setup is done, then run startup animation.
        self._activate_control_mode()
        self._init_color_sequence()

    def _setup_control_buttons_and_encoders(self):
        """
        this function is only called once when the BeatStep is plugged in to
        ensure correct assignments of function-buttons and transpose encoder
        """
        # set shift button to note-mode
        self._send_midi(self.QS.set_B_mode("shift", 8))
        self._send_midi(self.QS.set_B_channel("shift", CHANNEL))
        self._send_midi(self.QS.set_B_behaviour("shift", 1))

        # set stop button to note-mode
        self._send_midi(self.QS.set_B_mode("stop", 8))
        self._send_midi(self.QS.set_B_channel("stop", CHANNEL))
        self._send_midi(self.QS.set_B_behaviour("stop", 1))

        # set play button to note-mode
        self._send_midi(self.QS.set_B_mode("play", 8))
        self._send_midi(self.QS.set_B_channel("play", CHANNEL))
        self._send_midi(self.QS.set_B_behaviour("play", 1))

        # set cntrl/seq button to note-mode
        self._send_midi(self.QS.set_B_mode("cntrl", 8))
        self._send_midi(self.QS.set_B_channel("cntrl", CHANNEL))
        # set button behaviour to toggle
        self._send_midi(self.QS.set_B_behaviour("cntrl", 0))

        # set chan button to note mode
        self._send_midi(self.QS.set_B_mode("chan", 8))
        self._send_midi(self.QS.set_B_channel("chan", CHANNEL))
        self._send_midi(self.QS.set_B_behaviour("chan", 1))

        # set store button to note mode
        self._send_midi(self.QS.set_B_mode("store", 8))
        self._send_midi(self.QS.set_B_channel("store", CHANNEL))
        self._send_midi(self.QS.set_B_behaviour("store", 1))

        # set store button to note mode
        self._send_midi(self.QS.set_B_mode("recall", 8))
        self._send_midi(self.QS.set_B_channel("recall", CHANNEL))
        self._send_midi(self.QS.set_B_behaviour("recall", 1))

        # set transpose encoder channel
        self._send_midi(self.QS.set_E_channel("transpose", CHANNEL))
        self._send_midi(self.QS.set_E_behaviour("transpose", 2))
        # set encoder cc to something else than the shift-encoder cc
        # (4 is unused since it would represent the ext/sync button)
        self._send_midi(self.QS.set_E_cc("transpose", 4))

    def _setup_buttons_and_encoders(self):
        # Stagger every sysex message by 1 tick — sending them all at once
        # causes the hardware to silently drop most of them.
        tick = 1
        for i in range(1, 17):
            self.schedule_message(tick, self._send_midi_callback(self.QS.set_B_mode(i, 9)));      tick += 1
            self.schedule_message(tick, self._send_midi_callback(self.QS.set_B_channel(i, CHANNEL))); tick += 1
            self.schedule_message(tick, self._send_midi_callback(self.QS.set_B_behaviour(i, 1))); tick += 1
            self.schedule_message(tick, self._send_midi_callback(self.QS.set_E_channel(i, CHANNEL))); tick += 1
            self.schedule_message(tick, self._send_midi_callback(self.QS.set_E_behaviour(i, 2))); tick += 1
            self.schedule_message(tick, self._send_midi_callback(self.QS.set_E_mode(i, 1)));      tick += 1
            self.schedule_message(tick, self._send_midi_callback(self.QS.set_E_cc(i, ENCODER_MSG_IDS[i - 1]))); tick += 1
        self._setup_done_at_tick = tick

    def _send_midi_callback(self, msg):
        def f():
            self._send_midi(msg)
        return f

    def _do_activate_control_mode(self):
        # for all buttons
        for i in range(1, 17):
            # set pad to cc-mode
            self._send_midi(self.QS.set_B_mode(i, 8))
            # set pad channel
            self._send_midi(self.QS.set_B_channel(i, CHANNEL))
            # set pad behaviour to gate (127 on press, 0 on release)
            self._send_midi(self.QS.set_B_behaviour(i, 1))

            # set encoder channel
            self._send_midi(self.QS.set_E_channel(i, CHANNEL))
            # set all encoders to relative-mode 2
            self._send_midi(self.QS.set_E_behaviour(i, 2))

        # set transpose encoder channel to follow global channel
        self._send_midi(self.QS.set_E_channel("transpose", CHANNEL))
        # set transpose encoder to relative mode 2
        self._send_midi(self.QS.set_E_behaviour("transpose", 2))

    def _deactivate_control_mode(self):
        self._send_midi(self.QS.recall_preset(MEMORY_SLOT))
        self.control_layer_active = False

    def _activate_control_mode(self):
        # only save the current configuration if no control-layer is active
        if not self.control_layer_active:
            self._send_midi(self.QS.store_preset(MEMORY_SLOT))

        self._do_activate_control_mode()
        self.control_layer_active = True

    def _create_controls(self):
        self._play_button = ButtonElement(
            True, MIDI_CC_TYPE, CHANNEL, 2, name="Play_Button"
        )
        self._play_S_button = ButtonElement(
            True, MIDI_NOTE_TYPE, 0, 60, name="Play_Button"
        )
        self._stop_button = ButtonElement(
            True, MIDI_CC_TYPE, CHANNEL, 1, name="Stop_Button"
        )
        self._cntrl_button = ButtonElement(
            True, MIDI_CC_TYPE, CHANNEL, 3, name="cntrl_Button"
        )
        self._recall_button = ButtonElement(
            True, MIDI_CC_TYPE, CHANNEL, 5, name="recall_Button"
        )
        self._store_button = ButtonElement(
            True, MIDI_CC_TYPE, CHANNEL, 6, name="store_Button"
        )
        self._shift_button = ButtonElement(
            True, MIDI_CC_TYPE, CHANNEL, 7, name="Shift_Button"
        )
        self._chan_button = ButtonElement(
            True, MIDI_CC_TYPE, CHANNEL, 8, name="chan_Button"
        )
        # Pads and encoders are handled directly in receive_midi.
        # Registering ButtonElements for them would prevent receive_midi from
        # seeing their CC messages.

        self._transpose_encoder = EncoderElement(
            MIDI_CC_TYPE,
            CHANNEL,
            4,
            Live.MidiMap.MapMode.relative_smooth_two_compliment,
            name="_transpose_encoder",
        )
        # Note: _device_encoders removed — it duplicated encoder CC registrations
        # and caused the framework to route only half the encoders correctly.

    def _create_mix_mode(self):\n        self._mix_mode = CMix(self)\n        self._mix_mode.set_recall_button(self._recall_button)

    def _create_Q_control(self):
        # Kept for reference. Not used in new architecture.
        pass

    def disconnect(self):
        if hasattr(self, '_mix_mode'):
            self._mix_mode.disconnect()
        super(BeatStep_Q, self).disconnect()

    def _create_device(self):
        self._device = DeviceComponent(
            name="Device",
            is_enabled=False,
            layer=Layer(parameter_controls=self._device_encoders),
            device_selection_follows_track_selection=True,
        )
        self._device.set_enabled(True)
        self.set_device_component(self._device)
