"""
QSetup — pure sysex message builders for the Arturia BeatStep.
No state; all functions return tuples of bytes ready for _send_midi().

Sysex format (write to working RAM):
  F0 00 20 6B 7F 42 02 00 <cmd> <index> <value> F7

Control index space (verified from MidiView capture):
  Pads 0-15  → hardware index = pad_index + 0x70  (i.e. 0x70–0x7F)
  Encoders   → hardware indices TBD (TODO: verify from MidiView)
  Transpose  → hardware index TBD

CMD bytes for pads (verified from MidiView capture):
  0x01 = channel     (0-indexed: CH10 = 0x09)
  0x02 = mode        (0x41 = CC gate / "switched control")
  0x03 = CC/note number
  0x04 = min value   (0x00)
  0x05 = max value   (0x7F)
  0x06 = flag        (0x01 — purpose unknown, but required)

CMD bytes for encoders (not yet verified):
  0x01 = channel
  0x02 = mode        (0x02 = relative mode 2 — TODO: verify)
  0x03 = CC number

LED control (cmd 0x10 — format not yet verified from capture):
  0x10 = LED color   (hw_index = pad_index + PAD_HW_OFFSET for pads)

LED color values (not yet verified against hardware):
  0  = off / black
  1  = red
  16 = blue
  17 = magenta
"""

_HEADER = (0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42, 0x02, 0x00)
_FOOTER = (0xF7,)

# LED colors — use these names everywhere; no magic numbers in logic code.
OFF     = 0
RED     = 1
BLUE    = 16
MAGENTA = 17

# CMD bytes (verified for pads; encoders use same channel/number cmds)
_CMD_CHANNEL  = 0x01
_CMD_MODE     = 0x02  # pad: mode byte; encoder: relative/absolute mode
_CMD_NUMBER   = 0x03  # CC or note number
_CMD_MIN_VAL  = 0x04  # min output value
_CMD_MAX_VAL  = 0x05  # max output value
_CMD_FLAG     = 0x06  # unknown flag; hardware requires value 0x01
_CMD_LED      = 0x10  # LED color — cmd byte unverified, may need adjustment

# Pad mode value: CC gate = "switched control" in MIDI Control Center
_PAD_CC_GATE = 0x41  # verified from MidiView capture

# Encoder relative mode (TODO: verify against hardware)
_ENC_RELATIVE_MODE_2 = 0x02

# MIDI channel for all BeatStep controls (CH10, 0-indexed)
_BEATSTEP_CHANNEL = 0x09

# Hardware index offset for pads (verified from MidiView capture)
PAD_HW_OFFSET = 0x70

# Encoder hardware index offsets (TODO: verify from MidiView)
_ENCODER_HW_OFFSET   = 0x20  # placeholder — unverified
_TRANSPOSE_HW_INDEX  = 0x00  # placeholder — unverified

# Hardware LED index for the RECALL button (TODO: verify)
RECALL_LED_INDEX = 0x02


def _msg(cmd, index, value):
    return _HEADER + (cmd, index, value) + _FOOTER


# ---------------------------------------------------------------------------
# LED control
# ---------------------------------------------------------------------------

def set_led(hw_index, color):
    """Set LED at hw_index to color (use OFF/RED/BLUE/MAGENTA constants).
    For pads, pass pad_index + PAD_HW_OFFSET as hw_index.
    """
    return _msg(_CMD_LED, hw_index, color)


# ---------------------------------------------------------------------------
# Pad setup — six sysex messages per pad
# ---------------------------------------------------------------------------

def setup_pad(pad_index, cc_number):
    """
    Return a list of sysex tuples that fully configure one pad.
    Hardware index = pad_index + PAD_HW_OFFSET (0x70).
    """
    hw = pad_index + PAD_HW_OFFSET
    return [
        _msg(_CMD_CHANNEL, hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_MODE,    hw, _PAD_CC_GATE),
        _msg(_CMD_NUMBER,  hw, cc_number),
        _msg(_CMD_MIN_VAL, hw, 0x00),
        _msg(_CMD_MAX_VAL, hw, 0x7F),
        _msg(_CMD_FLAG,    hw, 0x01),
    ]


# ---------------------------------------------------------------------------
# Encoder setup — TODO: hardware indices not yet verified
# ---------------------------------------------------------------------------

def setup_encoder(enc_index, cc_number):
    """
    Return a list of sysex tuples that configure one encoder.
    NOTE: _ENCODER_HW_OFFSET is a placeholder — verify from MidiView.
    """
    hw = enc_index + _ENCODER_HW_OFFSET
    return [
        _msg(_CMD_CHANNEL, hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_MODE,    hw, _ENC_RELATIVE_MODE_2),
        _msg(_CMD_NUMBER,  hw, cc_number),
    ]


def setup_transpose_encoder(cc_number):
    """Configure the transpose encoder. TODO: hardware index unverified."""
    hw = _TRANSPOSE_HW_INDEX
    return [
        _msg(_CMD_CHANNEL, hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_MODE,    hw, _ENC_RELATIVE_MODE_2),
        _msg(_CMD_NUMBER,  hw, cc_number),
    ]
