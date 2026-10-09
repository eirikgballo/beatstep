"""
RackMode — encoders 1–16 control macros 1–16 of the first Audio Effect Rack on the selected track.
It also gives the pads access to the rack's macro variations (the variation picker, see TrackPads).
"""

from .Encoders import feel, turn


class RackMode:

    name = 'Rack'
    arms_on_select = True

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

    def variations(self):
        """(number of macro variations, index of the selected one) for the rack on the selected track.
        (0, -1) without a rack."""
        rack = self._find_rack()
        if rack is None:
            return 0, -1
        return rack.variation_count, rack.selected_variation_index

    def recall_variation(self, index):
        """Recall macro variation `index` (0-based), like a click on it in Live."""
        rack = self._find_rack()
        if rack is None:
            self._show_message('No Audio Effect Rack on selected track')
        elif index >= rack.variation_count:
            self._show_message('Variation %d is empty' % (index + 1))
        else:
            rack.selected_variation_index = index
            rack.recall_selected_variation()

    def on_encoder(self, encoder_index, value, reset=False):
        delta = self._accelerator.delta(encoder_index, value, feel('rack'))
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
        turn(params[macro_index], delta, reset)
