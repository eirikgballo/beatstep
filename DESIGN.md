# BeatStep_Q — Design Document

This document is a living outline for the planned refactoring of the BeatStep_Q MIDI Remote Script.
Fill in the sections below as you decide on your intentions. The goal is to have a clear enough
picture before touching any code, so that structural decisions (layers, components, LED model, etc.)
are consistent from the start.

---

## 1. Goals & Motivation

> *What prompted the rewrite? What problems in the current code do you want to solve?*

- [ ] I want to use the BS controller in a very certain way. There are many of the features in this repo I do not need, but I figured it would be good to have as reference.
- The original repo [raphaelquast/beatstep](https://github.com/raphaelquast/beatstep) (docs at https://raphaelquast.github.io/beatstep/) is a useful reference for patterns around sysex scheduling, hardware setup, and general MIDI Remote Script structure for the BeatStep. The functionality here is deliberately narrower.
- [ ] MODE: Firstly, i would like to make a "mix mode". The script boots directly into Mix Mode. The RECALL button should be continuously lit **blue** to signal that Mix Mode is active.
- [ ] MIX MODE PAD FUNCTIONS: I want to use the pads to select track. I want TO use the pads "in reverse". By this i mean that i want the top left pad to be tied to TRACK 1 in Ableton. Then the top row should be tracks 1-8, and the lower row should be tracks 9-16. When a pad is selected it the light should be RED. If possible it would be nice to double tap a pad to SOLO the associated track in ableton
- [ ] ENCODER FUNCTIONS: the encoders should control the 16 macros of the audio effect rack on the associated track.

---

## 2. Hardware Reference

The Arturia BeatStep has the following physical controls:

| Group              | Controls                                      | Current MIDI mapping            |
|--------------------|-----------------------------------------------|---------------------------------|
| Pads (16)          | Pad 1–8 (top row), Pad 9–16 (bottom row)      | CC, CH10, IDs from PAD_MSG_IDS |
| Encoders (16)      | Encoder 1–16                                  | CC, CH10, IDs from ENCODER_MSG_IDS |
| Transpose encoder  | Single rotary at top-left                     | CC 4, CH10, relative mode 2     |
| Function buttons   | `play`, `stop`, `cntrl`, `shift`, `chan`, `store`, `recall` | CC, CH10 |

> **Note on pad numbering:** In this script "Pad 1–8" always refers to the **top row** of physical pads. The bottom row is "Pad 9–16". Within this codebase, top row = indices 0–7, bottom row = indices 8–15.
>
> The CC IDs in `PAD_MSG_IDS` (44–51 for the top row, 36–43 for the bottom row) are **explicitly programmed into the hardware** by `_setup_hardware` via `set_B_cc` sysex on every connection — the same way encoder CC IDs are set. Any prior hardware configuration (e.g. from Arturia MIDI Control Center) is overwritten. So `PAD_MSG_IDS` is the authoritative source, not an assumption about factory defaults.

### Pad LED colors (sysex, via QSetup)

| Value | Color   |
|-------|---------|
| 0     | off / black |
| 1     | red     |
| 16    | blue    |
| 17    | magenta |

> *Do you want to change or extend the color scheme?*

---

## 3. Mode / Layer Model

### 3a. Current layer model (reference)

The existing script uses a flat set of boolean flags in `QControlComponent`:

| Flag                  | Activated by           | Description              |
|-----------------------|------------------------|--------------------------|
| `_control_layer_1`    | `shift` + `chan`       | Mix (track arm/mute/solo)|
| `_control_layer_2`    | `store`                | Control / device         |
| `_control_layer_3`    | `recall`               | Session launch           |
| `_layer_onetrack`     | (variant of layer 3)   | One-track clip launch    |
| `_sequencer`          | `cntrl`                | Step sequencer           |
| `_browser`            | `shift` + `recall`     | Library browser          |
| `_shift_fixed`        | double-tap `shift`     | Shift modifier, latched  |

Layers toggle independently; multiple can be active simultaneously. LED colors signal which
layers are on, but the logic is spread across `_update_button_light_status()` in QControlComponent.

### 3b. New layer model

> *Define your intended mode structure here. Some questions to consider:*
>
> - Keep the same layers, or consolidate/rename?
> - Exclusive modes (only one active at a time) vs. stacked modifiers?
> - How do you enter and exit each mode?
> - What happens to LED state during transitions?
> - Should "shift" remain a latching modifier or become a full layer?

| Mode / Layer | Enter | Exit | Exclusive? | Description |
|--------------|-------|------|------------|-------------|
| Mix          | Active on boot; pressing `recall` repaints LEDs | — (always active; no exit) | N/A (only mode) | Track select, solo, macro control |

---

## 4. Control Assignments per Mode

> *For each mode, define what every physical control does.
> A simple table per mode works well here.*

### Mode: Mix (only mode for now)

| Control        | Action |
|----------------|--------|
| Pad top-left → top-right (row 1) | Select Track 1–8. LED: red if selected, blue if track exists, black if no track |
| Pad bottom-left → bottom-right (row 2) | Select Track 9–16. Same LED rules. |
| Double-tap pad | Toggle solo on the associated track (additive — multiple tracks can be soloed simultaneously). Double-tapping again turns solo off. Does **not** change track selection. |
| Single-tap pad | Select the track (exclusive — only one pad is red at a time). Pressing pad 5 when pad 3 is red turns pad 5 red and pad 3 returns to blue or magenta depending on its solo state. |
| Encoders 1–16  | Control macro 1–16 of the Audio Effect Rack on the **currently selected track**. If the track has no rack, show "No rack on track" in the status bar. |
| `recall`       | Mix Mode indicator — lit **blue** continuously. Script boots into Mix Mode. Pressing `recall` repaints all LEDs. No exit. |
| `play`         | … (TBD) |
| `stop`         | … (TBD) |
| `shift`        | … (TBD) |
| `chan`         | … (reserved for future mode) |
| `store`        | … (reserved for future mode) |
| `cntrl`        | … (reserved for future mode) |

> *Add a table for every additional mode when they are designed.*

---

## 5. LED Feedback Model

> *Define what each LED state communicates, consistently across all modes.*
> *This avoids magic color numbers scattered through the code.*

Proposed semantic color vocabulary:

| Semantic meaning                                          | Color   | Notes |
|-----------------------------------------------------------|---------|-------|
| No track exists at this pad position                      | black   |       |
| Track exists, not selected, not soloed                    | blue    | All existing tracks default to blue |
| Track soloed but not currently selected                   | magenta |       |
| Track currently selected (exclusive — only one at a time) | red     | Selected takes priority over soloed: a track that is both selected and soloed shows red |
| Mix Mode indicator (`recall` button)                      | blue    |       |

> *Extend or change this as needed. The goal is one place that defines what colors mean.*

---

## 6. Component Structure

### 6a. Current structure (reference)

```
BeatStep_Q          — ControlSurface subclass; hardware setup, sysex scheduling
  QSetup            — Sysex message builders (no state; pure utility)
  QControlComponent — All layer logic, listeners, LED updates (~600+ lines)
    QSequencer      — Step sequencer (Live 11+ only)
    QBrowser        — Library browser navigation
  BaseComponent     — Generic button setter/listener wiring helper
```

### 6b. New component structure

```
BeatStep_Q  — ControlSurface subclass; hardware setup, sysex scheduling, MIDI routing
  QSetup    — Sysex message builders (no state; pure utility)
  CMix      — Mix Mode: track selection, solo, encoder→macro control, LED management
```

---

## 7. Live API Surface

> *List the Live API objects and events you plan to use.
> Knowing this upfront helps catch version-compatibility issues early.*

| Live object / event                              | Used for                          | Live version |
|--------------------------------------------------|-----------------------------------|--------------|
| `Live.Song.Song`                                              | Track list, song object                     | 9+ |
| `Song.view.selected_track` / `add_selected_track_listener`    | Track selection read and LED feedback       | 9+ |
| `Song.tracks` / `add_tracks_listener`                         | React to tracks being added or removed      | 9+ |
| `Song.visible_tracks` / `add_visible_tracks_listener`         | React to track visibility changes           | 9+ |
| `track.solo`                                                  | Solo state read and write                   | 9+ |
| `device.parameters`                                           | Encoder → macro parameter value control     | 9+ |

---

## 8. Open Questions

> *Things you haven't decided yet. Use this as a parking lot.*

- [x] ~~Target Live versions~~ → **Ableton Live 11**, with the **"value scaling"** setting enabled in Live's MIDI Preferences (this affects how CC values from relative encoders are interpreted by Live's internal parameter mapping; our script reads raw CC values directly in `receive_midi` so it is not affected, but it is relevant context).
- [x] ~~Keep the `sys.version_info` guard for QSequencer?~~ → N/A — QSequencer has been removed from the codebase.
- [x] ~~Save/restore vs configure on startup~~ → Configure on **every startup** via `_setup_hardware` (called from `port_settings_changed`). Keeps controller state deterministic and foolproof.
- [x] ~~Hardware setup delay~~ → Keep current approach: `Task.sequence(Task.wait(2.1), Task.run(_setup_hardware))`. The BeatStep requires ~2 seconds after connection before reliably accepting sysex.
- [x] ~~Any new features beyond what's listed in the current README?~~ → Scope is Mix Mode only for now; other modes (chan, store, recall) reserved for future.
- [x] ~~Encoder → track mapping~~ → Encoders always follow the **currently selected track** (the last tapped pad).
- [x] ~~Mix Mode exit~~ → No exit for now; Mix Mode is always active once entered.
- [x] ~~Fewer than 16 tracks~~ → Existing tracks: blue (not selected), red (selected and not soloed), magenta (soloed). Empty pad positions: black.

---

## 9. Migration / Refactoring Plan

Not applicable at current scope — the codebase has been rewritten from scratch. The active implementation is in `BeatStep_Q.py` and `CMix.py`.
