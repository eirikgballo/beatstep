"""
RackMode — encoders 1–16 control macros 1–16 of the first Audio Effect Rack on the selected track.
"""

from .Encoders import KNOB_FEEL, nudge


class RackMode:

    def __init__(self, song, show_message, accelerator):
        self._song          = song
        self._show_message  = show_message
        self._accelerator   = accelerator

    def _find_rack(self):
        """First Audio Effect Rack on the selected track, or None.
        Looked up on every use so added or deleted racks are picked up immediately."""
        track = self._song.view.selected_track
        if track is not None:
            for device in track.devices:
                if device.class_name == 'AudioEffectGroupDevice':
                    return device
        return None

    def on_encoder(self, encoder_index, value):
        delta = self._accelerator.delta(encoder_index, value, KNOB_FEEL)
        if delta is None:
            return
        rack = self._find_rack()
        if rack is None:
            self._show_message('No Audio Effect Rack on selected track')
            return
        macro_index = encoder_index + 1  # parameters[0] is the device on/off toggle
        params = rack.parameters
        if macro_index >= len(params):
            self._show_message('Macro %d not available' % (encoder_index + 1))
            return
        nudge(params[macro_index], delta)
