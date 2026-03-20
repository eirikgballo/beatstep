# Dev Plan: Fix startup crash + RECALL preset-recall override

## Context

Two distinct hardware/script failures are blocking progress:

1. **Script has trouble launching** — unknown root cause without current Log.txt. Could be a Python exception, a timing issue, or the duplicate-instance problem returning.

2. **RECALL button reverts BeatStep to factory defaults** — this is a firmware-level behavior. When RECALL is pressed, the BeatStep hardware enters "preset recall mode" and loads a stored preset (pad 1 lighting red is the visual feedback for that mode). This completely overwrites any sysex configuration our script sent. The script does correctly intercept CC 5 on CH1 and calls `CMix.on_recall_press()`, but the hardware *also* executes the preset recall independently, at the firmware level, overriding our pad/encoder setup.

---

## Phase 1 — Diagnose startup (do this first on Mac)

Check `~/Library/Preferences/Ableton/Live x.x.x/Log.txt` and search for `BeatStep_Q`.

Expected healthy startup sequence:
```
BeatStep_Q: __init__ start
BeatStep_Q: CMix created OK
BeatStep_Q: scheduling hardware setup
BeatStep_Q: __init__ done
... (2.1 seconds later) ...
BeatStep_Q: _setup_hardware running
BeatStep_Q: sysex sent OK
BeatStep_Q: LEDs painted
```

Any deviation points directly to the failure. Common issues to look for:
- Python traceback → code error to fix
- Missing "CMix created OK" → constructor crash in CMix.py
- Missing "_setup_hardware running" → task scheduling broken
- Script appearing twice in log → duplicate instance still present (remove in Preferences → Link/Tempo/MIDI)

---

## Phase 2 — Fix RECALL firmware override

**Root cause:** BeatStep firmware intercepts the RECALL button press and loads a stored preset before our script even sees the CC message. The preset restores factory pad/encoder configuration, undoing our sysex setup.

**Fix:** After detecting a RECALL press, schedule a re-send of the full hardware setup sysex.

**Prerequisite — verify RECALL is on CH1:**
The code has a `TODO` on line 23-24 of `Beatstep_Q.py`: the function button channel is unconfirmed. If RECALL actually sends on CH10 (not CH1), `_handle_ch1()` never sees it, and the fix below won't trigger. Verify with a MIDI monitor (MidiView): press RECALL and check the status byte — `0xB0` = CH1 (correct), `0xB9` = CH10 (wrong routing in code).

**File to change:** `Beatstep_Q.py` — `_handle_ch1()` (around line 154)

**Change:** After calling `self._cmix.on_recall_press()`, also call `self._schedule_hardware_setup()`. The existing 2.1 s delay gives the BeatStep time to finish loading its preset before we re-configure it.

```python
elif cc == BTN_RECALL_CC and is_press:
    self._cmix.on_recall_press()
    self._schedule_hardware_setup()   # ← re-configure after preset recall
```

This is the minimum fix. No architectural change needed.

**Alternative considered:** Use a different button (STORE or CNTRL) for page advance to avoid the firmware preset-recall side effect entirely. Downside: less intuitive button choice, and we'd still want to handle RECALL defensively anyway.

---

## Phase 3 — Verify sysex format (still open from previous session)

Still unverified:
- `_PAD_CC_GATE = 0x02` in `QSetup.py` line 46 — may be `0x08` or `0x09`
- Encoder relative mode `0x02` (line 18) — unverified
- `RECALL_LED_INDEX = 0x02` (line 60) — unverified

**Verification method:**
1. Open Arturia MIDI Control Center on Mac
2. Configure one pad to CC gate mode and one LED to a color
3. Capture sysex output with MidiView
4. Compare byte-by-byte against what `QSetup.setup_pad()` and `QSetup.set_led()` produce

Once the correct byte values are confirmed, update the constants in `QSetup.py`.

---

## Dev workflow going forward

The feedback loop (change code → reload in Ableton → test on hardware → find Log.txt) is inherently slow. Ways to reduce iteration cost:

- **Log.txt is the source of truth** — share it at the start of each session so we don't guess at what happened
- **Keep changes small and isolated** — fix one thing per session, verify in log before testing hardware
- **MidiView captures are definitive** — for sysex questions, one capture session eliminates all guessing

---

## Verification

After implementing Phase 2 fix:
1. Check Log.txt confirms two `_setup_hardware running` entries after a RECALL press (startup + recall-triggered)
2. On hardware: pressing RECALL should repaint LEDs within ~2 seconds rather than staying in preset-recall mode

After Phase 3 sysex fix:
1. Hardware LEDs should light correctly on startup
2. Pads should send CC messages on CH10 (verifiable with a MIDI monitor in Ableton or MidiView)
