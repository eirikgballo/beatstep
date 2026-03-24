"""
CMix — Mix Mode component.

Responsibilities:
  - Pad 0-14: select regular tracks (with double-tap solo)
  - Pad 15: select master track
  - Shift+Recall: advance track page (wraps)
"""

import time

DOUBLE_TAP_MS = 0.400  # seconds

# ---------------------------------------------------------------------------
# Macro encoder feel (the 16 knobs → Audio Effect Rack macros)
# ---------------------------------------------------------------------------

# Minimum step per tick as a fraction of the parameter's full range.
# Applied when turning very slowly. Lower = finer slow-turn resolution.
ENCODER_MIN_STEP = 0.002

# Maximum step per tick as a fraction of the parameter's full range.
# Applied when turning at full speed. Raise to sweep faster; lower for finer fast control.
ENCODER_MAX_STEP = 0.05

# Acceleration curve exponent. Controls how aggressively fast turns are boosted.
#   1.0 = linear (no real acceleration — fast and slow feel the same)
#   2.0 = quadratic (noticeable but gentle — good starting point)
#   3.0 = aggressive (fast spin is very fast, slow spin is very fine)
# The BeatStep always sends the same magnitude per tick regardless of speed, so
# acceleration here is based on TIME between ticks: fast spin = short interval.
ENCODER_ACCELERATION = 2.0

# Tick interval thresholds (seconds). Ticks arriving faster than FAST_INTERVAL
# get full MAX_STEP; ticks slower than SLOW_INTERVAL get only MIN_STEP.
# Typical ranges: fast spin ~0.03–0.06 s/tick, slow spin ~0.2–0.5 s/tick.
# FAST_INTERVAL is the most impactful constant: lower it if fast spins feel
# sluggish, raise it if acceleration kicks in too easily.
ENCODER_FAST_INTERVAL = 0.06   # s — at or below this → full speed
ENCODER_SLOW_INTERVAL = 0.30   # s — at or above this → minimum speed

# ---------------------------------------------------------------------------
# Transpose encoder feel (large knob → volume of selected track)
# ---------------------------------------------------------------------------

TRANSPOSE_MIN_STEP      = 0.005  # larger min than macros for a smoother, less laggy feel
TRANSPOSE_MAX_STEP      = 0.08
TRANSPOSE_ACCELERATION  = 1.5    # gentler curve — volume should feel linear-ish
TRANSPOSE_FAST_INTERVAL = 0.05   # s — tighter window so fast spins register sooner
TRANSPOSE_SLOW_INTERVAL = 0.25   # s


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

        # Last-tick timestamps for time-based encoder acceleration.
        # Key: encoder index (0-15) or 'transpose'.
        self._enc_last_tick = {}

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

    def _encoder_delta(self, key, value, transpose=False):
        """
        Return a signed step fraction for a relative mode-2 CC value, or None if neutral.
        Step magnitude is time-based: fast spin (ticks close together) → larger step.
        key: encoder index 0-15, or 'transpose'.
        transpose: use the transpose encoder constants instead of the macro constants.
        """
        if value == 0 or value == 64:
            return None
        direction = 1 if value < 64 else -1

        now = time.time()
        dt = now - self._enc_last_tick.get(key, now)
        self._enc_last_tick[key] = now

        if transpose:
            fast, slow = TRANSPOSE_FAST_INTERVAL, TRANSPOSE_SLOW_INTERVAL
            min_step, max_step, accel = TRANSPOSE_MIN_STEP, TRANSPOSE_MAX_STEP, TRANSPOSE_ACCELERATION
        else:
            fast, slow = ENCODER_FAST_INTERVAL, ENCODER_SLOW_INTERVAL
            min_step, max_step, accel = ENCODER_MIN_STEP, ENCODER_MAX_STEP, ENCODER_ACCELERATION

        velocity = max(0.0, min(1.0, (slow - dt) / (slow - fast)))
        step = min_step + (velocity ** accel) * max_step
        return direction * step

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
        delta = self._encoder_delta(encoder_index, value)
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
        span = param.max - param.min
        param.value = max(param.min, min(param.max, param.value + delta * span))

    def on_transpose_encoder(self, value):
        """Transpose encoder → volume of the selected track."""
        delta = self._encoder_delta('transpose', value, transpose=True)
        if delta is None:
            return
        track = self._song.view.selected_track
        if track is None:
            return
        vol = track.mixer_device.volume
        span = vol.max - vol.min
        vol.value = max(vol.min, min(vol.max, vol.value + delta * span))

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
