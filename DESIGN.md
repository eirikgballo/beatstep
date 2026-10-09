# BeatStep_Q — Design Document

This document is the authoritative plan for the BeatStep_Q MIDI Remote Script.
All structural decisions (components, LED model, control assignments, etc.) are defined here
before any code is written. The code should follow this document, not the other way around.

Hardware facts (MIDI messages, LED addresses, firmware side effects) are **measured** and live in
[SIGNALS.md](SIGNALS.md). When this document and SIGNALS.md disagree on hardware behaviour, SIGNALS.md wins.

---

## 1. Goals & Motivation

- Use the BeatStep as a focused mixing controller for Ableton Live. Many features in the original repo are not needed here.
- The original repo [raphaelquast/beatstep](https://github.com/raphaelquast/beatstep) is a useful reference for sysex and
  MIDI Remote Script structure. This implementation is deliberately narrower in scope.
- **Three modes**, chosen with dedicated buttons: **Rack** (macros), **Volume** (track volumes), **Record** (pad actions for recording).
- **Pads select tracks** (tap) and toggle solo (`shift` + pad, without selecting) in Rack and Volume mode. In Record mode the pads are actions.
- **Track pages** of 16 tracks, chosen with the page picker (`ext sync`, then pad N).

---

## 2. Hardware Reference

| Group | Controls | MIDI (after script setup) |
|-------|----------|---------------------------|
| Pads (16) | Pad 1–8 top row, pad 9–16 bottom row, left→right | Note on/off CH10, notes in `PAD_MSG_IDS` |
| Encoders (16) | Knob 1–8 top row, 9–16 bottom row | CC 10–25 CH10, relative mode 2 |
| Transpose encoder | Large knob | CC 27 CH10, relative mode 2 |
| `shift` | | CC 7 CH10 |
| `recall` | | CC 5 CH10 |
| `chan` | | CC 33 CH10 |
| `store` | | CC 32 CH10 |
| `cntrl/seq` | | CC 30 CH10 (tracks sequencer mode, triggers a repaint) |
| `play`, `stop` | | CC 28, 29 CH10 (only used to trigger a repaint) |
| `ext sync` | | CC 31 CH10 |

> Pad numbering: "pad 1–8" is always the **top row**. In code, top row = indices 0–7, bottom row = 8–15.
> LED addresses are row-major: pad index N → hw `0x70 + N`.

### LED colors

| Control | Available colors |
|---------|------------------|
| Pads, `cntrl/seq` | 0 off, 1 red, 16 blue, 17 magenta |
| `recall`, `chan`, `shift`, `ext sync` | blue (on/off) |
| `store` | red (on/off) |
| `play` | white (on/off) |
| `stop` | no LED |

---

## 3. Modes

| Mode | Button | Button LED when active | Encoders 1–16 control |
|------|--------|------------------------|-----------------------|
| Rack (default on boot) | `chan` | blue | Macro 1–16 of the first Audio Effect Rack on the selected track |
| Volume | `recall` | blue | Volume of the 16 tracks on the current page |
| Record | `store` | red | The same macros as in Rack mode. The pads are actions (see Record mode below) |

- Pressing a mode button switches to that mode. Pressing `recall` or `store` again while active does nothing
  (only repaints). Pressing `chan` again in Rack mode opens the variation picker (see below).
- Exactly one mode button LED is lit at any time. The other two are off.
- The transpose encoder controls the **volume of the selected track** in every mode.
  With `shift` held it **resets** that volume to its default (0 dB).
- `shift` + encoder 1–16 **resets** the parameter the encoder controls to its default value
  (`parameter.default_value`), like a double-click in Live: macro to its default, volume to 0 dB.
  One detent in either direction is enough, and further turning with `shift` held changes nothing.
- The script always boots in Rack mode. The mode is not remembered between sessions.

---

## 4. Control Assignments

### Pads (Rack and Volume mode)

Selecting a track with a pad in **Rack mode** (and with `shift` + pad in Record mode) also **arms** it for
recording and disarms every other track. Live only does that on a mouse click, so the script does it itself.
A track that can't be armed (group) is only selected, and the arming is left as it was. Volume mode and
selecting a track in Live never change the arming.

### Record mode

| Pad | Action | LED |
|-----|--------|-----|
| 1 | Arrangement record on/off (`song.record_mode`). Only arms the recording, it doesn't start playback (needs Live's preference *Start Transport With Record* set to Off) | blinks red = on, blue = off |
| 2 | Undo (`song.undo()`). Nothing to undo → status bar `"Nothing to undo"` | blue = possible, off = nothing to undo |
| 3 | Redo (`song.redo()`) | blue = possible, off = nothing to redo |
| 4 | Metronome on/off (`song.metronome`) | red = on, blue = off |
| 5 | Marker at the needle: adds one, or removes the one that is there (`song.set_or_delete_cue()`) | red = the needle is on a marker, blue = not |
| 6 | Loop on/off (`song.loop`) | red = on, blue = off |
| 7 | Set the loop start at the needle. The end stays, unless the needle is at or past it: then the whole loop moves | blue |
| 8 | Set the loop end at the needle. At or before the loop start → status bar `"The loop end must be after the loop start"` | blue |
| 9 | Zoom in on the Arrangement, one step (`application.view.zoom_view(right, 'Arranger', False)`) | magenta |
| 10 | Zoom out, one step (`left`) | magenta |
| 11–14 | Pan the Arrangement left, right, up, down, `PAN_STEG` pixels per press (see the scroll helper below) | blue |
| 15–16 | Unused | off |

