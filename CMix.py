"""
CMix — Mix Mode component.

Responsibilities:
  - Pad 0-14: select regular tracks (with double-tap solo)
  - Pad 15: select master track
  - Encoders 0-15: control macros 1-16 of the first Audio Effect Rack on
    the selected track
  - Transpose encoder: control volume of the selected track
  - Shift+Recall: advance track page (wraps)
"""

import time

# ---------------------------------------------------------------------------
# Sensitivity constants  (calibrate against real hardware after deployment)
# ---------------------------------------------------------------------------
# Encoder feel — adjust these to taste:
#   ENCODER_SENSITIVITY:  step size per single slow click (delta=1).
#                         0.005 → ~200 slow clicks sweeps full range.
#                         Increase to make slow turns coarser.
#   ENCODER_ACCELERATION: exponent applied to speed. 1.0 = linear (every click
#                         the same size). 1.5 = fast turns are disproportionately
#                         larger, giving fine control when slow + quick sweep when fast.
ENCODER_SENSITIVITY   = 0.005   # ~200 slow clicks to sweep full range
ENCODER_ACCELERATION  = 1.0

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

        self._song.view.add_selected_track_listener(self._on_selected_track_changed)

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    def _on_selected_track_changed(self):
        self._request_rebuild_midi_map()

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
    # Encoder MIDI map
    # ------------------------------------------------------------------

    def on_encoder_turn(self, encoder_index, raw_value):
        """Handle encoder CC from receive_midi. Expects two's-complement relative values."""
        track = self._song.view.selected_track
        rack  = self._find_rack(track)
        if rack is None:
            return
        param_index = encoder_index + 1  # parameters[0] = Device On; macros start at 1
        if param_index >= len(rack.parameters):
            return
        param  = rack.parameters[param_index]
        # Two's-complement relative decoding (BeatStep relative mode 2):
        #   CW:  raw 1–63  → +1 to +63
        #   CCW: raw 65–127 → -63 to -1  (127 = -1, 65 = -63)
        delta  = raw_value if raw_value < 64 else raw_value - 128
        speed  = abs(delta)
        step   = (speed ** ENCODER_ACCELERATION) * ENCODER_SENSITIVITY * (param.maximum - param.minimum)
        param.value = max(param.minimum, min(param.maximum, param.value + (step if delta > 0 else -step)))

    # ------------------------------------------------------------------
    # Encoder input
    # ------------------------------------------------------------------

    def on_transpose_turn(self, raw_value):
        """Transpose encoder: always controls volume of selected track."""
        delta = raw_value if raw_value < 64 else raw_value - 128
        if delta == 0:
            return
        speed = abs(delta)
        vol   = self._song.view.selected_track.mixer_device.volume
        step  = (speed ** ENCODER_ACCELERATION) * ENCODER_SENSITIVITY * (vol.maximum - vol.minimum)
        vol.value = max(vol.minimum, min(vol.maximum, vol.value + (step if delta > 0 else -step)))

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
            self._song.view.remove_selected_track_listener(self._on_selected_track_changed)
        except Exception:
            pass
