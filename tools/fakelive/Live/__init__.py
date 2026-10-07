"""Falsk `Live`-modul: bare det BeatStep bruker."""


class MidiMap:
    """Registrerer hvilke noter/CC-er scriptet ber Live videresende til receive_midi."""

    @staticmethod
    def forward_midi_note(script_handle, midi_map_handle, channel, note):
        midi_map_handle.notes.add((channel, note))

    @staticmethod
    def forward_midi_cc(script_handle, midi_map_handle, channel, cc):
        midi_map_handle.ccs.add((channel, cc))