- `shift` held: the pads show the tracks again, and `shift` + pad **selects and arms** the track. There is no
  solo in Record mode. The script repaints the pads when `shift` is pressed, over the firmware's overlay.
- The LEDs follow changes made in Live (polled every tick, there are no listeners).
- The page picker, the markers (`stop` held) and the sequencer warning take precedence over the actions.
- **Scroll helper**: Live's API can't pan or scroll the Arrangement. Seen in Live: `scroll_view` moves the needle
  (left/right) or the track selection (up/down), and selecting a track from the script doesn't bring it into
  view. The pan pads therefore send `scroll <dx> <dy>` (pixels) as UDP to `127.0.0.1:9817`, where
  `tools/scrollhjelper/beatstep-scroll` (Swift, macOS only) posts a scroll event. The event goes to the window
  under the mouse pointer, the helper needs Accessibility permission, and without it running the pads do nothing.
  The script starts the helper when Live loads it and stops it on disconnect. With `--stopp-med-forelder` the
  helper also exits by itself when Live is gone. Its output goes to `logs/scrollhjelper.log`.
- `store` + pad was rejected as the select gesture: the firmware stores a preset and hides the pad colors.
  `recall` + pad would load another preset and wipe the script's setup.

### Pads in Rack and Volume mode

| Action | Result |
|--------|--------|
| Single tap pad N | Select track `page_start + N` |
| `shift` + pad N | Toggle solo on the track **without selecting it**. Solo is additive |
| `stop` + pad 1–15 | Play from marker N (locators in the arrangement, counted from the start of the song). Stopped: jump and start playing. Playing: jump with Live's global quantization. No marker N: status message |
| `stop` + pad 16 | Play from the start of the loop (`song.loop_start`), immediately |
| `stop` + transpose | Scrub: move the playhead, a quarter of a beat per detent when turning slowly and up to 4 beats at full speed (`SCRUB_FEEL`) |
| Tap a pad without a track | Nothing |

### Encoders

| Mode | Encoder N (1–16) |
|------|------------------|
| Rack | Macro N of the cached rack. No rack → status bar `"No Audio Effect Rack on selected track"` |
| Volume | Volume of track `page_start + N`. No track → ignored |
| Record | As Rack |

