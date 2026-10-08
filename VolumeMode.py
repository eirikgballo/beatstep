"""
VolumeMode — encoders 1–16 control the volume of the 16 tracks on the current pad page.
Encoder N always belongs to the same track as pad N.
"""

from .Encoders import KNOB_FEEL, turn
from .TrackPads import PADS_PER_PAGE


class VolumeMode:

    name = 'Volume'

    def __init__(self, song, pads, accelerator):
        self._song          = song
        self._pads          = pads
        self._accelerator   = accelerator

    def on_encoder(self, encoder_index, value, reset=False):
        delta = self._accelerator.delta(encoder_index, value, KNOB_FEEL)
        if delta is None:
            return
        track_index = self._pads.page * PADS_PER_PAGE + encoder_index
        tracks = self._song.tracks
        if track_index < len(tracks):
            turn(tracks[track_index].mixer_device.volume, delta, reset)
