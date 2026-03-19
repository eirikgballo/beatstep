import time


# CC numbers for the BeatStep function buttons on channel 10
BUTTON_CC = {
    'stop':   1,
    'play':   2,
    'cntrl':  3,
    'recall': 5,
    'store':  6,
    'shift':  7,
    'chan':    8,
}


class CMix:
    """
    Mix Mode — the only mode for now.

    Physical layout:
      Top row    pads 1-8   -> CC 44-51 -> PAD_MSG_IDS index 0-7  -> Tracks 1-8
      Bottom row pads 9-16  -> CC 36-43 -> PAD_MSG_IDS index 8-15 -> Tracks 9-16

    LEDs:
      red     = selected track (takes priority over solo)
      magenta = soloed but not selected
      blue    = track exists, not selected, not soloed
      black   = no track at this position
      recall button = blue (mix mode indicator)

    Pad behaviour:
      single tap        -> select track (exclusive: only one red at a time)
      double tap        -> toggle solo on/off (additive: multiple tracks can be soloed)
                          double-tapping does NOT change track selection

    Encoder behaviour:
      each encoder controls the corresponding macro (1-16) of the first
      rack device on the currently selected track.
    """

    DOUBLE_TAP_TIME = 0.4   # seconds

    # Arturia relative mode 2: 1-63 = clockwise, 65-127 = counterclockwise
    ENCODER_STEP = 0.01     # fraction of param range per click

    def __init__(self, parent):
        self._parent = parent
        self._last_tap_time = [-99.0] * 16
        self._last_tapped_pad = -1

        song = parent.song()
        song.view.add_selected_track_listener(self._update_leds)
        song.add_tracks_listener(self._update_leds)
        song.add_visible_tracks_listener(self._update_leds)

    # ── Entry points called from BeatStep_Q.receive_midi ───────────────────

    def handle_pad(self, pad_index, value):
        """pad_index 0-15 matches PAD_MSG_IDS order."""
        if value == 0:
            # Gate release: hardware may clear LED — repaint after 1 tick
            self._parent.schedule_message(1, self._update_leds)
            return

        tracks = list(self._parent.song().tracks)
        if pad_index >= len(tracks):
            self._parent.show_message(
                "Mix: no track at pad {}".format(pad_index + 1))
            return

        track = tracks[pad_index]
        now = time.time()
        if (self._last_tapped_pad == pad_index
                and now - self._last_tap_time[pad_index] <= self.DOUBLE_TAP_TIME):
            track.solo = not track.solo
        else:
            self._parent.song().view.selected_track = track
            self._parent.show_message("Mix: {}".format(track.name))

        self._last_tap_time[pad_index] = now
        self._last_tapped_pad = pad_index
        self._update_leds()

    def handle_encoder(self, encoder_index, raw_value):
        """encoder_index 0-15 matches ENCODER_MSG_IDS order."""
        track = self._parent.song().view.selected_track
        if track is None:
            return
        device = self._get_rack(track)
        if device is None:
            self._parent.show_message("No rack on track '{}'".format(track.name))
            return

        # parameters[0] = Device On/Off; macros start at index 1
        params = device.parameters
        idx = encoder_index + 1
        if idx >= len(params):
            return
        param = params[idx]
        if not param.is_enabled or param.is_quantized:
            return

        direction = 1 if raw_value < 64 else -1
        step = (param.max - param.min) * self.ENCODER_STEP * direction
        param.value = max(param.min, min(param.max, param.value + step))
        self._parent.show_message(
            "enc{} {} = {:.2f}".format(encoder_index + 1, param.name, param.value))

    def handle_button(self, cc, value):
        """Function button handler — only recall is used for now."""
        if cc == BUTTON_CC['recall']:
            # Repaint LEDs on both press and release (hardware clears on release)
            self._parent.schedule_message(1, self._update_leds)

    # ── LED management ─────────────────────────────────────────────────────

    def _set_color(self, button_id, color):
        colordict = {'black': 0, 'red': 1, 'blue': 16, 'magenta': 17}
        self._parent._send_midi(
            self._parent.QS.set_B_color(button_id, colordict[color]))

    def _update_leds(self):
        tracks = list(self._parent.song().tracks)
        selected = self._parent.song().view.selected_track

        for i in range(16):
            btn_id = self._pad_index_to_button_id(i)
            if i < len(tracks):
                track = tracks[i]
                if track == selected:
                    color = 'red'      # selected always wins
                elif track.solo:
                    color = 'magenta'  # soloed but not selected
                else:
                    color = 'blue'     # exists
            else:
                color = 'black'
            self._set_color(btn_id, color)

        # Recall button = blue = mix mode indicator
        self._set_color('recall', 'blue')

    def _pad_index_to_button_id(self, pad_index):
        """
        PAD_MSG_IDS = CC 44-51 (pad_index 0-7) + CC 36-43 (pad_index 8-15)
        QSetup button IDs:  pads 1-8 -> IDs 1-8, pads 9-16 -> IDs 9-16
        Physical top row = pads 1-8 = CC 44-51 = pad_index 0-7 -> IDs 1-8 (NOT 9-16!)
        The QSetup._B dict: button i -> 111+i, so button 1 -> sysex ID 112... 
        Actually QSetup.set_B_color(ID, val) where ID is 1-16 directly.
        Pads 1-8 (top row, CC 44-51) = pad_index 0-7 -> button ID 1-8 in QSetup
        Pads 9-16 (bottom row, CC 36-43) = pad_index 8-15 -> button ID 9-16
        """
        return pad_index + 1

    # ── Helpers ────────────────────────────────────────────────────────────

    def _get_rack(self, track):
        """Return first device with can_have_chains (Instrument/Audio Rack)."""
        for device in track.devices:
            if getattr(device, 'can_have_chains', False):
                return device
        return None

    # ── Cleanup ────────────────────────────────────────────────────────────

    def disconnect(self):
        song = self._parent.song()
        try:
            song.view.remove_selected_track_listener(self._update_leds)
        except Exception:
            pass
        try:
            song.remove_tracks_listener(self._update_leds)
        except Exception:
            pass
        try:
            song.remove_visible_tracks_listener(self._update_leds)
        except Exception:
            pass