### Pages

- Pads and Volume: page P covers tracks `16·(P−1) + 1` … `16·P`.
- `STARTSPOR` in `Innstillinger.py` (default 1) is the track on pad 1 of page 1. The tracks above it have no
  pad and no Volume encoder, and the pages count from it. Changing it while Live runs goes back to page 1.
- Page changes repaint all pad LEDs.
- If tracks are removed so the current page is empty, the page stays and all pads show black.

### Page picker

- Press `ext sync`: the pads show pages instead of tracks. Pad N = page N.
  Red = current page, blue = page with tracks, black = empty page. The `ext sync` LED is on.
- Press pad N: go to page N and show tracks again. An empty page is refused with status bar
  `"Page N is empty"` and the picker stays open.
- Press `ext sync` again: close the picker without changing page.

### Variation picker

- Press `chan` while already in Rack mode: the pads show the macro variations of the first Audio Effect Rack on
  the selected track instead of tracks. Pad N = variation N.
  Red = selected variation, magenta = variation exists, black = empty. Magenta and not blue, so the picker
  can't be mistaken for the tracks.
- Press pad N: recall variation N. The picker **stays open**, so variations can be compared. An empty pad gives
  status bar `"Variation N is empty"`, no rack gives `"No Audio Effect Rack on selected track"`.
- Press `chan` again, or change mode: close the picker. Opening the page picker also closes it.
- The pads don't select or solo tracks while the picker is open. The picker follows the selected track and what
  is stored, deleted or chosen in Live (checked on the blink tick, there are no listeners).
- Storing and naming variations is done in Live. Showing or hiding the variation view in Live is not possible:
  the API has no property for it.

### Sequencer mode warning

`cntrl/seq` switches the firmware to sequencer mode, where the pads send no notes. The script can't read
the mode, so it counts `cntrl/seq` presses and assumes control mode on start. In sequencer mode:

- all pads blink red (same 0.3 s phase as the solo blink) and `cntrl/seq` is lit red
- status bar: `"BeatStep in sequencer mode, press cntrl/seq to return"`
- track colors are restored when `cntrl/seq` is pressed again

### Buttons

| Button | Action |
|--------|--------|
| `chan` | Rack mode. Pressed again in Rack mode: opens or closes the variation picker |
| `recall` | Volume mode |
| `store` | Record mode |
| `shift` | Modifier for `shift` + pad (solo, or select track in Record mode), `shift` + encoder and `shift` + transpose (reset to default). A short tap on `shift` alone (released within `SHIFT_TRYKK` seconds from `Innstillinger.py`, default 0.4, nothing else touched) switches between Session and Arrangement, like Tab |
| `cntrl/seq` | Firmware toggles sequencer mode. Script shows the sequencer mode warning (see above) |
| `stop` | Pressed on its own: stops playback in Live, or starts it if the song is stopped (on release): from where it stopped, or from the new position if it was scrubbed while stopped. Held: the pads show the markers (blue = marker exists) and the loop start (pad 16, magenta), `stop` + pad plays from there, and `stop` + transpose scrubs. Firmware also sends MIDI Stop, which Live ignores |
| `play` | Firmware starts its sequencer. Script only repaints on release |
| `ext sync` | Opens the page picker, or closes it without changing page |

> Firmware side effects (see SIGNALS.md): `recall`/`store` + pad recalls/stores a preset, `chan` + pad changes the
> global MIDI channel, `shift` + pad changes sequencer settings (harmless, the sequencer is not used).
> Only `shift` + pad is used deliberately.

---

## 5. LED Feedback Model

### Pads

| Meaning | Color |
|---------|-------|
| No track at this position | black |
| Track, not selected, not soloed | blue |
| Track soloed, not selected | blinks magenta/off (0.3 s per phase) |
| Track selected | red |
| Track selected **and** soloed | blinks red/magenta (0.3 s per phase) |

