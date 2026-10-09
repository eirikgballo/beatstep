"""
BeatStep — MIDI Remote Script for the Arturia BeatStep.

Owns the hardware setup, MIDI routing and the active mode. Hardware is configured via sysex on
every connection so controller state is always deterministic.

See DESIGN.md for the full specification and SIGNALS.md for measured hardware behaviour.
"""

from collections import OrderedDict
import io
import math
import os
import socket
import subprocess
import time

import Live

from _Framework.ControlSurface import ControlSurface
from _Framework import Task

from . import Sysex
from . import Encoders
from .Encoders import Accelerator, feel, turn
from .RackMode import RackMode
from .RecordMode import RecordMode
from .TrackPads import LOOP_START_PAD, TrackPads
from .VolumeMode import VolumeMode

# ---------------------------------------------------------------------------
# MIDI constants
# ---------------------------------------------------------------------------

# Everything the script uses is on CH10 after setup. The BeatStep sequencer
# sends notes on CH1, which must never reach the pad handler.
_CHANNEL         = 9
_STATUS_NOTE_ON  = 0x90 | _CHANNEL
_STATUS_NOTE_OFF = 0x80 | _CHANNEL
_STATUS_CC       = 0xB0 | _CHANNEL

# Function button CC numbers (programmed via sysex on every connection).
BTN_SHIFT_CC  = 7
BTN_RECALL_CC = 5
BTN_PLAY_CC   = 28
BTN_STOP_CC   = 29
BTN_CNTRL_CC  = 30
BTN_EXTSYNC_CC = 31
BTN_STORE_CC  = 32
BTN_CHAN_CC   = 33

# hw index → CC for every button the script configures.
_BUTTONS = [
    (Sysex.SHIFT_HW_INDEX,  BTN_SHIFT_CC),
    (Sysex.RECALL_HW_INDEX, BTN_RECALL_CC),
    (Sysex.PLAY_HW_INDEX,   BTN_PLAY_CC),
    (Sysex.STOP_HW_INDEX,   BTN_STOP_CC),
    (Sysex.CNTRL_HW_INDEX,  BTN_CNTRL_CC),
    (Sysex.EXTSYNC_HW_INDEX, BTN_EXTSYNC_CC),
    (Sysex.STORE_HW_INDEX,  BTN_STORE_CC),
    (Sysex.CHAN_HW_INDEX,   BTN_CHAN_CC),
]
_BUTTON_CCS = [cc for _, cc in _BUTTONS]

# Encoder CC numbers (programmed via sysex on every connection).
# Encoders 0–15 → CC 10–25; transpose encoder → CC 27.
ENCODER_CC_BASE  = 10
TRANSPOSE_CC     = 27

# Note numbers programmed into the hardware via sysex (note gate mode).
# Row-major: index 0–7 = top row, 8–15 = bottom row, left to right.
PAD_MSG_IDS = [
    44, 45, 46, 47, 48, 49, 50, 51,   # hw 0x70–0x77
    36, 37, 38, 39, 40, 41, 42, 43,   # hw 0x78–0x7F
]

# Set to True to log incoming MIDI (the first 50 messages) and the outgoing queue to Live's Log.txt.
DEBUG_MIDI = False

# Set to True to log where playback starts after scrubbing while stopped, and whether it had to be corrected.
DEBUG_TRANSPORT = False

# The BeatStep loses sysex that arrives less than ~1 ms apart (measured on the Mac, see SIGNALS.md),
# so the script waits this long between messages.
MIDI_MESSAGE_GAP = 0.003

# Waiting blocks Live's main thread, so messages are queued and sent at most this many per
# update_display tick (100 ms): 16 messages is about 50 ms of waiting.
MIDI_MESSAGES_PER_TICK = 16

