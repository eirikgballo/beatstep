"""
bs.py — snakk direkte med BeatStep fra Windows, uten Ableton.

Bruker QSetup.py fra scriptet, så vi tester de samme sysex-byggerne som Live sender.

  python tools/bs.py ports                      # list MIDI-porter
  python tools/bs.py listen [--log fil]         # logg alt BeatStep sender
  python tools/bs.py setup                      # samme hardware-oppsett som _send_setup_sysex
  python tools/bs.py led 1 2 5 7 --color red    # pad-nummer 1-16 (via QSetup.set_pad_color)
  python tools/bs.py led --hw 0x73 --color 1    # rå hardware-indeks
  python tools/bs.py clear                      # alle pads svarte
  python tools/bs.py sysex F0 00 20 6B 7F 42 02 00 10 70 01 F7

--gap MS setter pause mellom meldinger (for å teste burst-grensen).
"""

import argparse
import importlib.util
import os
import sys
import time

import mido

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location('QSetup', os.path.join(_REPO, 'QSetup.py'))
QSetup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(QSetup)

# Speiler konstantene i Beatstep_Q.py (kan ikke importeres uten Live).
PAD_MSG_IDS = [44, 45, 46, 47, 48, 49, 50, 51, 36, 37, 38, 39, 40, 41, 42, 43]
ENCODER_CC_BASE = 10
TRANSPOSE_CC = 27
BUTTON_CCS = {7: 'shift', 5: 'recall'}

COLORS = {
    'off': QSetup.COLOR_OFF, 'black': QSetup.COLOR_OFF,
    'red': QSetup.COLOR_RED, 'blue': QSetup.COLOR_BLUE, 'magenta': QSetup.COLOR_MAGENTA,
}


def _find_port(names, wanted):
    for name in names:
        if wanted.lower() in name.lower():
            return name
    sys.exit('Fant ingen port som matcher %r. Tilgjengelige: %s' % (wanted, names))


def _open_out(args):
    return mido.open_output(_find_port(mido.get_output_names(), args.port))


def _send_all(out, messages, gap_ms):
    for raw in messages:
        out.send(mido.Message.from_bytes(list(raw)))
        print('-> ' + ' '.join('%02X' % b for b in raw))
        if gap_ms:
            time.sleep(gap_ms / 1000.0)


def _parse_int(text):
    return int(text, 16) if text.lower().startswith('0x') else int(text)


def _parse_color(text):
    return COLORS[text.lower()] if text.lower() in COLORS else _parse_int(text)


def _describe(msg):
    """Tolk en innkommende melding etter oppsettet i Beatstep_Q."""
    if msg.type == 'sysex':
        return 'sysex'
    if not hasattr(msg, 'channel'):
        return msg.type  # sanntidsmeldinger som start/stop/clock
    ch ='CH%d' % (msg.channel + 1)
    if msg.type in ('note_on', 'note_off'):
        state = 'trykk' if msg.type == 'note_on' and msg.velocity > 0 else 'slipp'
        pad = PAD_MSG_IDS.index(msg.note) + 1 if msg.note in PAD_MSG_IDS else None
        return '%s pad %s note=%d vel=%d %s' % (ch, pad, msg.note, msg.velocity, state)
    if msg.type == 'control_change':
        cc, v = msg.control, msg.value
        if ENCODER_CC_BASE <= cc < ENCODER_CC_BASE + 16 or cc == TRANSPOSE_CC:
            name = 'transpose' if cc == TRANSPOSE_CC else 'encoder %d' % (cc - ENCODER_CC_BASE + 1)
            delta = v if v < 64 else -(128 - v)
            return '%s %s cc=%d val=%d (delta %+d)' % (ch, name, cc, v, delta)
        if cc in BUTTON_CCS:
            return '%s %s cc=%d val=%d %s' % (ch, BUTTON_CCS[cc], cc, v, 'trykk' if v else 'slipp')
        return '%s ukjent cc=%d val=%d' % (ch, cc, v)
    return str(msg)


