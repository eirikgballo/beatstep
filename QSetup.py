"""
QSetup — sysex message builders for the Arturia BeatStep.
No state; all functions return tuples of bytes ready for _send_midi().

Sysex format:
  F0 00 20 6B 7F 42 02 00 <cmd> <index> <value> F7

CMD bytes (verified from raphaelquast reference / untergeek.de):
  0x01 = mode
  0x02 = channel   (0-indexed: CH10 = 0x09; 65 = follow global)
  0x03 = CC / note number
  0x04 = off / min value
  0x05 = on  / max value
  0x06 = behaviour  (pad: 0=toggle, 1=gate; encoder: 1-3=relative mode 1-3)

Pad mode values (cmd 0x01):
  8 = CC gate ("switched control")
  9 = Note gate

Encoder mode values (cmd 0x01):
  1 = MIDI CC

Hardware index space (verified):
  Pads 0-15      → hw = pad_index + 0x70   (0x70–0x7F)
  Encoders 0-15  → hw = enc_index  + 0x20   (0x20–0x2F)
  Transpose enc  → hw = 0x30
  Recall button  → hw = 0x5C  (92)
  Shift button   → hw = 0x5E  (94)
"""

_HEADER = (0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42, 0x02, 0x00)
_FOOTER = (0xF7,)

# CMD bytes
_CMD_MODE      = 0x01
_CMD_CHANNEL   = 0x02
_CMD_NUMBER    = 0x03  # CC or note number
_CMD_OFF_VAL   = 0x04  # min / off value
_CMD_ON_VAL    = 0x05  # max / on value
_CMD_BEHAVIOUR = 0x06

# Mode values
_PAD_NOTE_GATE    = 9   # pads: note gate mode
_PAD_CC_GATE      = 8   # pads: CC gate mode (function buttons use this too)
_ENC_MIDI_CC      = 1   # encoders: MIDI CC mode

# Behaviour values
_BEHAVIOUR_GATE       = 1  # pad/button: send while held, release on let go
_ENC_RELATIVE_MODE_2  = 2  # encoder: relative mode 2 / two's complement (CW=1-63, CCW=65-127)
                            # Value N ≥ 65 means -(128-N) steps. Matches our decoder formula.

# MIDI channel for all controls (CH10, 0-indexed = 9)
_BEATSTEP_CHANNEL = 0x09

# Hardware index offsets (verified)
PAD_HW_OFFSET       = 0x70   # pads 0-15  → 0x70–0x7F
_ENC_HW_OFFSET      = 0x20   # encoders 0-15 → 0x20–0x2F
_TRANSPOSE_HW_INDEX = 0x30   # transpose encoder
RECALL_HW_INDEX     = 0x5C   # recall button (92)
SHIFT_HW_INDEX      = 0x5E   # shift button  (94)

_CMD_COLOR = 0x10

COLOR_OFF     = 0
COLOR_RED     = 1
COLOR_BLUE    = 16
COLOR_MAGENTA = 17


def _msg(cmd, index, value):
    return _HEADER + (cmd, index, value) + _FOOTER


def set_pad_color(pad_index, color):
    """Return a sysex tuple to set the LED color of a pad (0-15)."""
    hw = pad_index + PAD_HW_OFFSET
    return _msg(_CMD_COLOR, hw, color)


# ---------------------------------------------------------------------------
# Pad setup (note gate mode)
# ---------------------------------------------------------------------------

def setup_pad(pad_index):
    """
    Configure one pad in note gate mode on CH10.
    Hardware index = pad_index + PAD_HW_OFFSET (0x70).
    Note number is intentionally NOT set — factory defaults (44-51, 36-43) are correct.
    """
    hw = pad_index + PAD_HW_OFFSET
    return [
        _msg(_CMD_MODE,      hw, _PAD_NOTE_GATE),
        _msg(_CMD_CHANNEL,   hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_BEHAVIOUR, hw, _BEHAVIOUR_GATE),
    ]


# ---------------------------------------------------------------------------
# Function button setup (CC gate mode)
# ---------------------------------------------------------------------------

def setup_button(hw_index):
    """Configure a function button (recall, shift, etc.) in CC gate mode on CH10."""
    return [
        _msg(_CMD_MODE,      hw_index, _PAD_CC_GATE),
        _msg(_CMD_CHANNEL,   hw_index, _BEATSTEP_CHANNEL),
        _msg(_CMD_BEHAVIOUR, hw_index, _BEHAVIOUR_GATE),
    ]


# ---------------------------------------------------------------------------
# Encoder setup
# ---------------------------------------------------------------------------

def setup_encoder(enc_index, cc_number):
    """
    Configure one encoder in MIDI CC relative mode 2 on CH10.
    Hardware index = enc_index + 0x20.
    """
    hw = enc_index + _ENC_HW_OFFSET
    return [
        _msg(_CMD_MODE,      hw, _ENC_MIDI_CC),
        _msg(_CMD_CHANNEL,   hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_BEHAVIOUR, hw, _ENC_RELATIVE_MODE_2),
        _msg(_CMD_NUMBER,    hw, cc_number),
    ]


def setup_transpose_encoder(cc_number):
    """Configure the transpose encoder (hw index 0x30)."""
    hw = _TRANSPOSE_HW_INDEX
    return [
        _msg(_CMD_MODE,      hw, _ENC_MIDI_CC),
        _msg(_CMD_CHANNEL,   hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_BEHAVIOUR, hw, _ENC_RELATIVE_MODE_2),
        _msg(_CMD_NUMBER,    hw, cc_number),
    ]
