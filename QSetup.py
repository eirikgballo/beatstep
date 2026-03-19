"""
QSetup — pure sysex message builders for the Arturia BeatStep.
No state; all functions return tuples of bytes ready for _send_midi().

Sysex format (write to working RAM):
  F0 00 20 6B 7F 42 02 00 <cmd> <index> <value> F7

Control index space (flat):
  0-15  = pads 1-16
  16-31 = encoders 1-16
  32    = transpose encoder

CMD bytes (parameter types):
  0x01 = channel     (0-indexed: CH10 = 0x09)
  0x02 = CC/note number
  0x03 = behavior / mode
         Pad values:  0x00=note gate, 0x01=note toggle,
                      0x02=CC gate,   0x03=CC toggle     # TODO: verify 0x02 against hardware
         Encoder:     0x00=absolute,  0x01=rel mode 1,
                      0x02=rel mode 2, 0x03=rel mode 3   # TODO: verify against hardware
  0x10 = LED color   (pads 0-15 and button indices)

LED color values:
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

# CMD bytes
_CMD_CHANNEL  = 0x01
_CMD_VALUE    = 0x02  # CC number or note number
_CMD_BEHAVIOR = 0x03  # pad behavior / encoder mode
_CMD_LED      = 0x10

# Pad behavior values for CMD_BEHAVIOR
_PAD_CC_GATE = 0x02   # TODO: verify — may be 0x08 or 0x09 depending on firmware

# Encoder mode values for CMD_BEHAVIOR
_ENC_RELATIVE_MODE_2 = 0x02  # centred at 64; 65=+1, 63=-1

# MIDI channel for all BeatStep controls (CH10, 0-indexed)
_BEATSTEP_CHANNEL = 0x09

# Control index offsets
_ENCODER_OFFSET   = 16
_TRANSPOSE_OFFSET = 32

# Hardware LED index for the RECALL button.
# TODO: verify against hardware / raphaelquast reference.
RECALL_LED_INDEX = 0x02


def _msg(cmd, index, value):
    return _HEADER + (cmd, index, value) + _FOOTER


# ---------------------------------------------------------------------------
# LED control
# ---------------------------------------------------------------------------

def set_led(hw_index, color):
    """Set LED at hw_index to color (use OFF/RED/BLUE/MAGENTA constants)."""
    return _msg(_CMD_LED, hw_index, color)


# ---------------------------------------------------------------------------
# Pad setup — three sysex messages per pad to fully configure it
# ---------------------------------------------------------------------------

def setup_pad(pad_index, cc_number):
    """
    Return a list of sysex tuples that fully configure one pad:
      1. Set channel to CH10
      2. Switch message type to CC gate
      3. Set CC number
    """
    return [
        _msg(_CMD_CHANNEL,  pad_index, _BEATSTEP_CHANNEL),
        _msg(_CMD_BEHAVIOR, pad_index, _PAD_CC_GATE),
        _msg(_CMD_VALUE,    pad_index, cc_number),
    ]


# ---------------------------------------------------------------------------
# Encoder setup — three sysex messages per encoder
# ---------------------------------------------------------------------------

def setup_encoder(enc_index, cc_number):
    """
    Return a list of sysex tuples that fully configure one encoder:
      1. Set channel to CH10
      2. Set relative mode 2
      3. Set CC number
    enc_index is 0-15 for main encoders, or pass TRANSPOSE_HW_INDEX directly.
    """
    hw = enc_index + _ENCODER_OFFSET
    return [
        _msg(_CMD_CHANNEL,  hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_BEHAVIOR, hw, _ENC_RELATIVE_MODE_2),
        _msg(_CMD_VALUE,    hw, cc_number),
    ]


def setup_transpose_encoder(cc_number):
    """Configure the transpose encoder (hardware index 32)."""
    hw = _TRANSPOSE_OFFSET
    return [
        _msg(_CMD_CHANNEL,  hw, _BEATSTEP_CHANNEL),
        _msg(_CMD_BEHAVIOR, hw, _ENC_RELATIVE_MODE_2),
        _msg(_CMD_VALUE,    hw, cc_number),
    ]
