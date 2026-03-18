# BeatStep_Q — Design Document

This document is a living outline for the planned refactoring of the BeatStep_Q MIDI Remote Script.
Fill in the sections below as you decide on your intentions. The goal is to have a clear enough
picture before touching any code, so that structural decisions (layers, components, LED model, etc.)
are consistent from the start.

---

## 1. Goals & Motivation

> *What prompted the rewrite? What problems in the current code do you want to solve?*

- [ ] I want to use the BS controller in a very certain way. There are many of the features in this repo I do not need, but I figured it would be good to have as reference.
- [ ] MODE: Firstly, i would like to make a "mix mode". I want to enter the mix mode by pushing the CONTROL button (when the "mix mode" is active, the control button should light up red.)
- [ ] MIX MODE PAD FUNCTIONS: I want to use the pads to select track. I want TO use the pads "in reverse". By this i mean that i want the top left pad to be tied to TRACK 1 in Ableton. Then the top row should be tracks 1-8, and the lower row should be tracks 9-16. When a pad is selected it the light should be RED. If possible it would be nice to double tap a pad to SOLO the associated track in ableton
- [ ] ENCODER FUNCTIONS: the encoders should control the 16 macros of the audio effect rack on the associated track.

---

## 2. Hardware Reference

The Arturia BeatStep has the following physical controls:

| Group              | Controls                                      | Current MIDI mapping            |
|--------------------|-----------------------------------------------|---------------------------------|
| Pads (16)          | Pad 1–8 (bottom row), Pad 9–16 (top row)      | Note, CH10, IDs from PAD_MSG_IDS |
| Encoders (16)      | Encoder 1–16                                  | CC, CH10, IDs from ENCODER_MSG_IDS |
| Transpose encoder  | Single rotary at top-left                     | CC 4, CH10, relative mode 2     |
| Function buttons   | `play`, `stop`, `cntrl`, `shift`, `chan`, `store`, `recall` | CC, CH10 |

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
| Mix          | Press `cntrl` | — (no exit for now; always active) | N/A (only mode) | Track select, solo, macro control |

---

## 4. Control Assignments per Mode

> *For each mode, define what every physical control does.
> A simple table per mode works well here.*

### Mode: Mix (only mode for now)

| Control        | Action |
|----------------|--------|
| Pad top-left → top-right (row 1) | Select Track 1–8. LED: red if selected, blue if track exists, black if no track |
| Pad bottom-left → bottom-right (row 2) | Select Track 9–16. Same LED rules. |
| Double-tap pad | Solo the associated track |
| Encoders 1–16  | Control macro 1–16 of the Audio Effect Rack on the **currently selected track** |
| `cntrl`        | Enters Mix Mode (lights red). No exit for now. |
| `play`         | … (TBD) |
| `stop`         | … (TBD) |
| `shift`        | … (TBD) |
| `chan`          | … (reserved for future mode) |
| `store`        | … (reserved for future mode) |
| `recall`       | … (reserved for future mode) |

> *Add a table for every additional mode when they are designed.*

---

## 5. LED Feedback Model

> *Define what each LED state communicates, consistently across all modes.*
> *This avoids magic color numbers scattered through the code.*

Proposed semantic color vocabulary:

| Semantic meaning                        | Color   | Notes |
|-----------------------------------------|---------|-------|
| No track exists at this pad position    | black   |       |
| Track exists, not selected              | blue    |       |
| Track selected (currently active track) | red     |       |
| Mix Mode active (`cntrl` button)        | red     |       |
| Reserved for future use                 | magenta |       |

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

> *How would you like to split the responsibilities?
> Smaller focused components are easier to test and reason about.
> Some options:*
>
> - Extract `MixComponent`, `SessionComponent`, `SequencerComponent`, `BrowserComponent`
>   as proper sibling components rather than nested objects inside QControlComponent.
> - Keep a thin `LayerManager` or `ModeManager` that handles transitions and LED updates,
>   rather than booleans scattered across QControlComponent.
> - Consider whether BaseComponent should use `_Framework.CompoundComponent` instead of
>   rolling its own setter plumbing.

```
BeatStep_Q          — (same role)
  QSetup            — (same role, unchanged)
  ModeManager       — owns the current active mode(s); drives LED updates on transitions
  MixComponent      — track arm / mute / solo / volume
  SessionComponent  — clip launch, scene navigation
  SequencerComponent— step sequencer
  BrowserComponent  — library browser
  BaseComponent     — (keep, extend, or replace with _Framework equivalent)
```

> *Sketch your preferred structure here.*

---

## 7. Live API Surface

> *List the Live API objects and events you plan to use.
> Knowing this upfront helps catch version-compatibility issues early.*

| Live object / event                              | Used for                          | Live version |
|--------------------------------------------------|-----------------------------------|--------------|
| `Live.Song.Song`                                 | Transport, tracks, scenes         | 9+           |
| `Song.view.selected_track` / listener            | Track selection feedback          | 9+           |
| `Song.clip_trigger_quantization` / listener      | Quantization display              | 9+           |
| `Live.Browser`                                   | Library browsing                  | 9+           |
| `_Framework.DeviceComponent`                     | Encoder → device parameter        | 9+           |
| `_Framework.ClipSlotComponent`                   | (if you adopt framework components)| 9+          |
| …                                                | …                                 | …            |

---

## 8. Open Questions

> *Things you haven't decided yet. Use this as a parking lot.*

- [ ] Target Live versions: 10 only? 11+? Keep the `sys.version_info` guard for QSequencer?
- [ ] Should the script save/restore hardware config via sysex on connect/disconnect (current approach), or configure hardware on every startup?
- [ ] How to handle the 2-second hardware setup delay — keep `Task.sequence` / `Task.wait`, or find a cleaner pattern?
- [x] ~~Any new features beyond what's listed in the current README?~~ → Scope is Mix Mode only for now; other modes (chan, store, recall) reserved for future.
- [x] ~~Encoder → track mapping~~ → Encoders always follow the **currently selected track** (the last tapped pad).
- [x] ~~Mix Mode exit~~ → No exit for now; Mix Mode is always active once entered.
- [x] ~~Fewer than 16 tracks~~ → Existing tracks light blue, selected track lights red, empty pad positions are black.

---

## 9. Migration / Refactoring Plan

> *Once the design is settled, break the work into safe, testable steps.
> Each step should leave the script in a working state.*

1. …
2. …
3. …