### Buttons

| Button | LED |
|--------|-----|
| `chan` / `recall` / `store` | On when its mode is active |
| `cntrl/seq` | Red in sequencer mode, otherwise off |
| `ext sync` | On while the page picker is open |
| others | Off |

### Repaint rules (firmware overwrites our LEDs)

| Event | Repaint |
|-------|---------|
| Pad released | That pad |
| `shift`, `recall`, `store`, `chan` or `cntrl/seq` released | All pads + button LEDs (firmware shows an overlay while held and restores **its own** colors) |
| `stop` or `play` released | All pads + button LEDs (the running sequencer uses the pads as a step indicator) |
| Selection, solo, track list or page change | Pads whose color changed |
| Disconnect | All pads and button LEDs black |

---

## 6. Component Structure

```
__init__.py    Entry point for Live (create_instance)
BeatStep.py    ControlSurface: hardware setup, MIDI routing, mode switching, button LEDs, transpose encoder
Sysex.py       Sysex builders, hardware addresses, colors (no state)
TrackPads.py   Pads in every mode: selection, solo, paging, pad LEDs, blink
Encoders.py    Relative decoding, time-based acceleration, clamped parameter writes, sensitivity from the settings
Innstillinger.py  The user's settings: sensitivity per mode and the acceleration curve (not imported, read as text)
RackMode.py    Encoders → macros of the first Audio Effect Rack
VolumeMode.py  Encoders → volumes of the 16 tracks on the current page
RecordMode.py  Pads → record, undo, redo, loop. Encoders → macros, through RackMode
```

Each mode is a small class with `on_encoder(index, value)`. `BeatStep` holds the active mode and routes
encoder input to it. Shared behaviour lives in `TrackPads` and `Encoders`, never in a mode.

---

## 7. Live API Surface

| Live object / event | Used for |
|---------------------|----------|
| `Song.tracks` / `add_tracks_listener` | Track list |
| `Song.view.selected_track` / `add_selected_track_listener` | Selection and LEDs |
| `track.solo` / `add_solo_listener` | Solo and LEDs |
| `track.devices`, `class_name == "AudioEffectGroupDevice"` | First rack on the selected track |
| `device.parameters[1..16]` | Macros (index 0 is device on/off) |
| `track.mixer_device.volume` | Volume mode and transpose encoder |
| `track.arm`, `track.can_be_armed` | Arming on track select |
| `song.record_mode`, `undo()`, `redo()`, `can_undo`, `can_redo`, `loop`, `loop_start`, `loop_length`, `metronome`, `set_or_delete_cue()` | Record mode pads |

Return tracks and the master track are not addressable from the pads. Master volume has no control on the BeatStep (`shift` + transpose was master volume until it became reset).

---

## 8. Implementation Notes

**Target**: Ableton Live 11 (Python 3.7). Do not use syntax newer than 3.7.

**Hardware setup**: Queued once, 2.1 s after connection (`port_settings_changed`), followed by a full LED paint.

**Outgoing MIDI queue**: the BeatStep loses sysex that arrives less than ~1 ms apart (measured on the Mac,
see SIGNALS.md), so the script waits `MIDI_MESSAGE_GAP` (3 ms) between messages. The wait blocks Live's main
thread, so all sysex goes through a queue in `BeatStep`, sent at most `MIDI_MESSAGES_PER_TICK` (16) per
`update_display` tick. A newer value for the same LED or setting replaces the queued one. Setup takes ~1 s,
a full repaint up to ~0.2 s. The color of a released pad skips the queue and is sent at once, because the
firmware leaves the pad dark until it arrives. Pads whose color did not change are not resent, except after
setup, a pad release and a button release, where the firmware has painted over them. `disconnect` sends the whole queue at once, since Live stops
ticking after it.

**No re-setup on button presses**: the old re-setup on every `recall` press is removed. A preset recall from
the firmware (`recall` + pad) is the only case that changes the hardware config; it is not handled.

