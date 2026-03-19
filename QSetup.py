"""
QSetup — pure sysex message builders for the Arturia BeatStep.
No state; all functions return tuples of bytes ready for _send_midi().

Sysex format (write to working RAM):
  F0 00 20 6B 7F 42 02 00 <cmd> <index> <value> F7

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

# Sysex command bytes
_CMD_LED           = 0x10  # Set pad LED color
_CMD_CC_NUMBER     = 0x20  # Set CC number for a control
_CMD_ENCODER_MODE  = 0x06  # Set encoder mode  # TODO: verify byte against hardware

# Hardware indices for LEDs beyond pad 0-15.
# TODO: verify RECALL_LED_INDEX against hardware / raphaelquast reference.
RECALL_LED_INDEX = 0x02

# Encoder control index offset: encoders follow pads in the sysex index space.
_ENCODER_INDEX_OFFSET = 16

# Transpose encoder hardware index (for mode setup).
TRANSPOSE_ENC_HW_INDEX = 32  # TODO: verify


def _msg(cmd, index, value):
    return _HEADER + (cmd, index, value) + _FOOTER


# ---------------------------------------------------------------------------
# LED control
# ---------------------------------------------------------------------------

def set_led(hw_index, color):
    """Set LED at hw_index to color (use OFF/RED/BLUE/MAGENTA constants)."""
    return _msg(_CMD_LED, hw_index, color)


# ---------------------------------------------------------------------------
# CC number assignment  (called during _setup_hardware)
# ---------------------------------------------------------------------------

def set_pad_cc(pad_index, cc_number):
    """Program the CC number for pad pad_index (0-15)."""
    return _msg(_CMD_CC_NUMBER, pad_index, cc_number)


def set_encoder_cc(enc_index, cc_number):
    """Program the CC number for encoder enc_index (0-15)."""
    return _msg(_CMD_CC_NUMBER, enc_index + _ENCODER_INDEX_OFFSET, cc_number)


# ---------------------------------------------------------------------------
# Encoder mode  (relative mode 2: centre 64; 65=+1, 63=-1)
# ---------------------------------------------------------------------------

def set_encoder_relative_mode(hw_index):
    """Set encoder at hw_index to relative mode 2."""
    # mode value 0x02 = relative mode 2  # TODO: verify byte value
    return _msg(_CMD_ENCODER_MODE, hw_index, 0x02)
