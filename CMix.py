"""
CMix — Mix Mode component.

Responsibilities:
  - Pad 0-14: select regular tracks (with double-tap solo)
  - Pad 15: select master track
  - Encoders 0-15: control macros 1-16 of the first Audio Effect Rack on
    the selected track
  - Transpose encoder: control volume of the selected track
  - Shift+Recall: advance track page (wraps)
  - LED management: reacts to track selection, solo, and track list changes
"""

import time

from . import QSetup

# ---------------------------------------------------------------------------
# Sensitivity constants  (calibrate against real hardware after deployment)
# ---------------------------------------------------------------------------
ENCODER_CLICKS_PER_ROTATION = 24   # physical detents for one full rotation
ENCODER_SENSITIVITY         = 1.0  # multiplier; >1 = faster, <1 = slower

DOUBLE_TAP_MS = 0.400  # seconds


class CMix:

    def __init__(self, song, send_led, show_message):
        self._song         = song
        self._send_led     = send_led       # fn(hw_index, color)
        self._show_message = show_message   # fn(text)

        self._page        = 0
        self._shift_held  = False

        # LED state cache: only send sysex when color changes (BeatStep drops rapid bursts)
        self._led_state = [None] * 17

        # Double-tap state: pad_index -> (timestamp, track)
        self._last_tap = {}

        # Solo listeners: list of (track, listener_fn) to allow cleanup
        self._solo_listeners = []

        self._song.add_tracks_listener(self._on_tracks_changed)
        self._song.view.add_selected_track_listener(self._on_selected_track_changed)
        self._rebuild_solo_listeners()

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    def _rebuild_solo_listeners(self):
        for track, fn in self._solo_listeners:
            try:
                track.remove_solo_listener(fn)
            except Exception:
                pass
        self._solo_listeners = []
        for track in self._song.tracks:
            fn = self._make_solo_listener()
            track.add_solo_listener(fn)
            self._solo_listeners.append((track, fn))

    def _make_solo_listener(self):
        def _listener():
            self.update_leds()
        return _listener

    def _on_tracks_changed(self):
        self._rebuild_solo_listeners()
        self.update_leds()

    def _on_selected_track_changed(self):
        self.update_leds()

    # ------------------------------------------------------------------
    # Track helpers
    # ------------------------------------------------------------------

    def _track_for_pad(self, pad_index):
        """Return the Live track for pad 0-14, or None."""
        track_index = self._page * 15 + pad_index
        tracks = self._song.tracks
        if track_index < len(tracks):
            return tracks[track_index]
        return None

    def _pad_color(self, pad_index):
        """Return the LED color for a regular-track pad (0-14)."""
        track = self._track_for_pad(pad_index)
        if track is None:
            return QSetup.OFF
        selected = self._song.view.selected_track
        if track == selected:
            return QSetup.RED
        if track.solo:
            return QSetup.MAGENTA
        return QSetup.BLUE

    # ------------------------------------------------------------------
    # LED update
    # ------------------------------------------------------------------

    def _set_led(self, index, color):
        """Send LED sysex only if color has changed since last send."""
        if self._led_state[index] != color:
            self._led_state[index] = color
            self._send_led(index, color)

    def paint_led(self, index):
        """Force-send the current desired color for one LED, bypassing the delta cache.
        Used during the staggered initial paint from Beatstep_Q."""
        if index == QSetup.RECALL_LED_INDEX:
            color = QSetup.BLUE if self._page == 0 else QSetup.MAGENTA
        elif index == 15:
            master   = self._song.master_track
            selected = self._song.view.selected_track
            color = QSetup.RED if selected == master else QSetup.BLUE
        else:
            color = self._pad_color(index)
        self._led_state[index] = color
        self._send_led(index, color)

    def update_leds(self):
        # Pads 0-14: regular tracks
        for i in range(15):
            self._set_led(i, self._pad_color(i))

        # Pad 15: master track
        master   = self._song.master_track
        selected = self._song.view.selected_track
        self._set_led(15, QSetup.RED if selected == master else QSetup.BLUE)

        # Recall button LED: blue on page 1, magenta on page 2+
        recall_color = QSetup.BLUE if self._page == 0 else QSetup.MAGENTA
        self._set_led(QSetup.RECALL_LED_INDEX, recall_color)

    # ------------------------------------------------------------------
    # Pad input
    # ------------------------------------------------------------------

    def on_pad_press(self, pad_index):
        now = time.time()

        if pad_index == 15:
            # Master track
            last_time, _ = self._last_tap.get(15, (0, None))
            if now - last_time < DOUBLE_TAP_MS:
                self._show_message("Master can't be solo'ed")
                self._last_tap[15] = (0, None)
            else:
                self._song.view.selected_track = self._song.master_track
                self._last_tap[15] = (now, self._song.master_track)
                self.update_leds()
            return

        track = self._track_for_pad(pad_index)
        if track is None:
            return

        last_time, last_track = self._last_tap.get(pad_index, (0, None))
        if now - last_time < DOUBLE_TAP_MS and last_track is track:
            # Second tap within window: toggle solo
            track.solo = not track.solo
            self._last_tap[pad_index] = (0, None)
        else:
            # First tap: select track
            self._song.view.selected_track = track
            self._last_tap[pad_index] = (now, track)
            self.update_leds()

    # ------------------------------------------------------------------
    # Encoder input
    # ------------------------------------------------------------------

    @staticmethod
    def _raw_to_delta(raw):
        """Convert BeatStep relative mode 2 raw CC value to signed integer delta."""
        return raw - 64  # 65 -> +1, 63 -> -1, 64 -> 0

    def on_encoder_turn(self, enc_index, raw_value):
        """enc_index 0-15."""
        delta = self._raw_to_delta(raw_value)
        if delta == 0:
            return

        track = self._song.view.selected_track
        rack  = self._find_rack(track)

        if rack is None:
            self._show_message("No rack on track")
            return

        macro_num = enc_index + 1  # 1-based for user-facing message
        # parameters[0] = Device On; macros start at index 1
        if len(rack.parameters) <= enc_index + 1:
            self._show_message("Nothing assigned to macro %d" % macro_num)
            return

        param = rack.parameters[enc_index + 1]
        step  = delta * ENCODER_SENSITIVITY / ENCODER_CLICKS_PER_ROTATION
        param.value = max(0.0, min(1.0, param.value + step))

    def on_transpose_turn(self, raw_value):
        """Transpose encoder: always controls volume of selected track."""
        delta = self._raw_to_delta(raw_value)
        if delta == 0:
            return
        vol  = self._song.view.selected_track.mixer_device.volume
        step = delta * ENCODER_SENSITIVITY / ENCODER_CLICKS_PER_ROTATION
        vol.value = max(0.0, min(1.0, vol.value + step))

    # ------------------------------------------------------------------
    # Function button input
    # ------------------------------------------------------------------

    def on_shift_press(self):
        self._shift_held = True

    def on_shift_release(self):
        self._shift_held = False

    def on_recall_press(self):
        if self._shift_held:
            self._advance_page()
        else:
            self.update_leds()

    # ------------------------------------------------------------------
    # Paging
    # ------------------------------------------------------------------

    def _advance_page(self):
        tracks   = self._song.tracks
        n_pages  = max(1, -(-len(tracks) // 15))  # ceil division
        self._page = (self._page + 1) % n_pages
        self.update_leds()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_rack(track):
        for device in track.devices:
            if device.class_name == 'AudioEffectGroupDevice':
                return device
        return None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        try:
            self._song.remove_tracks_listener(self._on_tracks_changed)
        except Exception:
            pass
        try:
            self._song.view.remove_selected_track_listener(self._on_selected_track_changed)
        except Exception:
            pass
        for track, fn in self._solo_listeners:
            try:
                track.remove_solo_listener(fn)
            except Exception:
                pass
        self._solo_listeners = []
