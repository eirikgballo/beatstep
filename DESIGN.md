# BeatStep_Q — Design Document

This document is the authoritative plan for the BeatStep_Q MIDI Remote Script.
All structural decisions (components, LED model, control assignments, etc.) are defined here
before any code is written. The code should follow this document, not the other way around.

---

## 1. Goals & Motivation

- Use the BeatStep controller in a focused way. Many features in the original repo are not needed here.
- The original repo [raphaelquast/beatstep](https://github.com/raphaelquast/beatstep) (docs at https://raphaelquast.github.io/beatstep/) is a useful reference for patterns around sysex scheduling, hardware setup, and general MIDI Remote Script structure for the BeatStep. This implementation is deliberately narrower in scope.
- **Mix Mode**: Script boots directly into Mix Mode. The RECALL button is continuously lit **blue** to signal that Mix Mode is active.
- **Mix Mode Pad Functions**: Pads 1–15 select regular tracks (top row = tracks 1–8, bottom row left-to-right = tracks 9–15). Pad 16 (bottom-right) always selects the **master track**. Selected pad lights **red**. Double-tap a pad to toggle **solo** on the associated track.
---

## 2. Hardware Reference

The Arturia BeatStep has the following physical controls:

| Group              | Controls                                      | MIDI mapping                        |
|--------------------|-----------------------------------------------|-------------------------------------|
| Pads (16)          | Pad 1–8 (top row), Pad 9–16 (bottom row)      | Note, CH10, IDs from `PAD_MSG_IDS`  |
| Encoders (16)      | Knobs 1–16 (left→right)                       | CC, CH10, CC 10–25 (set via sysex)  |
| Transpose encoder  | Large knob (top-left)                         | CC, CH10, CC 26 (set via sysex)     |
| Function buttons   | `play`, `stop`, `cntrl`, `shift`, `chan`, `store`, `recall` | CC, CH10 |

> **Note on pad numbering:** "Pad 1–8" always refers to the **top row** of physical pads. The bottom row is "Pad 9–16". Within this codebase, top row = indices 0–7, bottom row = indices 8–15.
>
> The CC IDs in `PAD_MSG_IDS` (44–51 for the top row, 36–43 for the bottom row) are **explicitly programmed into the hardware** by `_setup_hardware` via `set_B_cc` sysex on every connection. Any prior hardware configuration (e.g. from Arturia MIDI Control Center) is overwritten. `PAD_MSG_IDS` is the authoritative source.

### Pad LED colors (sysex, via QSetup)

| Value | Color       |
|-------|-------------|
| 0     | off / black |
| 1     | red         |
| 16    | blue        |
| 17    | magenta     |

---

## 3. Mode Activation

| Mode | Enter | Exit | Exclusive? | Description |
|------|-------|------|------------|-------------|
| Mix  | Active on boot; pressing `recall` repaints LEDs | — (always active; no exit) | N/A (only mode) | Track select, solo, macro control, volume |

---

## 4. Control Assignments per Mode

### Mode: Mix (only mode for now)

| Control | Action |
|---------|--------|
| Encoder 1–16 (knobs, left→right) | Control macro 1–16 on the first Audio Effect Rack found in the selected track's device chain. Encoders run in relative mode 1 (CW=1–63, CCW=65–127). Acceleration is applied: slow spin ≈ 0.002/tick, fast spin ≈ 0.02/tick. If the selected track has no Audio Effect Rack, turning any encoder shows a status bar message. If the rack has fewer than 16 macros, encoders beyond the available count show a status bar message. No status bar message is shown on successful macro adjustment. |
| Transpose encoder (large knob) | Controls the **volume** of the currently selected track. Same relative mode 1 and acceleration curve as the 16 encoders. Clamped to `[0.0, 1.0]`. Always active — no mode dependency. |
| Pad 1–8 (top row, left→right) | Select regular track 1–8 on the current page. LED: red if selected, magenta if soloed, blue if exists, black if no track. |
| Pad 9–15 (bottom row, left→right, first 7) | Select regular track 9–15 on the current page. Same LED rules. |
| Pad 16 (bottom-right) | Always selects the **master track**, regardless of page. LED: red if selected, blue always (master always exists). |
| Single-tap pad | Selects the associated track (exclusive — only one pad is red at a time). The previously selected pad returns to blue or magenta depending on its solo state. |
| Double-tap pad (≤ 400 ms between taps) | The **first tap** selects the track (as above). The **second tap** toggles solo on that track. Solo is additive — multiple tracks can be soloed simultaneously. Double-tapping a soloed track turns solo off. Double-tapping **pad 16** (master track) shows status bar: `"Master can't be solo'ed"` and does nothing else. A double-tap **always requires two taps in sequence** — tapping an already-selected pad resets the gesture timer, so a second tap within 400 ms is still needed to toggle solo. |
| `recall` | Mix Mode indicator — lit **blue** continuously. Pressing `recall` repaints all LEDs. On page 2+, pressing `recall` alone repaints without changing page. |
| `shift` + `recall` | Advance to the next track page (+15 regular tracks). From the last page, wraps back to page 1. |
| `play` | No function (reserved). |
| `stop` | No function (reserved). |
| `shift` | Modifier key (no standalone function). Used for `shift`+`recall` page advance. `shift`+pad is reserved for future use. |
| `chan` | Reserved for future mode. |
| `store` | Reserved for future mode. |
| `cntrl` | Reserved for future mode. |

### Track paging

With more than 15 regular tracks, pads 1–15 show one page of 15 tracks at a time. Pad 16 always shows the master track.

| Page | Pads 1–15 map to regular tracks |
|------|---------------------------------|
| 1    | 1–15                            |
| 2    | 16–30                           |
| 3    | 31–45                           |
| …    | …                               |

**Page indicator**: `recall` button is **blue** on page 1, **magenta** on page 2+.

Pressing `shift`+`recall` advances the page by one (wraps from last page back to page 1) and repaints all pad LEDs for the new page.

> *Add a table for every additional mode when they are designed.*

---

## 5. LED Feedback Model

All LED semantics in one place — no magic color numbers in logic code.

### Pad LEDs (track pads 1–15)

| Semantic meaning | Color | Priority |
|------------------|-------|----------|
| No track exists at this pad position | black | — |
| Track exists, not selected, not soloed | blue | lowest |
| Track soloed, not currently selected | magenta | middle |
| Track currently selected | red | highest — overrides soloed |

> A track that is both selected and soloed shows **red**.

### Pad 16 (master track)

| Semantic meaning | Color |
|------------------|-------|
| Master not selected | blue |
| Master selected | red |

### Function button LEDs

| Button | State | Color |
|--------|-------|-------|
| `recall` | Page 1 active | blue |
| `recall` | Page 2+ active | magenta |

### On disconnect

All LEDs are cleared (set to **black**) when the script disconnects.

---

## 6. Component Structure

```
BeatStep_Q  — ControlSurface subclass; hardware setup, sysex scheduling, MIDI routing
  QSetup    — Sysex message builders (no state; pure utility)
  CMix      — Mix Mode: track selection, solo, encoder→macro control, volume, LED management, track paging
```

---

## 7. Live API Surface

| Live object / event | Used for | Live version |
|---------------------|----------|--------------|
| `Live.Song.Song` | Track list, song object | 9+ |
| `Song.view.selected_track` / `add_selected_track_listener` | Track selection read and LED feedback | 9+ |
| `Song.tracks` / `add_tracks_listener` | Regular tracks list; react to tracks being added or removed | 9+ |
| `Song.master_track` | Master track object for pad 16 | 9+ |
| `track.solo` / `add_solo_listener` | Solo state read, write, and real-time LED feedback | 9+ |
| `track.devices` | Device chain; scan for first Audio Effect Rack on track change | 9+ |
| `device.class_name == "AudioEffectGroupDevice"` | Identify an Audio Effect Rack in the device chain | 9+ |
| `device.parameters` | Macro parameter list on the Audio Effect Rack (indices 1–16 are macros 1–16; index 0 is the device on/off toggle) | 9+ |
| `parameter.value` / `parameter.min` / `parameter.max` | Read and write macro values | 9+ |

> Return tracks (`Song.return_tracks`) are **not used** in this implementation.

---

## 8. Implementation Notes & Design Decisions

**Target Live versions**: Ableton Live 11, with the **"value scaling"** setting enabled in Live's MIDI Preferences. Our script reads raw CC values directly in `receive_midi` so it is not affected by this setting, but it is relevant context.

**Hardware configuration**: Configured on **every startup** via `_setup_hardware` (called from `port_settings_changed`). This keeps controller state deterministic. Do not save/restore hardware state across sessions.

**Hardware setup timing**: Use a two-stage task sequence: sysex at T+2.1 s, LED paint starting at T+3.6 s. The BeatStep requires ~2 s after connection before reliably accepting sysex. The additional 1.5 s gap before LED commands gives the BeatStep time to finish processing all sysex — LED color commands (sysex cmd 0x10) are silently ignored by the firmware for any pad that has not yet been switched to note mode (mode 9). Sending LEDs too quickly after sysex results in only a subset of pads responding.

**LED burst limit**: The BeatStep silently drops LED sysex messages when too many arrive in rapid succession — it only processes roughly 4 before the buffer overflows. This means sending all 17 LED commands in one tight loop results in only the first 4 lighting up. Because the hardware index space is iterated sequentially (0x70, 0x71, 0x72, 0x73 = physical pads 1, 5, 9, 13 in the column-major layout), only those 4 physical positions would light. The fix is two-pronged: (1) for the initial paint, use a staggered task sequence that sends 4 LEDs per batch with 0.15 s between batches; (2) for subsequent updates, use a delta-tracking cache (`_led_state`) in CMix so only LEDs whose color has actually changed are sent (typically 1–2 sysex messages per track selection).

**Disconnect cleanup**: On disconnect (`disconnect()` or `port_settings_changed` when port is lost), send all-black to all pad LEDs.

**Double-tap detection**: The first tap of a double-tap gesture **does** select the track (LED changes to red immediately). If a second tap arrives within 400 ms, solo is toggled on that track. A single tap never triggers solo.

**Track paging**: `CMix` maintains a `_page` integer (0-indexed). Pads 1–15 map to `Song.tracks[page*15 + pad_index]`. Pad 16 always maps to `Song.master_track`. Page advances on `shift`+`recall` (wraps). The `recall` LED reflects the current page (blue = page 1, magenta = page 2+). If tracks are added or removed such that the current page has no tracks, the script stays on the current page and all pads 1–15 show black. If the currently selected track belongs to a page other than the active page, no pad shows red on the current page — the Live selection is preserved, but LED feedback for it is simply absent until the user navigates back to that track's page.

**Solo listeners**: `CMix` registers a `solo_changed` listener on each track so that pad LEDs update in real-time when solo state is changed externally (e.g. via the Live UI).

**`shift` key state**: `CMix` maintains a `_shift_held` boolean. It is set to `True` on the CC press message for `shift` and back to `False` on the CC release message. `shift`+`recall` is detected by checking `_shift_held` when the `recall` press arrives.

**Track selection model**: Only `Song.tracks` (regular tracks) and `Song.master_track` are addressable. Return tracks are excluded.

**Feature scope**: Mix Mode only. `play`, `stop`, `chan`, `store`, `cntrl` have no function in the current implementation.

**Encoder CC assignment**: Encoders 0–15 are programmed to send CC 10–25 (encoder N → CC 10+N) on CH10 via `QSetup.setup_encoder` called from `_send_setup_sysex`. The transpose encoder is programmed to CC 26. None of these conflict with existing controls (SHIFT=CC 7, RECALL=CC 5). `build_midi_map` must forward CC 10–26 on CH10 so `receive_midi` is called.

**Encoder relative value decoding**: BeatStep encoders in relative mode 1 send:
- CW (clockwise): raw value 1–63 → positive delta = raw value
- CCW (counter-clockwise): raw value 65–127 → negative delta = -(128 − raw value)
- Value 0 or 64 should be ignored (not produced in normal use)

**Encoder acceleration**: Apply a gentle acceleration curve so that slow turns adjust finely and fast turns sweep larger ranges:
```
raw_delta = value if value < 64 else -(128 - value)
magnitude = abs(raw_delta)
step = 0.002 + (magnitude / 63.0) * 0.018   # range: 0.002 (slow) to 0.020 (fast)
delta = step if raw_delta > 0 else -step
```
Clamp the resulting parameter value to `[0.0, 1.0]` before assigning.

**Rack binding in CMix**: `CMix` caches the current Audio Effect Rack in `_current_rack`. This cache is refreshed whenever the selected track changes (`_on_selected_track_changed`). The scan iterates `song.view.selected_track.devices` and picks the first device whose `class_name == "AudioEffectGroupDevice"`. If none is found, `_current_rack` is set to `None`. The cache is also invalidated on track change even if the same track somehow re-fires the listener.

**Macro parameter indexing**: `device.parameters` on an Audio Effect Rack includes index 0 (device on/off) followed by the macro parameters. Macro N (1-indexed) is at `device.parameters[N]`. The rack always has exactly 16 macro parameter slots regardless of how many are visible in the UI; hidden macros still accept value writes. If a macro slot does not exist (e.g. `N >= len(device.parameters)`), show a status bar message.

**MIDI map rebuild on track change**: After refreshing `_current_rack` in `_on_selected_track_changed`, call `request_rebuild_midi_map()` so that Live re-runs `build_midi_map`. This is already called; encoder CC forwarding is static and does not need to change per-track.

**Function button CC IDs (confirmed)**: Function buttons send CC on **CH10** (same channel as pads and encoders). Confirmed values: `shift` = CC 7, `recall` = CC 5. The CC value is 127 on press, 0 on release. Before the script's sysex runs (factory state), buttons may temporarily send on CH1 — the script handles both channels defensively in `_handle_function_button`.

**Parameter value clamping**: When adjusting a parameter value via encoder delta, clamp the result to `[0.0, 1.0]` before assigning: `param.value = max(0.0, min(1.0, param.value + delta))`.

**Script entry point**: `__init__.py` must define `create_instance(c_instance)` returning the `ControlSurface` instance. Without it Live silently ignores the script and it will not appear in the Control Surface dropdown. Use `self._task_group` (not `self._tasks`) for the task scheduler in `_Framework.ControlSurface`.

**MIDI routing — `receive_midi` requires explicit registration (Live 11+)**: In Live 11 and later, `receive_midi` is **not called by default** for MIDI arriving on the script's port. MIDI addresses must be explicitly forwarded via `build_midi_map`:

```python
def build_midi_map(self, midi_map_handle):
    ControlSurface.build_midi_map(self, midi_map_handle)
    h = self._c_instance.handle()
    for note in PAD_MSG_IDS:
        Live.MidiMap.forward_midi_note(h, midi_map_handle, 9, note)
    # ... etc for all other CCs
```

### Todo

- [ ] Add encoder sysex setup to `_send_setup_sysex` in `Beatstep_Q.py` (call `QSetup.setup_encoder(i, 10+i)` for i in 0–15)
- [ ] Forward CC 10–25 on CH10 in `build_midi_map` in `Beatstep_Q.py`
- [ ] Route incoming CC 10–25 to `CMix.on_encoder(encoder_index, value)` in `_handle_cc`
- [ ] Implement `_current_rack` caching and rack scan in `CMix` (`_on_selected_track_changed` already triggers `request_rebuild_midi_map`)
- [ ] Implement `CMix.on_encoder(encoder_index, value)` with relative decoding, acceleration, macro write, and error messages
- [ ] Update hardware reference note (`PAD_MSG_IDS` note) to add an equivalent note for encoder CC IDs

