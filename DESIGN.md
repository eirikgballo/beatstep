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
- **Three encoder modes**, chosen with dedicated buttons: **Rack** (macros), **Volume** (track volumes), **Sends** (send A/B).
- **Pads always select tracks** (single tap) and toggle solo (double tap), in every mode.
- **Track pages** of 16 tracks, chosen directly with `shift` + pad N.

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
| `cntrl/seq` | | CC 30 CH10 (only used to trigger a repaint) |
| `play`, `stop` | | CC 28, 29 CH10 (only used to trigger a repaint) |
| `ext sync` | | Not configured, not used |

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
| Sends | `store` | red | Encoder 1–8: send A of tracks 1–8 of the send page. Encoder 9–16: send B of the same tracks |

- Pressing a mode button switches to that mode. Pressing the active mode button again does nothing (only repaints).
- Exactly one mode button LED is lit at any time. The other two are off.
- The transpose encoder controls the **volume of the selected track** in every mode.
  With `shift` held it controls the **master volume**.
- The script always boots in Rack mode. The mode is not remembered between sessions.

---

## 4. Control Assignments

### Pads (all modes)

| Action | Result |
|--------|--------|
| Single tap pad N | Select track `page_start + N` |
| Double tap pad N (≤ 400 ms) | First tap selects, second tap toggles solo. Solo is additive |
| Tap a pad without a track | Nothing |
| `shift` + pad N | Go to page N, if page N has at least one track. Otherwise status bar: `"Page N is empty"` |

### Encoders

| Mode | Encoder N (1–16) |
|------|------------------|
| Rack | Macro N of the cached rack. No rack → status bar `"No Audio Effect Rack on selected track"` |
| Volume | Volume of track `page_start + N`. No track → ignored |
| Sends | N ≤ 8: send A of track `send_start + N`. N > 8: send B of track `send_start + N - 8`. Missing track or send → ignored |

### Pages

- Pads and Volume: page P covers tracks `16·(P−1) + 1` … `16·P`.
- Sends: page P covers tracks `8·(P−1) + 1` … `8·P`. Sends has its own 8-track paging, so the same
  `shift` + pad N shows different tracks in Sends than on the pads. This is a deliberate choice.
- Page changes repaint all pad LEDs.
- If tracks are removed so the current page is empty, the page stays and all pads show black.

### Buttons

| Button | Action |
|--------|--------|
| `chan` | Rack mode |
| `recall` | Volume mode |
| `store` | Sends mode |
| `shift` | Modifier for `shift` + pad (page) and `shift` + transpose (master volume) |
| `cntrl/seq` | Firmware switches to sequencer mode. Script only repaints on release |
| `play`, `stop` | Firmware starts/stops its sequencer. Script only repaints on release |
| `ext sync` | No function |

> Firmware side effects (see SIGNALS.md): `recall`/`store` + pad recalls/stores a preset, `chan` + pad changes the
> global MIDI channel, `shift` + pad changes sequencer settings. Only `shift` + pad is used deliberately.

---

## 5. LED Feedback Model

### Pads

| Meaning | Color |
|---------|-------|
| No track at this position | black |
| Track, not selected, not soloed | blue |
| Track soloed, not selected | magenta |
| Track selected | red |
| Track selected **and** soloed | blinks red/magenta (0.3 s per phase) |

### Buttons

| Button | LED |
|--------|-----|
| `chan` / `recall` / `store` | On when its mode is active |
| `cntrl/seq` | Off |
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
BeatStep_Q  — ControlSurface subclass; hardware setup, MIDI routing, update_display tick
  QSetup    — Sysex message builders (no state)
  CMix      — Track selection, solo, paging, modes, encoder routing, LED management
```

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
| `track.mixer_device.sends[0]`, `[1]` | Send A and B |

Return tracks and the master track are not addressable from the pads. Master volume is reached with `shift` + transpose.

---

## 8. Implementation Notes

**Target**: Ableton Live 11 (Python 3.7). Do not use syntax newer than 3.7.

**Hardware setup**: Sent once, 2.1 s after connection (`port_settings_changed`), then a full LED paint immediately after.
Measured on hardware: the BeatStep accepts all setup sysex and 16 LED messages back to back without loss
(SIGNALS.md). Earlier notes about a 4-message burst limit and a 1.5 s pause did not reproduce outside Live.
If LEDs go missing in Live, check Live's `Log.txt` for MIDI buffer errors before adding throttling.

**No re-setup on button presses**: the old re-setup on every `recall` press is removed. A preset recall from
the firmware (`recall` + pad) is the only case that changes the hardware config; it is not handled.

**MIDI channel filter**: only pad notes on **CH10** are forwarded and handled. The BeatStep sequencer sends notes
on CH1, which must never select tracks.

**Encoder decoding**: relative mode 2. Value 1–63 = clockwise, 65–127 = counter-clockwise, 0 and 64 ignored.
Normally ±1 per detent; very fast spins send larger values (measured 12). Any magnitude > 1 is treated as full speed.

**Encoder acceleration**: time-based, from the interval between ticks per encoder:
`velocity = clamp((SLOW − dt) / (SLOW − FAST), 0, 1)`, `step = MIN + velocity^ACCEL · MAX`, as a fraction of the
parameter range. The first tick after a pause (no previous tick) counts as slow, not fast.

**Parameter writes**: always clamp to `[param.min, param.max]`. Macro range is 0–127, volume and sends 0–1.

**Double tap**: first tap selects, second tap within 400 ms on the same pad and track toggles solo.

**Blink**: driven from `update_display` (~100 ms). A LED message is only sent when the blink phase changes.

**Script entry point**: `__init__.py` defines `create_instance(c_instance)`. Use `self._task_group` for tasks.

**`receive_midi` requires registration (Live 11+)**: every note/CC must be forwarded in `build_midi_map`.

---

## 9. Testing

| Level | Tool | What it covers |
|-------|------|----------------|
| Hardware probe | `tools/bs.py` | Send raw sysex / LEDs, log everything the BeatStep sends |
| Simulator | `tools/sim.py` | The unmodified script against the real BeatStep and a fake Live (`tools/fakelive`) |
| Unit tests | pytest (planned) | Scenario tests on the sent MIDI without hardware |

Only behaviour inside Live itself (listener timing, `_send_midi` buffering) needs testing on the Mac.

---

## 10. Open Questions

None at the moment.
