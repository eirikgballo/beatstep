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

import Live
import time

# ---------------------------------------------------------------------------
# Sensitivity constants  (calibrate against real hardware after deployment)
# ---------------------------------------------------------------------------
ENCODER_CLICKS_PER_ROTATION = 24   # physical detents for one full rotation
ENCODER_SENSITIVITY         = 1.0  # multiplier; >1 = faster, <1 = slower

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

    def map_encoders(self, midi_map_handle, encoder_ccs):
        """Called from build_midi_map. Maps each encoder CC to a macro parameter."""
        track = self._song.view.selected_track
        rack  = self._find_rack(track)
        if rack is None:
            return
        for i, cc in enumerate(encoder_ccs):
            param_index = i + 1  # parameters[0] = Device On; macros start at 1
            if param_index >= len(rack.parameters):
                break
            Live.MidiMap.map_midi_cc(
                midi_map_handle,
                rack.parameters[param_index],
                9,   # CH10 (0-indexed)
                cc,
                Live.MidiMap.MapMode.relative_smooth_signed_bit,
                False,
            )

    # ------------------------------------------------------------------
    # Encoder input
    # ------------------------------------------------------------------

    @staticmethod
    def _raw_to_delta(raw):
        """Convert BeatStep relative mode 1 (signed bit) CC value to signed integer delta."""
        return raw if raw < 64 else raw - 128  # 1 -> +1, 127 -> -1

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
