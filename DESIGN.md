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
- **Mix Mode Encoder Functions**: Encoders 1–16 control macros 1–16 of the Audio Effect Rack on the currently selected track.
- **Transpose Encoder**: Always controls the volume of the currently selected track.

---

## 2. Hardware Reference

The Arturia BeatStep has the following physical controls:

| Group              | Controls                                      | MIDI mapping                        |
|--------------------|-----------------------------------------------|-------------------------------------|
| Pads (16)          | Pad 1–8 (top row), Pad 9–16 (bottom row)      | CC, CH10, IDs from `PAD_MSG_IDS`    |
| Encoders (16)      | Encoder 1–16                                  | CC, CH10, IDs from `ENCODER_MSG_IDS`; **relative mode 2** |
| Transpose encoder  | Single rotary at top-left                     | CC 4, CH10, **relative mode 2**     |
| Function buttons   | `play`, `stop`, `cntrl`, `shift`, `chan`, `store`, `recall` | CC, CH10 |

> **Note on pad numbering:** "Pad 1–8" always refers to the **top row** of physical pads. The bottom row is "Pad 9–16". Within this codebase, top row = indices 0–7, bottom row = indices 8–15.
>
> The CC IDs in `PAD_MSG_IDS` (44–51 for the top row, 36–43 for the bottom row) are **explicitly programmed into the hardware** by `_setup_hardware` via `set_B_cc` sysex on every connection — the same way encoder CC IDs are set. Any prior hardware configuration (e.g. from Arturia MIDI Control Center) is overwritten. `PAD_MSG_IDS` is the authoritative source.

### Encoder relative mode (mode 2)

The BeatStep sends relative values around the centre point 64:

| Raw CC value | Meaning            |
|--------------|--------------------|
| 65           | +1 step clockwise  |
| 63           | -1 step counter-clockwise |
| 66, 67, …    | larger CW increment (faster spin) |
| 62, 61, …    | larger CCW increment (faster spin) |

The script reads these raw values directly in `receive_midi` and converts them to parameter delta moves.

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
| Pad 1–8 (top row, left→right) | Select regular track 1–8 on the current page. LED: red if selected, magenta if soloed, blue if exists, black if no track. |
| Pad 9–15 (bottom row, left→right, first 7) | Select regular track 9–15 on the current page. Same LED rules. |
| Pad 16 (bottom-right) | Always selects the **master track**, regardless of page. LED: red if selected, blue always (master always exists). |
| Single-tap pad | Selects the associated track (exclusive — only one pad is red at a time). The previously selected pad returns to blue or magenta depending on its solo state. |
| Double-tap pad (≤ 400 ms between taps) | The **first tap** selects the track (as above). The **second tap** toggles solo on that track. Solo is additive — multiple tracks can be soloed simultaneously. Double-tapping a soloed track turns solo off. Double-tapping **pad 16** (master track) shows status bar: `"Master can't be solo'ed"` and does nothing else. A double-tap **always requires two taps in sequence** — tapping an already-selected pad resets the gesture timer, so a second tap within 400 ms is still needed to toggle solo. |
| Encoders 1–16 | Control macro 1–16 of the first Audio Effect Rack on the **currently selected track**. Status bar messages: "No rack on track" (shown on every turn when no rack exists); "Nothing assigned to macro N" (shown on every turn when the rack has fewer than N macros). |
| Transpose encoder | Controls the **volume** of the currently selected track. Always active, regardless of pad selection. |
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
| `track.mixer_device.volume` | Transpose encoder → selected track volume | 9+ |
| `device.parameters` | Encoder → macro parameter value control | 9+ |

> Return tracks (`Song.return_tracks`) are **not used** in this implementation.

---

## 8. Implementation Notes & Design Decisions

**Target Live versions**: Ableton Live 11, with the **"value scaling"** setting enabled in Live's MIDI Preferences. Our script reads raw CC values directly in `receive_midi` so it is not affected by this setting, but it is relevant context.

**Hardware configuration**: Configured on **every startup** via `_setup_hardware` (called from `port_settings_changed`). This keeps controller state deterministic. Do not save/restore hardware state across sessions.

