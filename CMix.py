import time


class CMix:
    """
    Mix Mode for BeatStep_Q.

    Pad layout (viewed from the player):
      Top row    (pads 9-16, pad_index 8-15)  -> Ableton Tracks  1-8  (track_index 0-7)
      Bottom row (pads 1-8,  pad_index 0-7)   -> Ableton Tracks  9-16 (track_index 8-15)

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
    # pad_index 0-7  = bottom row (pads 1-8)  -> tracks 9-16 (indices 8-15)
    # pad_index 8-15 = top row    (pads 9-16) -> tracks 1-8  (indices 0-7)
    _PAD_TO_TRACK = [8, 9, 10, 11, 12, 13, 14, 15,
                     0, 1,  2,  3,  4,  5,  6,  7]

    # Encoder step as a fraction of the full parameter range per encoder click.
    _ENCODER_STEP_FRACTION = 0.01

    def __init__(self, parent):
        self._parent = parent
        self._pad_buttons = [None] * 16
        self._encoder_buttons = [None] * 16
        self._cntrl_button = None

        self._last_tap_time = [-99.0] * 16
        self._last_tapped_pad = -1

        # Stable callables (created once so add/remove_value_listener work correctly).
        self._pad_listeners = [self._make_pad_listener(i) for i in range(16)]
        self._encoder_listeners = [self._make_encoder_listener(i) for i in range(16)]

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

    def set_encoder_button(self, encoder_index, button):
        """Wire an EncoderElement to encoder_index (0-15)."""
        old = self._encoder_buttons[encoder_index]
        listener = self._encoder_listeners[encoder_index]
        if old is not None:
            try:
                old.remove_value_listener(listener)
            except Exception:
                pass
        if button is not None:
            button.add_value_listener(listener)
        self._encoder_buttons[encoder_index] = button

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

    def _make_encoder_listener(self, encoder_index):
        def listener(value):
            self._on_encoder(encoder_index, value)
        return listener

    # ── Event handlers ─────────────────────────────────────────────────────

    def _on_recall(self, value):
        # The BeatStep hardware physically recalls its stored preset whenever the
        # recall button fires, resetting pad modes and LED colours. Re-apply
        # control mode immediately to restore CC mode on the pads, then repaint.
        self._parent._activate_control_mode()
        self._update_leds()

    def _on_pad(self, pad_index, value):
        if value == 0:
            return
        track_index = self._PAD_TO_TRACK[pad_index]
        tracks = list(self._parent.song().tracks)
        if track_index >= len(tracks):
            return
        track = tracks[track_index]

        now = time.time()
        if (self._last_tapped_pad == pad_index
                and now - self._last_tap_time[pad_index] <= self.DOUBLE_TAP_TIME):
            track.solo = not track.solo
        else:
            self._parent.song().view.selected_track = track

        self._last_tap_time[pad_index] = now
        self._last_tapped_pad = pad_index
        self._update_leds()

    def _on_encoder(self, encoder_index, value):
        track = self._parent.song().view.selected_track
        if track is None:
            return
        device = self._get_rack_device(track)
        if device is None:
            return
        params = device.parameters
        # parameters[0] is "Device On"; macros start at index 1.
        param_index = encoder_index + 1
        if param_index >= len(params):
            return
        param = params[param_index]
        if not param.is_enabled or param.is_quantized:
            return
        # Relative smooth two's complement: < 65 = clockwise, > 65 = counterclockwise.
        direction = 1 if value < 65 else -1
        step = (param.max - param.min) * self._ENCODER_STEP_FRACTION * direction
        param.value = max(param.min, min(param.max, param.value + step))

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
        """
        track_index 0-7  -> button ID 9-16  (top row)
        track_index 8-15 -> button ID 1-8   (bottom row)
        """
        if track_index < 8:
            return track_index + 9
        return track_index - 7  # equivalent to (track_index - 8) + 1

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
