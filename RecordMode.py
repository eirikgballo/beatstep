"""
RecordMode — the pads become recording actions, the encoders keep controlling the macros.

  pad 1  arrangement record on/off (blinks red while on). It only arms the recording, it doesn't start playback
  pad 2  undo
  pad 3  redo
  pad 4  metronome on/off (red while on)
  pad 5  marker at the needle: add one, or remove the one that is there (red while the needle is on a marker)
  pad 6  loop on/off (red while on)
  pad 7  set the loop start at the needle
  pad 8  set the loop end at the needle
  pad 9  zoom in on the arrangement, pad 10 zoom out
  pad 11 pan the arrangement left, pad 12 right, pad 13 up, pad 14 down (needs the scroll helper)

Shift + pad selects a track in this mode, see BeatStep.
"""

from . import Sysex

PAD_RECORD, PAD_UNDO, PAD_REDO, PAD_METRONOME, PAD_MARKER, PAD_LOOP, PAD_LOOP_START, PAD_LOOP_END = range(8)
# Pad → what it does to the arrangement view (see BeatStep._move_arrangement_view).
VIEW_PADS = {8: 'zoom in', 9: 'zoom out', 10: 'left', 11: 'right', 12: 'up', 13: 'down'}


class RecordMode:

    name = 'Record'
    arms_on_select = True

    def __init__(self, song, show_message, rack_mode, move_view):
        self._song          = song
        self._show_message  = show_message
        self._rack_mode     = rack_mode
        self._move_view     = move_view

    def on_encoder(self, encoder_index, value, reset=False):
        self._rack_mode.on_encoder(encoder_index, value, reset)

    def pad_color(self, pad_index, blink_on):
        """Blue = the action is available, red = it is switched on. Record blinks while it is on."""
        song = self._song
        if pad_index == PAD_RECORD:
            if not song.record_mode:
                return Sysex.COLOR_BLUE
            return Sysex.COLOR_RED if blink_on else Sysex.COLOR_OFF
        if pad_index == PAD_UNDO:
            return Sysex.COLOR_BLUE if song.can_undo else Sysex.COLOR_OFF
        if pad_index == PAD_REDO:
            return Sysex.COLOR_BLUE if song.can_redo else Sysex.COLOR_OFF
        if pad_index == PAD_LOOP:
            return Sysex.COLOR_RED if song.loop else Sysex.COLOR_BLUE
        if pad_index == PAD_METRONOME:
            return Sysex.COLOR_RED if song.metronome else Sysex.COLOR_BLUE
        if pad_index == PAD_MARKER:
            on_marker = any(abs(cue.time - song.current_song_time) < 0.001 for cue in song.cue_points)
            return Sysex.COLOR_RED if on_marker else Sysex.COLOR_BLUE
        if pad_index in (PAD_LOOP_START, PAD_LOOP_END):
            return Sysex.COLOR_BLUE
        if pad_index in VIEW_PADS:
            # Zoom magenta, panning blue, so the two groups can be told apart.
            return Sysex.COLOR_MAGENTA if VIEW_PADS[pad_index].startswith('zoom') else Sysex.COLOR_BLUE
        return Sysex.COLOR_OFF

    def on_pad(self, pad_index):
        song = self._song
        if pad_index == PAD_RECORD:
            song.record_mode = not song.record_mode
        elif pad_index == PAD_UNDO:
            if song.can_undo:
                song.undo()
            else:
                self._show_message('Nothing to undo')
        elif pad_index == PAD_REDO:
            if song.can_redo:
                song.redo()
            else:
                self._show_message('Nothing to redo')
        elif pad_index == PAD_LOOP:
            song.loop = not song.loop
        elif pad_index == PAD_METRONOME:
            song.metronome = not song.metronome
        elif pad_index == PAD_MARKER:
            song.set_or_delete_cue()  # Live's own toggle: it works on the needle
        elif pad_index == PAD_LOOP_START:
            self._set_loop_start(song.current_song_time)
        elif pad_index == PAD_LOOP_END:
            self._set_loop_end(song.current_song_time)
        elif pad_index in VIEW_PADS:
            self._move_view(VIEW_PADS[pad_index])

    def _set_loop_start(self, time):
        """Move the loop start and keep the end where it is. At or past the end the whole loop moves."""
        song = self._song
        end = song.loop_start + song.loop_length
        song.loop_start = time
        if time < end:
            song.loop_length = end - time

    def _set_loop_end(self, time):
        song = self._song
        if time <= song.loop_start:
            self._show_message('The loop end must be after the loop start')
            return
        song.loop_length = time - song.loop_start
