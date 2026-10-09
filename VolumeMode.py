"""
VolumeMode — encoders 1–16 control the volume of the 16 tracks on the current pad page.
Encoder N always belongs to the same track as pad N.
"""

from .Encoders import feel, turn


class VolumeMode:

    name = 'Volume'
    arms_on_select = False

    def __init__(self, song, pads, accelerator):
        self._song          = song
        self._pads          = pads
        self._accelerator   = accelerator

    def on_encoder(self, encoder_index, value, reset=False):
        delta = self._accelerator.delta(encoder_index, value, feel('volume'))
        if delta is None:
            return
        track = self._pads.track_for_pad(encoder_index)
        if track is not None:
            turn(track.mixer_device.volume, delta, reset)
