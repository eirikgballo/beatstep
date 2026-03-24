"""
CMix — Mix Mode component.

Responsibilities:
  - Pad 0-14: select regular tracks (with double-tap solo)
  - Pad 15: select master track
  - Shift+Recall: advance track page (wraps)
"""

import time

DOUBLE_TAP_MS = 0.400  # seconds


class CMix:

    def __init__(self, song, show_message, request_rebuild_midi_map):
        self._song                      = song
        self._show_message              = show_message
        self._request_rebuild_midi_map  = request_rebuild_midi_map

        self._page        = 0
        self._shift_held  = False

        # Double-tap state: pad_index -> (timestamp, track_index)
        self._last_tap = {}

        # Cached Audio Effect Rack on the selected track (None if not found).
        self._current_rack = None

        self._song.view.add_selected_track_listener(self._on_selected_track_changed)
        self._scan_rack()

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    def _on_selected_track_changed(self):
        self._scan_rack()
        self._request_rebuild_midi_map()

    # ------------------------------------------------------------------
    # Rack helpers
    # ------------------------------------------------------------------

    def _scan_rack(self):
        """Cache the first Audio Effect Rack on the selected track."""
        track = self._song.view.selected_track
        if track is not None:
            for device in track.devices:
                if device.class_name == 'AudioEffectGroupDevice':
                    self._current_rack = device
                    return
        self._current_rack = None

    @staticmethod
    def _encoder_delta(value):
        """
        Decode a relative mode-1 CC value into a signed, accelerated step.
        Returns None for neutral values (0 or 64).
        CW  (1–63):  positive delta, slow≈0.002, fast≈0.020
        CCW (65–127): negative delta, same magnitude
        """
        if value == 0 or value == 64:
            return None
        raw = value if value < 64 else -(128 - value)
        magnitude = abs(raw)
        step = 0.002 + (magnitude / 63.0) * 0.018
        return step if raw > 0 else -step

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

    # ------------------------------------------------------------------
    # Encoder input
    # ------------------------------------------------------------------

    def on_encoder(self, encoder_index, value):
        """Encoder 0–15 → macro 1–16 on the first Audio Effect Rack."""
        delta = self._encoder_delta(value)
        if delta is None:
            return
        if self._current_rack is None:
            self._show_message('No Audio Effect Rack on selected track')
            return
        macro_index = encoder_index + 1  # parameters[0] is the device on/off toggle
        params = self._current_rack.parameters
        if macro_index >= len(params):
            self._show_message('Macro %d not available' % (encoder_index + 1))
            return
        param = params[macro_index]
        param.value = max(0.0, min(1.0, param.value + delta))

    def on_transpose_encoder(self, value):
        """Transpose encoder → volume of the selected track."""
        delta = self._encoder_delta(value)
        if delta is None:
            return
        track = self._song.view.selected_track
        if track is None:
            return
        vol = track.mixer_device.volume
        vol.value = max(0.0, min(1.0, vol.value + delta))

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
            return

        track = self._track_for_pad(pad_index)
        if track is None:
            return

        track_index = self._page * 15 + pad_index
        last_time, last_index = self._last_tap.get(pad_index, (0, -1))
        if now - last_time < DOUBLE_TAP_MS and last_index == track_index:
            # Second tap within window: toggle solo
            track.solo = not track.solo
            self._last_tap[pad_index] = (0, -1)
        else:
            # First tap: select track
            self._song.view.selected_track = track
            self._last_tap[pad_index] = (now, track_index)

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

    # ------------------------------------------------------------------
    # Paging
    # ------------------------------------------------------------------

    def _advance_page(self):
        tracks   = self._song.tracks
        n_pages  = max(1, -(-len(tracks) // 15))  # ceil division
        self._page = (self._page + 1) % n_pages

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        try:
            self._song.view.remove_selected_track_listener(self._on_selected_track_changed)
        except Exception:
            pass