**MIDI channel filter**: only pad notes on **CH10** are forwarded and handled. The BeatStep sequencer sends notes
on CH1, which must never select tracks.

**Encoder decoding**: relative mode 2. Value 1–63 = clockwise, 65–127 = counter-clockwise, 0 and 64 ignored.
Normally ±1 per detent; very fast spins send larger values (measured 12). Any magnitude > 1 is treated as full speed.

**Encoder acceleration**: speed-based, from the number of detents per encoder in the last 0.1 s:
`rate = detents / 0.1`, `velocity = clamp((rate − START) / (FULL − START), 0, 1)`, `step = MIN + velocity · MAX`,
as a fraction of the parameter range. A single detent after a pause is 10 per second and counts as slow.
The time between two single detents was used first, but it is too jittery: Live hands MIDI to the script in
clumps, and normal turning (measured 10–40 detents/s) was treated as fast (see SIGNALS.md).

**Scrub grid**: `SCRUB_SNAP` in `Innstillinger.py` is a grid in beats (0 = free, the default without the file).
With a grid every detent moves at least one step, a fast spin several, and the position always lands on the grid.
From between two lines the first detent goes to the nearest line in that direction. Live's own arrangement grid
and *Snap to Grid* are not in the API, so the script can't follow them.

**Settings file**: the user tunes the feel in `Innstillinger.py`: two levels from 1 to 10 (slow, fast) for each of
`RACK`, `VOLUM`, `TRANSPOSE` and `SCRUB`, plus `KAST` from 1 to 10: how fast the knob must be spun for
the full step (`FULL` = 135 · 1.3^(KAST − 5) detents per second, `START` = `FULL` / 3).
Levels are logarithmic: slow step = 0.2 % · 1.58^(level − 3), full-speed step =
2.2 % · 1.5^(level − 5), and `MAX` is the difference. Scrub uses the same levels in beats (fraction · 125).
`BeatStep` checks the file once a second and reads it again when it has changed, so the feel can be tuned while
Live runs. A mistake in the file shows a status message and keeps the previous values; a missing file or a
missing name gives the defaults in `Encoders.DEFAULT_SETTINGS`.

**Parameter writes**: always clamp to `[param.min, param.max]`. Macro range is 0–127, volume 0–1.

**Solo gesture**: `shift` + pad. A double tap was tried first; selecting on the first tap made it impossible to
solo without selecting, and delaying the selection by 400 ms felt too slow.

**Blink**: driven from `update_display` (~100 ms). A LED message is only sent when the blink phase changes.

**Script entry point**: `__init__.py` defines `create_instance(c_instance)`. Use `self._task_group` for tasks.

**`receive_midi` requires registration (Live 11+)**: every note/CC must be forwarded in `build_midi_map`.

---

## 9. Testing

| Level | Tool | What it covers |
|-------|------|----------------|
| Hardware probe | `tools/bs.py` | Send raw sysex / LEDs, log everything the BeatStep sends |
| Simulator | `tools/sim.py` | The unmodified script against the real BeatStep and a fake Live (`tools/fakelive`) |
| Unit tests | `tests/` (pytest) | The behaviour in this document, checked on sent MIDI and fake Live state, no hardware |
| Refactor check | `tools/scenario.py` | Fixed scenario printed as text; identical output before and after a refactor |

```
uv pip install -r requirements-dev.txt
python -m pytest tests                       # unit tests
python tools/sim.py --log logs/sim.log       # simulator, BeatStep on USB
python tools/bs.py listen                    # raw MIDI from the BeatStep
```

The tests use a fake clock, so timing (blink, encoder acceleration) is deterministic.
When a hardware test reveals a bug, add a test for it before fixing it.

Only behaviour inside Live itself (listener timing, `_send_midi` buffering) needs testing on the Mac.

---

## 10. Open Questions

None at the moment.
