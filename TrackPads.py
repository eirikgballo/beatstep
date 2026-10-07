"""
TrackPads — the pads in every mode.

  - Pad 0-15: select tracks on the current page (shift + pad toggles solo, see BeatStep)
  - Track paging, 16 tracks per page
  - Pad LEDs, including the red/magenta blink for a selected + soloed track
"""

import time

from . import Sysex

BLINK_INTERVAL = 0.3   # seconds per blink phase (solo pads and the sequencer mode warning)
PADS_PER_PAGE = 16


class TrackPads:

    def __init__(self, song, show_message, send_midi):
        self._song          = song
        self._show_message  = show_message
        self._send_midi     = send_midi

        self._page = 0

        # True while the pads show the page picker instead of tracks.
        self.picking_page = False

        # True while the BeatStep is in sequencer mode: the pads don't send notes, so instead of
        # track colors all pads blink red as a warning.
        self.suspended = False

        # Tracks we have solo listeners on.
        self._subscribed_tracks = []

        # Blink phase for a track that is both selected and soloed (red/magenta).
        self._blink_on = True

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

    def update_leds(self):
        for pad_index in range(16):
            self._send_pad_led(pad_index)

    def _send_pad_led(self, pad_index):
        if self.suspended:
            color = Sysex.COLOR_RED if self._blink_on else Sysex.COLOR_OFF
            self._send_midi(Sysex.set_pad_color(pad_index, color))
            return
        if self.picking_page:
            if pad_index == self._page:
                color = Sysex.COLOR_RED
            elif pad_index < self._page_count():
                color = Sysex.COLOR_BLUE
            else:
                color = Sysex.COLOR_OFF
            self._send_midi(Sysex.set_pad_color(pad_index, color))
            return

        track = self._track_for_pad(pad_index)

        if track is None:
            color = Sysex.COLOR_OFF
        elif track is self._song.view.selected_track:
            if getattr(track, 'solo', False) and not self._blink_on:
                color = Sysex.COLOR_MAGENTA
            else:
                color = Sysex.COLOR_RED
        elif getattr(track, 'solo', False):
            color = Sysex.COLOR_MAGENTA if self._blink_on else Sysex.COLOR_OFF
        else:
            color = Sysex.COLOR_BLUE

        self._send_midi(Sysex.set_pad_color(pad_index, color))

    def tick(self):
        """Called every ~100 ms from update_display. Drives the solo blink and the sequencer mode warning."""
        blink_on = int(time.monotonic() / BLINK_INTERVAL) % 2 == 0
        if blink_on == self._blink_on:
            return
        self._blink_on = blink_on
        if self.suspended:
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
        if self.picking_page or track is None:
            return
        track.solo = not track.solo

    def on_pad_release(self, pad_index):
        # The firmware turns the pad off on release, so the color must be sent again.
        self._send_pad_led(pad_index)

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
