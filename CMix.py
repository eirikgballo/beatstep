import time


class CMix:
    """
    Mix Mode for BeatStep_Q.

    Pad layout (viewed from the player):
      Top row    (pads 1-8,  pad_index 0-7)   -> Ableton Tracks  1-8  (track_index 0-7)
      Bottom row (pads 9-16, pad_index 8-15)  -> Ableton Tracks  9-16 (track_index 8-15)

    Behaviour:
      Single tap  -> select that track in Ableton
      Double tap  -> toggle solo on that track
      Encoders    -> control macros 1-16 of the first rack device on the selected track

    LED scheme:
      red    = currently selected track
      blue   = track exists but not selected
      black  = no track at this position
      cntrl  = red while Mix Mode is active
    """

    DOUBLE_TAP_TIME = 0.5  # seconds

    # Maps pad_index (0-15) -> track_index (0-15).
    # pad_index 0-7  = top row    (pads 1-8)  -> tracks 1-8  (indices 0-7)
    # pad_index 8-15 = bottom row (pads 9-16) -> tracks 9-16 (indices 8-15)
    _PAD_TO_TRACK = [0, 1, 2, 3, 4, 5, 6, 7,
                     8, 9, 10, 11, 12, 13, 14, 15]

    # Encoder step as a fraction of the full parameter range per encoder click.
    _ENCODER_STEP_FRACTION = 0.01

    def __init__(self, parent):
        self._parent = parent
        self._pad_buttons = [None] * 16
        self._cntrl_button = None

        self._last_tap_time = [-99.0] * 16
        self._last_tapped_pad = -1

        # Stable callables for pads only.
        self._pad_listeners = [self._make_pad_listener(i) for i in range(16)]

        song = self._parent.song()
        song.view.add_selected_track_listener(self._on_state_changed)
        song.add_tracks_listener(self._on_state_changed)
        song.add_visible_tracks_listener(self._on_state_changed)

    # ── Button wiring ──────────────────────────────────────────────────────

    def set_pad_button(self, pad_index, button):
        """Wire a pad ButtonElement to pad_index (0-15)."""
        old = self._pad_buttons[pad_index]
        listener = self._pad_listeners[pad_index]
        if old is not None:
            try:
                old.remove_value_listener(listener)
            except Exception:
                pass
        if button is not None:
            button.add_value_listener(listener)
        self._pad_buttons[pad_index] = button

    def set_recall_button(self, button):
        """Wire the recall ButtonElement."""
        if self._cntrl_button is not None:
            try:
                self._cntrl_button.remove_value_listener(self._on_recall)
            except Exception:
                pass
        if button is not None:
            button.add_value_listener(self._on_recall)
        self._cntrl_button = button

    # ── Listener factories ─────────────────────────────────────────────────

    def _make_pad_listener(self, pad_index):
        def listener(value):
            self._on_pad(pad_index, value)
        return listener

    # ── Event handlers ─────────────────────────────────────────────────────

    def _on_recall(self, value):
        # Re-apply CC mode (hardware recall resets pad modes) then repaint.
        # Schedule 1 tick later so our sysex fires after the hardware
        # gate-release LED reset clears the button colour.
        self._parent._activate_control_mode()
        self._parent.schedule_message(1, self._update_leds)
        if value > 0:
            self._parent.show_message("Mix Mode active")

    def _on_pad(self, pad_index, value):
        track_index = self._PAD_TO_TRACK[pad_index]
        tracks = list(self._parent.song().tracks)

        if value == 0:
            # Hardware resets the LED on gate-release — repaint 1 tick later.
            self._parent.schedule_message(1, self._update_leds)
            return

        if track_index >= len(tracks):
            self._parent.show_message("Mix: no track at pad {}".format(pad_index + 1))
            return
        track = tracks[track_index]
        self._parent.show_message("Mix: pad {} -> {}".format(pad_index + 1, track.name))

        now = time.time()
        if (self._last_tapped_pad == pad_index
                and now - self._last_tap_time[pad_index] <= self.DOUBLE_TAP_TIME):
            track.solo = not track.solo
        else:
            self._parent.song().view.selected_track = track

        self._last_tap_time[pad_index] = now
        self._last_tapped_pad = pad_index
        self._update_leds()

    def handle_encoder(self, encoder_index, raw_value):
        """Called directly from receive_midi with the raw MIDI CC value."""
        track = self._parent.song().view.selected_track
        if track is None:
            return
        device = self._get_rack_device(track)
        if device is None:
            self._parent.show_message(
                "Mix enc{}: no rack on '{}'".format(encoder_index + 1, track.name))
            return
        params = device.parameters
        # parameters[0] is "Device On"; macros start at index 1.
        param_index = encoder_index + 1
        if param_index >= len(params):
            return
        param = params[param_index]
        if not param.is_enabled or param.is_quantized:
            return
        # Arturia relative mode 2 = two's complement:
        # 1-63  = clockwise  (increase)
        # 65-127 = counterclockwise (decrease)
        direction = 1 if raw_value < 64 else -1
        step = (param.max - param.min) * self._ENCODER_STEP_FRACTION * direction
        param.value = max(param.min, min(param.max, param.value + step))
        self._parent.show_message(
            "enc{} -> {} = {:.2f}".format(encoder_index + 1, param.name, param.value))

    def _on_state_changed(self):
        self._update_leds()

    # ── LED management ─────────────────────────────────────────────────────

    def _set_color(self, button_id, color):
        colordict = {'black': 0, 'red': 1, 'blue': 16, 'magenta': 17}
        self._parent._send_midi(
            self._parent.QS.set_B_color(button_id, colordict[color]))

    def _update_leds(self):
        tracks = list(self._parent.song().tracks)
        selected = self._parent.song().view.selected_track

        for track_index in range(16):
            button_id = self._track_to_button_id(track_index)
            if track_index < len(tracks):
                color = 'red' if tracks[track_index] == selected else 'blue'
            else:
                color = 'black'
            self._set_color(button_id, color)

        self._set_color('recall', 'red')

    @staticmethod
    def _track_to_button_id(track_index):
        # Physical pads 1-8  (top row)    = software button IDs 9-16
        # Physical pads 9-16 (bottom row) = software button IDs 1-8
        if track_index < 8:
            return track_index + 9
        return track_index - 7

    # ── Helpers ────────────────────────────────────────────────────────────

    def _get_rack_device(self, track):
        """Return the first rack device (Audio/Instrument Rack) on the track."""
        for device in track.devices:
            if getattr(device, 'can_have_chains', False):
                return device
        return None

    # ── Cleanup ────────────────────────────────────────────────────────────

    def disconnect(self):
        song = self._parent.song()
        for remove_fn, has_fn, listener in [
            (song.view.remove_selected_track_listener,
             song.view.selected_track_has_listener,
             self._on_state_changed),
            (song.remove_tracks_listener,
             song.tracks_has_listener,
             self._on_state_changed),
            (song.remove_visible_tracks_listener,
             song.visible_tracks_has_listener,
             self._on_state_changed),
        ]:
            try:
                if has_fn(listener):
                    remove_fn(listener)
            except Exception:
                pass
