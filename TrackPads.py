"""
TrackPads — the pads in every mode.

  - Pad 0-15: select tracks on the current page (shift + pad toggles solo, see BeatStep)
  - Track paging, 16 tracks per page
  - Pad LEDs, including the red/magenta blink for a selected + soloed track
  - The variation picker: the pads recall the macro variations of the rack on the selected track
"""

import time

from . import Sysex

BLINK_INTERVAL = 0.3   # seconds per blink phase for solo pads
# The warning blinks all 16 pads, so it gets a slower phase than the solo blink.
WARNING_BLINK_INTERVAL = 0.8
PADS_PER_PAGE = 16
# While stop is held, the last pad is the start of the loop and the others are markers.
LOOP_START_PAD = 15


class TrackPads:

    def __init__(self, song, show_message, send_midi):
        self._song          = song
        self._show_message  = show_message
        self._send_midi     = send_midi

        self._page = 0

        # True while the pads show the page picker instead of tracks.
        self.picking_page = False

        # True while the pads show the variation picker. `variation_source` is the RackMode, set by BeatStep.
        self.picking_variation = False
        self.variation_source = None

        # True while the BeatStep is in sequencer mode: the pads don't send notes, so instead of
        # track colors all pads blink red as a warning.
        self.suspended = False

        # True while stop is held: the pads show which markers exist (blue) and the loop start (magenta).
        # Stop + pad plays from there, see BeatStep.
        self.showing_markers = False

        # Tracks we have solo listeners on.
        self._subscribed_tracks = []

        # Blink phase for a track that is both selected and soloed (red/magenta).
        self._blink_on = True

        # Last color sent per pad. Unchanged pads are skipped: every message costs a few ms of waiting
        # in Live's main thread (see BeatStep.py), which delays the handling of the next pad event.
        self._shown = {}

        self._song.view.add_selected_track_listener(self._on_selected_track_changed)
        self._song.add_tracks_listener(self._on_tracks_changed)
        self._setup_solo_listeners()

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    def _on_selected_track_changed(self):
        self.update_leds()

    def _on_tracks_changed(self):
        self._setup_solo_listeners()
        self.update_leds()

    def _on_solo_changed(self):
        self.update_leds()

    def _setup_solo_listeners(self):
        self._teardown_solo_listeners()
        for track in self._song.tracks:
            track.add_solo_listener(self._on_solo_changed)
        self._subscribed_tracks = list(self._song.tracks)

    def _teardown_solo_listeners(self):
        for track in self._subscribed_tracks:
            try:
                track.remove_solo_listener(self._on_solo_changed)
            except Exception:
                pass
        self._subscribed_tracks = []

    # ------------------------------------------------------------------
    # LED output
    # ------------------------------------------------------------------

    def update_leds(self, force=False):
        """Paint the pads. `force` also resends unchanged colors, for when the firmware has painted over them."""
        for pad_index in range(16):
            self._send_pad_led(pad_index, force)

    def _send_pad_led(self, pad_index, force=False, urgent=False):
        color = self._pad_color(pad_index)
        if not force and self._shown.get(pad_index) == color:
            return
        self._shown[pad_index] = color
        self._send_midi(Sysex.set_pad_color(pad_index, color), urgent)

    def _pad_color(self, pad_index):
        if self.suspended:
            return Sysex.COLOR_RED if self._blink_on else Sysex.COLOR_OFF
        if self.showing_markers:
            if pad_index == LOOP_START_PAD:
                return Sysex.COLOR_MAGENTA
            return Sysex.COLOR_BLUE if pad_index < len(self._song.cue_points) else Sysex.COLOR_OFF
        if self.picking_variation:
            # Magenta and not blue, so the picker can't be mistaken for the tracks.
            count, selected = self.variation_source.variations()
            if pad_index == selected:
                return Sysex.COLOR_RED
            return Sysex.COLOR_MAGENTA if pad_index < count else Sysex.COLOR_OFF
        if self.picking_page:
            if pad_index == self._page:
                return Sysex.COLOR_RED
            if pad_index < self._page_count():
                return Sysex.COLOR_BLUE
            return Sysex.COLOR_OFF

        track = self._track_for_pad(pad_index)

        if track is None:
            color = Sysex.COLOR_OFF
        # == and not `is`: Live hands out a new Python object for the same track on every access.
        elif track == self._song.view.selected_track:
            if getattr(track, 'solo', False) and not self._blink_on:
                color = Sysex.COLOR_MAGENTA
            else:
                color = Sysex.COLOR_RED
        elif getattr(track, 'solo', False):
            color = Sysex.COLOR_MAGENTA if self._blink_on else Sysex.COLOR_OFF
        else:
            color = Sysex.COLOR_BLUE
        return color

    def tick(self):
        """Called every ~100 ms from update_display. Drives the solo blink and the sequencer mode warning."""
        interval = WARNING_BLINK_INTERVAL if self.suspended else BLINK_INTERVAL
        blink_on = int(time.monotonic() / interval) % 2 == 0
        if blink_on == self._blink_on:
            return
        self._blink_on = blink_on
        if self.suspended:
            self.update_leds()
            return
        if self.picking_variation:
            # No listeners on the variations: follow what is stored, deleted or chosen in Live from here.
            self.update_leds()
            return
        if self.picking_page:
            return
        for pad_index in range(PADS_PER_PAGE):
            if getattr(self._track_for_pad(pad_index), 'solo', False):
                self._send_pad_led(pad_index)

    # ------------------------------------------------------------------
    # Track helpers
    # ------------------------------------------------------------------

    def _track_for_pad(self, pad_index):
        """Return the Live track for pad 0-15 on the current page, or None."""
        track_index = self._page * PADS_PER_PAGE + pad_index
        tracks = self._song.tracks
        if track_index < len(tracks):
            return tracks[track_index]
        return None

    # ------------------------------------------------------------------
    # Pad input
    # ------------------------------------------------------------------

    def on_pad_press(self, pad_index):
        if self.picking_variation:
            self.variation_source.recall_variation(pad_index)
            self.update_leds()
            return
        if self.picking_page:
            self._go_to_page(pad_index)
            return

        track = self._track_for_pad(pad_index)
        if track is None:
            return

        self._song.view.selected_track = track

    def toggle_solo(self, pad_index):
        """Toggle solo on the pad's track without selecting it (shift + pad). Ignored in the page picker."""
        track = self._track_for_pad(pad_index)
        if self.picking_page or self.picking_variation or track is None:
            return
        track.solo = not track.solo

    def on_pad_release(self, pad_index):
        # The firmware turns the pad off on release, so the color must be sent again, and right away:
        # until it arrives the pad is dark.
        self._send_pad_led(pad_index, force=True, urgent=True)

    # ------------------------------------------------------------------
    # Paging
    # ------------------------------------------------------------------

    @property
    def page(self):
        """Current page, 0-indexed. Modes use it to pick their tracks."""
        return self._page

    def _page_count(self):
        return max(1, -(-len(self._song.tracks) // PADS_PER_PAGE))  # ceil division, at least one page

    def toggle_page_picker(self):
        """Enter or leave the page picker, where pad N chooses page N."""
        self.picking_page = not self.picking_page
        self.picking_variation = False
        self.update_leds()

    def toggle_variation_picker(self):
        """Enter or leave the variation picker, where pad N recalls macro variation N. It stays open
        after a choice, so variations can be compared."""
        self.picking_variation = not self.picking_variation
        self.picking_page = False
        self.update_leds()

    def close_variation_picker(self):
        if self.picking_variation:
            self.picking_variation = False
            self.update_leds()

    def _go_to_page(self, page):
        """Show page `page` (0-indexed) and leave the picker. Empty pages are refused and the picker stays open."""
        if page >= self._page_count():
            self._show_message('Page %d is empty' % (page + 1))
            return
        self._page = page
        self.picking_page = False
        self.update_leds()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        try:
            self._song.view.remove_selected_track_listener(self._on_selected_track_changed)
        except Exception:
            pass
        try:
            self._song.remove_tracks_listener(self._on_tracks_changed)
        except Exception:
            pass
        self._teardown_solo_listeners()
        for pad_index in range(16):
            self._send_midi(Sysex.set_pad_color(pad_index, Sysex.COLOR_OFF))
