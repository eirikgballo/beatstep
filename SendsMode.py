"""
SendsMode — encoders 1–8 control send A, encoders 9–16 send B, of the same 8 tracks.

Sends has its own 8-track paging: pad page P covers tracks 8·(P−1)+1 … 8·P here,
while the pads show 16 tracks per page. See DESIGN.md.
"""

from .Encoders import KNOB_FEEL, nudge

TRACKS_PER_PAGE = 8


class SendsMode:

    name = 'Sends'

    def __init__(self, song, pads, accelerator):
        self._song          = song
        self._pads          = pads
        self._accelerator   = accelerator

    def on_encoder(self, encoder_index, value):
        delta = self._accelerator.delta(encoder_index, value, KNOB_FEEL)
        if delta is None:
            return
        track_index = self._pads.page * TRACKS_PER_PAGE + encoder_index % TRACKS_PER_PAGE
        send_index = encoder_index // TRACKS_PER_PAGE  # 0 = send A, 1 = send B
        tracks = self._song.tracks
        if track_index >= len(tracks):
            return
        sends = tracks[track_index].mixer_device.sends
        if send_index < len(sends):
            nudge(sends[send_index], delta)
