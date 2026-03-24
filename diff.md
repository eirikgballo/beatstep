# Encoder Implementation: BeatStep_Q vs raphaelquast/beatstep

Comparison of encoder design decisions between this implementation and the
[raphaelquast/beatstep](https://github.com/raphaelquast/beatstep) reference repo.

---

## CC Numbers

**raphaelquast**: Scattered, non-sequential — `(10, 74, 71, 76, 77, 93, 73, 75, 114, 18, 19, 16, 17, 91, 79, 72)`.
Chosen to avoid conflicts with standard General MIDI CC meanings.

**BeatStep_Q**: Sequential CC 10–25 for encoders 1–16; CC 26 for the transpose encoder.
Simpler to reason about. For a dedicated remote script, standard CC semantics don't matter.

---

## Relative Mode: Mode 1 vs Mode 2

**raphaelquast**: Relative mode 2 (two's complement, behaviour=2). Uses `_Framework.EncoderElement`
with `Live.MidiMap.MapMode.relative_smooth_two_compliment` — Live decodes the delta internally
and the listener receives a pre-computed float, not a raw CC value. Neutral threshold in manual
code is **65**.

**BeatStep_Q**: Relative mode 1 (signed bit, behaviour=1). Raw CC values decoded manually
in `receive_midi`. Threshold: values 1–63 = CW (+), 65–127 = CCW (−), 0 and 64 ignored.

The threshold difference (64 vs 65) matters if the mode byte is ever changed; mode 1 and
mode 2 differ in how value 64 is treated. Both modes produce identical output in practice
for normal use.

---

## Acceleration

**raphaelquast**: Two-pronged:
1. Hardware global acceleration via `set_E_acceleration(0)` sysex (slow/medium/fast).
2. Software tick accumulators for coarse controls (skip every N ticks). Continuous controls
   (volume, pan) use a **fixed step** (0.005 or 0.01) with no per-tick scaling — no acceleration.

**BeatStep_Q**: Software-only magnitude-based acceleration curve:
```
step = 0.002 + (magnitude / 63.0) * 0.018   →   0.002 (slow) to 0.020 (fast)
```
No hardware acceleration sysex. Fast spins move macros up to 10× further than slow turns.
More suitable for sweeping macro parameters over a wide range.

---

## Device / Macro Binding

**raphaelquast**: Uses `_Framework.DeviceComponent` with `parameter_controls=self._device_encoders`.
Binds a 2×4 matrix of 8 encoders to the first 8 parameters of the **currently selected device**
(any device type). Live handles parameter wiring automatically. The other 8 encoders control
volume and pan per-track.

**BeatStep_Q**: Manual — scans `selected_track.devices` for the first `AudioEffectGroupDevice`,
caches it in `_current_rack`, and writes to `device.parameters[N]` directly. All 16 encoders
target macros 1–16. The transpose encoder always controls the volume of the selected track.

Key behavioural difference: `DeviceComponent` follows the **selected device** in Live's UI (click
any device to control it). BeatStep_Q follows the **first rack on the track** regardless of what's
selected — more deterministic, but the user cannot redirect encoders by clicking a different rack.

---

## Framework Usage

**raphaelquast**: Heavy use of `_Framework` — `EncoderElement`, `ButtonMatrixElement`,
`DeviceComponent`, `Layer`. Live manages MIDI routing and parameter mapping internally.

**BeatStep_Q**: No framework components for encoders. Raw `receive_midi` + manual routing.
Consistent with the existing pad/button handling in the codebase. More explicit and easier
to debug.

---

## Summary Table

| Aspect | raphaelquast | BeatStep_Q |
|---|---|---|
| Encoder CC numbers | Scattered (10, 74, 71, …) | Sequential (10–25) |
| Transpose CC | 4 | 26 |
| Relative mode | Mode 2 (two's complement) | Mode 1 (signed bit) |
| Decoding | `_Framework` / `EncoderElement` | Manual in `receive_midi` |
| Neutral threshold | 65 | 0 and 64 both ignored |
| Acceleration | Hardware global + fixed steps | Software magnitude curve |
| Device target | Selected device (any type, 8 params) | First Audio Effect Rack (16 macros) |
| Transpose encoder | Scrolls device chain / transposes | Volume of selected track |
| Framework | Heavy (`EncoderElement`, `DeviceComponent`) | None |