# The user's settings file. It is read again whenever it changes, so the feel can be tuned while Live runs.
# The environment variable lets the tests point at their own file.
SETTINGS_PATH = os.environ.get('BEATSTEP_Q_SETTINGS') or os.path.join(os.path.dirname(__file__), 'Innstillinger.py')
SETTINGS_CHECK_TICKS = 10
# Where tools/scrollhjelper listens. It turns the script's messages into scroll events for Live.
SCROLL_HELPER_ADDRESS = ('127.0.0.1', 9817)
# The environment variable lets the tests run without starting the helper.
SCROLL_HELPER_PATH = os.environ.get('BEATSTEP_Q_SCROLL_HELPER') or os.path.join(
    os.path.dirname(__file__), 'tools', 'scrollhjelper', 'beatstep-scroll')
_PAN_DIRECTIONS = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}

# Reverse-lookup map built once at import time for O(1) dispatch.
_PAD_NOTE_TO_INDEX = {note: i for i, note in enumerate(PAD_MSG_IDS)}


# ---------------------------------------------------------------------------
# ControlSurface
# ---------------------------------------------------------------------------

class BeatStep(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._hw_task = None
        self._debug_count = 0
        self._last_sent = 0.0
        # Outgoing sysex, keyed by (cmd, hw index): a newer value for the same LED or setting
        # replaces the queued one, so blinking and repaints don't pile up.
        self._midi_queue = OrderedDict()
        self._shift_held = False
        self._shift_used = False  # a pad, a knob or another button was used while shift was held
        self._shift_pressed_at = 0.0
        # Shift released within this many seconds, with nothing else touched, is a tap: it switches the view.
        self._shift_tap_time = 0.4  # SHIFT_TRYKK in Innstillinger.py
        self._stop_held = False
        self._settings_mtime = None
        self._ticks = 0
        self._stop_used = False  # a pad or the transpose knob was used while stop was held
        self._stopped_target = None  # where scrubbing has put the needle while the song is stopped
        self._pan_step = 200  # pixels per press on a pan pad (PAN_STEG in Innstillinger.py)
        self._scroll_socket = None
        self._scroll_helper = None
        self._scrub_snap = 0.0  # grid for scrubbing in beats (SCRUB_SNAP in Innstillinger.py), 0 = free
        self._play_check = None
        self._seq_mode = False
        # No try/except: if a component fails, Live should show the error instead of a silent, dead controller.
        self._pads = TrackPads(
            song         = self.song(),
            show_message = self.show_message,
            send_midi    = self._queue_midi,
        )
        self._accelerator = Accelerator()
        # Mode button CC → mode. The script always boots in Rack mode.
        rack = RackMode(self.song(), self.show_message, self._accelerator)
        self._record_mode = RecordMode(self.song(), self.show_message, rack, self._move_arrangement_view)
        self._modes = {
            BTN_CHAN_CC:   rack,
            BTN_RECALL_CC: VolumeMode(self.song(), self._pads, self._accelerator),
            BTN_STORE_CC:  self._record_mode,
        }
        self._mode = rack
        self._pads.variation_source = rack
        self._load_settings(announce=False)
        self._start_scroll_helper()
        self._schedule_hardware_setup()
        self.request_rebuild_midi_map()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def port_settings_changed(self):
        ControlSurface.port_settings_changed(self)
        self._schedule_hardware_setup()

    def _start_scroll_helper(self):
        """Start the scroll helper the pan pads need (macOS, see tools/scrollhjelper). It runs as long as
        Live does. If one is already running, the new one finds the port taken and exits."""
        if not os.path.isfile(SCROLL_HELPER_PATH):
            return
        try:
            log_dir = os.path.join(os.path.dirname(__file__), 'logs')
            if not os.path.isdir(log_dir):
                os.makedirs(log_dir)
            log = open(os.path.join(log_dir, 'scrollhjelper.log'), 'w')
            self._scroll_helper = subprocess.Popen([SCROLL_HELPER_PATH, '--stopp-med-forelder'],
                                                   stdout=log, stderr=log)
            log.close()
        except Exception as error:  # the controller must work without the pan pads
            self.log_message('BeatStep: could not start the scroll helper (%s)' % error)

    def disconnect(self):
        if self._scroll_helper is not None:
            try:
                self._scroll_helper.terminate()
            except Exception:
                pass
        self._pads.cleanup()
        for hw, _ in _BUTTONS:
            if hw != Sysex.STOP_HW_INDEX:
                self._queue_midi(Sysex.set_button_led(hw, False))
        self._flush_midi(limit=None)  # Live stops ticking after disconnect, so send everything now
        ControlSurface.disconnect(self)

    def update_display(self):
        ControlSurface.update_display(self)
        self._pads.tick()
        self._flush_midi()
        self._ticks += 1
        if self._ticks % SETTINGS_CHECK_TICKS == 0:
            self._load_settings(announce=True)
        if self._play_check is not None:
            self._check_playback_start()
        elif self._stopped_target is not None and self.song().is_playing:
            self._stopped_target = None  # playback was started from Live, the scrub is used up

    def build_midi_map(self, midi_map_handle):
        """Register MIDI addresses so receive_midi is called for them."""
        ControlSurface.build_midi_map(self, midi_map_handle)
        h = self._c_instance.handle()
        for note in PAD_MSG_IDS:
            Live.MidiMap.forward_midi_note(h, midi_map_handle, _CHANNEL, note)
        for cc in _BUTTON_CCS + [TRANSPOSE_CC] + [ENCODER_CC_BASE + i for i in range(16)]:
            Live.MidiMap.forward_midi_cc(h, midi_map_handle, _CHANNEL, cc)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _load_settings(self, announce):
        """Read Innstillinger.py if it is new or has changed. Without the file the defaults apply."""
        try:
            mtime = os.path.getmtime(SETTINGS_PATH)
        except OSError:
            mtime = None
        if mtime == self._settings_mtime:
            return
        self._settings_mtime = mtime
        settings = {}
        try:
            if mtime is not None:
                with io.open(SETTINGS_PATH, encoding='utf-8') as f:
                    exec(compile(f.read(), SETTINGS_PATH, 'exec'), settings)
            first_track = settings.get('STARTSPOR', 1)
            if isinstance(first_track, bool) or not isinstance(first_track, int) or first_track < 1:
                raise ValueError('STARTSPOR must be a whole number from 1')
            pan_step = settings.get('PAN_STEG', 200)
            if isinstance(pan_step, bool) or not isinstance(pan_step, int) or pan_step < 1:
                raise ValueError('PAN_STEG must be a whole number from 1')
            tap_time = settings.get('SHIFT_TRYKK', 0.4)
            if isinstance(tap_time, bool) or not isinstance(tap_time, (int, float)) or tap_time < 0:
                raise ValueError('SHIFT_TRYKK must be 0 or a positive number of seconds')
            snap = settings.get('SCRUB_SNAP', 0)
            if isinstance(snap, bool) or not isinstance(snap, (int, float)) or snap < 0:
                raise ValueError('SCRUB_SNAP must be 0 or a positive number of beats')
            Encoders.configure(settings)
        except Exception as error:  # a typo in the file must not take the controller down
            self.show_message('BeatStep: error in Innstillinger.py, keeping the old values (%s)' % error)
            return
        self._pads.set_first_track(first_track)
        self._scrub_snap = float(snap)
        self._pan_step = pan_step
        self._shift_tap_time = float(tap_time)
        if announce:
            self.show_message('BeatStep: Innstillinger.py loaded')

    # ------------------------------------------------------------------
    # Hardware setup
    # ------------------------------------------------------------------

    def _schedule_hardware_setup(self):
        if self._hw_task is not None:
            self._hw_task.kill()
        steps = [Task.wait(2.1), Task.run(self._send_setup_sysex)]
        self._hw_task = self._task_group.add(Task.sequence(*steps))

    def _send_setup_sysex(self):
        # Note and CC numbers are set explicitly so a different preset in the BeatStep can't break the mapping.
        messages = []
        for i, note in enumerate(PAD_MSG_IDS):
            messages += Sysex.setup_pad(i, note)
        for hw, cc in _BUTTONS:
            messages += Sysex.setup_button(hw, cc)
        for i in range(16):
            messages += Sysex.setup_encoder(i, ENCODER_CC_BASE + i)
        messages += Sysex.setup_transpose_encoder(TRANSPOSE_CC)

        for msg in messages:
            self._queue_midi(msg)
        self.log_message('BeatStep: %d setup sysex queued' % len(messages))
        self._update_leds()

    # ------------------------------------------------------------------
    # MIDI receive
    # ------------------------------------------------------------------

    def receive_midi(self, midi_bytes):
        if DEBUG_MIDI and self._debug_count < 50:
            self._debug_count += 1
            self.log_message('BeatStep: IN %s' % ' '.join('%02X' % b for b in midi_bytes))
        if len(midi_bytes) < 3:
            return
        status, data1, data2 = midi_bytes[0], midi_bytes[1], midi_bytes[2]

        if status == _STATUS_NOTE_ON:
            self._handle_pad_note(data1, data2)
        elif status == _STATUS_NOTE_OFF:
            self._handle_pad_note(data1, 0)
        elif status == _STATUS_CC:
            self._handle_cc(data1, data2)

    def _handle_pad_note(self, note, velocity):
        """Pad presses and releases in note gate mode."""
        if note not in _PAD_NOTE_TO_INDEX:
            return
        idx = _PAD_NOTE_TO_INDEX[note]
        self._shift_used = True
        if velocity > 0 and self._stop_held:
            self._play_from_marker(idx)
        elif velocity > 0 and self._shift_held and self._mode is not self._record_mode:
            self._pads.toggle_solo(idx)
        elif velocity > 0:
            # In Record mode the pads are actions, and with shift held they are the tracks again.
            was_picking = self._pads.picking_page
            self._pads.on_pad_press(idx, arm=self._mode.arms_on_select)
            if self._pads.picking_page != was_picking:
                self._update_button_leds()
        else:
            self._pads.on_pad_release(idx)

    def _handle_cc(self, cc, value):
        """Encoders and function buttons."""
        if cc != BTN_SHIFT_CC:
            self._shift_used = True
        if ENCODER_CC_BASE <= cc < ENCODER_CC_BASE + 16:
            self._mode.on_encoder(cc - ENCODER_CC_BASE, value, reset=self._shift_held)
        elif cc == TRANSPOSE_CC and self._stop_held:
            self._scrub(value)
        elif cc == TRANSPOSE_CC:
            self._on_transpose_encoder(value)
        elif cc in _BUTTON_CCS:
            if cc == BTN_SHIFT_CC:
                self._shift_held = value > 0
                self._sync_pad_actions()
                if self._shift_held:
                    self._shift_used = False
                    self._shift_pressed_at = time.monotonic()
                    # The firmware puts its own overlay on the pads while shift is held.
                    self._pads.update_leds(force=True)
                elif not self._shift_used and time.monotonic() - self._shift_pressed_at <= self._shift_tap_time:
                    # A short tap on shift alone. A longer hold is a look at the tracks or a change of mind.
                    self._toggle_main_view()
            elif cc == BTN_STOP_CC:
                # While stop is held the pads show the markers and stop + pad plays from one.
                # The firmware turns the pads off when stop is pressed, so all of them are repainted.
                self._stop_held = value > 0
                self._pads.showing_markers = self._stop_held
                if self._stop_held:
                    self._stop_used = False
                    self._pads.update_leds(force=True)
                elif not self._stop_used:
                    # Stop pressed on its own: stop, or play on from the playhead. Done on release,
                    # since on press the script can't know whether a pad or the knob will follow.
                    before = self.song().current_song_time
                    if self.song().is_playing:
                        action = 'stop_playing'
                        self.song().stop_playing()
                    elif self._stopped_target is not None:
                        action = 'play from scrub target %.3f' % self._stopped_target
                        self._play_from(self._stopped_target)
                    else:
                        action = 'continue_playing'
                        self.song().continue_playing()
                    self._stopped_target = None
                    if DEBUG_TRANSPORT:
                        self.log_message('BeatStep: stop tap -> %s, needle %.3f -> %.3f'
                                         % (action, before, self.song().current_song_time))
            elif cc == BTN_EXTSYNC_CC and value > 0:
                self._pads.toggle_page_picker()
            elif cc in self._modes and value > 0 and self._modes[cc] is not self._mode:
                self._mode = self._modes[cc]
                self._pads.close_variation_picker()
                self._sync_pad_actions()
                self.show_message('BeatStep: %s mode' % self._mode.name)
            elif cc == BTN_CHAN_CC and value > 0:
                # chan pressed while already in Rack mode: open or close the variation picker.
                self._pads.toggle_variation_picker()
            elif cc == BTN_CNTRL_CC and value > 0:
                # The firmware toggles between control and sequencer mode. The script can't read the mode,
                # so it counts presses and assumes control mode on start.
                self._seq_mode = not self._seq_mode
                self._pads.suspended = self._seq_mode
                if self._seq_mode:
                    self.show_message('BeatStep in sequencer mode, press cntrl/seq to return')
            if value == 0:
                # While a button is held the firmware shows its own overlay on the pads (or the sequencer
                # runs its step indicator), and on release it restores its own colors, not ours.
                self._update_leds()

    def _sync_pad_actions(self):
        # Record mode turns the pads into actions. Holding shift gives the tracks back, for selecting one.
        showing = self._mode is self._record_mode and not self._shift_held
        self._pads.actions = self._record_mode if showing else None
        self._pads.update_leds()

    def _update_leds(self):
        # Called after setup and after a button release, where the firmware has put its own colors on the pads.
        self._pads.update_leds(force=True)
        self._update_button_leds()

    def _update_button_leds(self):
        # Every configured button is turned off (the firmware lights some of them on its own), except the
        # active mode button, ext sync while the page picker is open and cntrl/seq (red) in sequencer mode.
        for hw, cc in _BUTTONS:
            if hw == Sysex.STOP_HW_INDEX:
                continue
            if cc == BTN_CNTRL_CC:
                self._queue_midi(Sysex.set_button_led(hw, self._seq_mode, Sysex.COLOR_RED))
            elif cc == BTN_EXTSYNC_CC:
                self._queue_midi(Sysex.set_button_led(hw, self._pads.picking_page))
            else:
                self._queue_midi(Sysex.set_button_led(hw, self._modes.get(cc) is self._mode))

    # ------------------------------------------------------------------
    # Outgoing MIDI queue
    # ------------------------------------------------------------------

    def _queue_midi(self, msg, urgent=False):
        key = msg[8:10]  # (cmd, hw index) of a BeatStep sysex message
        self._midi_queue[key] = msg
        if urgent:
            # Feedback for something the user just did: skip the queue instead of waiting for a tick.
            self._midi_queue.move_to_end(key, last=False)
            self._flush_midi(limit=1)

    def _flush_midi(self, limit=MIDI_MESSAGES_PER_TICK):
        count = len(self._midi_queue) if limit is None else min(limit, len(self._midi_queue))
        for _ in range(count):
            wait = self._last_sent + MIDI_MESSAGE_GAP - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            _, msg = self._midi_queue.popitem(last=False)
            self._send_midi(msg)
            self._last_sent = time.perf_counter()
        if DEBUG_MIDI and count and not self._midi_queue:
            self.log_message('BeatStep: MIDI queue drained')

    def _toggle_main_view(self):
        """A tap on shift: switch between Session and Arrangement, like Tab in Live."""
        view = self.application().view
        view.show_view('Arranger' if view.is_view_visible('Session') else 'Session')

    def _move_arrangement_view(self, action):
        """One step in the Arrangement: 'zoom in' or 'zoom out' (horizontal), or pan 'left', 'right', 'up'
        or 'down'.

        Live has no call for panning (seen in Live: scroll_view moves the needle or the track selection,
        and the picture stays). So panning is sent to the scroll helper, which makes a scroll event for the
        window under the mouse pointer. Without the helper running nothing happens."""
        if action in _PAN_DIRECTIONS:
            dx, dy = _PAN_DIRECTIONS[action]
            message = 'scroll %d %d' % (dx * self._pan_step, dy * self._pan_step)
            try:
                if self._scroll_socket is None:
                    self._scroll_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._scroll_socket.sendto(message.encode('ascii'), SCROLL_HELPER_ADDRESS)
            except (OSError, socket.error) as error:
                self.show_message('BeatStep: could not reach the scroll helper (%s)' % error)
            return
        nav = Live.Application.Application.View.NavDirection
        direction = nav.right if action == 'zoom in' else nav.left
        self.application().view.zoom_view(direction, 'Arranger', False)

    def _play_from_marker(self, index):
        """Jump to marker 1–15, counted from the start of the song, or to the loop start (last pad),
        and make sure the song plays."""
        self._stop_used = True
        song = self.song()
        if index == LOOP_START_PAD:
            if song.is_playing:
                song.current_song_time = song.loop_start
            else:
                self._play_from(song.loop_start)
            return
        markers = sorted(song.cue_points, key=lambda cue: cue.time)[:LOOP_START_PAD]
        if index >= len(markers):
            self.show_message('No marker %d' % (index + 1))
            return
        # While the song plays, jump() follows Live's global quantization, like a click on the marker.
        markers[index].jump()
        if not song.is_playing:
            song.continue_playing()

    def _scrub(self, value):
        """Stop + transpose knob: move the playhead along the timeline."""
        self._stop_used = True
        beats = self._accelerator.delta('scrub', value, feel('scrub'))
        if beats is None:
            return
        song = self.song()
        if song.is_playing:
            target = self._scrub_target(song.current_song_time, beats)
            song.jump_by(target - song.current_song_time)
            return
        # Stopped: the script keeps the position itself. What Live reads back right after a move is the old
        # value (the move is carried out after the script returns), so counting from it loses detents.
        if self._stopped_target is None:
            self._stopped_target = song.current_song_time
        self._stopped_target = self._scrub_target(self._stopped_target, beats)
        song.current_song_time = self._stopped_target  # shows the needle there

    def _scrub_target(self, position, beats):
        """Where a scrub of `beats` from `position` lands, never before the start of the song. With a grid
        every detent moves at least one grid step, a fast spin several, and it always lands on the grid."""
        snap = self._scrub_snap
        if snap <= 0:
            return max(0.0, position + beats)
        steps = max(1, int(round(abs(beats) / snap)))
        if beats < 0:
            steps = -steps
        # From a position between two lines, the first detent goes to the nearest line in that direction.
        line = position / snap
        line = math.floor(line + 1e-6) if steps > 0 else math.ceil(line - 1e-6)
        return max(0.0, (line + steps) * snap)

    def _play_from(self, target):
        """Start playback at `target` from a stopped song.

        Measured in Live (see SIGNALS.md): setting the time and then start_playing() plays from there, while
        continue_playing() goes back to where the song was stopped. In real use playback has still started
        from somewhere else, so update_display checks where it landed and moves it if needed."""
        song = self.song()
        song.current_song_time = target
        song.start_playing()
        self._stopped_target = None
        self._play_check = [target, time.monotonic(), 3]  # where, when, checks left

    def _check_playback_start(self):
        """Called on every tick after _play_from: is the song playing where it should?"""
        target, started, checks = self._play_check
        song = self.song()
        if not song.is_playing:
            self._play_check = None
            return
        expected = target + (time.monotonic() - started) * song.tempo / 60.0
        position = song.current_song_time
        if abs(position - expected) > 1.0:
            # Moving the playhead while the song plays is the one thing that has worked every time.
            song.current_song_time = expected
        if DEBUG_TRANSPORT:
            self.log_message('BeatStep: play from %.3f, expected %.3f, was at %.3f%s'
                             % (target, expected, position, ' (corrected)' if abs(position - expected) > 1.0 else ''))
        self._play_check = [target, started, checks - 1] if checks > 1 else None

    def _on_transpose_encoder(self, value):
        """Transpose encoder → volume of the selected track in every mode. With shift held it resets the
        volume to its default, like shift + encoder."""
        delta = self._accelerator.delta('transpose', value, feel('transpose'))
        if delta is None:
            return
        track = self.song().view.selected_track
        if track is None:
            return
        turn(track.mixer_device.volume, delta, reset=self._shift_held)