def cmd_ports(args):
    print('Inn: ', mido.get_input_names())
    print('Ut:  ', mido.get_output_names())


def cmd_listen(args):
    name = _find_port(mido.get_input_names(), args.port)
    log = open(args.log, 'a', encoding='utf-8') if args.log else None
    print('Lytter på %s (Ctrl+C for å stoppe)' % name, flush=True)
    start = time.time()
    with mido.open_input(name) as inp:
        for msg in inp:
            if msg.type == 'polytouch' and not args.aftertouch:
                continue
            raw = ' '.join('%02X' % b for b in msg.bytes())
            line = '%8.3f  %-48s %s' % (time.time() - start, raw, _describe(msg))
            print(line, flush=True)
            if log:
                log.write(line + '\n')
                log.flush()


def _setup_messages():
    messages = []
    for i in range(16):
        messages += QSetup.setup_pad(i)
    messages += QSetup.setup_button(QSetup.RECALL_HW_INDEX)
    messages += QSetup.setup_button(QSetup.SHIFT_HW_INDEX)
    for i in range(16):
        messages += QSetup.setup_encoder(i, ENCODER_CC_BASE + i)
    messages += QSetup.setup_transpose_encoder(TRANSPOSE_CC)
    return messages


def cmd_setup(args):
    messages = _setup_messages()
    with _open_out(args) as out:
        _send_all(out, messages, args.gap)
    print('%d meldinger sendt' % len(messages))


def cmd_boot(args):
    """Som _send_setup_sysex: oppsett, valgfri pause, så LED-maling (pad 1 rød, resten blå)."""
    leds = [QSetup.set_pad_color(i, QSetup.COLOR_RED if i == 0 else QSetup.COLOR_BLUE) for i in range(16)]
    with _open_out(args) as out:
        _send_all(out, _setup_messages(), args.gap)
        time.sleep(args.led_delay / 1000.0)
        _send_all(out, leds, args.gap)


def cmd_led(args):
    color = _parse_color(args.color)
    if args.hw:
        messages = [QSetup._msg(QSetup._CMD_COLOR, _parse_int(h), color) for h in args.hw]
    else:
        messages = [QSetup.set_pad_color(int(p) - 1, color) for p in args.pads]
    with _open_out(args) as out:
        _send_all(out, messages, args.gap)


def cmd_clear(args):
    messages = [QSetup.set_pad_color(i, QSetup.COLOR_OFF) for i in range(16)]
    with _open_out(args) as out:
        _send_all(out, messages, args.gap)


def cmd_sysex(args):
    with _open_out(args) as out:
        _send_all(out, [tuple(int(b, 16) for b in args.bytes)], 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port', default='Arturia BeatStep', help='del av portnavnet')
    p.add_argument('--gap', type=float, default=0, help='ms pause mellom meldinger')
    sub = p.add_subparsers(dest='cmd', required=True)

    sub.add_parser('ports').set_defaults(func=cmd_ports)

    s = sub.add_parser('listen')
    s.add_argument('--log')
    s.add_argument('--aftertouch', action='store_true', help='vis også aftertouch-strømmen')
    s.set_defaults(func=cmd_listen)

    sub.add_parser('setup').set_defaults(func=cmd_setup)

    s = sub.add_parser('boot')
    s.add_argument('--led-delay', type=float, default=0, help='ms mellom oppsett og LED-maling')
    s.set_defaults(func=cmd_boot)

    s = sub.add_parser('led')
    s.add_argument('pads', nargs='*', help='pad-nummer 1-16')
    s.add_argument('--hw', nargs='+', help='rå hardware-indeks, f.eks. 0x73')
    s.add_argument('--color', default='red', help='off/red/blue/magenta eller tall')
    s.set_defaults(func=cmd_led)

    sub.add_parser('clear').set_defaults(func=cmd_clear)

    s = sub.add_parser('sysex')
    s.add_argument('bytes', nargs='+', help='hex-bytes')
    s.set_defaults(func=cmd_sysex)

    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