**Hardware setup timing**: Use `Task.sequence(Task.wait(2.1), Task.run(_setup_hardware))`. The BeatStep requires ~2 seconds after connection before reliably accepting sysex.

**Disconnect cleanup**: On disconnect (`disconnect()` or `port_settings_changed` when port is lost), send all-black to all pad LEDs.

**Encoder relative mode**: All 16 encoders and the transpose encoder use relative mode 2. Raw CC value 65 = +1, 63 = −1; values further from 64 = larger delta. The script maps these directly to parameter value changes in `receive_midi`.

**Encoder → macro assignment**: Encoder N controls macro N of the **first** Audio Effect Rack found on the selected track (searching `track.devices`). On every encoder turn:
- If no rack found → status bar: `"No rack on track"`
- If rack has fewer than N macros → status bar: `"Nothing assigned to macro N"`
- Otherwise → adjust `device.parameters[N]` by the encoder delta (`parameters[0]` is Device On; macros are at indices 1–16, so encoder N maps to `parameters[N]`)

**Encoder sensitivity**: One click (raw delta = 1) moves the parameter by `(1 / ENCODER_CLICKS_PER_ROTATION) * ENCODER_SENSITIVITY`. The goal is that one full 360° rotation covers the full parameter range (0.0–1.0). `ENCODER_CLICKS_PER_ROTATION` defaults to `24` (placeholder — calibrate against real hardware after deployment). `ENCODER_SENSITIVITY` defaults to `1.0` and acts as a multiplier for fine-tuning — increase it to make encoders faster, decrease to make them slower. Both constants are defined in one place so sensitivity can be adjusted without touching logic code. The transpose encoder (volume) uses the same two constants.

**Transpose encoder → volume**: Always acts on `Song.view.selected_track.mixer_device.volume`. No mode dependency.

**Double-tap detection**: The first tap of a double-tap gesture **does** select the track (LED changes to red immediately). If a second tap arrives within 400 ms, solo is toggled on that track. A single tap never triggers solo.

**Track paging**: `CMix` maintains a `_page` integer (0-indexed). Pads 1–15 map to `Song.tracks[page*15 + pad_index]`. Pad 16 always maps to `Song.master_track`. Page advances on `shift`+`recall` (wraps). The `recall` LED reflects the current page (blue = page 1, magenta = page 2+). If tracks are added or removed such that the current page has no tracks, the script stays on the current page and all pads 1–15 show black. If the currently selected track belongs to a page other than the active page, no pad shows red on the current page — the Live selection is preserved, but LED feedback for it is simply absent until the user navigates back to that track's page.

**Solo listeners**: `CMix` registers a `solo_changed` listener on each track so that pad LEDs update in real-time when solo state is changed externally (e.g. via the Live UI).

**`shift` key state**: `CMix` maintains a `_shift_held` boolean. It is set to `True` on the CC press message for `shift` and back to `False` on the CC release message. `shift`+`recall` is detected by checking `_shift_held` when the `recall` press arrives.

**Track selection model**: Only `Song.tracks` (regular tracks) and `Song.master_track` are addressable. Return tracks are excluded.

**Feature scope**: Mix Mode only. `play`, `stop`, `chan`, `store`, `cntrl` have no function in the current implementation.

**Function button CC IDs**: It is **not confirmed** that function buttons (`play`, `stop`, `recall`, `shift`, `chan`, `store`, `cntrl`) send CC messages at all. They may use a different MIDI message type. This must be investigated against the BeatStep MIDI implementation documentation or the reference implementation (raphaelquast/beatstep) before implementation.

**Parameter value clamping**: When adjusting a parameter value via encoder delta, clamp the result to `[0.0, 1.0]` before assigning: `param.value = max(0.0, min(1.0, param.value + delta))`.

**Script entry point**: `__init__.py` must define `create_instance(c_instance)` returning the `ControlSurface` instance. Without it Live silently ignores the script and it will not appear in the Control Surface dropdown. Use `self._task_group` (not `self._tasks`) for the task scheduler in `_Framework.ControlSurface`.
